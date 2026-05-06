# Creal for Python — CS453 Team 7

Creal for Python is a fuzzing framework that tests Python source-processing tools by injecting real-world code snippets into synthetically generated programs. Inspired by [Creal for C compilers (PLDI'24)](https://dl.acm.org/doi/10.1145/3656462), the core hypothesis is that real-world code injection produces richer, more diverse test inputs than synthetic generation alone — and therefore exposes more bugs.

---

## Project Structure

```
CS374.../
├── src/
│   ├── __init__.py
│   ├── generate.py     # Hypothesmith baseline + real-world injection logic
│   ├── execute.py      # Run target tools on generated programs
│   ├── oracles.py      # Property-based oracles (AST idempotence, behavioral equiv.)
│   └── targets.py      # Wrappers for ast, Black, ruff, lark
├── corpus/
│   ├── raw/            # Downloaded code snippets (gitignored)
│   ├── filtered/       # Compilable, relevant snippets (gitignored)
│   └── collect.py      # Corpus collection & filtering script
├── results/           
|   └── generated/      # Stores generated programs (baseline & proposed)
│   │   ├── baseline/
│   │   └── proposed/
|   └── bugs/
|   └── coverage/
|   └── logs/
├── tests/
│   ├── test_generate.py    # Tests for Hypothesmith + injection logic
│   ├── test_oracles.py     # Tests for AST idempotence & behavioral equiv.
│   ├── test_targets.py     # Tests each tool wrapper runs without error
│   └── test_corpus.py      # Tests that collect.py filters correctly
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Setup

**Requirements:** Python 3.12+

```bash
git clone <repo-url>
cd CS374
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Usage

### 1. Collect the corpus

Downloads and filters real-world Python snippets from sources like GitHub or CodeSearchNet into `corpus/filtered/`.

```bash
python corpus/collect.py
```

### 2. Run the baseline (synthetic only)

Generates programs using Hypothesmith alone and runs them against the target tools.

```bash
python src/execute.py --mode baseline
```

### 3. Run the proposed approach (synthetic + injection)

Generates programs using Hypothesmith and injects real-world snippets from the corpus.

```bash
python src/execute.py --mode proposed
```

### 4. Compare results

Results (bug reports, coverage, validity rate, throughput) are written to `results/`.

```bash
python src/execute.py --compare
```

---

## Oracles

Two property-based oracles are used to detect bugs:

- **AST Idempotence** (`ast`): Verifies that `parse(unparse(parse(src))) == parse(src)`. A mismatch indicates a bug in Python's AST module.
- **Behavioral Equivalence** (`Black`, `ruff`, `lark`): Verifies that `output(src) == output(transformed(src))`. A mismatch after formatting or linting indicates unexpected behavior.

---

## Target Tools

| Tool | Type | Oracle |
|------|------|--------|
| `ast` | Parser / unparser | AST idempotence |
| `black` | Formatter | Behavioral equivalence |
| `ruff` | Linter | Behavioral equivalence |
| `lark` | Parser | Behavioral equivalence |

---

## Evaluation Metrics

| Metric | Description |
|--------|-------------|
| **Bug detection** | Number of unique bugs found |
| **Code coverage** | How much of the target tool's code is exercised |
| **Validity** | Proportion of generated programs that are valid Python |
| **Throughput** | Speed of generating and testing programs (programs/sec) |

---

## Team

| Name | Student ID |
|------|-----------|
| Jinyeong Maeng | 20220228 |
| Thai Binh Ngo | 20231008 |
| Steve Gustaman | 20240607 |
| Morgan Aubert | 20266102 |

---

## Reference

> Boosting Compiler Testing by Injecting Real-World Code — PLDI'24
