# Creal for Python

Creal for Python extends
[Hypothesmith](https://github.com/Zac-HD/hypothesmith) with real-world donor
snippet injection.  The main experiment compares normal Hypothesmith generation
against an injected variant where each generated host program is combined with a
snippet from a donor corpus.

The intended API is Hypothesis-native:

```python
import ast

from hypothesis import given

import hypothesmith


@given(hypothesmith.from_source(inject_realworld=True))
def test_ast_parse_unparse_roundtrip(example):
    tree1 = ast.parse(example.source)
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
│   ├── execute_baseline.py    # Evaluate hypothesmith.from_source()
│   ├── execute_proposed.py    # Evaluate hypothesmith.from_source(inject_realworld=True)
│   ├── evaluation.py          # Shared on-the-fly evaluation harness
│   ├── injects/               # Existing injection experiments
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
python3 src/execute_baseline.py --examples 100
```

Proposed donor-injected generation:

```bash
python3 src/execute_proposed.py --examples 100
```

Use a different donor snippet directory:

```bash
python3 src/execute_proposed.py \
  --examples 100 \
  --donor-dir directory/base_programs/donor_corpus/filtered
```

The evaluation draws examples on the fly with Hypothesis.  It writes summaries
and failing inputs under `results/`, but it does not save every generated
program.

## Patched Hypothesmith API

The submodule adds:

```python
hypothesmith.from_source(
    inject_realworld=False,
    donor_dir=None,
    injection_strategy="append",
)
```

`from_source()` returns a Hypothesis strategy of `hypothesmith.Example` objects.
Each object has:

```python
example.source
example.tree
```

When `inject_realworld=True`, donor snippets are loaded from `donor_dir`, or from
`directory/base_programs/donor_corpus/filtered` by default.  The first supported
injection strategies are `append` and `prepend`, matching the current
`src/injects` experiments.

## Oracles

The current evaluation runs three source-processing checks:

| Oracle | Check |
| --- | --- |
| `ast` | Parse, unparse, and parse again |
| `tokenize` | Tokenize, untokenize, and parse again |
| `black` | Verify Black formatting is idempotent |
