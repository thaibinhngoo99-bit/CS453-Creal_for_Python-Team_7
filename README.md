# (CS453) Automated Software Testing - Creal for Python - Team 7

Creal for Python is a fuzzing framework that tests Python source-processing tools by injecting real-world code snippets into synthetically generated programs. Inspired by [Creal for C compilers (PLDI'24)](https://dl.acm.org/doi/10.1145/3656462), the core hypothesis is that real-world code injection produces richer, more diverse test inputs than synthetic generation alone — and therefore exposes more bugs.

---

## Project Structure

```
CS374.../
├── directory/
│   ├── base_programs/      # Stores Hypothesmith baseline & donor corpus (raw & filtered)
│   │   ├── donor_corpus/
│   │   │   ├── filtered/
│   │   │   └── raw/
│   │   └── hypo_baseline/
│   └── injected_programs   # Stores injected programs (valid & invalid)   
│   │   ├── invalid/
│   │   └── valid/
├── results/         
|   └── baseline/        
|   └── proposed/       
├── src/
│   ├── __init__.py
│   ├── execute_baseline.py      # Run target tools on Hypothesmith baseline 
│   ├── execute_proposed.py      # Run target tools on injected programs
│   ├── filter_donor.py          # Filters donor corpus 
│   ├── generate_baseline.py     # Generate Hypothesmith baseline 
│   ├── inject/                  # Injects donor corpus into Hypothesmith baseline with different logics
│   │   ├── logic_1/
│   │   └── logic_2/
│   ├── oracles.py               # Property-based oracles (AST idempotence, behavioral equiv.)
│   └── targets.py               # Wrappers for ast, Black, ruff, lark
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
