# Real-World Donor Injection for Hypothesmith

This project compares normal Hypothesmith generation with variants that inject
real-world Python donor snippets into generated programs. The main workflow is
to run the same target oracle under multiple generation strategies and compare
coverage.

Current target oracles:

- `tokenize`
- `black`
- `lib2to3`
- `libcst`

Current strategy variants used in the main experiments:

- `aggressive`
- `append`
- `no_injection`

## Setup

```bash
git clone --recurse-submodules <repo-url>
cd CS374_Team7

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If submodules were not cloned:

```bash
git submodule update --init --recursive
pip install -r requirements.txt
```

On Ubuntu/Python 3.12, `lib2to3` may need the split stdlib package:

```bash
sudo apt-get install python3-lib2to3
```

The runner scripts add the patched Hypothesmith paths automatically, so use
`venv/bin/python3 src/execute_*.py` from the repo root.

## Single Runs

No donor injection:

```bash
venv/bin/python3 src/execute_baseline.py \
  --examples 100 \
  --generation-mode from_node \
  --oracle black
```

Injection enabled:

```bash
venv/bin/python3 src/execute_proposed.py \
  --examples 100 \
  --generation-mode from_node \
  --oracle black \
  --injection-strategy append
```

Use a time budget instead of an example count:

```bash
venv/bin/python3 src/execute_proposed.py \
  --timeout 600 \
  --generation-mode from_node \
  --oracle tokenize \
  --injection-strategy aggressive
```

Useful options:

| Option | Meaning |
| --- | --- |
| `--oracle {ast,tokenize,black,lib2to3,libcst}` | Target oracle |
| `--generation-mode {from_grammar,from_node}` | Hypothesmith generator |
| `--injection-strategy {aggressive,append,prepend,host_wrap_donor,donor_wrap_host}` | Donor injection strategy (only aggressive and append were tested) |
| `--no-injection` | Disable donor injection in the proposed runner |
| `--no-auto-target` | Disable Hypothesmith target guidance |
| `--coverage` | Write final Python coverage reports |
| `--coverage-snapshot-interval N` | Write periodic coverage snapshots during timeout runs |
| `--results-dir PATH` | Output directory |

## Run The Three Main Strategies

Set the target and output root:

```bash
TARGET=black
ROOT=results/${TARGET}_from_node_24h_auto_target_on_cst_lazy_batch10000_v1
mkdir -p "$ROOT"/{aggressive,append,no_injection}
```

Launch `aggressive`:

```bash
timeout --verbose --signal=INT --kill-after=300 90000 \
  venv/bin/python3 -u src/execute_proposed.py \
    --oracle "$TARGET" \
    --timeout 86400 \
    --coverage \
    --coverage-snapshot-interval 900 \
    --generation-mode from_node \
    --injection-strategy aggressive \
    --results-dir "$ROOT/aggressive" \
    > "$ROOT/aggressive/launcher.stdout.log" \
    2> "$ROOT/aggressive/launcher.stderr.log" &
```

Launch `append`:

```bash
timeout --verbose --signal=INT --kill-after=300 90000 \
  venv/bin/python3 -u src/execute_proposed.py \
    --oracle "$TARGET" \
    --timeout 86400 \
    --coverage \
    --coverage-snapshot-interval 900 \
    --generation-mode from_node \
    --injection-strategy append \
    --results-dir "$ROOT/append" \
    > "$ROOT/append/launcher.stdout.log" \
    2> "$ROOT/append/launcher.stderr.log" &
```

Launch `no_injection`:

```bash
timeout --verbose --signal=INT --kill-after=300 90000 \
  venv/bin/python3 -u src/execute_proposed.py \
    --oracle "$TARGET" \
    --timeout 86400 \
    --coverage \
    --coverage-snapshot-interval 900 \
    --generation-mode from_node \
    --no-injection \
    --results-dir "$ROOT/no_injection" \
    > "$ROOT/no_injection/launcher.stdout.log" \
    2> "$ROOT/no_injection/launcher.stderr.log" &
```

Change `TARGET` to `tokenize`, `black`, or `lib2to3` for Python coverage runs.
For shorter smoke tests, reduce `--timeout` and `--coverage-snapshot-interval`.

## Results

Each variant writes a target directory like:

```text
results/.../append/black/
```

Important files:

- `summaries/summary.txt`
- `execution_results.txt`
- `coverage.txt`
- `coverage.json`
- `coverage_snapshots/`
- `failures/`

LibCST native coverage uses the separate LLVM snapshot setup under
`.native_coverage/`; see `scripts/native_coverage_snapshotter.sh` if you need
to rerun that path.
