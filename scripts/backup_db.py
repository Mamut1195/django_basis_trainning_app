"""PostgreSQL custom backups; restore only to a NEW disposable database."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def pg_run(command: list[str], environment: dict[str, str]) -> None:
    """Postgres diagnostics may contain row data, hosts or secrets: don't relay them."""
    subprocess.run(command, env=environment, check=True, capture_output=True, timeout=300)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore-test"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--database")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    temporary: Path | None = None
    reserved = False
    try:
        import django
        from django.conf import settings

        django.setup()
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.postgresql":
            parser.error("PostgreSQL required; SQLite source data is never opened.")
        environment = {
            **os.environ,
            "PGHOST": database.get("HOST") or "127.0.0.1",
            "PGPORT": str(database.get("PORT") or 5432),
            "PGUSER": database["USER"],
            "PGPASSWORD": database.get("PASSWORD") or "",
            "PGDATABASE": database["NAME"],
            "PGSSLMODE": database.get("OPTIONS", {}).get("sslmode", "prefer"),
            "PGCONNECT_TIMEOUT": "10",
        }
        if args.action == "backup":
            args.file.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive reservation prevents overwrite, including concurrent callers.
            with args.file.open("xb"):
                reserved = True
            args.file.chmod(0o600)
            with tempfile.NamedTemporaryFile(
                prefix=".basis-dump-", dir=args.file.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
            pg_run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(temporary)],
                environment,
            )
            pg_run(["pg_restore", "--list", str(temporary)], environment)
            temporary.replace(args.file)
            reserved = False
        else:
            if (
                not args.database
                or not args.database.startswith("basis_restore_")
                or not args.database.replace("_", "").isalnum()
                or args.database == database["NAME"]
            ):
                parser.error("Choose a NEW disposable database named basis_restore_*.")
            if not args.file.is_file():
                parser.error("Backup does not exist.")
            pg_run(["pg_restore", "--list", str(args.file)], environment)
            # createdb fails if the name exists. No --clean, reuse or source overwrite.
            pg_run(["createdb", args.database], environment)
            environment["PGDATABASE"] = args.database
            pg_run(
                [
                    "pg_restore",
                    "--exit-on-error",
                    "--single-transaction",
                    "--no-owner",
                    "--no-acl",
                    "--dbname",
                    args.database,
                    str(args.file),
                ],
                environment,
            )
    except Exception as exc:
        print(
            f"Backup operation failed ({type(exc).__name__}); diagnostics suppressed.",
            file=sys.stderr,
        )
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if reserved:
            args.file.unlink(missing_ok=True)
    print("Backup operation completed; no credentials were written to output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
