"""
Run the baseline Hypothesmith workflow on the fly.

Example:
    python3 src/execute_baseline.py --examples 100 --oracle ast
"""

import argparse
from pathlib import Path

from evaluation import ORACLE_NAMES, run_evaluation

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
    parser.add_argument(
        "--oracle",
        choices=ORACLE_NAMES,
        required=True,
        help="oracle to run",
    )
    parser.add_argument(
        "--log-generated",
        action="store_true",
        help="save every generated source file and a pass/failure manifest",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    strategy = hypothesmith.from_grammar()
    run_evaluation(
        label="baseline",
        strategy=strategy,
        results_dir=args.results_dir,
        oracle_name=args.oracle,
        max_examples=args.examples,
        log_generated=args.log_generated,
    )


if __name__ == "__main__":
    main()
