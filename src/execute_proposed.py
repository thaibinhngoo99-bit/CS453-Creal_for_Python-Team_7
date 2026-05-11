"""
Run the real-world donor injection workflow on the fly.

Example:
    python3 src/execute_proposed.py --examples 100
"""

import argparse
from pathlib import Path

from evaluation import run_evaluation

import hypothesmith


DEFAULT_DONOR_DIR = Path("directory/base_programs/donor_corpus/filtered")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Hypothesmith generation with donor injection."
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=100,
        help="number of generated examples to evaluate",
    )
    parser.add_argument(
        "--donor-dir",
        type=Path,
        default=DEFAULT_DONOR_DIR,
        help="directory containing .py donor snippets",
    )
    parser.add_argument(
        "--injection-strategy",
        choices=("append", "prepend"),
        default="append",
        help="how donor snippets are combined with generated hosts",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/proposed"),
        help="directory for evaluation reports",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    strategy = hypothesmith.from_source(
        inject_realworld=True,
        donor_dir=args.donor_dir,
        injection_strategy=args.injection_strategy,
    )
    run_evaluation(
        label="proposed",
        strategy=strategy,
        results_dir=args.results_dir,
        max_examples=args.examples,
    )


if __name__ == "__main__":
    main()
