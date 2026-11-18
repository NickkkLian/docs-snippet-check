#!/usr/bin/env python3
"""Run the ```python blocks in Markdown docs and fail on the first broken block per page.

    python3 check_docs.py [PATH ...]      # default: docs

Backtick and `~~~` fences are both read. Each page runs top to bottom in one fresh namespace, so a block can use names
defined by earlier blocks on the same page. A block whose first line starts with
`>>>`, and every `pycon` block, is run as an interactive session and its output is
compared with the text under each prompt. `<!-- snippet: skip -->` on the line
before a fence skips it. The last line says how many blocks of other languages
were not run.
Exit status: 0 all blocks passed, 1 a block failed, 2 nothing to run or bad path.
"""
import argparse
import contextlib
import doctest
import io
import os
import re
import sys
import traceback
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PY_LANGS = {"python", "py", "python3"}
SESSION_LANGS = {"pycon"}
FENCE_OPEN = re.compile(r"^(?P<indent> *)(?:(?P<ticks>`{3,})(?P<info>[^`]*)|(?P<tildes>~{3,})(?P<tinfo>.*))$")
SKIP_MARK = re.compile(r"^\s*<!--\s*snippet:\s*skip\s*-->\s*$")
DOCTEST_FLAGS = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE


@dataclass
class Block:
    line: int  # 1-based line of the first line of code
    code: str
    skip: bool
    session: bool = False  # run as a >>> session


class Failure(Exception):
    def __init__(self, line, message, detail=""):
        super().__init__(message)
        self.line, self.message, self.detail = line, message, detail


def language(info):
    """First word of a fence's info string, lower-cased, without Pandoc/attribute braces: `{.Python}` -> `python`."""
    words = info.split()
    return words[0].lstrip("{.").rstrip("}").lower() if words else ""


def find_blocks(path):
    """Return (python blocks, Counter of other-language fenced blocks); raise Failure on an unclosed fence."""
    blocks, others, fence, prev = [], Counter(), None, ""
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if fence is None:
            m = FENCE_OPEN.match(raw)
            if m:
                lang = language(m["info"] if m["ticks"] else m["tinfo"])
                mark = m["ticks"] or m["tildes"]
                fence = {"open": n, "char": mark[0], "ticks": len(mark), "indent": len(m["indent"]), "lang": lang,
                         "python": lang in PY_LANGS or lang in SESSION_LANGS,
                         "skip": bool(SKIP_MARK.match(prev)), "body": []}
            elif raw.strip():
                prev = raw
        elif re.fullmatch(rf" *{re.escape(fence['char'])}{{{fence['ticks']},}} *", raw):
            if fence["python"]:
                code = "\n".join(fence["body"]) + "\n"
                blocks.append(Block(fence["open"] + 1, code, fence["skip"],
                                    fence["lang"] in SESSION_LANGS or code.lstrip().startswith(">>>")))
            else:
                others[fence["lang"] or "no language"] += 1
            fence, prev = None, ""
        else:
            fence["body"].append(raw[min(fence["indent"], len(raw) - len(raw.lstrip(" "))):])
    if fence is not None:
        raise Failure(fence["open"], "code fence is never closed")
    return blocks, others


def last_line(exc):
    return traceback.format_exception_only(type(exc), exc)[-1].strip()


def run_code(path, block, ns):
    # Pad with blank lines so tracebacks carry the line numbers of the Markdown file.
    try:
        code = compile("\n" * (block.line - 1) + block.code, str(path), "exec")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, ns)
    except (Exception, SystemExit) as exc:
        line = block.line
        if isinstance(exc, SyntaxError) and exc.lineno:
            line = exc.lineno
        for frame, lineno in traceback.walk_tb(exc.__traceback__):
            if frame.f_code.co_filename == str(path):
                line = lineno
        raise Failure(line, last_line(exc)) from None


def run_session(path, block, ns):
    try:
        examples = doctest.DocTestParser().get_examples(block.code)
    except ValueError as exc:
        raise Failure(block.line, f"bad >>> session: {exc}") from None
    if not examples:
        raise Failure(block.line, "session block has no >>> prompts, nothing was checked")
    checker = doctest.OutputChecker()
    for ex in examples:
        line = block.line + ex.lineno
        flags = DOCTEST_FLAGS
        for flag, on in ex.options.items():
            flags = flags | flag if on else flags & ~flag
        if flags & doctest.SKIP:
            continue
        out, error = io.StringIO(), None
        try:
            with contextlib.redirect_stdout(out):
                exec(compile(ex.source, str(path), "single"), ns)
        except (Exception, SystemExit) as exc:
            error = exc
        if error is not None:
            if ex.exc_msg is None:
                raise Failure(line, last_line(error))
            got = traceback.format_exception_only(type(error), error)[-1]
            if not checker.check_output(ex.exc_msg, got, flags):
                raise Failure(line, "wrong exception", f"expected: {ex.exc_msg.strip()}\n     got: {got.strip()}")
        elif ex.exc_msg is not None:
            raise Failure(line, "expected an exception, none was raised", f"expected: {ex.exc_msg.strip()}")
        elif not checker.check_output(ex.want, out.getvalue(), flags):
            raise Failure(line, "output differs", f"expected: {ex.want.strip() or '(nothing)'}\n     got: {out.getvalue().strip() or '(nothing)'}")


@dataclass
class Page:
    path: Path
    found: int = 0  # python blocks in the file
    ran: int = 0
    skipped: int = 0  # marked skip, before or after a failure
    not_run: int = 0  # not marked skip, after the page's first failure
    failure: Failure = None
    others: Counter = field(default_factory=Counter)  # fenced blocks of other languages, not run


def run_page(path):
    page = Page(path)
    try:
        blocks, page.others = find_blocks(path)
        page.found = len(blocks)
        ns = {"__name__": "__docs__"}
        for block in blocks:
            if block.skip:
                page.skipped += 1
            elif page.failure:
                page.not_run += 1
            else:
                try:
                    (run_session if block.session else run_code)(path, block, ns)
                    page.ran += 1
                except Failure as failure:
                    page.failure = failure
    except Failure as failure:  # an unclosed fence: nothing on the page was found
        page.failure = failure
    return page


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def summary(pages):
    failed = sum(1 for p in pages if p.failure)
    blocks = f"{plural(sum(p.ran for p in pages), 'block')} passed, {sum(p.skipped for p in pages)} skipped, {failed} failed"
    after = sum(p.not_run for p in pages)
    return (f"{plural(len(pages), 'page')}: {len(pages) - failed} passed, {failed} failed; "
            f"{blocks}" + (f", {after} not run" if after else ""))


def collect(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(p.rglob("*.md"))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"{p} does not exist")
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", default=["docs"], help="Markdown files or folders (default: docs)")
    args = ap.parse_args(argv)
    try:
        pages = [run_page(f) for f in collect(args.paths)]
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not any(p.found for p in pages):
        print(f"error: no python blocks found in {', '.join(args.paths)}", file=sys.stderr)
        return 2
    shown = [p for p in pages if p.found or p.failure]
    for p in shown:
        note = f"{p.ran} passed" + (f", {p.skipped} skipped" if p.skipped else "")
        if p.failure is None:
            print(f"ok    {p.path}  ({note})")
        else:
            print(f"FAIL  {p.path}  ({p.ran} passed before the failure"
                  + (f", {p.skipped} skipped" if p.skipped else "")
                  + (f", {p.not_run} after it not run" if p.not_run else "") + ")")
    failed = [p for p in pages if p.failure]
    print()
    for p in failed:
        f = p.failure
        print(f"{p.path}:{f.line}: {f.message}")
        for extra in filter(None, f.detail.split("\n")):
            print(f"    {extra}")
        if os.environ.get("GITHUB_ACTIONS"):
            msg = f"{f.message} {f.detail}".replace("\n", " ").strip()
            print(f"::error file={p.path},line={f.line}::{msg}")
    print(summary(shown))
    others = sum((p.others for p in pages), Counter())
    if others:
        langs = ", ".join(f"{name} {n}" for name, n in sorted(others.items(), key=lambda kv: (-kv[1], kv[0])))
        print(f"not run: {plural(sum(others.values()), 'fenced block')} in other languages ({langs})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
