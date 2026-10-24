#!/usr/bin/env python3
"""Start an isolated local PostgreSQL cluster using installed PostgreSQL binaries.

Usage: python3 scripts/local_db.py start|stop|status
The cluster and secrets stay in ignored .local/; no existing database is modified.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres"
CONFIG = LOCAL / "postgres-config.json"
PORT = "55432"


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def configure_env(config):
    path = ROOT / ".env"
    content = path.read_text() if path.exists() else ""
    existing = {}
    for line in content.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            existing[key.strip().removeprefix("export ")] = shlex.split(value, comments=True)
    settings = {
        "DATABASE_URL": f"postgresql://veil:{config['password']}@127.0.0.1:{PORT}/veil",
        "VEIL_STORAGE_KEY": config["key"],
        "TEST_DATABASE_URL": f"postgresql://veil:{config['password']}@127.0.0.1:{PORT}/veil_test",
    }
    additions = []
    for key, value in settings.items():
        if existing.get(key) and existing[key][0]:
            if existing[key][0] != value:
                raise SystemExit(f"Existing {key} differs from the local setup. Keep it or configure manually; not overwritten.")
        else:
            # Replace an empty example entry rather than leaving duplicate keys.
            content = "\n".join(line for line in content.splitlines()
                                if line.split("=", 1)[0].strip().removeprefix("export ") != key)
            additions.append(f"{key}={value}")
    if additions:
        with path.open("a" if not path.exists() else "w") as handle:
            os.chmod(path, 0o600)
            handle.write(content.rstrip() + "\n\n" + "\n".join(additions) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    for binary in ("initdb", "pg_ctl", "psql", "createdb"):
        if not shutil.which(binary):
            raise SystemExit(f"Missing {binary}. Install PostgreSQL 16+ and add its bin directory to PATH.")
    if args.action != "start":
        if not (DATA / "PG_VERSION").exists():
            raise SystemExit("Local cluster has not been initialized.")
        command = ["pg_ctl", "-D", str(DATA), args.action]
        if args.action == "stop":
            command += ["-m", "fast", "-w"]
        run(command)
        return
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    if CONFIG.exists():
        config = json.loads(CONFIG.read_text())
    else:
        config = {"password": secrets.token_urlsafe(32),
                  "key": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}
        with CONFIG.open("x") as handle:
            os.chmod(CONFIG, 0o600)
            json.dump(config, handle)
    configure_env(config)
    if not (DATA / "PG_VERSION").exists():
        with tempfile.NamedTemporaryFile(mode="w", dir=LOCAL) as password:
            password.write(config["password"] + "\n")
            password.flush()
            run(["initdb", "-D", str(DATA), "-U", "veil", "--auth-local=trust",
                 "--auth-host=scram-sha-256", "--encoding=UTF8", "--locale=C",
                 f"--pwfile={password.name}"], stdout=subprocess.DEVNULL)
    status = subprocess.run(["pg_ctl", "-D", str(DATA), "status"], stdout=subprocess.DEVNULL)
    if status.returncode != 0:
        run(["pg_ctl", "-D", str(DATA), "-l", str(LOCAL / "postgres.log"),
             "-o", f"-h 127.0.0.1 -p {PORT} -k {shlex.quote(str(LOCAL))}", "-w", "start"])
    env = {**os.environ, "PGPASSWORD": config["password"]}
    connection = ["-h", "127.0.0.1", "-p", PORT, "-U", "veil"]
    for name in ("veil", "veil_test"):
        found = run(["psql", *connection, "-d", "postgres", "-At", "-c",
                     f"SELECT 1 FROM pg_database WHERE datname = '{name}'"],
                    env=env, capture_output=True, text=True).stdout.strip()
        if not found:
            run(["createdb", *connection, name], env=env)
    print("PostgreSQL ready at 127.0.0.1:55432 (veil and isolated veil_test databases).")
    print("Local connection settings and encryption key are configured in ignored .env.")


if __name__ == "__main__":
    main()
