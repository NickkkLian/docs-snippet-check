"""Self-test: the runner must pass on the shipped docs and fail, with the right file:line, on broken copies.

    python3 -m unittest discover -s tests -v
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "check_docs.py"


class DocsCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.docs = self.tmp / "docs"
        shutil.copytree(ROOT / "docs", self.docs)

    def run_runner(self, *args, env=None):
        full_env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
        full_env.update(env or {})
        return subprocess.run([sys.executable, str(RUNNER), *(args or [str(self.docs)])],
                              capture_output=True, text=True, cwd=self.tmp, env=full_env)

    def edit(self, page, old, new):
        """Replace `old` (must occur once) in a copied page; return the 1-based line where it starts."""
        path = self.docs / page
        text = path.read_text()
        self.assertEqual(text.count(old), 1, f"{old!r} must occur exactly once in {page}")
        path.write_text(text.replace(old, new))
        return text[: text.index(old)].count("\n") + 1


class RunnerTest(DocsCopy):
    def test_control_passes(self):
        r = self.run_runner()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 pages: 3 passed, 0 failed; 9 blocks passed, 1 skipped, 0 failed", r.stdout)

    def test_broken_code_names_file_and_line(self):
        line = self.edit("guide/slugs.md", "textkit.slugify(title)\nprint(slug)", "textkit.slugfy(title)\nprint(slug)")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"guide/slugs.md:{line}: AttributeError", r.stdout)
        self.assertIn("FAIL", r.stdout)

    def test_error_inside_multiline_block_reports_the_failing_line_not_the_fence(self):
        line = self.edit("guide/counting.md", "assert total == textkit.word_count(review)",
                         "assert total == textkit.word_count(review) + 1")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"guide/counting.md:{line}: AssertionError", r.stdout)

    def test_later_block_uses_earlier_block(self):
        self.edit("index.md", "text = \"the cat sat on the mat. The cat left.\"\n", "")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"index\.md:\d+: NameError.*'text'")

    def test_output_mismatch_fails_with_expected_and_got(self):
        line = self.edit("index.md", "[('the', 3), ('cat', 2)]", "[('the', 4), ('cat', 2)]")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"index.md:{line - 1}: output differs", r.stdout)
        self.assertIn("expected: [('the', 4), ('cat', 2)]", r.stdout)
        self.assertIn("got: [('the', 3), ('cat', 2)]", r.stdout)

    def test_expected_exception_is_checked(self):
        self.edit("guide/slugs.md", "TypeError: slugify() expects str, got int", "TypeError: wrong text")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn("wrong exception", r.stdout)

    def test_skip_marker_skips_and_its_absence_does_not(self):
        broken = "```python\nraise RuntimeError('boom')\n```\n"
        page = self.docs / "extra.md"
        page.write_text("# Extra\n\n<!-- snippet: skip -->\n" + broken)
        r = self.run_runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        page.write_text("# Extra\n\n" + broken)
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn("extra.md:4: RuntimeError: boom", r.stdout)

    def test_skip_marker_applies_to_one_block_only(self):
        page = self.docs / "extra.md"
        page.write_text("<!-- snippet: skip -->\n```python\nraise RuntimeError('a')\n```\n\n"
                        "```python\nraise RuntimeError('b')\n```\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn("extra.md:7: RuntimeError: b", r.stdout)

    def test_other_languages_are_ignored(self):
        (self.docs / "extra.md").write_text("```bash\nexit 1\n```\n\n```text\nraise nothing\n```\n")
        self.assertEqual(self.run_runner().returncode, 0)

    def test_unclosed_fence_fails(self):
        (self.docs / "extra.md").write_text("intro\n\n```python\nprint(1)\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn("extra.md:3: code fence is never closed", r.stdout)

    def test_no_python_blocks_is_an_error_not_a_pass(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        (empty / "a.md").write_text("# no code here\n")
        r = self.run_runner(str(empty))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no python blocks", r.stderr)

    def test_missing_path_is_an_error(self):
        self.assertEqual(self.run_runner(str(self.tmp / "nope")).returncode, 2)

    def test_github_annotation(self):
        line = self.edit("guide/slugs.md", "textkit.slugify(title)\nprint(slug)", "textkit.slugfy(title)\nprint(slug)")
        r = self.run_runner(env={"GITHUB_ACTIONS": "true"})
        self.assertIn(f"::error file={self.docs}/guide/slugs.md,line={line}::", r.stdout)

    def test_pycon_block_is_run_as_a_session(self):
        page = self.docs / "extra.md"
        page.write_text("```pycon\n>>> 1 + 1\n3\n```\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("extra.md:2: output differs", r.stdout)
        page.write_text("```pycon\n>>> 1 + 1\n2\n```\n")
        self.assertEqual(self.run_runner().returncode, 0)

    def test_pycon_block_without_prompts_fails_instead_of_passing(self):
        (self.docs / "extra.md").write_text("```pycon\n1 + 1\n3\n```\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertIn("extra.md:2: session block has no >>> prompts", r.stdout)

    def test_python_info_string_variants_are_run(self):
        for info in ("Python", "PY", "python3", "{.python}", "{.python .numberLines}", "python title=\"a.py\""):
            with self.subTest(info=info):
                (self.docs / "extra.md").write_text(f"```{info}\nraise RuntimeError('boom')\n```\n")
                r = self.run_runner()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("extra.md:2: RuntimeError: boom", r.stdout)

    def test_other_languages_are_counted_not_silently_skipped(self):
        (self.docs / "extra.md").write_text("```bash\nexit 1\n```\n\n```text\nx\n```\n\n```\nplain\n```\n\n```bash\nls\n```\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("3 pages: 3 passed", r.stdout)  # a page with no Python block is not a checked page
        # docs/ already holds one bash block: 5 in total
        self.assertEqual(r.stdout.splitlines()[-1],
                         "not run: 5 fenced blocks in other languages (bash 3, no language 1, text 1)")

    def test_tilde_fences_are_run_or_counted(self):
        page = self.docs / "extra.md"
        for info in ("python", "Python", "pycon"):
            with self.subTest(info=info):
                body = "raise RuntimeError('boom')" if info != "pycon" else ">>> 1 + 1\n3"
                page.write_text(f"~~~{info}\n{body}\n~~~\n")
                r = self.run_runner()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("extra.md:2:", r.stdout)
        page.write_text("~~~bash\nls\n~~~\n\n~~~\nplain\n~~~\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1],
                         "not run: 3 fenced blocks in other languages (bash 2, no language 1)")

    def test_tilde_fence_closes_only_on_tildes_and_can_hold_backticks(self):
        page = self.docs / "extra.md"
        page.write_text('~~~python\nx = """\n```\n"""\nassert x == "\\n```\\n"\n~~~\n\n'
                        "```python\nraise RuntimeError('after')\n```\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("extra.md:9: RuntimeError: after", r.stdout)

    def test_skip_marked_block_after_a_failure_counts_as_skipped_not_not_run(self):
        (self.docs / "extra.md").write_text(
            "```python\nraise RuntimeError('boom')\n```\n\n"
            "<!-- snippet: skip -->\n```python\nprint('needs a file')\n```\n\n"
            "```python\nprint('never reached')\n```\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("extra.md  (0 passed before the failure, 1 skipped, 1 after it not run)", r.stdout)
        summary = [l for l in r.stdout.splitlines() if " pages: " in l][0]
        # docs/ has 9 passing blocks and 1 skip; the page adds 1 skip and 1 not run
        self.assertEqual(summary, "4 pages: 3 passed, 1 failed; 9 blocks passed, 2 skipped, 1 failed, 1 not run")

    def test_summary_counts_pages_and_blocks_separately(self):
        self.edit("guide/slugs.md", "textkit.slugify(title)\nprint(slug)", "textkit.slugfy(title)\nprint(slug)")
        r = self.run_runner()
        summary = [l for l in r.stdout.splitlines() if " pages: " in l][0]
        self.assertRegex(summary, r"^3 pages: 2 passed, 1 failed; 5 blocks passed, 1 skipped, 1 failed, \d+ not run$")

    def test_summary_uses_singular(self):
        one = self.tmp / "one"
        one.mkdir()
        (one / "a.md").write_text("```python\nprint(1)\n```\n")
        r = self.run_runner(str(one))
        self.assertIn("1 page: 1 passed, 0 failed; 1 block passed, 0 skipped, 0 failed", r.stdout)
        self.assertNotIn("1 pages", r.stdout)
        self.assertNotIn("1 blocks", r.stdout)


if __name__ == "__main__":
    unittest.main()
