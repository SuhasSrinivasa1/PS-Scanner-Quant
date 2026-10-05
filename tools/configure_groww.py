#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from psscanner_quant.paths import CREDENTIALS_PATH
from psscanner_quant.broker import broker


def secret(label: str) -> str:
    value=getpass.getpass(label).strip()
    if not value:
        raise SystemExit(f"{label.strip(': ')} is required")
    return value


def main() -> int:
    print("PS Scanner Quant — Groww credential setup")
    print("Secrets are written only to the local chmod-600 credential file.")
    print("They are never committed to GitHub or written to application logs.")
    print()
    print("1) TOTP token + TOTP secret (recommended when configured in Groww)")
    print("2) API key + API secret approval flow")
    print("3) Existing access token (temporary; no automatic refresh pair)")
    mode=input("Select authentication mode [1]: ").strip() or "1"
    payload={}
    if mode=="1":
        payload={"auth_mode":"totp","totp_token":secret("Groww TOTP token: "),"totp_secret":secret("Groww TOTP secret: ")}
    elif mode=="2":
        payload={"auth_mode":"approval","api_key":secret("Groww API key: "),"api_secret":secret("Groww API secret: ")}
    elif mode=="3":
        payload={"auth_mode":"access_token","access_token":secret("Groww access token: ")}
    else:
        raise SystemExit("Unsupported mode")

    CREDENTIALS_PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=CREDENTIALS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    os.chmod(tmp,0o600)
    os.replace(tmp,CREDENTIALS_PATH)
    os.chmod(CREDENTIALS_PATH,0o600)
    print(f"Credential file written: {CREDENTIALS_PATH}")
    print("Probing Groww authentication...")
    status=broker.status()
    safe={k:v for k,v in status.items() if k not in ("token","access_token","api_key","api_secret","totp_token","totp_secret")}
    print(json.dumps(safe,indent=2,default=str))
    if status.get("connected") is not True:
        print("Groww is not CONNECTED yet. Recheck the credential pair and network access.")
        return 2
    print("Groww authentication VERIFIED.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
