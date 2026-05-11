"""
targets.py

Wrappers around Python source-processing tools.
"""

import ast
import io
import tokenize

import black

# --------------------------------------------------
# AST
# --------------------------------------------------

def ast_parse(code: str):
    return ast.parse(code)


def ast_unparse(tree):
    return ast.unparse(tree)


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