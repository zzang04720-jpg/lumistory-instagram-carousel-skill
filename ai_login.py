"""Claude Code / Codex CLI login helpers used by app.py (local machine only)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROVIDERS = {
    "claude": {"label": "Claude", "status": ["auth", "status"], "login": ["auth", "login"], "logout": ["auth", "logout"]},
    "codex": {"label": "Codex", "status": ["login", "status"], "login": ["login"], "logout": ["logout"]},
}


def find_cli(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidates = [Path.home() / ".local" / "bin" / f"{name}.exe"]
    if os.environ.get("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "npm" / f"{name}.cmd")
    return next((str(p) for p in candidates if p.exists()), None)


def get_status(name: str) -> dict:
    """Return {installed, logged_in, detail}."""
    exe = find_cli(name)
    if not exe:
        return {"installed": False, "logged_in": False, "detail": "설치되어 있지 않습니다"}
    try:
        done = subprocess.run([exe, *PROVIDERS[name]["status"]], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=20)
    except Exception as exc:
        return {"installed": True, "logged_in": False, "detail": f"상태 확인 실패: {exc}"}
    out = (done.stdout or done.stderr or "").strip()
    if name == "claude":
        try:
            info = json.loads(out)
            return {"installed": True, "logged_in": bool(info.get("loggedIn")),
                    "detail": info.get("email") or "로그인되지 않았습니다"}
        except ValueError:
            pass
    return {"installed": True, "logged_in": done.returncode == 0 and "not logged" not in out.lower(),
            "detail": out.splitlines()[0] if out else "로그인되지 않았습니다"}


def open_login(name: str) -> None:
    """Open a console window running the interactive CLI login (browser OAuth)."""
    exe = find_cli(name)
    if not exe:
        raise FileNotFoundError(f"{name} 실행 파일을 찾지 못했습니다")
    cmd = [exe, *PROVIDERS[name]["login"]]
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/k", *cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(cmd)


def logout(name: str) -> None:
    exe = find_cli(name)
    if exe:
        subprocess.run([exe, *PROVIDERS[name]["logout"]], capture_output=True, timeout=20)
