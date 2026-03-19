# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-18
# Description: Metamodel DSL loader

from pathlib import Path
import logging as lg

from lark import Lark, Transformer, indenter

from syntagmax.errors import FatalError


class DSLTransformer(Transformer):
    def artifact(self, children):
        # children[0] is ARTIFACT token, children[1] is name
        attrs = {c['name']: c for c in children[2:] if isinstance(c, dict) and 'name' in c}
        return {'type': 'artifact', 'artifact_name': str(children[1]), 'attributes': attrs}

    def rule(self, children):
        # children[0] is name, children[1] is presence
        return {'name': str(children[0]), 'presence': str(children[1]), 'type_info': children[2]}

    def trace(self, children):
        # trace: "trace" "from" name "to" target_list "is" PRESENCE _NL
        return {
            'type': 'trace',
            'source': str(children[0]),
            'targets': children[1],
            'presence': str(children[2]),
        }

    def target_list(self, children):
        return [str(c) for c in children]

    def type_string(self, _):
        return {'type': 'string'}

    def type_integer(self, _):
        return {'type': 'integer'}

    def type_boolean(self, _):
        return {'type': 'boolean'}

    def type_reference(self, _):
        return {'type': 'reference'}

    def type_enum(self, values):
        # values are now clean strings because of ?value
        return {'type': 'enum', 'allowed': [str(v).strip('"') for v in values]}

    def start(self, items):
        # filter out any leading/trailing _NL tokens
        return [i for i in items if isinstance(i, dict)]


class DSLIndenter(indenter.Indenter):
    NL_type = '_NL'
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = '_INDENT'
    DEDENT_type = '_DEDENT'
    tab_len = 4


def load_metamodel(model_filename: Path, errors, validate=True):
    try:
        grammar = (Path(__file__).parent / 'metamodel.lark').read_text()
        lg.debug(f'Using model grammar:\n{grammar}')
        parser = Lark(grammar, parser='lalr', postlex=DSLIndenter())
        lg.info(f'Read metamodel from {model_filename}')
        metamodel_text = model_filename.read_text(encoding='utf-8')
        lg.debug(f'Using model text:\n{metamodel_text}')
        tree = parser.parse(metamodel_text)
        metamodel = DSLTransformer().transform(tree)
    except Exception as e:
        errors.append(f'Error loading metamodel: {e}')

    if errors:
        raise FatalError(errors)

    artifact_defs = {a['artifact_name']: a for a in metamodel if a['type'] == 'artifact'}
    trace_rules = {}
    for t in metamodel:
        if t['type'] == 'trace':
            source = t['source']
            if source not in trace_rules:
                trace_rules[source] = []
            trace_rules[source].append(t)

    metamodel = {'artifacts': artifact_defs, 'traces': trace_rules}

    if validate:
        validate_metamodel(metamodel, errors)
        if errors:
            raise FatalError(errors)

    return metamodel


def validate_metamodel(metamodel: dict, errors: list[str]):
    for artifact_def in metamodel['artifacts'].values():
        attributes = artifact_def['attributes']

        if 'id' not in attributes:
            errors.append(f"Artifact '{artifact_def['artifact_name']}' is missing an id attribute")
        elif attributes['id']['presence'] != 'mandatory':
            errors.append(f"Artifact '{artifact_def['artifact_name']}' id attribute is not mandatory")

        if 'contents' not in attributes:
            errors.append(f"Artifact '{artifact_def['artifact_name']}' is missing a contents attribute")
        elif attributes['contents']['presence'] != 'mandatory':
            errors.append(f"Artifact '{artifact_def['artifact_name']}' contents attribute is not mandatory")
