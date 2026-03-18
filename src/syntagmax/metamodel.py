# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-18
# Description: Metamodel DSL loader

from pathlib import Path
import logging as lg

from lark import Lark, Transformer, indenter


class DSLTransformer(Transformer):
    def artifact(self, children):
        # children[0] is now a string/token because of ?name
        return {'artifact_name': str(children[0]), 'attributes': children[1:]}

    def rule(self, children):
        # children[0] is name, children[1] is presence
        return {'name': str(children[0]), 'presence': str(children[1]), 'type_info': children[2]}

    def type_string(self, _):
        return {'type': 'string'}

    def type_integer(self, _):
        return {'type': 'integer'}

    def type_boolean(self, _):
        return {'type': 'boolean'}

    def type_enum(self, values):
        # values are now clean strings because of ?value
        return {'type': 'enum', 'allowed': [str(v).strip('"') for v in values]}

    def start(self, items):
        return items


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
    lg.debug(f'Using model text:\n{metamodel_text}')
    tree = parser.parse(metamodel_text)
    metamodel = DSLTransformer().transform(tree)
    artifact_defs = {a['artifact_name']: a for a in metamodel}
    return artifact_defs
