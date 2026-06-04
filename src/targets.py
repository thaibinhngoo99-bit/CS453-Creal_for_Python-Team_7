"""
targets.py

Wrappers around Python source-processing tools.
"""

import ast
import io
import tokenize
import warnings

import black

# --------------------------------------------------
# AST
# --------------------------------------------------

def ast_parse(code: str):
    return ast.parse(code)


def ast_unparse(tree):
    return ast.unparse(tree)


# --------------------------------------------------
# lib2to3
# --------------------------------------------------

_LIB2TO3_DRIVER = None
_LIBCST = None


def _get_lib2to3_driver():
    global _LIB2TO3_DRIVER
    if _LIB2TO3_DRIVER is None:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from lib2to3 import pygram, pytree
                from lib2to3.pgen2 import driver
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "lib2to3 is unavailable in this Python environment"
            ) from error

        _LIB2TO3_DRIVER = driver.Driver(
            pygram.python_grammar_no_print_statement,
            convert=pytree.convert,
        )
    return _LIB2TO3_DRIVER


def lib2to3_parse(code: str):
    if not code.endswith("\n"):
        code += "\n"
    return _get_lib2to3_driver().parse_string(code)


def lib2to3_roundtrip(code: str) -> str:
    return str(lib2to3_parse(code))


# --------------------------------------------------
# LibCST
# --------------------------------------------------

def _get_libcst():
    global _LIBCST
    if _LIBCST is None:
        try:
            import libcst
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "libcst is unavailable in this Python environment"
            ) from error
        _LIBCST = libcst
    return _LIBCST


def libcst_parse_module(code: str):
    return _get_libcst().parse_module(code)


def libcst_roundtrip(code: str) -> str:
    return libcst_parse_module(code).code


# --------------------------------------------------
# tokenize
# --------------------------------------------------

def tokenize_code(code: str):

    return list(
        tokenize.generate_tokens(
            io.StringIO(code).readline
        )
    )


def untokenize_code(tokens):

    return tokenize.untokenize(tokens)


# --------------------------------------------------
# Black
# --------------------------------------------------

def black_format(code: str):

    return black.format_str(
        code,
        mode=black.FileMode(),
    )
