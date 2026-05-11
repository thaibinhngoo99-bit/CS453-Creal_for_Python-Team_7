"""
oracles.py

Property-based testing oracles.
"""

import ast

from targets import (
    ast_parse,
    ast_unparse,
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