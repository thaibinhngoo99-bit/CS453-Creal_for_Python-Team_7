"""
generate_baseline.py

Generate RAW Hypothesmith host programs.

This version intentionally keeps generation close to
original Hypothesmith behavior for baseline comparison.

Goals:
- Preserve authentic Hypothesmith generation
- Keep only syntactically valid programs
- Remove exact duplicates
- Avoid empty/broken outputs
- DO NOT aggressively filter structure

Outputs:
    directory/base_programs/hypo_baseline

Example:
    python src/generate_baseline.py
"""

import ast
import hashlib
from pathlib import Path

from hypothesmith import from_node

# --------------------------------------------------
# Configuration
# --------------------------------------------------

OUTPUT_DIR = Path("directory/base_programs/hypo_baseline")

NUM_PROGRAMS = 300
MAX_ATTEMPTS = 3000

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_SOURCE_LEN = 1
MAX_SOURCE_LEN = 50000

seen_hashes = set()

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def valid_python(src: str) -> bool:
    """
    Ensure generated code parses successfully.
    """

    try:
        ast.parse(src)
        return True

    except Exception:
        return False


def reasonable_program(src: str) -> bool:
    """
    Remove obviously broken outputs only.
    """

    if len(src.strip()) == 0:
        return False

    if "\x00" in src:
        return False

    if len(src) < MIN_SOURCE_LEN:
        return False

    if len(src) > MAX_SOURCE_LEN:
        return False

    return True


def unique_program(src: str) -> bool:
    """
    Remove exact duplicate programs.
    """

    h = hashlib.sha256(src.encode()).hexdigest()

    if h in seen_hashes:
        return False

    seen_hashes.add(h)

    return True


def save_program(code: str, index: int):
    """
    Save generated host to disk.
    """

    out_path = OUTPUT_DIR / f"host_{index}.py"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)


# --------------------------------------------------
# Main generation loop
# --------------------------------------------------

def generate_hosts():

    strategy = from_node()

    generated = 0
    attempts = 0

    skipped_duplicates = 0
    skipped_invalid = 0
    skipped_empty = 0

    while generated < NUM_PROGRAMS and attempts < MAX_ATTEMPTS:

        attempts += 1

        try:
            # --------------------------------------------------
            # Generate source code
            # --------------------------------------------------

            code = strategy.example()

            # Hypothesmith should return strings
            if not isinstance(code, str):
                skipped_invalid += 1
                continue

            # --------------------------------------------------
            # Lightweight sanity filtering
            # --------------------------------------------------

            if not reasonable_program(code):
                skipped_empty += 1
                continue

            # --------------------------------------------------
            # Syntax validation
            # --------------------------------------------------

            if not valid_python(code):
                skipped_invalid += 1
                continue

            # --------------------------------------------------
            # Deduplicate
            # --------------------------------------------------

            if not unique_program(code):
                skipped_duplicates += 1
                continue

            # --------------------------------------------------
            # Save host
            # --------------------------------------------------

            save_program(code, generated)

            print(f"[+] Generated host_{generated}.py")

            generated += 1

        except Exception:
            skipped_invalid += 1
            continue

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    print()
    print("===================================")
    print(f"Generated hosts      : {generated}")
    print(f"Total attempts       : {attempts}")
    print(f"Skipped duplicates   : {skipped_duplicates}")
    print(f"Skipped invalid      : {skipped_invalid}")
    print(f"Skipped empty        : {skipped_empty}")
    print(f"Output directory     : {OUTPUT_DIR}")
    print("===================================")


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    generate_hosts()