"""PostgreSQL custom-format backups; restoration is restricted to a NEW test database."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import django
from django.conf import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "basis_trainning_app.settings")
django.setup()

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["backup", "restore-test"])
parser.add_argument("file", type=Path)
parser.add_argument("--database")
args = parser.parse_args()
database = settings.DATABASES["default"]
if database["ENGINE"] != "django.db.backends.postgresql":
    parser.error("This command requires PostgreSQL; it never opens SQLite source data.")
environment = {
    **os.environ,
    "PGHOST": database.get("HOST") or "127.0.0.1",
    "PGPORT": str(database.get("PORT") or 5432),
    "PGUSER": database["USER"],
    "PGPASSWORD": database.get("PASSWORD") or "",
    "PGDATABASE": database["NAME"],
}
if args.action == "backup":
    if args.file.exists():
        parser.error("Backup file already exists; refusing to overwrite it.")
    args.file.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(args.file)],
        env=environment,
        check=True,
    )
else:
    if (
        not args.database
        or not args.database.startswith("basis_restore_")
        or args.database == database["NAME"]
    ):
        parser.error(
            "Choose a NEW disposable database named basis_restore_*. Production restoration is deliberately not automated."
        )
    if not args.file.is_file():
        parser.error("Backup does not exist.")
    environment["PGDATABASE"] = args.database
    subprocess.run(["createdb", args.database], env=environment, check=True)
    subprocess.run(
        [
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
            "--dbname",
            args.database,
            str(args.file),
        ],
        env=environment,
        check=True,
    )
print("Backup operation completed; no credentials were written to output.")
