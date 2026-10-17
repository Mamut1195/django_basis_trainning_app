"""Migrate a disposable SQLite backup; the original is always opened read-only."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "db.sqlite3"
target = root / ".cache/legacy-migration-check.sqlite3"
if target.exists():
    raise SystemExit(
        "A prior validation copy exists. Choose another evidence filename; do not overwrite it."
    )
before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
with (
    sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original,
    sqlite3.connect(target) as copy,
):
    original.backup(copy)
    tables = [
        "daily_trainning_app_" + name
        for name in ("classification", "exercise", "user", "userexerciserm", "workoutdata")
    ]
    before = {
        table: original.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
        for table in tables
    }
    original_ids = {
        table: [row[0] for row in original.execute('SELECT id FROM "' + table + '" ORDER BY id')]
        for table in tables
    }
env = {**os.environ, "BASIS_DATABASE_PATH": str(target)}
env.pop("DATABASE_URL", None)
subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=root, env=env, check=True)
with sqlite3.connect(target) as copy:
    after = {
        table: copy.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
        for table in tables
    }
    for table in tables:
        assert original_ids[table] == [
            row[0] for row in copy.execute('SELECT id FROM "' + table + '" ORDER BY id')
        ]
    total, distinct, linked = copy.execute(
        "SELECT COUNT(*),COUNT(DISTINCT public_id),COUNT(account_id) FROM daily_trainning_app_user"
    ).fetchone()
    assert total == distinct and linked == 0
assert before == after
assert hashlib.sha256(source.read_bytes()).hexdigest() == before_hash
result = {
    "original_unchanged": True,
    "counts_before": before,
    "counts_after": after,
    "legacy_profiles_unassigned": True,
    "unique_public_ids": True,
}
evidence = root / "artifacts/legacy-migration.json"
evidence.parent.mkdir(exist_ok=True)
evidence.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
