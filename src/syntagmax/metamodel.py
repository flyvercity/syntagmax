# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-18
# Description: Metamodel DSL loader

from pathlib import Path
import logging as lg

from lark import Lark, indenter


class DSLIndenter(indenter.Indenter):
    NL_type = '_NL'
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = '_INDENT'
    DEDENT_type = '_DEDENT'
    tab_len = 4


def load_model(model_filename: Path):
    grammar = (Path(__file__).parent / 'metamodel.lark').read_text()
    lg.debug(f'Using model grammar:\n{grammar}')
    parser = Lark(grammar, parser='lalr', postlex=DSLIndenter())
    lg.info(f'Read metamodel from {model_filename}')
    metamodel_text = model_filename.read_text(encoding='utf-8')
    lg.info(f'Using model text:\n{metamodel_text}')
    return parser.parse(metamodel_text)
