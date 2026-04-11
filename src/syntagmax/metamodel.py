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
        # We need to allow multiple rules for the same attribute name
        attrs = {}
        for c in children[2:]:
            if isinstance(c, dict) and 'name' in c:
                name = c['name']
                if name not in attrs:
                    attrs[name] = []
                attrs[name].append(c)
        return {'type': 'artifact', 'artifact_name': str(children[1]), 'attributes': attrs}

    def rule(self, children):
        # Handle the "attribute" rule
        # rule: "attribute" name "is" PRESENCE [MULTIPLE] type [condition] _NL
        if hasattr(children[0], 'type') and children[0].type == 'WORD':
            # children: name, presence, (multiple_token | None), type_info, [condition]
            name = str(children[0])
            presence = str(children[1])
            multiple = children[2] is not None
            type_info = children[3]
            condition = children[4] if len(children) > 4 else None
            return {
                'name': name,
                'presence': presence,
                'multiple': multiple,
                'type_info': type_info,
                'condition': condition,
                'id_rule': False,
            }
        # Handle the "id" rule
        else:
            # children: type_info, [schema]
            schema = children[1] if len(children) > 1 and children[1] is not None else None
            return {
                'name': 'id',
                'presence': 'mandatory',
                'multiple': False,
                'type_info': children[0],
                'schema': schema,
                'id_rule': True,
            }

    def condition(self, children):
        # condition: "if" [NOT] anchor
        negated = False
        anchor = None
        for child in children:
            if hasattr(child, 'type') and child.type == 'NOT':
                negated = True
            else:
                anchor = str(child)
        return {'anchor': anchor, 'negated': negated}

    def anchor(self, children):
        return str(children[0])

    def trace(self, children):
        # trace: "trace" "from" name "to" target_list "is" PRESENCE ["via" TRACE_MODE] [condition] _NL
        # children: source, targets, presence, [mode], [condition]
        
        mode = 'timestamp'
        condition = None
        
        presence = str(children[2])
        
        if len(children) > 3:
            # children[3] could be TRACE_MODE or condition
            if isinstance(children[3], dict) and 'anchor' in children[3]:
                condition = children[3]
            elif children[3] is not None:
                mode = str(children[3])
                
        if len(children) > 4 and children[4] is not None:
            condition = children[4]

        return {
            'type': 'trace',
            'source': str(children[0]),
            'targets': children[1],
            'presence': presence,
            'mode': mode,
            'condition': condition,
        }

    def target_list(self, children):
        return [str(c) for c in children]

    def unquoted_items(self, children):
        return ''.join(map(str, children))

    def quoted_items(self, children):
        # We need to strip the quotes if they were included by the rule?
        # quoted_items: "\"" (QUOTED_PART | placeholder | invalid_placeholder)* "\""
        # The children will be only the items inside the quotes because "\"" are literal strings in the rule.
        return ''.join(map(str, children))

    def PLACEHOLDER(self, token):
        return str(token)

    def INVALID_PLACEHOLDER(self, token):
        raise ValueError(f'Invalid placeholder: {token}')

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
        attributes = artifact_def['attributes']  # name -> list of rules
        artifact_name = artifact_def['artifact_name']

        for attr_name, rules in attributes.items():
            for rule in rules:
                # Forbid definitions of "regular" attributes named 'id'.
                if attr_name == 'id' and not rule.get('id_rule', False):
                    errors.append(
                        f"Artifact '{artifact_name}' has a regular attribute named 'id'. Use 'id is ...' instead."
                    )
                
                # Check condition's anchor
                condition = rule.get('condition')
                if condition:
                    anchor_name = condition['anchor']
                    # Requirement: the attribute shall be boolean
                    # Requirement: the attribute shall not be conditional
                    # If it's boolean, its type_info['type'] is 'boolean'
                    
                    if anchor_name not in attributes:
                        errors.append(f"Artifact '{artifact_name}' has rule for '{attr_name}' with unknown anchor '{anchor_name}'")
                    else:
                        anchor_rules = attributes[anchor_name]
                        # Must have at least one rule that is boolean AND not conditional
                        found_valid_anchor = False
                        for ar in anchor_rules:
                            if ar.get('type_info', {}).get('type') == 'boolean' and ar.get('condition') is None:
                                found_valid_anchor = True
                                break
                        
                        if not found_valid_anchor:
                            errors.append(f"Artifact '{artifact_name}' has rule for '{attr_name}' with invalid anchor '{anchor_name}': must be a non-conditional boolean attribute")

        # id must have at least one mandatory rule (usually only one)
        id_rules = attributes.get('id', [])
        if not id_rules:
            errors.append(f"Artifact '{artifact_name}' is missing an id attribute")
        else:
            has_mandatory_id = any(r.get('presence') == 'mandatory' and r.get('condition') is None for r in id_rules)
            if not has_mandatory_id:
                errors.append(f"Artifact '{artifact_name}' id attribute is not mandatory (or is conditional)")

        # contents must have at least one mandatory rule
        contents_rules = attributes.get('contents', [])
        if not contents_rules:
            errors.append(f"Artifact '{artifact_name}' is missing a contents attribute")
        else:
            has_mandatory_contents = any(r.get('presence') == 'mandatory' and r.get('condition') is None for r in contents_rules)
            if not has_mandatory_contents:
                errors.append(f"Artifact '{artifact_name}' contents attribute is not mandatory (or is conditional)")

    # Validate traces
    for source_atype, rules in metamodel['traces'].items():
        for rule in rules:
            condition = rule.get('condition')
            if condition:
                anchor_name = condition['anchor']
                if source_atype not in metamodel['artifacts']:
                    # Source atype unknown? Should have been caught by target_list or similar if we checked that.
                    continue
                
                source_attrs = metamodel['artifacts'][source_atype]['attributes']
                if anchor_name not in source_attrs:
                    errors.append(f"Trace from '{source_atype}' has unknown anchor '{anchor_name}'")
                else:
                    anchor_rules = source_attrs[anchor_name]
                    found_valid_anchor = False
                    for ar in anchor_rules:
                        if ar.get('type_info', {}).get('type') == 'boolean' and ar.get('condition') is None:
                            found_valid_anchor = True
                            break
                    if not found_valid_anchor:
                        errors.append(f"Trace from '{source_atype}' has invalid anchor '{anchor_name}': must be a non-conditional boolean attribute")
