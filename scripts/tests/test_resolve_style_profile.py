"""Tests for scripts/resolve_style_profile.py.

Run from the plugin root:
    python -m unittest scripts.tests.test_resolve_style_profile

Verifies:
- Name validation (good names, bad names with spaces / specials / leading dashes).
- init_profile creates the profile dir, meta.json stub, sources/ subdir.
- list_profiles returns [] when dir is empty, and well-formed records otherwise.
- set_default / get_default / clear_default round-trips.
- delete_profile clears default if it was the default.
- validate_profile catches missing files and inconsistent has_template/template.md.
- resolve_paths returns template_path=null when template.md is absent.
- CLI subcommand surface (subprocess) works end-to-end.

Tests use a tempdir + LEGAL_MEMO_PROFILES_HOME env var so they never touch the
real ~/.claude/plugin-data/ directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "scripts" / "resolve_style_profile.py"

sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import resolve_style_profile as rsp  # noqa: E402


class _TempHomeMixin:
    """Mixin: set LEGAL_MEMO_PROFILES_HOME to a fresh tempdir per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_env = os.environ.get("LEGAL_MEMO_PROFILES_HOME")
        os.environ["LEGAL_MEMO_PROFILES_HOME"] = self._tmp.name
        self.home = Path(self._tmp.name)

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop("LEGAL_MEMO_PROFILES_HOME", None)
        else:
            os.environ["LEGAL_MEMO_PROFILES_HOME"] = self._prev_env
        self._tmp.cleanup()


class NameValidationTests(unittest.TestCase):
    def test_valid_names(self):
        for name in ("a", "my-firm", "firm_v2", "abc123", "x" * 64):
            self.assertIsNone(rsp.validate_name(name), msg=f"name={name!r}")

    def test_invalid_names(self):
        for name, _label in [
            ("", "empty"),
            ("My-Firm", "uppercase"),
            ("my firm", "space"),
            ("-leading-dash", "leading dash"),
            ("_leading-underscore", "leading underscore"),
            ("a/b", "slash"),
            ("a.b", "dot"),
            ("x" * 65, "too long"),
        ]:
            self.assertIsNotNone(
                rsp.validate_name(name), msg=f"expected invalid: {name!r}"
            )


class ProfileLifecycleTests(_TempHomeMixin, unittest.TestCase):
    def test_init_creates_dir_and_meta(self):
        files = rsp.init_profile("test-profile", "examples", "brief")
        self.assertTrue(files["dir"].is_dir())
        self.assertTrue(files["meta"].is_file())
        self.assertTrue(files["sources_dir"].is_dir())
        # template.md and prose-style.md not yet written by init
        self.assertFalse(files["template"].is_file())
        self.assertFalse(files["prose_style"].is_file())

        meta = json.loads(files["meta"].read_text(encoding="utf-8"))
        self.assertEqual(meta["name"], "test-profile")
        self.assertEqual(meta["input_type"], "examples")
        self.assertEqual(meta["mode_binding"], "brief")
        self.assertFalse(meta["has_template"])
        self.assertFalse(meta["rules_provided"])

    def test_init_rejects_bad_name(self):
        with self.assertRaises(ValueError):
            rsp.init_profile("Bad Name", "examples", "brief")

    def test_init_rejects_bad_input_type(self):
        with self.assertRaises(ValueError):
            rsp.init_profile("ok", "bogus", "brief")

    def test_init_rejects_bad_mode(self):
        with self.assertRaises(ValueError):
            rsp.init_profile("ok", "examples", "bogus")

    def test_list_empty(self):
        self.assertEqual(rsp.list_profiles(), [])

    def test_list_with_profiles(self):
        rsp.init_profile("alpha", "examples", "brief")
        rsp.init_profile("beta", "rules", "full", rules_provided=True)
        records = rsp.list_profiles()
        names = sorted(r["name"] for r in records)
        self.assertEqual(names, ["alpha", "beta"])
        for r in records:
            self.assertIn("meta", r)
            self.assertIn("valid", r)
            self.assertIn("is_default", r)
            self.assertFalse(r["is_default"])  # no default set


class DefaultTests(_TempHomeMixin, unittest.TestCase):
    def test_default_roundtrip(self):
        rsp.init_profile("alpha", "examples", "brief")
        self.assertIsNone(rsp.get_default())
        rsp.set_default("alpha")
        self.assertEqual(rsp.get_default(), "alpha")
        rsp.clear_default()
        self.assertIsNone(rsp.get_default())

    def test_set_default_rejects_unknown(self):
        with self.assertRaises(FileNotFoundError):
            rsp.set_default("does-not-exist")

    def test_delete_clears_default_when_was_default(self):
        rsp.init_profile("alpha", "examples", "brief")
        rsp.init_profile("beta", "rules", "full")
        rsp.set_default("alpha")
        rsp.delete_profile("alpha")
        self.assertIsNone(rsp.get_default())
        # beta still present, not affected
        names = [r["name"] for r in rsp.list_profiles()]
        self.assertEqual(names, ["beta"])

    def test_delete_other_keeps_default(self):
        rsp.init_profile("alpha", "examples", "brief")
        rsp.init_profile("beta", "rules", "full")
        rsp.set_default("alpha")
        rsp.delete_profile("beta")
        self.assertEqual(rsp.get_default(), "alpha")


class ValidateProfileTests(_TempHomeMixin, unittest.TestCase):
    def test_init_then_missing_prose_style_is_invalid(self):
        # init_profile writes meta.json but not prose-style.md
        rsp.init_profile("p", "examples", "brief")
        valid, errors = rsp.validate_profile("p")
        self.assertFalse(valid)
        joined = "\n".join(errors)
        self.assertIn("prose-style.md", joined)

    def test_complete_profile_is_valid(self):
        files = rsp.init_profile("p", "examples", "brief")
        files["prose_style"].write_text("# stub\n", encoding="utf-8")
        valid, errors = rsp.validate_profile("p")
        self.assertTrue(valid, msg=f"errors={errors}")

    def test_template_inconsistency_is_invalid(self):
        files = rsp.init_profile("p", "examples", "brief")
        files["prose_style"].write_text("# stub\n", encoding="utf-8")
        # write template.md but meta still has has_template=false
        files["template"].write_text("# template stub\n", encoding="utf-8")
        valid, errors = rsp.validate_profile("p")
        self.assertFalse(valid)
        self.assertTrue(
            any("template.md exists but" in e for e in errors), msg=errors
        )

    def test_missing_meta_is_invalid(self):
        files = rsp.init_profile("p", "examples", "brief")
        files["prose_style"].write_text("# stub\n", encoding="utf-8")
        files["meta"].unlink()
        valid, errors = rsp.validate_profile("p")
        self.assertFalse(valid)
        self.assertTrue(any("meta.json" in e for e in errors), msg=errors)

    def test_nonexistent_profile_is_invalid(self):
        valid, errors = rsp.validate_profile("ghost")
        self.assertFalse(valid)
        self.assertTrue(any("does not exist" in e for e in errors), msg=errors)


class ResolvePathsTests(_TempHomeMixin, unittest.TestCase):
    def test_resolves_with_template(self):
        files = rsp.init_profile("p", "examples", "brief")
        files["prose_style"].write_text("# stub\n", encoding="utf-8")
        files["template"].write_text("# template\n", encoding="utf-8")
        # update meta.has_template
        meta = json.loads(files["meta"].read_text(encoding="utf-8"))
        meta["has_template"] = True
        files["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")

        paths = rsp.resolve_paths("p")
        self.assertEqual(paths["style_profile"], "p")
        self.assertTrue(paths["style_profile_path"].endswith("/p"))
        self.assertTrue(paths["prose_style_path"].endswith("/p/prose-style.md"))
        self.assertTrue(paths["template_path"].endswith("/p/template.md"))

    def test_resolves_without_template(self):
        files = rsp.init_profile("p", "rules", "brief", rules_provided=True)
        files["prose_style"].write_text("# stub\n", encoding="utf-8")
        paths = rsp.resolve_paths("p")
        self.assertIsNone(paths["template_path"])
        self.assertTrue(paths["prose_style_path"].endswith("/p/prose-style.md"))

    def test_paths_use_posix_separator(self):
        files = rsp.init_profile("p", "examples", "brief")
        files["prose_style"].write_text("# stub\n", encoding="utf-8")
        paths = rsp.resolve_paths("p")
        for key in ("style_profile_path", "prose_style_path"):
            self.assertNotIn("\\", paths[key], msg=f"{key}={paths[key]}")


class WriteMetaTests(_TempHomeMixin, unittest.TestCase):
    def test_write_meta_roundtrip(self):
        files = rsp.init_profile("p", "examples", "brief")
        new_meta = {
            "name": "p",
            "created_at": "2026-05-25T12:00:00Z",
            "input_type": "examples",
            "examples_count": 3,
            "rules_provided": False,
            "mode_binding": "brief",
            "has_template": True,
            "jurisdictions": ["EU"],
            "language": "en",
            "confidence": 0.85,
            "summary": "From 3 EU GDPR memos.",
        }
        rsp.write_meta("p", json.dumps(new_meta))
        on_disk = json.loads(files["meta"].read_text(encoding="utf-8"))
        self.assertEqual(on_disk["examples_count"], 3)
        self.assertTrue(on_disk["has_template"])

    def test_write_meta_rejects_missing_keys(self):
        rsp.init_profile("p", "examples", "brief")
        with self.assertRaises(ValueError):
            rsp.write_meta("p", json.dumps({"name": "p"}))

    def test_write_meta_rejects_invalid_json(self):
        rsp.init_profile("p", "examples", "brief")
        with self.assertRaises(ValueError):
            rsp.write_meta("p", "{not json}")


class CliTests(_TempHomeMixin, unittest.TestCase):
    def _run(self, *args):
        env = dict(os.environ)
        env["LEGAL_MEMO_PROFILES_HOME"] = str(self.home)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    def test_list_empty(self):
        code, out, err = self._run("list")
        self.assertEqual(code, 0, msg=err)
        self.assertEqual(json.loads(out), [])

    def test_validate_name_good(self):
        code, _, _ = self._run("validate-name", "my-firm")
        self.assertEqual(code, 0)

    def test_validate_name_bad(self):
        code, _, err = self._run("validate-name", "Bad Name")
        self.assertEqual(code, 2)
        self.assertIn("must match", err)

    def test_init_then_list(self):
        code, _, err = self._run("init-profile", "alpha", "examples", "brief")
        self.assertEqual(code, 0, msg=err)
        code, out, _ = self._run("list")
        self.assertEqual(code, 0)
        records = json.loads(out)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "alpha")
        self.assertEqual(records[0]["meta"]["input_type"], "examples")

    def test_set_default_unknown_fails(self):
        code, _, err = self._run("set-default", "ghost")
        self.assertEqual(code, 2)
        self.assertIn("profile not found", err)

    def test_resolve_paths_cli(self):
        self._run("init-profile", "alpha", "examples", "brief")
        # Need prose-style.md to exist for a "complete" profile, but
        # resolve-paths doesn't require it — it only checks profile dir exists.
        # Write a stub so the path is realistic.
        (self.home / "profiles" / "alpha" / "prose-style.md").write_text("# stub\n")
        code, out, err = self._run("resolve-paths", "alpha")
        self.assertEqual(code, 0, msg=err)
        paths = json.loads(out)
        self.assertEqual(paths["style_profile"], "alpha")
        self.assertIsNone(paths["template_path"])


if __name__ == "__main__":
    unittest.main()
