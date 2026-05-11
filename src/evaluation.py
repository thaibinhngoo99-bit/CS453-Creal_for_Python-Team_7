"""
Shared on-the-fly evaluation harness for Hypothesmith strategies.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from hypothesis import HealthCheck, given, settings

# Prefer the patched submodule when running scripts from this repository.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_HYPOTHESMITH_SRC = PROJECT_ROOT / "vendor" / "hypothesmith" / "src"

import sys

if VENDOR_HYPOTHESMITH_SRC.exists():
    sys.path.insert(0, str(VENDOR_HYPOTHESMITH_SRC))

from oracles import (  # noqa: E402
    oracle_ast_roundtrip,
    oracle_black_idempotent,
    oracle_tokenize_roundtrip,
)


Oracle = tuple[str, Callable[[str], bool]]
ORACLES: tuple[Oracle, ...] = (
    ("ast", oracle_ast_roundtrip),
    ("tokenize", oracle_tokenize_roundtrip),
    ("black", oracle_black_idempotent),
)


@dataclass
class EvaluationStats:
    total_programs: int = 0
    successes: int = 0
    failures: int = 0
    ast_failures: int = 0
    tokenize_failures: int = 0
    black_failures: int = 0

    def record_failure(self, oracle_name: str) -> None:
        self.failures += 1
        if oracle_name == "ast":
            self.ast_failures += 1
        elif oracle_name == "tokenize":
            self.tokenize_failures += 1
        elif oracle_name == "black":
            self.black_failures += 1


def _source_from_example(example) -> str:
    return example.source if hasattr(example, "source") else example


def _append_result(results_file: Path, message: str) -> None:
    with results_file.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def _save_failure(
    *,
    failures_dir: Path,
    oracle_name: str,
    index: int,
    source: str,
    error: Exception,
) -> None:
    out_path = failures_dir / f"{index:04d}_{oracle_name}_failure.py"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# ==================================\n")
        f.write(f"# Oracle: {oracle_name}\n")
        f.write(f"# Example: {index}\n")
        f.write("# ==================================\n\n")
        f.write("## ERROR\n\n")
        f.write(repr(error))
        f.write("\n\n")
        f.write("## TRACEBACK\n\n")
        f.write(traceback.format_exc())
        f.write("\n\n")
        f.write("## SOURCE CODE\n\n")
        f.write(source)


def _summary(
    *,
    label: str,
    stats: EvaluationStats,
    results_file: Path,
    failures_dir: Path,
) -> str:
    return f"""
===================================
{label.title()} Execution Summary
===================================

Total programs      : {stats.total_programs}

Successful          : {stats.successes}
Failed              : {stats.failures}

AST failures        : {stats.ast_failures}
Tokenize failures   : {stats.tokenize_failures}
Black failures      : {stats.black_failures}

Results file:
{results_file}

Failure directory:
{failures_dir}

===================================
""".strip()


def run_evaluation(
    *,
    label: str,
    strategy,
    results_dir: Path,
    max_examples: int,
    oracles: Iterable[Oracle] = ORACLES,
) -> EvaluationStats:
    """Run oracles against examples drawn by a Hypothesis strategy."""

    failures_dir = results_dir / "failures"
    summaries_dir = results_dir / "summaries"
    results_file = results_dir / "execution_results.txt"

    results_dir.mkdir(parents=True, exist_ok=True)
    failures_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    results_file.write_text("", encoding="utf-8")

    stats = EvaluationStats()
    oracle_list = tuple(oracles)

    @settings(
        max_examples=max_examples,
        deadline=None,
        suppress_health_check=[
            HealthCheck.filter_too_much,
            HealthCheck.too_slow,
        ],
    )
    @given(example=strategy)
    def execute_oracles(example) -> None:
        source = _source_from_example(example)
        stats.total_programs += 1

        for oracle_name, oracle in oracle_list:
            try:
                oracle(source)
            except Exception as error:
                stats.record_failure(oracle_name)
                _save_failure(
                    failures_dir=failures_dir,
                    oracle_name=oracle_name,
                    index=stats.total_programs,
                    source=source,
                    error=error,
                )
                _append_result(
                    results_file,
                    f"[{oracle_name.upper()} FAILURE] example_{stats.total_programs:04d}",
                )
                return

        stats.successes += 1
        _append_result(results_file, f"[PASS] example_{stats.total_programs:04d}")

    execute_oracles()

    summary = _summary(
        label=label,
        stats=stats,
        results_file=results_file,
        failures_dir=failures_dir,
    )
    print(summary)
    _append_result(results_file, summary)
    (summaries_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    return stats
