"""Runner contracts: real argv/whitespace and simulated Git recovery without Git writes."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import arch09_remediation as module

CANDIDATE = "a" * 40


class GitSimulation(module.Runner):
    def __init__(self, directory: Path, manifest: module.Manifest) -> None:
        super().__init__(directory)
        self.manifest = manifest
        self.branch = "main"
        self.head = module.BASE
        self.main_ref = module.BASE
        self.candidate: str | None = None
        self.staged = False
        self.mutations: list[str] = []
        self.corrupt_blob = False
        self.mode = "100755"

    def git(self, arguments: list[str], label: str, *, allowed: tuple[int, ...] = (0,),
            data: bytes | None = None) -> module.Result:
        output = b""
        code = 0
        while arguments[0] == "-c":
            arguments = arguments[2:]
        command = arguments[0]
        if command == "branch":
            output = self.branch.encode()
        elif command == "show-ref":
            output, code = (self.candidate.encode(), 0) if self.candidate else (b"", 1)
        elif command == "rev-parse":
            if "--quiet" in arguments:
                output, code = (self.candidate.encode(), 0) if self.candidate else (b"", 1)
            else:
                ref = arguments[1]
                output = (self.head if ref == "HEAD" else self.main_ref if ref == "refs/heads/main" else module.BASE).encode()
        elif command == "diff":
            if "--quiet" in arguments:
                code = 1 if self.staged else 0
            elif "--check" not in arguments:
                paths = self.manifest.files if self.staged or "--cached" not in arguments else ()
                output = b"".join(path.encode() + b"\0" for path in paths)
        elif command == "ls-files":
            if "--others" in arguments:
                output = b""
            elif "--stage" in arguments:
                output = self.mode.encode() + b" hash 0\tmanage.py\n"
            else:
                output = b"".join(path.encode() + b"\0" for path in self.manifest.files)
        elif command == "ls-tree":
            if "--name-only" in arguments:
                output = b"".join(path.encode() + b"\0" for path in self.manifest.files)
            else:
                output = self.mode.encode() + b" blob hash\tmanage.py\n"
        elif command == "cat-file":
            assert data is not None
            for expression in data.decode().splitlines():
                relative = expression.partition(":")[2]
                content = module.safe_path(relative).read_bytes()
                if self.corrupt_blob:
                    content += b"wrong"
                output += b"f" * 40 + b" blob " + str(len(content)).encode() + b"\n" + content + b"\n"
        elif command == "diff-tree":
            output = b"".join(path.encode() + b"\0" for path in self.manifest.files)
        elif command in ("switch", "add", "update-index", "commit", "merge"):
            self.mutations.append(command)
            if command == "switch":
                self.branch = arguments[-1]
                if "-c" in arguments:
                    self.candidate = module.BASE
                self.head = self.main_ref if self.branch == "main" else self.candidate or module.BASE
            elif command == "add":
                self.staged = True
            elif command == "commit":
                self.head, self.candidate, self.staged = CANDIDATE, CANDIDATE, False
            elif command == "merge":
                self.head = self.main_ref = self.candidate or module.BASE
        else:
            raise AssertionError("Unexpected simulated Git command: " + repr(arguments))
        if code not in allowed:
            raise RuntimeError("Simulated nonzero Git exit")
        return module.Result(code, output, b"", self.directory / (label + ".out"), self.directory / (label + ".err"))


class RemediationRunnerTests(TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory(prefix="arch09 runner spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        replacement = patch.object(module, "ROOT", self.root)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.manifest = module.Manifest((module.MANIFEST, module.RECEIPT, "manage.py", "source file.py"),
            ("retired.py",), (module.MANIFEST, "manage.py", "source file.py"), ("seed.py",), 111, 224)
        module.write_json(self.root / module.MANIFEST, {
            "base_commit": module.BASE, "files": list(self.manifest.files),
            "deleted_files": list(self.manifest.deleted), "verification_files": list(self.manifest.verification),
            "protected_files": list(self.manifest.protected), "pure_tests": 111, "postgresql_tests": 224,
        })
        (self.root / "manage.py").write_text("print('config')\n", encoding="utf-8")
        (self.root / "source file.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "seed.py").write_text("unrelated user contents\n", encoding="utf-8")

    def browser(self, directory: Path) -> dict[str, object]:
        result: dict[str, object] = {"status": "VERIFIED", "browser_closed": True, "server_stopped": True,
            "browser": {"status": "VERIFIED", "checks": sorted(module.BROWSER_CHECKS),
                        "javascript_errors": [], "external_responses": []}}
        module.write_json(directory / "result.json", result)
        module.write_json(directory / "browser-closed.json", {"browser_closed": True})
        return result

    def receipt(self) -> dict[str, object]:
        original = self.root / ".cache/arch09-remediation" / ("b" * 32)
        original.mkdir(parents=True)
        checks: dict[str, object] = {}
        labels = ("architecture", "pure-tests", "core-types", "django-types", "imports", "ruff",
            "django-check", "migrations", "static-assets", "docker-access", "postgres-start",
            "loopback-binding", "postgres-version", "postgres-image", "postgres-tests", "real-browser")
        for label in labels:
            stdout, stderr = original / (label + ".out"), original / (label + ".err")
            text = "Contracts: 8 kept, 0 broken.\n" if label == "imports" else ""
            stdout.write_text(text, encoding="utf-8")
            stderr.write_text("Ran 111 tests\nOK\n" if label == "pure-tests" else "Ran 224 tests\nOK\n" if label == "postgres-tests" else "", encoding="utf-8")
            checks[label] = {"status": "VERIFIED", "exit_code": 0,
                "stdout": stdout.relative_to(self.root).as_posix(), "stderr": stderr.relative_to(self.root).as_posix()}
        hashes, modes = module.source_hashes(self.manifest)
        result: dict[str, object] = {"status": "VERIFIED", "base_commit": module.BASE, "run_id": "b" * 32,
            "tests": 224, "pure_tests": 111, "skipped": 0, "container_stopped": True,
            "source_hashes": hashes, "source_hash_modes": modes, "deleted_files": list(self.manifest.deleted),
            "protected_hashes": module.protected_hashes(self.manifest), "checks": checks,
            "browser": self.browser(original / "browser")}
        module.write_json(original / "receipt.json", result)
        module.write_json(self.root / module.RECEIPT, result)
        return result

    def simulated(self) -> GitSimulation:
        return GitSimulation(self.root / ("integration-" + str(len(tuple(self.root.glob("integration-*"))))), self.manifest)

    def test_manifest_includes_manage_contents_and_excludes_seed_and_receipt_self_hash(self) -> None:
        self.assertEqual(module.Manifest.load(), self.manifest)
        data = module.read_json(self.root / module.MANIFEST)
        data["verification_files"] = [*self.manifest.verification, module.RECEIPT]
        module.write_json(self.root / module.MANIFEST, data)
        with self.assertRaisesRegex(ValueError, "cannot hash itself"):
            module.Manifest.load()

    def test_manifest_rejects_path_escape_and_protected_file_in_scope(self) -> None:
        with self.assertRaises(ValueError):
            module.safe_path("../outside.py")
        data = module.read_json(self.root / module.MANIFEST)
        data["files"] = [*self.manifest.files, "seed.py"]
        module.write_json(self.root / module.MANIFEST, data)
        with self.assertRaisesRegex(ValueError, "seed.py"):
            module.Manifest.load()

    def test_hash_normalization_and_binary_hashes(self) -> None:
        self.assertEqual(module.normalized_hash(b"\xef\xbb\xbfline\r\n", "text.py"), module.normalized_hash(b"line\n", "text.py"))
        self.assertNotEqual(module.normalized_hash(b"line\r\n", "image.png"), module.normalized_hash(b"line\n", "image.png"))

    def test_native_capture_preserves_stderr_nonzero_and_paths_with_spaces(self) -> None:
        module.self_test(module.Runner(self.root / "native space output"))

    def test_runner_disables_provider_smtp_and_uses_temporary_secret(self) -> None:
        runner = module.Runner(self.root / "environment")
        for key in ("DEEPSEEK_API_KEY", "POLAR_ACCESS_TOKEN", "POLAR_WEBHOOK_SECRET", "POLAR_PRODUCT_ID"):
            self.assertEqual(runner.environment[key], "")
        self.assertEqual(runner.environment["AI_ENABLED"], "0")
        self.assertIn("locmem", runner.environment["EMAIL_BACKEND"])
        self.assertEqual(len(runner.environment["DJANGO_SECRET_KEY"]), 64)

    def test_whitespace_preflight_accepts_exit_one_and_overrides_autocrlf_locally(self) -> None:
        runner = module.Runner(self.root / "whitespace")
        original = runner.git

        def inherited_autocrlf(arguments: list[str], label: str, *, allowed: tuple[int, ...] = (0,), data: bytes | None = None) -> module.Result:
            return original(["-c", "core.autocrlf=true", *arguments], label, allowed=allowed, data=data)

        with patch.object(runner, "git", inherited_autocrlf):
            module.whitespace_preflight(runner, self.manifest)
        self.assertIn("whitespace-preflight", runner.checks)

    def test_whitespace_preflight_rejects_new_untracked_trailing_whitespace(self) -> None:
        (self.root / "source file.py").write_text("value = 1 \n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "[Ww]hitespace"):
            module.whitespace_preflight(module.Runner(self.root / "whitespace-bad"), self.manifest)

    def test_suite_rejects_skips_and_wrong_counts(self) -> None:
        for body in (b"Ran 224 tests\nOK (skipped=1)\n", b"Ran 223 tests\nOK\n"):
            with self.assertRaises(RuntimeError):
                module.assert_suite(module.Result(0, b"", body, self.root, self.root), 224, "PostgreSQL")

    def test_browser_requires_exact_names_javascript_silence_external_response_silence_and_cleanup(self) -> None:
        directory = self.root / "browser"
        good = self.browser(directory)
        self.assertEqual(module.browser_evidence(directory), good)
        browser = module.object_map(good["browser"])
        for key, bad in (("checks", [str(i) for i in range(14)]), ("javascript_errors", ["uncaught"]), ("external_responses", [{"host": "outside"}])):
            original = browser[key]
            browser[key] = bad
            module.write_json(directory / "result.json", good)
            with self.assertRaises(RuntimeError):
                module.browser_evidence(directory)
            browser[key] = original
        good["server_stopped"] = False
        module.write_json(directory / "result.json", good)
        with self.assertRaises(RuntimeError):
            module.browser_evidence(directory)

    def test_resume_rechecks_original_receipt_and_refuses_changed_sources(self) -> None:
        self.receipt()
        runner = self.simulated()
        module.verified_receipt(runner, self.manifest)
        (self.root / "source file.py").write_text("value = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "sources, deletions or protected"):
            module.verified_receipt(runner, self.manifest)
        self.assertFalse(runner.mutations)

    def test_resume_refuses_changed_protected_seed(self) -> None:
        self.receipt()
        (self.root / "seed.py").write_text("changed user contents\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "protected"):
            module.verified_receipt(self.simulated(), self.manifest)

    def test_resume_rechecks_original_native_test_logs(self) -> None:
        self.receipt()
        original = self.root / ".cache/arch09-remediation" / ("b" * 32)
        (original / "postgres-tests.err").write_text("Ran 224 tests\nOK (skipped=1)\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "without skips"):
            module.verified_receipt(self.simulated(), self.manifest)

    def test_new_integration_batches_real_index_and_head_hashes_and_preserves_mode(self) -> None:
        receipt = self.receipt()
        runner = self.simulated()
        output = StringIO()
        with redirect_stdout(output):
            result = module.integrate(runner, self.manifest, receipt, resume=False)
        self.assertIn("integrated in main at " + CANDIDATE, output.getvalue())
        self.assertEqual(result["commit"], CANDIDATE)
        self.assertEqual(result["manage_mode"], "100755")
        self.assertEqual(runner.mutations.count("commit"), 1)
        self.assertEqual(runner.main_ref, CANDIDATE)

    def test_resume_staged_branch_reuses_verified_evidence_without_services(self) -> None:
        self.receipt()
        runner = self.simulated()
        runner.branch, runner.candidate, runner.staged = module.BRANCH, module.BASE, True
        output = StringIO()
        with patch.object(module, "verify", side_effect=AssertionError("Services must not rerun")), redirect_stdout(output):
            result = module.complete(runner, self.manifest, 55440, resume=True)
        self.assertIn("without rerunning services", output.getvalue())
        self.assertIn("integrated in main at " + CANDIDATE, output.getvalue())
        self.assertEqual(result["commit"], CANDIDATE)
        self.assertTrue(result["resumed"])

    def test_resume_after_commit_or_after_main_merge_never_creates_another_commit(self) -> None:
        self.receipt()
        for already_merged in (False, True):
            with self.subTest(already_merged=already_merged):
                runner = self.simulated()
                runner.candidate = CANDIDATE
                if already_merged:
                    runner.head = runner.main_ref = CANDIDATE
                output = StringIO()
                with patch.object(module, "verify", side_effect=AssertionError("Services must not rerun")), redirect_stdout(output):
                    module.complete(runner, self.manifest, 55440, resume=True)
                self.assertIn("without rerunning services", output.getvalue())
                self.assertIn("integrated in main at " + CANDIDATE, output.getvalue())
                self.assertNotIn("commit", runner.mutations)

    def test_resume_rejects_candidate_blob_corruption_before_merging(self) -> None:
        receipt = self.receipt()
        runner = self.simulated()
        runner.candidate, runner.corrupt_blob = CANDIDATE, True
        with self.assertRaisesRegex(RuntimeError, "differs from reviewed bytes"):
            module.integrate(runner, self.manifest, receipt, resume=True)
        self.assertNotIn("merge", runner.mutations)

    def test_resume_rejects_independently_advanced_main(self) -> None:
        receipt = self.receipt()
        runner = self.simulated()
        runner.candidate, runner.main_ref = CANDIDATE, "c" * 40
        with self.assertRaisesRegex(RuntimeError, "main advanced"):
            module.integrate(runner, self.manifest, receipt, resume=True)
        self.assertFalse(runner.mutations)

    def test_changed_or_untracked_source_outside_manifest_is_rejected_before_services(self) -> None:
        runner = self.simulated()
        result = module.Result(0, b"unreviewed.py\0", b"", self.root, self.root)
        with patch.object(runner, "git", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "outside the reviewed/protected scope"):
                module.assert_candidate_scope(runner, self.manifest)
        self.assertFalse(runner.mutations)

    def test_non_executable_manage_mode_is_rejected_before_merging(self) -> None:
        receipt = self.receipt()
        runner = self.simulated()
        runner.candidate, runner.mode = CANDIDATE, "100644"
        with self.assertRaisesRegex(RuntimeError, "mode must remain 100755"):
            module.integrate(runner, self.manifest, receipt, resume=True)
        self.assertFalse(runner.mutations)
