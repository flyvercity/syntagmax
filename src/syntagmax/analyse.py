# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

import logging as lg

from syntagmax.artifact import ArtifactMap, Artifact
from syntagmax.config import Config
from syntagmax.i18n import _
from syntagmax.id_utils import compile_id_schema
from syntagmax.metamodel import evaluate_condition
from syntagmax.report import ReportError, CAT_SCHEMA, CAT_ATTRIBUTE, CAT_REFERENCE, CAT_TRACE, CAT_STRUCTURE

# OPTIMIZATION: Module-level precomputed constants to avoid set creation and formatting overhead in boolean type checks
_DEFAULT_BOOL_TRUTHY = {'true', 'yes', '1'}
_DEFAULT_BOOL_FALSY = {'false', 'no', '0'}
_DEFAULT_BOOL_ALLOWED = _DEFAULT_BOOL_TRUTHY | _DEFAULT_BOOL_FALSY


class ArtifactValidator:
    def __init__(self, metamodel, artifacts: ArtifactMap, errors: list | None = None, suppress_tracing: bool = False):
        # Index rules by artifact name for fast lookup
        if metamodel is not None and 'artifacts' in metamodel:
            self._artifacts = metamodel['artifacts']
            self._traces = metamodel.get('traces', {})
        else:
            # Backward compatibility or empty metamodel
            self._artifacts = metamodel if metamodel else {}
            self._traces = {}

        self._metamodel_dict = {'artifacts': self._artifacts, 'traces': self._traces}

        self.errors = errors if errors is not None else []
        self._artifacts_map = artifacts
        self._id_schema_cache = {}
        self._suppress_tracing = suppress_tracing

    def _make_error(self, artifact: Artifact, message: str, category: str) -> ReportError:
        from syntagmax.artifact import LineLocation

        file_path = artifact.location.filepath() if artifact.location else None
        line_range = None
        if isinstance(artifact.location, LineLocation):
            line_range = artifact.location.loc_lines
        return ReportError(
            message=message,
            category=category,
            input_record=artifact.record.name if artifact.record else None,
            artifact_id=artifact.aid,
            artifact_type=artifact.atype,
            file_path=file_path,
            line_range=line_range,
        )

    def validate(self, artifact: Artifact):
        if self._artifacts is None or not self._artifacts:
            return self.errors

        if artifact.atype not in self._artifacts:
            self.errors.append(self._make_error(artifact, _("Unknown artifact type: '{atype}'").format(atype=artifact.atype), CAT_ATTRIBUTE))
            return self.errors

        self._validate_attributes(artifact)
        self._validate_id_schema(artifact)
        if not self._suppress_tracing:
            self._validate_traces(artifact)

        return self.errors

    def _evaluate_condition(self, artifact: Artifact, condition: dict | None) -> bool:
        if not condition:
            return True

        # OPTIMIZATION: Reuse precomputed metamodel dict reference to avoid dictionary creation on every condition evaluation
        return evaluate_condition(artifact.fields, artifact.atype, condition, self._metamodel_dict)

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

            cache_key = (schema, artifact.atype)
            compiled_pattern = self._id_schema_cache.get(cache_key)

            if compiled_pattern is None:
                compiled_pattern = compile_id_schema(schema, artifact.atype)
                self._id_schema_cache[cache_key] = compiled_pattern

            if not compiled_pattern.match(artifact.aid):
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Artifact ID '{aid}' does not match schema '{schema}' for type '{atype}'").format(
                            aid=artifact.aid, schema=schema, atype=artifact.atype
                        ),
                        CAT_SCHEMA,
                    )
                )

    def _validate_attributes(self, artifact: Artifact):
        artifact_rules = self._artifacts[artifact.atype]['attributes']

        # 1. Identify active rules for each attribute
        active_rules_by_name = self._get_active_rules(artifact, artifact_rules)

        # 2. Check for Additional Attributes (Strict Mode)
        self._check_extra_attributes(artifact, active_rules_by_name)

        # 3. Check each attribute's rules
        self._check_attribute_requirements(artifact, active_rules_by_name)

    def _get_active_rules(self, artifact: Artifact, artifact_rules: dict) -> dict[str, list[dict]]:
        active_rules_by_name = {}
        for attr_name, rules in artifact_rules.items():
            if isinstance(rules, dict):
                rules = [rules]
            # OPTIMIZATION: Short-circuit rule evaluation when condition is None, avoiding method call overhead
            active = []
            for r in rules:
                cond = r.get('condition')
                if cond is None or self._evaluate_condition(artifact, cond):
                    active.append(r)
            if active:
                active_rules_by_name[attr_name] = active
        return active_rules_by_name

    def _check_extra_attributes(self, artifact: Artifact, active_rules_by_name: dict[str, list[dict]]):
        # OPTIMIZATION: Direct key lookup on active_rules_by_name dict avoids temporary set allocations
        for extra in artifact.fields:
            if extra not in active_rules_by_name:
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Attribute '{attr_name}' is not allowed for artifact '{atype}'").format(attr_name=extra, atype=artifact.atype),
                        CAT_ATTRIBUTE,
                    )
                )

    def _check_attribute_requirements(self, artifact: Artifact, active_rules_by_name: dict[str, list[dict]]):
        fields = artifact.fields
        for attr_name, active_rules in active_rules_by_name.items():
            # OPTIMIZATION: Loop replaces generator expression in mandatory check, eliminating generator allocation overhead
            is_mandatory = False
            for r in active_rules:
                if r.get('presence') == 'mandatory':
                    is_mandatory = True
                    break

            if is_mandatory and attr_name not in fields:
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Missing mandatory attribute: '{attr_name}'").format(attr_name=attr_name),
                        CAT_ATTRIBUTE,
                    )
                )
                continue

            if attr_name not in fields:
                continue

            value = fields[attr_name]

            for rule in active_rules:
                self._check_rule(artifact, attr_name, value, rule)

    def _check_rule(self, artifact: Artifact, attr_name: str, value, rule: dict):
        is_multiple = rule.get('multiple', False)
        type_info = rule['type_info']

        if is_multiple:
            if not isinstance(value, list):
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Attribute '{attr_name}' must be a list (multiple=True)").format(attr_name=attr_name),
                        CAT_ATTRIBUTE,
                    )
                )
            else:
                for item in value:
                    self._check_type(artifact, item, type_info, attr_name)
        else:
            if isinstance(value, list):
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Attribute '{attr_name}' must not be a list (multiple=False)").format(attr_name=attr_name),
                        CAT_ATTRIBUTE,
                    )
                )
            else:
                self._check_type(artifact, value, type_info, attr_name)

    def _check_type(self, artifact: Artifact, val, type_info: dict, attr_name: str):
        expected_type = type_info['type']

        if expected_type == 'integer':
            # OPTIMIZATION: Direct type check for Python int bypasses try-except block
            if type(val) is int:
                return
            try:
                int(val)
            except (ValueError, TypeError):
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Attribute '{attr_name}' value '{val}' cannot be converted to an integer").format(attr_name=attr_name, val=val),
                        CAT_ATTRIBUTE,
                    )
                )

        elif expected_type == 'boolean':
            # OPTIMIZATION: Early return if already a Python boolean avoids set building and string operations
            if isinstance(val, bool):
                return

            if 'custom_values' in type_info:
                truthy = {v.lower() for v in type_info['custom_values']['true']}
                falsy = {v.lower() for v in type_info['custom_values']['false']}
                allowed = truthy | falsy
                expected_str = _('expected {true_vals} / {false_vals}').format(
                    true_vals=', '.join(type_info['custom_values']['true']), false_vals=', '.join(type_info['custom_values']['false'])
                )
            else:
                allowed = _DEFAULT_BOOL_ALLOWED
                expected_str = _('expected true/false, yes/no, 1/0')

            if str(val).lower() not in allowed:
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Attribute '{attr_name}' value '{val}' is not a valid boolean ({expected})").format(
                            attr_name=attr_name, val=val, expected=expected_str
                        ),
                        CAT_ATTRIBUTE,
                    )
                )

        elif expected_type == 'enum':
            allowed = type_info['allowed']
            if val not in allowed:
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed}").format(attr_name=attr_name, val=val, allowed=allowed),
                        CAT_ATTRIBUTE,
                    )
                )

        elif expected_type == 'reference':
            if not isinstance(val, str):
                msg = _("Attribute '{attr_name}' value '{val}' is a malformed reference (expected ID string)").format(attr_name=attr_name, val=val)
                if self._suppress_tracing:
                    lg.warning(msg)
                else:
                    self.errors.append(self._make_error(artifact, msg, CAT_REFERENCE))
            else:
                aid = val.split('@')[0] if '@' in val else val
                ref_artifact = self._artifacts_map.get(aid)
                if not ref_artifact:
                    msg = _("Attribute '{attr_name}' value '{val}' refers to an unknown artifact ID '{aid}'").format(attr_name=attr_name, val=val, aid=aid)
                    if self._suppress_tracing:
                        lg.warning(msg)
                    else:
                        self.errors.append(self._make_error(artifact, msg, CAT_REFERENCE))
                elif ref_artifact.atype not in self._artifacts:
                    msg = _("Attribute '{attr_name}' value '{val}' refers to an artifact with unknown type '{atype}'").format(
                        attr_name=attr_name, val=val, atype=ref_artifact.atype
                    )
                    if self._suppress_tracing:
                        lg.warning(msg)
                    else:
                        self.errors.append(self._make_error(artifact, msg, CAT_REFERENCE))

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

        # 1. Forbidden undeclared traces
        allowed_target_types = set()
        for rule in active_trace_rules:
            allowed_target_types.update(rule['targets'])

        for parent in actual_parents:
            if parent.atype not in allowed_target_types:
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Trace from '{from_type}' to '{to_type}' is not allowed").format(from_type=artifact.atype, to_type=parent.atype),
                        CAT_TRACE,
                    )
                )

        # 2. Mandatory traces and Mode validation
        for rule in active_trace_rules:
            targets = set(rule['targets'])
            mode = rule.get('mode', 'timestamp')

            found = False
            for parent in actual_parents:
                if parent.atype in targets:
                    found = True
                    # Validate mode
                    # OPTIMIZATION: Avoid generator allocation overhead in hot trace validation loop
                    link = None
                    for pl in artifact.parent_links:
                        if pl.pid == parent.aid:
                            link = pl
                            break
                    if link:
                        if mode == 'timestamp' and link.nominal_revision != 'older' and link.nominal_revision is not None:
                            self.errors.append(
                                self._make_error(
                                    artifact,
                                    _("Trace from '{from_type}' to '{to_type}' is 'by timestamp', but revision was specified: '{ref}'").format(
                                        from_type=artifact.atype, to_type=parent.atype, ref=f'{link.pid}@{link.nominal_revision}'
                                    ),
                                    CAT_TRACE,
                                )
                            )
                        if mode == 'commit' and (link.nominal_revision is None or link.nominal_revision == 'older'):
                            self.errors.append(
                                self._make_error(
                                    artifact,
                                    _("Trace from '{from_type}' to '{to_type}' is 'by commit', but no revision was specified for parent '{parent_aid}'").format(
                                        from_type=artifact.atype, to_type=parent.atype, parent_aid=parent.aid
                                    ),
                                    CAT_TRACE,
                                )
                            )

            if rule.get('presence') == 'mandatory' and not found:
                target_str = ' or '.join(f"'{t}'" for t in targets)
                self.errors.append(
                    self._make_error(
                        artifact,
                        _("Missing mandatory trace from '{from_type}' to {targets}").format(from_type=artifact.atype, targets=target_str),
                        CAT_TRACE,
                    )
                )


def analyse_tree(config: Config, artifacts: ArtifactMap, errors: list):
    suppress = config.params.get('suppress_tracing', False)
    validator = ArtifactValidator(config.metamodel, artifacts, errors, suppress_tracing=suppress)

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
        errors.append(ReportError(message=_('Must have exactly one root artifact'), category=CAT_STRUCTURE))
