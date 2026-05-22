"""
Run the baseline Hypothesmith workflow on the fly.

Example:
    python3 src/execute_baseline.py --examples 100 --oracle ast
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_HYPOTHESMITH_SRC = PROJECT_ROOT / "vendor" / "hypothesmith" / "src"
VENDOR_HYPOTHESMITH_DEPS_SRC = (
    PROJECT_ROOT / "vendor" / "hypothesmith" / "deps" / "src"
)
for vendored_src in (VENDOR_HYPOTHESMITH_SRC, VENDOR_HYPOTHESMITH_DEPS_SRC):
    if vendored_src.exists():
        sys.path.insert(0, str(vendored_src))

from evaluation import ORACLE_NAMES, run_evaluation

import hypothesmith


DEFAULT_EXAMPLES = 100
GENERATION_MODES = ("from_grammar", "from_node")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive number of seconds")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate normal Hypothesmith generation."
    )
    termination = parser.add_mutually_exclusive_group()
    termination.add_argument(
        "--examples",
        type=positive_int,
        default=None,
        help=f"number of generated examples to evaluate (default: {DEFAULT_EXAMPLES})",
    )
    termination.add_argument(
        "--timeout",
        type=positive_float,
        default=None,
        help="seconds to keep generating examples",
    )
    parser.add_argument(
        "--generation-mode",
        choices=GENERATION_MODES,
        default="from_grammar",
        help="which Hypothesmith generator to use for the baseline run",
    )
    parser.add_argument(
        "--no-auto-target",
        dest="auto_target",
        action="store_false",
        help="disable Hypothesmith's target() guidance toward larger/richer programs",
    )
    parser.set_defaults(auto_target=True)
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
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="measure Python line coverage for the selected oracle target",
    )
    args = parser.parse_args()
    if args.examples is None and args.timeout is None:
        args.examples = DEFAULT_EXAMPLES
    return args


def main() -> None:
    args = parse_args()
    if args.generation_mode == "from_grammar":
        strategy = hypothesmith.from_grammar(auto_target=args.auto_target)
    else:
        strategy = hypothesmith.from_node(auto_target=args.auto_target)
    run_evaluation(
        label="baseline",
        strategy=strategy,
        results_dir=args.results_dir,
        oracle_name=args.oracle,
        max_examples=args.examples,
        timeout_seconds=args.timeout,
        log_generated=args.log_generated,
        measure_coverage=args.coverage,
    )


if __name__ == "__main__":
    main()
