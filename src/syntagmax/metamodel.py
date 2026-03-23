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
        # Handle the "attribute" rule
        # If the first child is the "attribute" token (implicitly handled by rule grammar)
        # or if it has a type, it's a regular attribute.
        if hasattr(children[0], 'type') and children[0].type == 'WORD':
            # children: name, presence, (multiple_token | None), type_info
            return {
                'name': str(children[0]),
                'presence': str(children[1]),
                'multiple': children[2] is not None,
                'type_info': children[3],
                'id_rule': False,
            }
        # Handle the "id" rule
        else:
            # children: type_info, [schema]
            schema = str(children[1]).strip('"') if len(children) > 1 and children[1] is not None else None
            return {
                'name': 'id',
                'presence': 'mandatory',
                'multiple': False,
                'type_info': children[0],
                'schema': schema,
                'id_rule': True,
            }

    def trace(self, children):
        # trace: "trace" "from" name "to" target_list "is" PRESENCE ["via" TRACE_MODE] _NL
        # TRACE_MODE is "commit" or "timestamp"
        mode = str(children[3]) if len(children) > 3 and children[3] is not None else 'timestamp'
        return {
            'type': 'trace',
            'source': str(children[0]),
            'targets': children[1],
            'presence': str(children[2]),
            'mode': mode,
        }

    def target_list(self, children):
        return [str(c) for c in children]

    def type_string(self, _):
        return {'type': 'string'}

    def type_integer(self, _):
        return {'type': 'integer'}

    def type_boolean(self, _):
        return {'type': 'boolean'}

    def type_reference(self, children):
        to_parent = len(children) > 0 and children[0] is not None
        return {'type': 'reference', 'to_parent': to_parent}

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

    # Consistency checks variables
    # To check consistency we track properties per target for a given source
    # properties: {source: {target: {'presence': p, 'mode': m}}}
    trace_props: dict[str, dict[str, dict[str, str]]] = {}

    for t in metamodel:
        if t['type'] == 'trace':
            source = t['source']
            if source not in trace_rules:
                trace_rules[source] = []
            trace_rules[source].append(t)

            # Check consistency of rules
            if source not in trace_props:
                trace_props[source] = {}
            for target in t['targets']:
                if target in trace_props[source]:
                    existing = trace_props[source][target]
                    if existing['presence'] != t['presence']:
                        errors.append(
                            f'Inconsistent trace rules for {source} -> {target}: '
                            f"presence is both '{existing['presence']}' and '{t['presence']}'"
                        )
                    if existing['mode'] != t['mode']:
                        errors.append(
                            f'Inconsistent trace rules for {source} -> {target}: '
                            f"mode is both '{existing['mode']}' and '{t['mode']}'"
                        )
                else:
                    trace_props[source][target] = {
                        'presence': t['presence'],
                        'mode': t['mode'],
                    }

    metamodel = {'artifacts': artifact_defs, 'traces': trace_rules}

    if validate:
        validate_metamodel(metamodel, errors)
        if errors:
            raise FatalError(errors)

    return metamodel


def validate_metamodel(metamodel: dict, errors: list[str]):
    for artifact_def in metamodel['artifacts'].values():
        attributes = artifact_def['attributes']
        artifact_name = artifact_def['artifact_name']

        # Check for regular attributes named 'id'
        # The parser now distinguishes between 'id is ...' and 'attribute name is ...'
        # but if someone does 'attribute id is ...' it might still come through as a regular rule.
        # Actually, the grammar I wrote is:
        # rule: "attribute" name "is" PRESENCE [MULTIPLE] type _NL
        #    | "id" "is" type ["as" SCHEMA] _NL
        # So "attribute id is ..." will match the first branch.

        # Let's check if any regular attribute (not from the "id" rule) is named 'id'
        # In our transformer, the "id" rule results in a dict with 'name': 'id' and possibly 'schema'.
        # The regular rule results in a dict with 'name': str(children[0]).

        # Actually, let's just check if there's more than one 'id' or if it doesn't have the expected mandatory properties.

        # Forbid definitions of "regular" attributes named 'id'.
        # All attributes named 'id' must come from the "id" rule.
        for attr_name, attr_def in attributes.items():
            if attr_name == 'id' and not attr_def.get('id_rule', False):
                errors.append(f"Artifact '{artifact_name}' has a regular attribute named 'id'. Use 'id is ...' instead.")

        id_attr = attributes.get('id')
        if not id_attr:
            errors.append(f"Artifact '{artifact_name}' is missing an id attribute")
        elif id_attr.get('presence') != 'mandatory':
            errors.append(f"Artifact '{artifact_name}' id attribute is not mandatory")

        if 'contents' not in attributes:
            errors.append(f"Artifact '{artifact_name}' is missing a contents attribute")
        elif attributes['contents']['presence'] != 'mandatory':
            errors.append(f"Artifact '{artifact_def['artifact_name']}' contents attribute is not mandatory")
