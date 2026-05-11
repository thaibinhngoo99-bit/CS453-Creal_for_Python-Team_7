"""
Run the baseline Hypothesmith workflow on the fly.

Example:
    python3 src/execute_baseline.py --examples 100
"""

import argparse
from pathlib import Path

from evaluation import run_evaluation

import hypothesmith


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate normal Hypothesmith generation."
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=100,
        help="number of generated examples to evaluate",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/baseline"),
        help="directory for evaluation reports",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    strategy = hypothesmith.from_source(inject_realworld=False)
    run_evaluation(
        label="baseline",
        strategy=strategy,
        results_dir=args.results_dir,
        max_examples=args.examples,
    )


if __name__ == "__main__":
    main()
