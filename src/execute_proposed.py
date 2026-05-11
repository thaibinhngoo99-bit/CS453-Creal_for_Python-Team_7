"""
execute_proposed.py

Execute injected Python programs against
source-processing tool oracles.

Pipeline:
    injected program
        ↓
    oracle execution
        ↓
    success / failure logging

Uses:
- targets.py
- oracles.py

Input:
    directory/injected_programs/logic_1/valid/

Outputs:
    results/proposed/
    ├── execution_results.txt
    ├── failures/
    └── summaries/

Example:
    python src/execute_proposed.py
"""

from pathlib import Path
import traceback

from oracles import (
    oracle_ast_roundtrip,
    oracle_tokenize_roundtrip,
    oracle_black_idempotent,
)

# --------------------------------------------------
# Configuration
# --------------------------------------------------

INPUT_DIR = Path("directory/injected_programs/logic_1/valid")

RESULTS_DIR = Path("results/proposed")
FAILURES_DIR = RESULTS_DIR / "failures"
SUMMARIES_DIR = RESULTS_DIR / "summaries"

RESULTS_FILE = RESULTS_DIR / "execution_results.txt"

# --------------------------------------------------
# Create directories
# --------------------------------------------------

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FAILURES_DIR.mkdir(parents=True, exist_ok=True)
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# Statistics
# --------------------------------------------------

total_programs = 0

successes = 0
failures = 0

ast_failures = 0
tokenize_failures = 0
black_failures = 0

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def append_result(message: str):

    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def save_failure(
    oracle_name: str,
    file_name: str,
    code: str,
    error: Exception,
):

    out_path = (
        FAILURES_DIR /
        f"{oracle_name}_{file_name}"
    )

    with open(out_path, "w", encoding="utf-8") as f:

        f.write("# ==================================\n")
        f.write(f"# Oracle: {oracle_name}\n")
        f.write(f"# File   : {file_name}\n")
        f.write("# ==================================\n\n")

        f.write("## ERROR\n\n")
        f.write(repr(error))
        f.write("\n\n")

        f.write("## TRACEBACK\n\n")
        f.write(traceback.format_exc())
        f.write("\n\n")

        f.write("## SOURCE CODE\n\n")
        f.write(code)


# --------------------------------------------------
# Execute all oracles
# --------------------------------------------------

def execute_program(path: Path):

    global successes
    global failures

    global ast_failures
    global tokenize_failures
    global black_failures

    code = read_file(path)

    # --------------------------------------------------
    # AST Oracle
    # --------------------------------------------------

    try:

        oracle_ast_roundtrip(code)

    except Exception as e:

        failures += 1
        ast_failures += 1

        save_failure(
            "ast",
            path.name,
            code,
            e,
        )

        append_result(
            f"[AST FAILURE] {path.name}"
        )

        print(f"[AST FAIL] {path.name}")

        return

    # --------------------------------------------------
    # tokenize Oracle
    # --------------------------------------------------

    try:

        oracle_tokenize_roundtrip(code)

    except Exception as e:

        failures += 1
        tokenize_failures += 1

        save_failure(
            "tokenize",
            path.name,
            code,
            e,
        )

        append_result(
            f"[TOKENIZE FAILURE] {path.name}"
        )

        print(f"[TOKENIZE FAIL] {path.name}")

        return

    # --------------------------------------------------
    # Black Oracle
    # --------------------------------------------------

    try:

        oracle_black_idempotent(code)

    except Exception as e:

        failures += 1
        black_failures += 1

        save_failure(
            "black",
            path.name,
            code,
            e,
        )

        append_result(
            f"[BLACK FAILURE] {path.name}"
        )

        print(f"[BLACK FAIL] {path.name}")

        return

    # --------------------------------------------------
    # Success
    # --------------------------------------------------

    successes += 1

    append_result(
        f"[PASS] {path.name}"
    )

    print(f"[PASS] {path.name}")


# --------------------------------------------------
# Main pipeline
# --------------------------------------------------

def main():

    global total_programs

    # Clear old results
    RESULTS_FILE.write_text("", encoding="utf-8")

    program_files = list(INPUT_DIR.glob("*.py"))

    if not program_files:

        print("No injected programs found.")
        return

    total_programs = len(program_files)

    print()
    print("===================================")
    print("Executing Oracles")
    print("===================================")
    print()

    for path in program_files:

        execute_program(path)

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    summary = f"""
===================================
Execution Summary
===================================

Total programs      : {total_programs}

Successful          : {successes}
Failed              : {failures}

AST failures        : {ast_failures}
Tokenize failures   : {tokenize_failures}
Black failures      : {black_failures}

Results file:
{RESULTS_FILE}

Failure directory:
{FAILURES_DIR}

===================================
"""

    print(summary)

    append_result(summary)

    summary_file = (
        SUMMARIES_DIR /
        "summary.txt"
    )

    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary)


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    main()