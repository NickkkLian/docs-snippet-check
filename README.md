# docs-snippet-check

Runs the Python blocks in your Markdown docs as tests and fails the build, with `file.md:LINE`, when one breaks.
Python standard library only; copy `check_docs.py` into your repo.

After a renamed function (`slugfy`) in `docs/guide/slugs.md` and a wrong expected output in `docs/index.md`:

```
$ python3 check_docs.py docs
ok    docs/guide/counting.md  (3 passed, 1 skipped)
FAIL  docs/guide/slugs.md  (0 passed before the failure, 3 after it not run)
FAIL  docs/index.md  (1 passed before the failure)

docs/guide/slugs.md:10: AttributeError: module 'textkit' has no attribute 'slugfy'. Did you mean: 'slugify'?
docs/index.md:26: output differs
    expected: [('the', 4), ('cat', 2)]
         got: [('the', 3), ('cat', 2)]
3 pages: 1 passed, 2 failed; 4 blocks passed, 1 skipped, 2 failed, 3 not run
not run: 1 fenced block in other languages (bash 1)
$ echo $?
1
```

Quick start: copy `check_docs.py` into your repo and run `python3 check_docs.py docs`.

The repo is a working example: `textkit/` is a three-function package, `docs/` documents it, and
`.github/workflows/docs.yml` runs the check and its self-test on every push and pull request.

## What it does

- Finds fenced Python blocks, in backtick or `~~~` fences (info string `python`, `py`, `python3`, `{.python}` or `pycon`, any case) in every `*.md` under the paths you give (default `docs`).
- Runs the blocks of one page top to bottom in one shared namespace, so a block can use names defined above it.
  Pages do not share names.
- A block whose first line starts with `>>>`, and every `pycon` block, runs as an interactive session (a `pycon` block with no `>>>` prompt fails). Each statement's printed output
  is compared with the text under it (`...` matches anything; whitespace differences are ignored). An expected
  traceback is checked by its last line. `# doctest: +SKIP` works per statement.
- Stops a page at its first failing block, because later blocks usually depend on it, and keeps going with the other pages.
- Exits 0 when everything passes, 1 when a block fails, 2 when a path is missing or no Python blocks were found
  (an empty docs folder is not a pass).
- Under GitHub Actions it also prints `::error file=...,line=...::` annotations, which GitHub shows on the pull request.

## Output

Passing:

```
ok    docs/guide/counting.md  (3 passed, 1 skipped)
ok    docs/guide/slugs.md  (4 passed)
ok    docs/index.md  (2 passed)

3 pages: 3 passed, 0 failed; 9 blocks passed, 1 skipped, 0 failed
not run: 1 fenced block in other languages (bash 1)
```

The last line counts the fenced blocks of other languages (`bash`, `text`, no language, ...), which are never run.

The reported line is the line of the Markdown file that failed, not the start of the block.

## Skip a block

Put `<!-- snippet: skip -->` on the line directly before the opening fence. It skips that one block.

````
<!-- snippet: skip -->
```python
open("reviews.txt")  # needs a file that is not in the docs
```
````

## Use it on your own docs

Copy `check_docs.py` into your repo, make your package importable from the folder that holds the script
(that folder is on `sys.path`), and run `python3 check_docs.py docs`.
Copy `.github/workflows/docs.yml` for the CI job.

## Tests

```
python3 -m unittest discover -s tests -v
```

The self-test copies `docs/` to a temp folder, breaks it in several ways, and checks that the runner exits non-zero
and names the right file and line. It covers `~~~` fences, a skip-marked block after a failure, `pycon` blocks, `Python`/`py`/`{.python}` info strings, the count of blocks not run, the summary wording, a bad call, a failing line inside a multi-line block, a name that an earlier
block should have defined, an output mismatch, a wrong expected exception, the skip marker (with and without it), an unclosed
fence, and an empty docs folder. An unmodified copy must pass.

## Limits

- Python blocks only; other languages are counted in the last output line, not run. A fence's info string is not parsed beyond the language name.
- A `# 9` comment after a statement is not checked; use a `>>>` session when the output matters.
- Output of plain blocks is discarded. Blocks run in the runner's own process: no timeout, no isolation
  from the file system, and a block that changes `sys.path` or global state affects the blocks after it.
- There is no fixture or setup mechanism.
- Blocks are executed, so run it only on docs you trust.

## Alternatives

[Sybil](https://pypi.org/project/sybil/) (10.1.0), [pytest-markdown-docs](https://pypi.org/project/pytest-markdown-docs/), [mktestdocs](https://pypi.org/project/mktestdocs/)
and [phmdoctest](https://pypi.org/project/phmdoctest/) run Markdown code blocks under pytest (phmdoctest by generating a pytest file),
and `python -m doctest docs/*.md` runs `>>>` sessions only.
Sybil is the richer tool: it plugs into pytest and the other main Python test runners and also checks examples in code, not only in Markdown.
This one has no dependencies and prints GitHub `::error` annotations without a plugin.
Use Sybil or the pytest plugins when you already use pytest and want fixtures, setup code or `capsys` assertions;
use this when you want one command and `file.md:LINE` annotations on the pull request.

## Licence

MIT, see [LICENSE](LICENSE).
