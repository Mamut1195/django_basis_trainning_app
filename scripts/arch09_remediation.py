"""Verify and integrate the exact ARCH-09 remediation candidate on disposable services."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
BASE = "337f12d8d6b78d52c77c3e7e821ab2af1351cdc8"
MANIFEST = "docs/architecture/ARCH-09-REMEDIATION-FILES.json"
RECEIPT = "docs/architecture/ARCH-09-REMEDIATION-RESULT.json"
BRANCH = "arch/09-remediation"
LABELS = (
    "tests.regression", "basis.bootstrap.tests",
    "basis.modules.billing.adapters.test_persistence",
    "basis.modules.billing.adapters.test_polar",
    "basis.modules.training.adapters.test_metrics", "basis.modules.sync.adapters.test_wire",
)
WHITESPACE = "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol"
BROWSER_CHECKS = {
    "desktop_mobile_navigation", "real_offline_reload", "fractional_result_persisted",
    "ordered_two_operation_outbox", "completed_revision_three",
    "idempotent_replay_historical_snapshot", "stale_revision_409", "csrf_403",
    "real_csrf_logout_post", "other_tab_logout_redirect", "logout_clears_local_account",
    "account_switch_hides_sessions", "foreign_snapshot_404", "foreign_queue_403",
}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2", ".pdf"}


def object_map(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("Expected a JSON object with string keys")
    return cast(dict[str, object], value)


def read_json(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8-sig"))
    return object_map(value)


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def safe_path(value: str) -> Path:
    candidate = Path(value)
    if not value or "\\" in value or "\n" in value or "\r" in value or ":" in value or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Manifest path must be a relative repository path: " + value)
    result = (ROOT / candidate).resolve()
    if not result.is_relative_to(ROOT) or result == ROOT or (ROOT / candidate).is_symlink():
        raise ValueError("Manifest path escapes the repository: " + value)
    return result


def string_list(data: dict[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Manifest requires a string list: " + key)
    result = tuple(cast(list[str], value))
    if len(set(result)) != len(result):
        raise ValueError("Duplicate manifest path in " + key)
    for path in result:
        safe_path(path)
    return result


@dataclass(frozen=True)
class Manifest:
    files: tuple[str, ...]
    deleted: tuple[str, ...]
    verification: tuple[str, ...]
    protected: tuple[str, ...]
    pure: int
    postgres: int

    @classmethod
    def load(cls) -> Manifest:
        data = read_json(ROOT / MANIFEST)
        if data.get("base_commit") != BASE:
            raise ValueError("Manifest does not identify the reviewed ARCH-09 base")
        pure, postgres = data.get("pure_tests"), data.get("postgresql_tests")
        if type(pure) is not int or type(postgres) is not int or pure < 111 or postgres < 224:
            raise ValueError("Manifest requires reviewed nondecreasing test counts")
        result = cls(string_list(data, "files"), string_list(data, "deleted_files"),
                     string_list(data, "verification_files"), string_list(data, "protected_files"),
                     pure, postgres)
        if RECEIPT not in result.files or MANIFEST not in result.files or "manage.py" not in result.files:
            raise ValueError("Scope must include the receipt, manifest and manage.py contents")
        if "seed.py" not in result.protected or "seed.py" in result.files or "seed.py" in result.verification:
            raise ValueError("Unrelated seed.py must remain protected and excluded")
        if RECEIPT in result.verification:
            raise ValueError("The verification receipt cannot hash itself")
        if not set(result.files).difference({RECEIPT}).issubset(result.verification):
            raise ValueError("Verification sources must cover the entire positive scope")
        if set(result.files) & set(result.deleted) or set(result.protected) & (set(result.files) | set(result.deleted) | set(result.verification)) or set(result.verification) & set(result.deleted):
            raise ValueError("Positive, deleted and protected sets overlap")
        return result


def normalized_hash(content: bytes, path: str) -> tuple[str, str]:
    if Path(path).suffix.lower() in BINARY_SUFFIXES:
        return hashlib.sha256(content).hexdigest(), "binary SHA256"
    text = content.decode("utf-8-sig").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), "UTF8-sig CRLF-to-LF SHA256"


def source_hashes(manifest: Manifest) -> tuple[dict[str, str], dict[str, str]]:
    hashes: dict[str, str] = {}
    modes: dict[str, str] = {}
    for relative in manifest.verification:
        path = safe_path(relative)
        if not path.is_file():
            raise ValueError("Missing verification source: " + relative)
        hashes[relative], modes[relative] = normalized_hash(path.read_bytes(), relative)
    for relative in manifest.deleted:
        if safe_path(relative).exists():
            raise ValueError("Retired path still exists: " + relative)
    return hashes, modes


def protected_hashes(manifest: Manifest) -> dict[str, str]:
    return {path: hashlib.sha256(safe_path(path).read_bytes()).hexdigest() for path in manifest.protected}


@dataclass(frozen=True)
class Result:
    code: int
    output: bytes
    error: bytes
    stdout: Path
    stderr: Path

    def text(self) -> str:
        return (self.output + self.error).decode("utf-8", errors="replace")


class Runner:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        self.environment = os.environ.copy()
        self.environment.update(PYTHONIOENCODING="utf-8", DJANGO_SETTINGS_MODULE="config.test_settings",
                                DJANGO_DEBUG="1", DATABASE_URL="sqlite:///:memory:",
                                DJANGO_SECRET_KEY=uuid4().hex + uuid4().hex,
                                DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,testserver,[::1]",
                                AI_ENABLED="0", DEEPSEEK_API_KEY="", POLAR_ACCESS_TOKEN="",
                                POLAR_PRODUCT_ID="", POLAR_WEBHOOK_SECRET="",
                                BASIS_DEVELOPMENT_ACCESS="0", BASIS_DEMO_PASSWORD="",
                                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                                EMAIL_HOST="127.0.0.1", EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="",
                                PUBLIC_URL="http://127.0.0.1:8000", PYTHONDONTWRITEBYTECODE="1")
        self.step = 0
        self.checks: dict[str, object] = {}

    def command(self, arguments: list[str], label: str, *, allowed: tuple[int, ...] = (0,),
                data: bytes | None = None) -> Result:
        self.step += 1
        prefix = self.directory / (str(self.step).zfill(3) + "-" + label)
        stdout, stderr = prefix.with_suffix(".stdout.log"), prefix.with_suffix(".stderr.log")
        completed = subprocess.run(arguments, cwd=ROOT, env=self.environment, input=data,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        stdout.write_bytes(completed.stdout)
        stderr.write_bytes(completed.stderr)
        result = Result(completed.returncode, completed.stdout, completed.stderr, stdout, stderr)
        if result.code not in allowed:
            raise RuntimeError(label + " failed with exit " + str(result.code) + "; logs: " + str(prefix))
        return result

    def check(self, arguments: list[str], label: str) -> Result:
        print("Checking " + label + "...", flush=True)
        result = self.command(arguments, label)
        self.checks[label] = {"status": "VERIFIED", "exit_code": result.code,
                              "stdout": str(result.stdout.relative_to(ROOT)), "stderr": str(result.stderr.relative_to(ROOT))}
        return result

    def git(self, arguments: list[str], label: str, *, allowed: tuple[int, ...] = (0,),
            data: bytes | None = None) -> Result:
        return self.command(["git", "--no-optional-locks", *arguments], label, allowed=allowed, data=data)


def assert_suite(result: Result, count: int, label: str, *, no_skips: bool = True) -> None:
    text = result.text()
    if result.code != 0 or re.search(r"Ran " + str(count) + r" tests?\b", text) is None or re.search(r"(?m)^OK\s*$", text) is None or (no_skips and re.search(r"skipped=|\bskipped\b", text, re.IGNORECASE)):
        raise RuntimeError(label + " must pass exactly " + str(count) + " tests without skips")


def whitespace_preflight(runner: Runner, manifest: Manifest) -> None:
    empty = runner.directory / "empty.txt"
    empty.write_bytes(b"")
    for relative in manifest.files:
        if relative == RECEIPT or Path(relative).suffix.lower() in BINARY_SUFFIXES:
            continue
        result = runner.git(["-c", "core.autocrlf=false", "-c", WHITESPACE, "diff", "--no-index", "--check", "--",
                             str(empty), str(safe_path(relative))], "whitespace", allowed=(0, 1))
        # A clean nonempty file differs from the empty file: exit 1 with no diagnostics is valid.
        if result.output or result.error:
            raise RuntimeError("Whitespace preflight failed: " + relative + "; " + str(result.stdout))
    runner.checks["whitespace-preflight"] = {"status": "VERIFIED", "files": len(manifest.files) - 1}


def self_test(runner: Runner) -> None:
    ok = runner.command([sys.executable, "-c", "import sys; print('native stderr success', file=sys.stderr)"], "stderr-success")
    if b"native stderr success" not in ok.error:
        raise RuntimeError("Native stderr capture failed")
    bad = runner.command([sys.executable, "--deliberately-invalid-arch09-remediation"], "nonzero-exit", allowed=(2,))
    if bad.code == 0:
        raise RuntimeError("Native nonzero exit capture failed")
    spaced = runner.directory / "path with spaces.txt"
    spaced.write_text("spaces-safe", encoding="utf-8")
    result = runner.command([sys.executable, "-c", "import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text())", str(spaced)], "spaced-path")
    if result.output.strip() != b"spaces-safe":
        raise RuntimeError("Argument vector did not preserve spaces")
    print("VERIFIED: native stderr, nonzero exit and paths with spaces", flush=True)


def browser_evidence(path: Path) -> dict[str, object]:
    result = read_json(path / "result.json")
    browser = object_map(result.get("browser"))
    checks = browser.get("checks")
    if result.get("status") != "VERIFIED" or result.get("server_stopped") is not True or result.get("browser_closed") is not True or browser.get("status") != "VERIFIED":
        raise RuntimeError("Real browser and owned server cleanup must be VERIFIED")
    if not isinstance(checks, list) or len(checks) != 14 or not all(isinstance(item, str) for item in checks) or set(cast(list[str], checks)) != BROWSER_CHECKS:
        raise RuntimeError("Real browser must verify all 14 distinct acceptance checks")
    if browser.get("javascript_errors") != [] or browser.get("external_responses") != []:
        raise RuntimeError("Browser reported JavaScript errors or external HTTP responses")
    closed = read_json(path / "browser-closed.json")
    if closed.get("browser_closed") is not True:
        raise RuntimeError("Original browser cleanup evidence is missing")
    return result


def assert_candidate_scope(runner: Runner, manifest: Manifest) -> None:
    changed = runner.git(["diff", "--name-only", "-z", "HEAD"], "changed-paths").output
    untracked = runner.git(["ls-files", "--others", "--exclude-standard", "-z"], "untracked-paths").output
    paths = {path.decode("utf-8") for path in (changed + untracked).split(b"\0") if path}
    unexpected = paths - (set(manifest.files) | set(manifest.deleted) | set(manifest.protected))
    if unexpected:
        raise RuntimeError("Changes outside the reviewed/protected scope: " + ", ".join(sorted(unexpected)))


def verify(runner: Runner, manifest: Manifest, port: int) -> dict[str, object]:
    before, modes = source_hashes(manifest)
    protected = protected_hashes(manifest)
    receipt: dict[str, object] = {"status": "FAILED", "run_id": runner.directory.name,
        "base_commit": BASE, "checks": runner.checks, "container_stopped": False}
    container: str | None = None
    cid_path = runner.directory / "container.cid"
    try:
        assert_candidate_scope(runner, manifest)
        whitespace_preflight(runner, manifest)
        runner.check([sys.executable, "scripts/architecture_check.py"], "architecture")
        pure = runner.check([sys.executable, "-m", "unittest", "discover", "-s", "tests_architecture"], "pure-tests")
        assert_suite(pure, manifest.pure, "Pure suite")
        runner.check([sys.executable, "-m", "mypy", "--config-file", "mypy-core.ini"], "core-types")
        runner.check([sys.executable, "-m", "mypy", "--config-file", "mypy-django.ini"], "django-types")
        import_tool = Path(sys.executable).parent / ("lint-imports.exe" if os.name == "nt" else "lint-imports")
        imports = runner.check([str(import_tool), "--no-cache"], "imports")
        if re.search(r"Contracts:\s*8 kept,\s*0 broken", imports.text()) is None:
            raise RuntimeError("Import Linter did not execute all eight contracts")
        runner.check([sys.executable, "-m", "ruff", "check", "."], "ruff")
        runner.check([sys.executable, "manage.py", "check"], "django-check")
        runner.check([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], "migrations")
        runner.check([sys.executable, "manage.py", "collectstatic", "--noinput"], "static-assets")
        runner.check(["docker", "version"], "docker-access")
        name = "basis-arch09-remediation-" + runner.directory.name
        try:
            runner.check(["docker", "run", "--detach", "--rm", "--name", name,
                "--cidfile", str(cid_path), "--label", "basis.arch09.remediation=" + runner.directory.name,
                "--publish", "127.0.0.1:" + str(port) + ":5432", "--env", "POSTGRES_USER=basis_remediation",
                "--env", "POSTGRES_PASSWORD=remediation-test-only", "--env", "POSTGRES_DB=basis_remediation", "postgres:18.4"], "postgres-start")
        finally:
            if cid_path.is_file():
                id = cid_path.read_text(encoding="ascii").strip()
                if re.fullmatch(r"[a-f0-9]{64}", id):
                    container = id
        if container is None:
            raise RuntimeError("Docker did not return an owned container ID")
        for attempt in range(40):
            probe = runner.command(["docker", "exec", container, "pg_isready", "-U", "basis_remediation", "-d", "basis_remediation"], "postgres-ready", allowed=tuple(range(256)))
            if probe.code == 0:
                break
            if attempt == 39:
                raise RuntimeError("Owned PostgreSQL did not become ready")
            time.sleep(1)
        mapping = runner.check(["docker", "port", container, "5432/tcp"], "loopback-binding")
        if mapping.output.decode().strip() != "127.0.0.1:" + str(port):
            raise RuntimeError("PostgreSQL binding is not the owned loopback port")
        version = runner.check(["docker", "exec", container, "postgres", "--version"], "postgres-version")
        if "PostgreSQL) 18.4" not in version.output.decode():
            raise RuntimeError("PostgreSQL 18.4 is required")
        image = runner.check(["docker", "inspect", "--format", "{{.Image}}", container], "postgres-image")
        runner.environment["DATABASE_URL"] = "postgresql://basis_remediation:remediation-test-only@127.0.0.1:" + str(port) + "/basis_remediation"
        suite = runner.check([sys.executable, "manage.py", "test", *LABELS, "--noinput"], "postgres-tests")
        assert_suite(suite, manifest.postgres, "PostgreSQL suite")
        browser_dir = runner.directory / "browser"
        runner.check([sys.executable, "scripts/acceptance_browser.py", "--output", str(browser_dir)], "real-browser")
        receipt["browser"] = browser_evidence(browser_dir)
        after, after_modes = source_hashes(manifest)
        if before != after or modes != after_modes or protected != protected_hashes(manifest):
            raise RuntimeError("Sources or protected files changed during verification")
        receipt.update(status="VERIFIED", tests=manifest.postgres, pure_tests=manifest.pure, skipped=0,
            engine=version.output.decode().strip(), image_id=image.output.decode().strip(),
            source_hashes=after, source_hash_modes=after_modes, deleted_files=list(manifest.deleted),
            protected_hashes=protected, fresh_schema="Disposable Django test database from initial module migrations")
    except Exception as error:
        receipt["error"] = str(error)
    finally:
        if container is not None:
            try:
                stopped = runner.command(["docker", "stop", "--time", "10", container], "postgres-stop", allowed=tuple(range(256)))
                receipt["container_stopped"] = stopped.code == 0
                if stopped.code != 0:
                    raise RuntimeError("Owned PostgreSQL container did not stop")
            except Exception as error:
                receipt.update(status="FAILED", cleanup_error=str(error))
        receipt["verified_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_json(runner.directory / "receipt.json", receipt)
        if receipt.get("status") == "VERIFIED" and receipt.get("container_stopped") is True:
            write_json(ROOT / RECEIPT, receipt)
    if receipt.get("status") != "VERIFIED" or receipt.get("container_stopped") is not True:
        raise RuntimeError("Verification FAILED; retained logs: " + str(runner.directory))
    return receipt


def batch_blobs(runner: Runner, expressions: tuple[str, ...]) -> dict[str, bytes]:
    result = runner.git(["cat-file", "--batch"], "batch-blobs", data=("\n".join(expressions) + "\n").encode("utf-8"))
    output = result.output
    offset = 0
    blobs: dict[str, bytes] = {}
    for expression in expressions:
        end = output.index(b"\n", offset)
        header = output[offset:end].decode("ascii").split()
        if len(header) != 3 or header[1] != "blob":
            raise RuntimeError("Missing expected Git blob: " + expression)
        size = int(header[2])
        start = end + 1
        blobs[expression] = output[start:start + size]
        if len(blobs[expression]) != size or output[start + size:start + size + 1] != b"\n":
            raise RuntimeError("Malformed Git batch content")
        offset = start + size + 1
    if offset != len(output):
        raise RuntimeError("Unexpected extra Git batch output")
    return blobs


def assert_git_hashes(runner: Runner, manifest: Manifest, hashes: dict[str, str], prefix: str) -> None:
    paths = tuple(hashes)
    blobs = batch_blobs(runner, tuple(prefix + path for path in paths))
    for path in paths:
        actual, _ = normalized_hash(blobs[prefix + path], path)
        if actual != hashes[path]:
            raise RuntimeError("Git blob differs from reviewed bytes: " + prefix + path)
    entries = runner.git(["ls-files", "--stage", "--", "manage.py"], "manage-mode") if prefix == ":" else runner.git(["ls-tree", prefix.removesuffix(":"), "--", "manage.py"], "manage-mode")
    if not entries.output.startswith(b"100755 "):
        raise RuntimeError("manage.py executable index/HEAD mode must remain 100755")
    if prefix == ":":
        listed = runner.git(["ls-files", "-z", "--", *manifest.files, *manifest.deleted], "indexed-paths")
    else:
        listed = runner.git(["ls-tree", "-r", "-z", "--name-only", prefix.removesuffix(":"), "--", *manifest.files, *manifest.deleted], "committed-paths")
    actual_paths = {path.decode("utf-8") for path in listed.output.split(b"\0") if path}
    if actual_paths != set(manifest.files):
        raise RuntimeError("Git positive/deletion scope does not match the manifest")


def verified_receipt(runner: Runner, manifest: Manifest) -> dict[str, object]:
    receipt = read_json(ROOT / RECEIPT)
    run_id = receipt.get("run_id")
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise RuntimeError("Receipt has no valid original verification run")
    original = safe_path(".cache/arch09-remediation/" + run_id)
    if read_json(original / "receipt.json") != receipt:
        raise RuntimeError("Receipt differs from the retained original verification evidence")
    if receipt.get("status") != "VERIFIED" or receipt.get("base_commit") != BASE or receipt.get("tests") != manifest.postgres or receipt.get("pure_tests") != manifest.pure or receipt.get("skipped") != 0 or receipt.get("container_stopped") is not True:
        raise RuntimeError("Resume requires the complete VERIFIED PostgreSQL/browser receipt")
    hashes, modes = source_hashes(manifest)
    if receipt.get("source_hashes") != hashes or receipt.get("source_hash_modes") != modes or receipt.get("deleted_files") != list(manifest.deleted) or receipt.get("protected_hashes") != protected_hashes(manifest):
        raise RuntimeError("Resume refused: sources, deletions or protected files differ from verified evidence")
    checks = object_map(receipt.get("checks"))
    required = ("architecture", "pure-tests", "core-types", "django-types", "imports", "ruff",
                "django-check", "migrations", "static-assets", "docker-access", "postgres-start",
                "loopback-binding", "postgres-version", "postgres-image", "postgres-tests", "real-browser")
    for label in required:
        check = object_map(checks.get(label))
        if check.get("status") != "VERIFIED" or check.get("exit_code") != 0:
            raise RuntimeError("Missing successful original check: " + label)
        for key in ("stdout", "stderr"):
            relative = check.get(key)
            if not isinstance(relative, str) or not safe_path(relative).is_relative_to(original) or not safe_path(relative).is_file():
                raise RuntimeError("Missing original native logs: " + label)
    for label, count in (("pure-tests", manifest.pure), ("postgres-tests", manifest.postgres)):
        check = object_map(checks[label])
        stdout, stderr = safe_path(cast(str, check["stdout"])), safe_path(cast(str, check["stderr"]))
        assert_suite(Result(0, stdout.read_bytes(), stderr.read_bytes(), stdout, stderr), count, label)
    imports = object_map(checks["imports"])
    imports_text = safe_path(cast(str, imports["stdout"])).read_text(encoding="utf-8")
    if re.search(r"Contracts:\s*8 kept,\s*0 broken", imports_text) is None:
        raise RuntimeError("Original Import Linter evidence is incomplete")
    if browser_evidence(original / "browser") != receipt.get("browser"):
        raise RuntimeError("Original 14-check browser evidence differs from the receipt")
    assert_candidate_scope(runner, manifest)
    return receipt


def candidate_ref(runner: Runner) -> str | None:
    result = runner.git(["rev-parse", "--verify", "--quiet", "refs/heads/" + BRANCH], "candidate-ref", allowed=(0, 1))
    return result.output.decode().strip() if result.code == 0 else None


def staged_scope(runner: Runner, manifest: Manifest) -> None:
    result = runner.git(["diff", "--cached", "--name-only", "-z"], "staged-scope")
    actual = {path.decode("utf-8") for path in result.output.split(b"\0") if path}
    if actual - (set(manifest.files) | set(manifest.deleted)):
        raise RuntimeError("Unexpected staged file; index retained for review")


def integrate(runner: Runner, manifest: Manifest, receipt: dict[str, object], *, resume: bool) -> dict[str, object]:
    branch = runner.git(["branch", "--show-current"], "integration-branch").output.decode().strip()
    head = runner.git(["rev-parse", "HEAD"], "integration-head").output.decode().strip()
    candidate = candidate_ref(runner)
    if branch not in ("main", BRANCH):
        raise RuntimeError("Resume/integration permits only main or the reviewed candidate branch")
    protected = protected_hashes(manifest)
    hashes, _ = source_hashes(manifest)
    if hashes != receipt.get("source_hashes"):
        raise RuntimeError("Sources changed after verification")
    hashes[RECEIPT] = normalized_hash((ROOT / RECEIPT).read_bytes(), RECEIPT)[0]
    staged_scope(runner, manifest)
    if candidate is not None and candidate != BASE:
        if not resume:
            raise RuntimeError("A candidate commit already exists; use explicit --resume after review")
        if head not in (BASE, candidate):
            raise RuntimeError("Current HEAD is outside the reviewed base/candidate pair")
        parent = runner.git(["rev-parse", BRANCH + "^"], "candidate-parent").output.decode().strip()
        if parent != BASE:
            raise RuntimeError("Candidate is not a direct child of the reviewed base")
        changed = runner.git(["diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z", BRANCH], "candidate-changes")
        if {path.decode("utf-8") for path in changed.output.split(b"\0") if path} - (set(manifest.files) | set(manifest.deleted)):
            raise RuntimeError("Candidate commit contains unrelated changes")
        assert_git_hashes(runner, manifest, hashes, BRANCH + ":")
        clean = runner.git(["diff", "--cached", "--quiet"], "committed-index", allowed=(0, 1))
        if clean.code != 0:
            raise RuntimeError("Already committed candidate requires a clean index")
        commit = candidate
    else:
        if head != BASE:
            raise RuntimeError("Uncommitted candidate must remain at the reviewed base")
        if branch == "main":
            if candidate is None:
                runner.git(["switch", "-c", BRANCH], "candidate-branch")
            else:
                runner.git(["switch", BRANCH], "candidate-branch")
        runner.git(["add", "--all", "--", *manifest.files, *manifest.deleted], "stage-scope")
        runner.git(["update-index", "--chmod=+x", "--", "manage.py"], "preserve-manage-mode")
        staged_scope(runner, manifest)
        runner.git(["-c", WHITESPACE, "diff", "--cached", "--check"], "indexed-whitespace")
        assert_git_hashes(runner, manifest, hashes, ":")
        current, _ = source_hashes(manifest)
        if {key: value for key, value in hashes.items() if key != RECEIPT} != current or protected != protected_hashes(manifest):
            raise RuntimeError("Sources/protected files changed before commit")
        message = runner.directory / "message.txt"
        message.write_text("arch: complete hexagonal cases and verified browser acceptance\n", encoding="utf-8")
        runner.git(["commit", "-F", str(message)], "commit")
        commit = runner.git(["rev-parse", "HEAD"], "commit-id").output.decode().strip()
        parent = runner.git(["rev-parse", "HEAD^"], "commit-parent").output.decode().strip()
        if parent != BASE:
            raise RuntimeError("Unexpected integration parent; no automatic recovery attempted")
    main_ref = runner.git(["rev-parse", "refs/heads/main"], "main-ref").output.decode().strip()
    if main_ref not in (BASE, commit):
        raise RuntimeError("main advanced independently; reconcile before resuming")
    runner.git(["switch", "main"], "main")
    runner.git(["merge", "--ff-only", BRANCH], "fast-forward")
    if runner.git(["rev-parse", "HEAD"], "main-id").output.decode().strip() != commit:
        raise RuntimeError("Main commit mismatch")
    assert_git_hashes(runner, manifest, hashes, "HEAD:")
    current, _ = source_hashes(manifest)
    if {key: value for key, value in hashes.items() if key != RECEIPT} != current or protected != protected_hashes(manifest):
        raise RuntimeError("Sources/protected files changed during integration")
    integration: dict[str, object] = {"status": "VERIFIED", "commit": commit, "base": BASE,
        "branch": "main", "verification_run": receipt["run_id"], "source_hashes": hashes,
        "deleted_files": list(manifest.deleted), "protected_hashes": protected,
        "manage_mode": "100755", "push": "NOT RUN", "resumed": resume}
    write_json(ROOT / ".cache/arch09-remediation-integration.json", integration)
    print("VERIFIED: ARCH-09 remediation integrated in main at " + commit, flush=True)
    return integration


def complete(runner: Runner, manifest: Manifest, port: int, *, resume: bool = False) -> dict[str, object]:
    if resume:
        receipt = verified_receipt(runner, manifest)
        print("VERIFIED: original sources/logs/browser receipt match; resuming Git without rerunning services", flush=True)
    else:
        branch = runner.git(["branch", "--show-current"], "branch").output.decode().strip()
        base = runner.git(["rev-parse", "HEAD"], "base").output.decode().strip()
        if branch != "main" or base != BASE:
            raise RuntimeError("Expected main at reviewed ARCH-09 base " + BASE + "; actual " + branch + "/" + base + ". Return this SHA if already integrated; do not change the guard.")
        staged = runner.git(["diff", "--cached", "--quiet"], "empty-index", allowed=(0, 1))
        if staged.code != 0:
            raise RuntimeError("Existing staged changes require review; nothing was staged by this runner")
        if candidate_ref(runner) is not None:
            raise RuntimeError("Candidate branch exists; use --resume with its verified receipt or reconcile first")
        assert_candidate_scope(runner, manifest)
        self_test(runner)
        receipt = verify(runner, manifest, port)
    return integrate(runner, manifest, receipt, resume=resume)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("verify", "complete", "self-test"))
    parser.add_argument("--port", type=int, default=55440)
    parser.add_argument("--resume", action="store_true")
    options = parser.parse_args()
    mode, port = cast(str, options.mode), cast(int, options.port)
    if not 1024 <= port <= 65535:
        parser.error("Port must be 1024..65535")
    directory = safe_path(".cache/arch09-remediation/" + uuid4().hex)
    runner = Runner(directory)
    try:
        if mode == "self-test":
            self_test(runner)
        elif mode == "verify":
            manifest = Manifest.load()
            self_test(runner)
            verify(runner, manifest, port)
            print("VERIFIED: ARCH-09 remediation PostgreSQL and 14 real browser checks; receipt: " + RECEIPT)
        else:
            complete(runner, Manifest.load(), port, resume=bool(options.resume))
        return 0
    except Exception as error:
        print("FAILED: " + str(error) + "; logs: " + str(directory), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
