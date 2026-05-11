# Creal for Python

Creal for Python extends
[Hypothesmith](https://github.com/Zac-HD/hypothesmith) with real-world donor
snippet injection.  The main experiment compares normal Hypothesmith generation
against an injected variant where each generated host program is combined with a
snippet from a donor corpus.

The intended API extends Hypothesmith's existing grammar generator:

```python
import ast

from hypothesis import given

import hypothesmith


@given(hypothesmith.from_grammar(inject_realworld=True))
def test_ast_parse_unparse_roundtrip(source):
    tree1 = ast.parse(source)
    new_source = ast.unparse(tree1)
    tree2 = ast.parse(new_source)
    assert ast.dump(tree1) == ast.dump(tree2)
```

## Project Structure

```text
CS374_Team7/
├── vendor/
│   └── hypothesmith/          # Git submodule with our patched Hypothesmith
├── src/
│   ├── execute_baseline.py    # Evaluate hypothesmith.from_grammar()
│   ├── execute_proposed.py    # Evaluate hypothesmith.from_grammar(inject_realworld=True)
│   ├── evaluation.py          # Shared on-the-fly evaluation harness
│   ├── oracles.py             # AST, tokenize, and Black oracles
│   └── targets.py             # Wrappers around target tools
├── directory/
│   └── base_programs/
│       └── donor_corpus/
│           └── filtered/      # Current .py donor snippets, ignored by Git
├── results/                   # Evaluation reports, ignored by Git
└── requirements.txt
```

## Setup

```bash
git clone --recurse-submodules <repo-url>
cd CS374_Team7
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If the repo was cloned without submodules:

```bash
git submodule update --init --recursive
```

## Run Evaluations

Baseline Hypothesmith generation:

```bash
python3 src/execute_baseline.py --examples 100 --oracle ast
```

Proposed donor-injected generation:

```bash
python3 src/execute_proposed.py --examples 100 --oracle ast
```

Choose the target oracle with `--oracle`:

```bash
python3 src/execute_baseline.py --examples 100 --oracle ast
python3 src/execute_proposed.py --examples 100 --oracle black
```

Log every generated source file and its result:

```bash
python3 src/execute_baseline.py \
  --examples 100 \
  --oracle ast \
  --log-generated
```

Use a different donor snippet directory:

```bash
python3 src/execute_proposed.py \
  --examples 100 \
  --oracle ast \
  --donor-dir directory/base_programs/donor_corpus/filtered
```

The evaluation draws examples on the fly with Hypothesis and runs one target per
command.  Summaries and failing inputs are written under target-specific
directories such as `results/baseline/ast/` and `results/proposed/black/`.
Generated programs are not saved by default; pass `--log-generated` to write
them under `generated/` and record pass/failure status in
`generated_results.tsv`.

## Patched Hypothesmith API

The submodule adds:

```python
hypothesmith.from_grammar(
    start="file_input",
    *,
    auto_target=True,
    inject_realworld=False,
    donor_dir=None,
    injection_strategy="append",
)
```

When `inject_realworld=True`, donor snippets are loaded from `donor_dir`, or from
`directory/base_programs/donor_corpus/filtered` by default.  The first supported
injection strategies are `append` and `prepend`.  Injection is supported for
`start="file_input"`, because the donor snippets are module-level Python
fragments.

## Work In Progress

- Injection strategy: improve beyond basic `append` / `prepend` in
  `vendor/hypothesmith/src/hypothesmith/injection.py`; the `from_grammar()` hook
  is in `vendor/hypothesmith/src/hypothesmith/syntactic.py`.
- Bug and coverage metrics: add unique-bug grouping, coverage collection, and
  baseline/proposed comparison reports in `src/evaluation.py`, `src/oracles.py`,
  and `src/targets.py`.

## Oracles

The current evaluation runs three source-processing checks:

| Oracle | Check |
| --- | --- |
| `ast` | Parse, unparse, and parse again |
| `tokenize` | Tokenize, untokenize, and parse again |
| `black` | Verify Black formatting is idempotent |
