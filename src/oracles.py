"""
oracles.py

Property-based testing oracles.
"""

import ast

from targets import (
    ast_parse,
    ast_unparse,
    lib2to3_parse,
    lib2to3_roundtrip,
    libcst_parse_module,
    libcst_roundtrip,
    tokenize_code,
    untokenize_code,
    black_format,
)

# --------------------------------------------------
# AST Oracle
# --------------------------------------------------

def oracle_ast_roundtrip(code: str):
    """
    parse -> unparse -> parse
    should remain valid
    """

    tree = ast_parse(code)

    regenerated = ast_unparse(tree)

    ast_parse(regenerated)

    return True


# --------------------------------------------------
# lib2to3 Oracle
# --------------------------------------------------

def oracle_lib2to3_roundtrip(code: str):
    """
    lib2to3 parse -> stringify should be stable and remain valid Python.
    """

    original_ast = ast.dump(ast_parse(code))

    regenerated = lib2to3_roundtrip(code)
    lib2to3_parse(regenerated)

    assert lib2to3_roundtrip(regenerated) == regenerated
    assert ast.dump(ast_parse(regenerated)) == original_ast

    return True


# --------------------------------------------------
# LibCST Oracle
# --------------------------------------------------

def oracle_libcst_roundtrip(code: str):
    """
    LibCST parse -> codegen should be stable and remain valid Python.
    """

    original_ast = ast.dump(ast_parse(code))

    regenerated = libcst_roundtrip(code)
    libcst_parse_module(regenerated)

    assert libcst_roundtrip(regenerated) == regenerated
    assert ast.dump(ast_parse(regenerated)) == original_ast

    return True


# --------------------------------------------------
# tokenize Oracle
# --------------------------------------------------

def oracle_tokenize_roundtrip(code: str):
    """
    tokenize -> untokenize
    should remain valid
    """

    tokens = tokenize_code(code)

    rebuilt = untokenize_code(tokens)

    ast.parse(rebuilt)

    return True


# --------------------------------------------------
# Black Oracle
# --------------------------------------------------

def oracle_black_idempotent(code: str):
    """
    black(black(x)) == black(x)
    """

    once = black_format(code)

    twice = black_format(once)

    assert once == twice

    return True
