# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

import logging as lg
import re

from syntagmax.artifact import ArtifactMap, Artifact
from syntagmax.config import Config

_NUM_PATTERN = re.compile(r'\{num(?::(\d+))?\}')


class ArtifactValidator:
    def __init__(self, metamodel, artifacts: ArtifactMap, errors: list[str] | None = None):
        # Index rules by artifact name for fast lookup
        if metamodel is not None and 'artifacts' in metamodel:
            self._artifacts = metamodel['artifacts']
            self._traces = metamodel.get('traces', {})
        else:
            # Backward compatibility or empty metamodel
            self._artifacts = metamodel if metamodel else {}
            self._traces = {}

        self.errors = errors if errors is not None else []
        self._artifacts_map = artifacts
        self._id_schema_cache = {}

    def validate(self, artifact: Artifact):
        if self._artifacts is None or not self._artifacts:
            return self.errors

        if artifact.atype not in self._artifacts:
            self.errors.append(f"Unknown artifact type: '{artifact.atype}' ({artifact})")
            return self.errors

        self._validate_attributes(artifact)
        self._validate_id_schema(artifact)
        self._validate_traces(artifact)

        return self.errors

    def _evaluate_condition(self, artifact: Artifact, condition: dict | None) -> bool:
        if not condition:
            return True
        
        anchor_name = condition['anchor']
        negated = condition['negated']
        
        value = artifact.fields.get(anchor_name)
        if value is None:
            # if the attribute is absent, the condition evaluates to False
            res = False
        else:
            # the attribute shall be boolean
            truthy = {'true', 'yes', '1'}
            res = str(value).lower() in truthy
        
        return not res if negated else res

    def _validate_id_schema(self, artifact: Artifact):
        artifact_rules = self._artifacts[artifact.atype]['attributes']
        id_rules = artifact_rules.get('id', [])
        if not id_rules:
            return

        if isinstance(id_rules, dict):
            id_rules = [id_rules]

        # Usually only one id rule, but let's be safe
        for rule in id_rules:
            if not self._evaluate_condition(artifact, rule.get('condition')):
                continue

            schema = rule.get('schema')
            if not schema:
                continue

            cache_key = (artifact.atype, schema)
            compiled_pattern = self._id_schema_cache.get(cache_key)

            if compiled_pattern is None:
                # Replace macros in schema with regex patterns
                # {atype} -> artifact.atype
                # {num:padding} -> \d{padding,} or \d+
                pattern = schema.replace('{atype}', artifact.atype)

                final_pattern = ''
                last_pos = 0
                for match in _NUM_PATTERN.finditer(pattern):
                    final_pattern += re.escape(pattern[last_pos : match.start()])
                    padding = match.group(1)
                    if padding:
                        final_pattern += rf'\d{{{padding}}}'
                    else:
                        final_pattern += r'\d+'
                    last_pos = match.end()
                final_pattern += re.escape(pattern[last_pos:])

                final_pattern = f'^{final_pattern}$'
                compiled_pattern = re.compile(final_pattern)
                self._id_schema_cache[cache_key] = compiled_pattern

            if not compiled_pattern.match(artifact.aid):
                self.errors.append(
                    f"Artifact ID '{artifact.aid}' does not match schema '{schema}' for type '{artifact.atype}' ({artifact})"
                )

    def _validate_attributes(self, artifact: Artifact):
        artifact_rules = self._artifacts[artifact.atype]['attributes']
        actual_names = set(artifact.fields.keys())

        # 1. Identify active rules for each attribute
        active_rules_by_name = {}
        for attr_name, rules in artifact_rules.items():
            if isinstance(rules, dict):
                rules = [rules]
            active = [r for r in rules if self._evaluate_condition(artifact, r.get('condition'))]
            if active:
                active_rules_by_name[attr_name] = active

        # 2. Check for Additional Attributes (Strict Mode)
        # An attribute is allowed only if it has at least one active rule.
        all_allowed_names = set(active_rules_by_name.keys())
        extra_fields = actual_names - all_allowed_names
        for extra in extra_fields:
            self.errors.append(f"Attribute '{extra}' is not allowed for artifact '{artifact.atype}' ({artifact})")

        # 3. Check each attribute's rules
        # We only need to check attributes that have rules defined in the metamodel.
        for attr_name, active_rules in active_rules_by_name.items():
            # Check if mandatory and missing
            is_mandatory = any(r['presence'] == 'mandatory' for r in active_rules)
            if is_mandatory and attr_name not in actual_names:
                self.errors.append(f"Missing mandatory attribute: '{attr_name}' ({artifact})")
                continue
            
            if attr_name not in actual_names:
                continue
            
            value = artifact.fields[attr_name]
            
            for rule in active_rules:
                self._check_rule(artifact, attr_name, value, rule)

    def _check_rule(self, artifact: Artifact, attr_name: str, value, rule: dict):
        is_multiple = rule.get('multiple', False)
        type_info = rule['type_info']

        if is_multiple:
            if not isinstance(value, list):
                self.errors.append(f"Attribute '{attr_name}' must be a list (multiple=True) ({artifact})")
            else:
                for item in value:
                    self._check_type(artifact, item, type_info, attr_name)
        else:
            if isinstance(value, list):
                self.errors.append(f"Attribute '{attr_name}' must not be a list (multiple=False) ({artifact})")
            else:
                self._check_type(artifact, value, type_info, attr_name)

    def _check_type(self, artifact: Artifact, val, type_info: dict, attr_name: str):
        expected_type = type_info['type']

        if expected_type == 'integer':
            try:
                int(val)
            except (ValueError, TypeError):
                self.errors.append(
                    f"Attribute '{attr_name}' value '{val}' cannot be converted to an integer ({artifact})"
                )

        elif expected_type == 'boolean':
            truthy = {'true', 'yes', '1'}
            falsy = {'false', 'no', '0'}
            if str(val).lower() not in truthy | falsy:
                self.errors.append(
                    f"Attribute '{attr_name}' value '{val}' is not a valid boolean (expected true/false, yes/no, 1/0) ({artifact})"
                )

        elif expected_type == 'enum':
            allowed = type_info['allowed']
            if val not in allowed:
                self.errors.append(
                    f"Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed} ({artifact})"
                )

        elif expected_type == 'reference':
            if not isinstance(val, str):
                self.errors.append(
                    f"Attribute '{attr_name}' value '{val}' is a malformed reference (expected ID string) ({artifact})"
                )
            else:
                aid = val.split('@')[0] if '@' in val else val
                ref_artifact = self._artifacts_map.get(aid)
                if not ref_artifact:
                    self.errors.append(
                        f"Attribute '{attr_name}' value '{val}' refers to an unknown artifact ID '{aid}' ({artifact})"
                    )
                elif ref_artifact.atype not in self._artifacts:
                    self.errors.append(
                        f"Attribute '{attr_name}' value '{val}' refers to an artifact with unknown type '{ref_artifact.atype}' ({artifact})"
                    )

    def _validate_traces(self, artifact: Artifact):
        all_trace_rules = self._traces.get(artifact.atype, [])
        
        # Evaluate conditions on the FROM artifact
        active_trace_rules = [r for r in all_trace_rules if self._evaluate_condition(artifact, r.get('condition'))]

        # Look up parents to get their types
        actual_parents = []
        for pid in artifact.pids:
            if pid == 'ROOT':
                continue
            parent_artifact = self._artifacts_map.get(pid)
            if parent_artifact:
                actual_parents.append(parent_artifact)

        # 1. Forbidden undeclared traces (against ALL rules, or just active ones?)
        # User said: "Example A: trace from REQ to SYS is mandatory if not derived; trace from REQ to SYS is optional"
        # If 'derived' is true, only 'optional' rule is active.
        # If 'derived' is false, both 'mandatory' and 'optional' are active.
        # It's safer to check forbidden traces against ALL possible rules for this source atype.
        allowed_target_types = set()
        for rule in all_trace_rules:
            allowed_target_types.update(rule['targets'])

        for parent in actual_parents:
            if parent.atype not in allowed_target_types:
                self.errors.append(f"Trace from '{artifact.atype}' to '{parent.atype}' is not allowed ({artifact})")

        # 2. Mandatory traces and Mode validation
        for rule in active_trace_rules:
            targets = set(rule['targets'])
            mode = rule.get('mode', 'timestamp')

            found = False
            for parent in actual_parents:
                if parent.atype in targets:
                    found = True
                    # Validate mode
                    link = next((pl for pl in artifact.parent_links if pl.pid == parent.aid), None)
                    if link:
                        if (
                            mode == 'timestamp'
                            and link.nominal_revision != 'older'
                            and link.nominal_revision is not None
                        ):
                            self.errors.append(
                                f"Trace from '{artifact.atype}' to '{parent.atype}' is 'by timestamp', "
                                f"but revision was specified: '{link.pid}@{link.nominal_revision}' ({artifact})"
                            )
                        if mode == 'commit' and (link.nominal_revision is None or link.nominal_revision == 'older'):
                            self.errors.append(
                                f"Trace from '{artifact.atype}' to '{parent.atype}' is 'by commit', "
                                f"but no revision was specified for parent '{parent.aid}' ({artifact})"
                            )

            if rule['presence'] == 'mandatory' and not found:
                target_str = ' or '.join(f"'{t}'" for t in targets)
                self.errors.append(f"Missing mandatory trace from '{artifact.atype}' to {target_str} ({artifact})")


def analyse_tree(config: Config, artifacts: ArtifactMap, errors: list[str]):
    validator = ArtifactValidator(config.metamodel, artifacts, errors)

    for artifact in artifacts.values():
        # Skipping the root pseudo-artifact
        if artifact.atype == 'ROOT':
            continue

        lg.info(f'Validating artifact: {artifact}')
        validator.validate(artifact)

    # Ensure there is only one ROOT
    root_count = 0

    for a in artifacts.values():
        if a.atype == 'ROOT':
            root_count += 1

    if root_count != 1:
        errors.append('Must have exactly one root artifact')
