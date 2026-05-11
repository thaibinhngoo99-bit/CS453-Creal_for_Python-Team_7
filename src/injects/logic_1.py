"""
Injection logic 1: append donor code after the generated host module.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENDOR_HYPOTHESMITH_SRC = PROJECT_ROOT / "vendor" / "hypothesmith" / "src"

if VENDOR_HYPOTHESMITH_SRC.exists():
    sys.path.insert(0, str(VENDOR_HYPOTHESMITH_SRC))

from hypothesmith.source import inject_donor_source  # noqa: E402


def inject_donor(host_code: str, donor_code: str) -> str:
    return inject_donor_source(
        host_code,
        donor_code,
        injection_strategy="append",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append a donor snippet to a host program."
    )
    parser.add_argument("host_file", type=Path)
    parser.add_argument("donor_file", type=Path)
    args = parser.parse_args()

    host_code = args.host_file.read_text(encoding="utf-8")
    donor_code = args.donor_file.read_text(encoding="utf-8")
    print(inject_donor(host_code, donor_code))


if __name__ == "__main__":
    main()
