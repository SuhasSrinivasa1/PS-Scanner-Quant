from __future__ import annotations

import io
import json
import os
import re
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable

from .constants import APP_NAME, VERSION
from .db import db, now_iso
from .paths import DATA, LOGS, CREDENTIALS_PATH

_SECRET_KEYS=("access_token","api_key","api_secret","totp_token","totp_secret","password","secret","authorization")
_EXPORT_DIR=DATA/"support_exports"
_LATEST_PATH=_EXPORT_DIR/"PS_Scanner_Logs_latest.zip"
_STATUS_PATH=_EXPORT_DIR/"status.json"
_LOCK=threading.RLock()
_PAYLOAD:bytes|None=None
_MIN_REFRESH_AGE_SECONDS=1800.0
_STATUS:Dict[str,Any]={"ready":False,"path":str(_LATEST_PATH),"generated_at":None,"last_error":"not yet built","elapsed_ms":None,
                       "payload_ready":False,"request_path_filesystem_reads":0,"min_refresh_age_seconds":_MIN_REFRESH_AGE_SECONDS}

_EXPORTS={
    "health_events.jsonl":"SELECT * FROM health_events ORDER BY id",
    "scan_runs.jsonl":"SELECT * FROM scan_runs ORDER BY id",
    "trade_decisions.jsonl":"SELECT * FROM trade_decisions ORDER BY id",
    "recommendations.jsonl":"SELECT * FROM recommendations ORDER BY created_at",
    "strategy_validation_runs.jsonl":"SELECT * FROM strategy_validation_runs ORDER BY id",
    "algorithm_versions.jsonl":"SELECT * FROM algorithm_versions ORDER BY id",
    "institutional_snapshots.jsonl":"SELECT * FROM institutional_snapshots ORDER BY captured_at",
    "system_state.jsonl":"SELECT key,value_json,updated_at FROM system_state ORDER BY key",
}


def _secret_values() -> list[str]:
    vals=[]
    try:
        raw=json.loads(CREDENTIALS_PATH.read_text()) if CREDENTIALS_PATH.exists() else {}
        if isinstance(raw,dict):
            for k,v in raw.items():
                if any(x in str(k).lower() for x in _SECRET_KEYS) and isinstance(v,str) and len(v)>=4:
                    vals.append(v)
    except Exception:
        pass
    return vals


def _redact_text(text:str,secrets:Iterable[str])->str:
    out=str(text)
    for s in secrets:
        if s:out=out.replace(s,"<REDACTED_SECRET>")
    out=re.sub(r'(?i)(authorization\s*[:=]\s*)(bearer\s+)?[^\s,;"\']+',r'\1<REDACTED_SECRET>',out)
    return out


def _sanitize(value:Any)->Any:
    if isinstance(value,dict):
        out={}
        for k,v in value.items():
            lk=str(k).lower()
            out[k]="<REDACTED>" if any(x in lk for x in _SECRET_KEYS) else _sanitize(v)
        return out
    if isinstance(value,list):
        return [_sanitize(x) for x in value]
    return value


def _write_logs(z:zipfile.ZipFile,secrets:Iterable[str])->int:
    count=0
    if not LOGS.exists():
        return count
    errors=[]
    for p in sorted(LOGS.rglob("*")):
        if not p.is_file():
            continue
        try:
            with p.open("r",encoding="utf-8",errors="replace") as src, z.open("logs/"+str(p.relative_to(LOGS)),"w") as dst:
                for line in src:
                    dst.write(_redact_text(line,secrets).encode("utf-8","replace"))
            count+=1
        except Exception as exc:
            errors.append(f"{p}: {exc}")
    if errors:
        z.writestr("logs/_export_errors.txt","\n".join(errors)+"\n")
    return count


def _write_db_exports(z:zipfile.ZipFile,secrets:Iterable[str])->Dict[str,int]:
    counts={}
    with db(timeout_seconds=10.0) as con:
        for name,sql in _EXPORTS.items():
            n=0
            try:
                with z.open("diagnostics/"+name,"w") as dst:
                    for row in con.execute(sql):
                        payload=_sanitize(dict(row))
                        line=json.dumps(payload,separators=(",",":"),default=str)+"\n"
                        dst.write(_redact_text(line,secrets).encode("utf-8"))
                        n+=1
                        if n%256==0:
                            time.sleep(0)
                counts[name]=n
            except Exception as exc:
                z.writestr("diagnostics/"+name+".error.txt",str(exc))
                counts[name]=0
    return counts


def _build_to_path(path:Path)->Dict[str,Any]:
    """Build a complete sanitized support archive off the HTTP request path."""
    started=time.monotonic();generated=now_iso();secrets=_secret_values()
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp.zip")
    manifest={
        "app":APP_NAME,"version":VERSION,"generated_at":generated,
        "scope":"ALL_RETAINED_SERVICE_LOGS_PLUS_SANITIZED_RUNTIME_AUDIT_EXPORT",
        "contains_credentials":False,"contains_settings":False,
        "format":"LOG_TEXT_PLUS_JSONL_DIAGNOSTICS",
        "note":"Raw service logs are secret-value redacted. Database exports exclude credential storage and redact secret-named fields.",
    }
    with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        z.writestr("manifest.json",json.dumps(manifest,indent=2,default=str))
        log_count=_write_logs(z,secrets)
        table_counts=_write_db_exports(z,secrets)
    os.replace(tmp,path)
    compressed_size=path.stat().st_size if path.exists() else None
    uncompressed_size=0
    try:
        with zipfile.ZipFile(path,"r") as check:
            uncompressed_size=sum(int(i.file_size or 0) for i in check.infolist())
    except Exception:
        uncompressed_size=0
    ratio=(float(compressed_size)/float(uncompressed_size)) if compressed_size and uncompressed_size else None
    return {
        "ready":True,"path":str(path),"generated_at":generated,"last_error":None,
        "elapsed_ms":round((time.monotonic()-started)*1000.0,1),
        "size_bytes":compressed_size,"uncompressed_size_bytes":uncompressed_size,
        "compression_ratio":round(ratio,4) if ratio is not None else None,
        "compression":"DEFLATE_LEVEL_1",
        "log_files":log_count,"table_rows":table_counts,
        "policy":"BACKGROUND_PREBUILT_SANITIZED_SUPPORT_BUNDLE_V6812",
    }


def _generated_age_seconds(status:Dict[str,Any])->float|None:
    raw=str((status or {}).get("generated_at") or "").strip()
    if not raw:return None
    try:
        from datetime import datetime
        dt=datetime.fromisoformat(raw)
        now=datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return max(0.0,(now-dt).total_seconds())
    except Exception:
        return None


def _load_payload(path:Path)->bytes:
    return path.read_bytes()


def refresh_support_bundle(*,force:bool=False,min_age_seconds:float=_MIN_REFRESH_AGE_SECONDS)->Dict[str,Any]:
    """Refresh off-request, but never continuously rebuild a still-fresh large archive."""
    global _PAYLOAD
    try:
        with _LOCK:
            current=dict(_STATUS)
        age=_generated_age_seconds(current)
        if not force and _LATEST_PATH.exists() and current.get("ready") is True and age is not None and age<max(60.0,float(min_age_seconds)):
            if _PAYLOAD is None:
                payload=_load_payload(_LATEST_PATH)
                with _LOCK:_PAYLOAD=payload
            with _LOCK:
                _STATUS.update({"payload_ready":_PAYLOAD is not None,
                                "payload_bytes":len(_PAYLOAD) if _PAYLOAD is not None else 0,
                                "request_path_filesystem_reads":0,
                                "min_refresh_age_seconds":max(60.0,float(min_age_seconds)),
                                "refresh_skipped_fresh":True})
            return support_bundle_status()
        out=_build_to_path(_LATEST_PATH)
        payload=_load_payload(_LATEST_PATH)
        out.update({"payload_ready":True,"payload_bytes":len(payload),
                    "request_path_filesystem_reads":0,
                    "min_refresh_age_seconds":max(60.0,float(min_age_seconds)),
                    "refresh_skipped_fresh":False})
        _STATUS_PATH.parent.mkdir(parents=True,exist_ok=True)
        _STATUS_PATH.write_text(json.dumps(out,separators=(",",":"),default=str))
        with _LOCK:
            _PAYLOAD=payload
            _STATUS.clear();_STATUS.update(out)
    except Exception as exc:
        with _LOCK:
            _STATUS["last_error"]=str(exc)[:240]
    return support_bundle_status()


def prime_support_bundle()->Dict[str,Any]:
    """Restore metadata and preload the completed compressed archive before serving HTTP."""
    global _PAYLOAD
    loaded={}
    payload=None
    try:
        if _STATUS_PATH.exists():
            loaded=json.loads(_STATUS_PATH.read_text())
    except Exception:
        loaded={}
    try:
        if _LATEST_PATH.exists():
            payload=_load_payload(_LATEST_PATH)
            loaded={**loaded,"ready":True,"path":str(_LATEST_PATH),"size_bytes":_LATEST_PATH.stat().st_size,
                    "payload_ready":True,"payload_bytes":len(payload),"request_path_filesystem_reads":0,
                    "min_refresh_age_seconds":_MIN_REFRESH_AGE_SECONDS}
    except Exception as exc:
        loaded={**loaded,"payload_ready":False,"last_error":str(exc)[:240]}
    with _LOCK:
        _PAYLOAD=payload
        if loaded:
            _STATUS.clear();_STATUS.update(loaded)
    return support_bundle_status()


def support_bundle_status()->Dict[str,Any]:
    with _LOCK:
        return dict(_STATUS)


def latest_support_bundle_path()->Path|None:
    return _LATEST_PATH if _LATEST_PATH.exists() else None


def latest_support_bundle_payload()->bytes|None:
    with _LOCK:
        return _PAYLOAD


def build_support_bundle()->tuple[bytes,str]:
    """Compatibility/testing helper for SERVICE_LOGS_PLUS_SANITIZED_RUNTIME_AUDIT_EXPORT.

    The production HTTP route serves the prebuilt file. The compatibility builder
    preserves contains_credentials=False semantics and never includes settings files.
    """
    tmp=_EXPORT_DIR/"PS_Scanner_Logs_compat.zip"
    out=_build_to_path(tmp)
    payload=tmp.read_bytes()
    try:tmp.unlink()
    except Exception:pass
    stamp=str(out.get("generated_at") or now_iso()).replace(":","-").replace("+","_")
    return payload,f"PS_Scanner_Logs_{VERSION}_{stamp}.zip"
