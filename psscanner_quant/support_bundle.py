from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable

from .constants import APP_NAME, VERSION
from .db import db, now_iso
from .paths import LOGS, CREDENTIALS_PATH

_SECRET_KEYS=("access_token","api_key","api_secret","totp_token","totp_secret","password","secret","authorization")
_MAX_FILE_BYTES=25*1024*1024

def _secret_values() -> list[str]:
    vals=[]
    try:
        raw=json.loads(CREDENTIALS_PATH.read_text()) if CREDENTIALS_PATH.exists() else {}
        if isinstance(raw,dict):
            for k,v in raw.items():
                if any(x in str(k).lower() for x in _SECRET_KEYS) and isinstance(v,str) and len(v)>=4:
                    vals.append(v)
    except Exception:pass
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
    if isinstance(value,list):return [_sanitize(x) for x in value]
    return value

def _query_rows(sql:str,args=())->list[dict]:
    with db(timeout_seconds=2.0) as con:
        return [dict(r) for r in con.execute(sql,tuple(args)).fetchall()]

def build_support_bundle()->tuple[bytes,str]:
    """Build a user-exportable diagnostic archive without credentials/settings."""
    secrets=_secret_values();buf=io.BytesIO();generated=now_iso()
    manifest={
        "app":APP_NAME,"version":VERSION,"generated_at":generated,
        "scope":"SERVICE_LOGS_PLUS_SANITIZED_RUNTIME_AUDIT_EXPORT",
        "contains_credentials":False,"contains_settings":False,
        "note":"Raw service log text is secret-value redacted. Database exports exclude credential storage.",
    }
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json",json.dumps(manifest,indent=2,default=str))
        if LOGS.exists():
            for p in sorted(LOGS.rglob("*")):
                if not p.is_file():continue
                try:
                    raw=p.read_bytes()
                    if len(raw)>_MAX_FILE_BYTES:raw=raw[-_MAX_FILE_BYTES:]
                    text=raw.decode("utf-8","replace")
                    z.writestr("logs/"+str(p.relative_to(LOGS)),_redact_text(text,secrets))
                except Exception as exc:
                    z.writestr("logs/_export_errors.txt",f"{p}: {exc}\n")
        exports={
            "health_events.json":("SELECT * FROM health_events ORDER BY id",()),
            "scan_runs.json":("SELECT * FROM scan_runs ORDER BY id",()),
            "trade_decisions.json":("SELECT * FROM trade_decisions ORDER BY id",()),
            "recommendations.json":("SELECT * FROM recommendations ORDER BY created_at",()),
            "strategy_validation_runs.json":("SELECT * FROM strategy_validation_runs ORDER BY id",()),
            "algorithm_versions.json":("SELECT * FROM algorithm_versions ORDER BY id",()),
            "institutional_snapshots.json":("SELECT * FROM institutional_snapshots ORDER BY captured_at",()),
            "system_state.json":("SELECT key,value_json,updated_at FROM system_state ORDER BY key",()),
        }
        for name,(sql,args) in exports.items():
            try:z.writestr("diagnostics/"+name,json.dumps(_sanitize(_query_rows(sql,args)),indent=2,default=str))
            except Exception as exc:z.writestr("diagnostics/"+name+".error.txt",str(exc))
    stamp=generated.replace(":","-").replace("+","_")
    return buf.getvalue(),f"PS_Scanner_Logs_{VERSION}_{stamp}.zip"
