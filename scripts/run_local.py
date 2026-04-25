from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
IS_WINDOWS = os.name == "nt"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def ensure_prerequisites() -> None:
    if not VENV_PYTHON.exists():
        raise SystemExit("Missing .venv. Run `python scripts/setup_local.py` first.")
    if not (ROOT / ".env").exists():
        raise SystemExit("Missing .env. Run `python scripts/setup_local.py` first and fill in LLM values.")


def start_app(app_port: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", app_port],
        cwd=ROOT,
    )


def run_controller(app_url: str) -> int:
    env = os.environ.copy()
    env["ALG_TARGET_URL"] = app_url
    completed = subprocess.run([str(VENV_PYTHON), "controller/main.py"], cwd=ROOT, env=env)
    return completed.returncode


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
        process.wait(timeout=10)
    except Exception:
        process.kill()


def main() -> None:
    ensure_prerequisites()

    app_port = os.getenv("APP_PORT", "8000")
    app_url = f"http://127.0.0.1:{app_port}"

    print("Starting ALG local stack...")
    print(f"FastAPI: {app_url}")
    print("Controller: Python + Locust in-process")
    print()

    app_process = start_app(app_port)
    try:
        time.sleep(3)
        raise SystemExit(run_controller(app_url))
    finally:
        stop_process(app_process)


if __name__ == "__main__":
    main()
