# Creal for Python

Creal for Python extends
[Hypothesmith](https://github.com/Zac-HD/hypothesmith) with real-world donor
snippet injection. The main experiment compares normal Hypothesmith generation
against an injected variant where each generated host program is combined with a
snippet from a donor corpus.

The intended API extends Hypothesmith's generators with optional real-world
donor injection:

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
│   └── hypothesmith/          # Git submodule with patched Hypothesmith code
├── src/
│   ├── execute_baseline.py    # Evaluate no-injection generation
│   ├── execute_proposed.py    # Evaluate injection-enabled generation
│   ├── evaluation.py          # Shared on-the-fly evaluation harness
│   ├── oracles.py             # AST, tokenize, and Black oracles
│   ├── target_configs/        # Target-specific coverage/configuration
│   └── targets.py             # Wrappers around target tools
├── vendor/hypothesmith/deps/src/hypothesmith/
│   ├── injection.py           # Donor injection entrypoint
│   └── injection_strategies/  # Strategy implementations + shared helpers
├── directory/
│   └── base_programs/
│       └── donor_corpus/
│           ├── raw/           # Raw donor snippets from The Stack
│           └── filtered/      # Current default donor snippets, ignored by Git
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

## Current Injection Code Path

The current refactored donor-injection implementation lives under:

```text
vendor/hypothesmith/deps/src/hypothesmith/
```

To run the patched Hypothesmith implementation, prefix commands with:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src
```

This prefix is recommended for both baseline and proposed runs so they use the
same patched generator code.

## Run Evaluations

Baseline generation means no donor injection. It now supports both generator
modes:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py --examples 100 --oracle ast
```

Proposed generation means donor injection is enabled:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py --examples 100 --oracle ast
```

Choose the baseline generator family:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py \
  --examples 100 \
  --oracle ast \
  --generation-mode from_grammar

PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py \
  --examples 100 \
  --oracle ast \
  --generation-mode from_node
```

Choose the target oracle with `--oracle`:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py --examples 100 --oracle ast
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py --examples 100 --oracle black
```

Use a wall-clock generation budget instead of an example count:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py --timeout 600 --oracle tokenize
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py --timeout 600 --oracle black
```

Log every generated source file and its result:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py \
  --examples 100 \
  --oracle ast \
  --log-generated
```

Measure Python line coverage for the selected target:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_baseline.py \
  --examples 100 \
  --oracle black \
  --coverage

PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py \
  --examples 100 \
  --oracle black \
  --coverage
```

Use a different donor snippet directory:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py \
  --examples 100 \
  --oracle ast \
  --donor-dir directory/base_programs/donor_corpus/filtered
```

Choose a specific injection strategy:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py \
  --timeout 600 \
  --oracle ast \
  --injection-strategy donor_wrap_host
```

Use Hypothesmith's CST generator instead of the grammar generator:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py \
  --examples 100 \
  --oracle ast \
  --generation-mode from_node
```

Use `from_node` together with donor injection:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py \
  --examples 100 \
  --oracle ast \
  --generation-mode from_node \
  --injection-strategy append
```

Disable donor injection in the proposed runner to match baseline-style
generation while keeping the same evaluation harness:

```bash
PYTHONPATH=vendor/hypothesmith/deps/src \
python3 src/execute_proposed.py \
  --examples 100 \
  --oracle ast \
  --generation-mode from_grammar \
  --no-injection
```

The evaluation draws examples on the fly with Hypothesis and runs one target per
command. Pass either `--examples` or `--timeout`; they are mutually exclusive,
and the default is `--examples 100`. Summaries and failing inputs are written
under target-specific directories such as `results/baseline/ast/` and
`results/proposed/black/`. Generated programs are not saved by default; pass
`--log-generated` to write them under `generated/` and record pass/failure
status in `generated_results.tsv`. Pass `--coverage` to write `coverage.txt`,
`coverage.json`, and `.coverage` under the target result directory. Coverage is
Python line coverage: `tokenize` is mostly measurable, `ast` does not include
CPython parser internals, and Black requires a pure-Python/editable install
rather than a compiled mypyc wheel for meaningful coverage data.

Run the six-way Black 24-hour coverage-snapshot comparison with stdout and
stderr captured per variant:

```bash
mkdir -p results/black_24h_compare_cov_snapshots_v5
nohup scripts/run_black_24h_compare_cov_snapshots.sh \
  results/black_24h_compare_cov_snapshots_v5 \
  > results/black_24h_compare_cov_snapshots_v5/launcher.stdout.log \
  2> results/black_24h_compare_cov_snapshots_v5/launcher.stderr.log &
```

Each variant writes `logs/<variant>.stdout.log`, `logs/<variant>.stderr.log`,
and `logs/<variant>.meta.log`. The evaluator also initializes
`run_error.log` inside each target result directory and writes a Python
traceback there before re-raising unexpected harness errors. The launcher wraps
each Python process in an outer `timeout --verbose` supervisor set to one hour
past the requested run budget by default, so a process that ignores the
in-process timer still leaves an exit status and timeout message in the logs.
Set `AUTO_TARGET=off` when launching to pass `--no-auto-target` to every
variant and disable Hypothesmith's target-guided search.
Set `ORACLE_NAME=tokenize` to run the same launcher against `tokenize`, and
set `RUN_VARIANTS="from_grammar_append from_grammar_aggressive
from_grammar_no_injection"` to run only grammar variants.

`--generation-mode from_grammar` uses Hypothesmith's grammar-based generator.
`--generation-mode from_node` uses Hypothesmith's LibCST-based generator.
In the baseline runner, both modes always run without injection. In the
proposed runner, injection is enabled by default and can be turned off with
`--no-injection`. Both modes support donor injection through `--donor-dir` and
`--injection-strategy`, but `from_node` tends to be slower because more
generated host/donor combinations get filtered out before acceptance.

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

```python
hypothesmith.from_node(
    *,
    auto_target=True,
    inject_realworld=False,
    donor_dir=None,
    injection_strategy="append",
)
```

When `inject_realworld=True`, donor snippets are loaded from `donor_dir`, or
from `directory/base_programs/donor_corpus/filtered` by default. Injection is
supported in both generator modes. For `from_grammar`, injection still requires
`start="file_input"` because donor snippets are module-level Python fragments.

## Injection Strategies

The current proposed runner supports 5 injection strategies:

| Strategy | Description |
| --- | --- |
| `aggressive` | Insert many copies of the generated host throughout nested donor code |
| `append` | Put donor statements after the generated host statements |
| `prepend` | Put donor statements before the generated host statements |
| `host_wrap_donor` | Try to insert donor statements into an existing nested block in the host |
| `donor_wrap_host` | Try to insert host statements into an existing nested block in the donor |

### `aggressive`

This strategy is an amplified version of `donor_wrap_host`. Instead of trying to
insert the generated host once, it attempts to insert multiple copies of the
host throughout nested donor bodies. The current implementation targets up to
`10` copies. If the donor has no suitable nested body, it falls back to adding
multiple synthetic wrapper functions that each contain a copy of the host.

Host:

```python
if ready:
    x = 1
```

Donor:

```python
def outer():
    if cond_a:
        y = 2
    if cond_b:
        z = 3
```

Possible result:

```python
def outer():
    if cond_a:
        y = 2
        if ready:
            x = 1
    if cond_b:
        z = 3
        if ready:
            x = 1
```

### `append`

Host:

```python
x = 1
print(x)
```

Donor:

```python
def helper():
    return 42
```

Result:

```python
x = 1
print(x)

def helper():
    return 42
```

### `prepend`

Host:

```python
x = 1
print(x)
```

Donor:

```python
def helper():
    return 42
```

Result:

```python
def helper():
    return 42

x = 1
print(x)
```

### `host_wrap_donor`

This strategy prefers a real nested insertion point in the generated host. If
the host already contains a compound statement such as `if`, `for`, `while`,
`with`, `try`, `match`, or a function body, donor statements are inserted into
that nested structure. If the host has no suitable nested body, the strategy
falls back to wrapping the donor in a synthetic helper function.

Host:

```python
if ready:
    x = 1
```

Donor:

```python
if enabled:
    y = 2
```

Possible result:

```python
if ready:
    x = 1
    if enabled:
        y = 2
```

### `donor_wrap_host`

This is the reverse direction: it prefers inserting generated host statements
into an existing nested block from the donor. If the donor has no suitable
nested body, the strategy falls back to wrapping the host in a synthetic helper
function.

Host:

```python
if ready:
    x = 1
```

Donor:

```python
def helper():
    y = 2
```

Possible result:

```python
def helper():
    y = 2
    if ready:
        x = 1
```

## Oracles

The current evaluation runs three source-processing checks:

| Oracle | Check |
| --- | --- |
| `ast` | Parse, unparse, and parse again |
| `tokenize` | Tokenize, untokenize, and parse again |
| `black` | Verify Black formatting is idempotent |
