"""
logic_1.py

Inject real-world donor functions into Hypothesmith-generated
host programs using AST manipulation.

Logic 1: Append donor after host module.
    host program + donor function -> injected program

Outputs:
    injected_programs/logic_1/
    ├── invalid/
    └── valid/

Example:
    python src/injects/logic_1.py
"""

import ast
import random
from pathlib import Path

# --------------------------------------------------
# Configuration
# --------------------------------------------------

HOST_DIR = Path("directory/base_programs/hypo_baseline")

DONOR_DIR = Path(
    "/home/ubuntu/CS374_Team7/directory/base_programs/donor_corpus/filtered"
)

OUTPUT_VALID_DIR = Path("directory/injected_programs/logic_1/valid")
OUTPUT_INVALID_DIR = Path("directory/injected_programs/logic_1/invalid")

OUTPUT_VALID_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_INVALID_DIR.mkdir(parents=True, exist_ok=True)

NUM_INJECTIONS = 100

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def load_python_files(directory: Path):
    return list(directory.glob("*.py"))


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def valid_python(code: str) -> bool:
    """
    Check whether code parses successfully.
    """

    try:
        ast.parse(code)
        return True

    except Exception:
        return False


def save_program(code: str, path: Path):
    """
    Save source code to disk.
    """

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)


# --------------------------------------------------
# Core injection logic
# --------------------------------------------------

def inject_donor(host_code: str, donor_code: str) -> str:
    """
    Inject donor AST into host AST.
    """

    host_tree = ast.parse(host_code)
    donor_tree = ast.parse(donor_code)

    # Append donor top-level nodes into host module
    host_tree.body.extend(donor_tree.body)

    # Convert AST back to source code
    injected_code = ast.unparse(host_tree)

    return injected_code


# --------------------------------------------------
# Main pipeline
# --------------------------------------------------

def main():

    host_files = load_python_files(HOST_DIR)
    donor_files = load_python_files(DONOR_DIR)

    if not host_files:
        print("No host files found.")
        return

    if not donor_files:
        print("No donor files found.")
        return

    valid_count = 0
    invalid_count = 0

    for i in range(NUM_INJECTIONS):

        try:

            # --------------------------------------
            # Randomly select host + donor
            # --------------------------------------

            host_path = random.choice(host_files)
            donor_path = random.choice(donor_files)

            host_code = read_file(host_path)
            donor_code = read_file(donor_path)

            # --------------------------------------
            # Inject donor into host
            # --------------------------------------

            injected_code = inject_donor(
                host_code,
                donor_code
            )

            # --------------------------------------
            # Syntax validation
            # --------------------------------------

            is_valid = valid_python(injected_code)

            # --------------------------------------
            # Save VALID program
            # --------------------------------------

            if is_valid:

                out_path = (
                    OUTPUT_VALID_DIR /
                    f"injected_valid_{i}.py"
                )

                save_program(injected_code, out_path)

                valid_count += 1

                print(
                    f"[VALID] injected_valid_{i}.py "
                    f"(host={host_path.name}, "
                    f"donor={donor_path.name})"
                )

            # --------------------------------------
            # Save INVALID program
            # --------------------------------------

            else:

                out_path = (
                    OUTPUT_INVALID_DIR /
                    f"injected_invalid_{i}.py"
                )

                save_program(injected_code, out_path)

                invalid_count += 1

                print(
                    f"[INVALID] injected_invalid_{i}.py "
                    f"(host={host_path.name}, "
                    f"donor={donor_path.name})"
                )

        except Exception as e:

            invalid_count += 1

            error_path = (
                OUTPUT_INVALID_DIR /
                f"injected_error_{i}.txt"
            )

            with open(error_path, "w", encoding="utf-8") as f:

                f.write(f"Injection failed\n")
                f.write(f"Error: {e}\n")

            print(f"[!] Injection failed: {e}")

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    total = valid_count + invalid_count

    validity_rate = 0

    if total > 0:
        validity_rate = (valid_count / total) * 100

    print()
    print("===================================")
    print(f"Valid injections     : {valid_count}")
    print(f"Invalid injections   : {invalid_count}")
    print(f"Total injections     : {total}")
    print(f"Validity rate        : {validity_rate:.2f}%")
    print(f"Valid output dir     : {OUTPUT_VALID_DIR}")
    print(f"Invalid output dir   : {OUTPUT_INVALID_DIR}")
    print("===================================")


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    main()