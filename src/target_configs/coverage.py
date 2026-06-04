"""Coverage configuration for evaluated targets."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

COMPILED_SUFFIXES = (".so", ".pyd")
TARGET_COVERAGE_SOURCES = {
    "ast": ["ast"],
    "black": ["black"],
    "lib2to3": ["lib2to3"],
    "tokenize": ["tokenize"],
}


@dataclass(frozen=True)
class CoverageConfig:
    source: list[str]
    unavailable_reason: str | None = None


def _compiled_module_reason(module_name: str, message: str) -> str | None:
    spec = importlib.util.find_spec(module_name)
    origin = "" if spec is None or spec.origin is None else spec.origin
    if origin.endswith(COMPILED_SUFFIXES):
        return message
    return None


def _missing_module_reason(module_name: str, message: str) -> str | None:
    if importlib.util.find_spec(module_name) is None:
        return message
    return None


def _black_unavailable_reason() -> str | None:
    return _compiled_module_reason(
        "black",
        (
            "Black is installed as a compiled mypyc extension, so Python line "
            "coverage is unavailable. Reinstall Black from source without mypyc "
            "or use an editable pure-Python Black checkout to collect coverage."
        ),
    )


def _lib2to3_unavailable_reason() -> str | None:
    return _missing_module_reason(
        "lib2to3",
        "lib2to3 is unavailable in this Python environment.",
    )


def get_coverage_config(oracle_name: str) -> CoverageConfig | None:
    if oracle_name not in TARGET_COVERAGE_SOURCES:
        return None

    unavailable_reason = None
    if oracle_name == "black":
        unavailable_reason = _black_unavailable_reason()
    elif oracle_name == "lib2to3":
        unavailable_reason = _lib2to3_unavailable_reason()

    return CoverageConfig(
        source=TARGET_COVERAGE_SOURCES[oracle_name],
        unavailable_reason=unavailable_reason,
    )


def supported_coverage_oracles() -> tuple[str, ...]:
    return tuple(TARGET_COVERAGE_SOURCES)
