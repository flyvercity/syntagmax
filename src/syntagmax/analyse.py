# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

import logging as lg

from syntagmax.artifact import ArtifactMap, Artifact
from syntagmax.config import Config


class ArtifactValidator:
    def __init__(self, metamodel, artifacts: ArtifactMap, errors: list[str] | None = None):
        # Index rules by artifact name for fast lookup
        if metamodel is not None and 'artifacts' in metamodel:
            self._artifacts = metamodel['artifacts']
            self._traces = metamodel.get('traces', {})
        else:
            # Backward compatibility
            self._artifacts = metamodel
            self._traces = {}

        self.errors = errors if errors is not None else []
        self._artifacts_map = artifacts

    def validate(self, artifact: Artifact):
        if self._artifacts is None:
            return self.errors

        if artifact.atype not in self._artifacts:
            self.errors.append(f"Unknown artifact type: '{artifact.atype}' ({artifact})")
            return self.errors

        self._validate_attributes(artifact)
        self._validate_traces(artifact)

        return self.errors

    def _validate_attributes(self, artifact: Artifact):
        artifact_rules = self._artifacts[artifact.atype]['attributes']

        # 1. Map rules by attribute name
        mandatory_names = {r['name'] for r in artifact_rules.values() if r['presence'] == 'mandatory'}
        all_allowed_names = set(artifact_rules.keys())

        # 2. Check for Additional Attributes (Strict Mode)
        actual_names = set(artifact.fields.keys())
        extra_fields = actual_names - all_allowed_names
        for extra in extra_fields:
            self.errors.append(f"Attribute '{extra}' is not allowed for artifact '{artifact.atype}' ({artifact})")

        # 3. Check for Mandatory Attributes
        missing_mandatory = mandatory_names - actual_names
        for missing in missing_mandatory:
            self.errors.append(f"Missing mandatory attribute: '{missing}' ({artifact})")

        # 4. Multiplicity and Type Validation
        def _check_type(val, type_info, attr_name):
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
                    # Look up the referenced artifact by ID
                    # Some refs might be TYPE-ID or ID@REVISION, so extract just ID
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

        for name, value in artifact.fields.items():
            if name not in artifact_rules:
                continue

            rule = artifact_rules[name]
            is_multiple = rule.get('multiple', False)
            type_info = rule['type_info']

            # Multiplicity check
            if is_multiple:
                if not isinstance(value, list):
                    self.errors.append(f"Attribute '{name}' must be a list (multiple=True) ({artifact})")
                else:
                    for item in value:
                        _check_type(item, type_info, name)
            else:
                if isinstance(value, list):
                    self.errors.append(f"Attribute '{name}' must not be a list (multiple=False) ({artifact})")
                else:
                    _check_type(value, type_info, name)

    def _validate_traces(self, artifact: Artifact):
        trace_rules = self._traces.get(artifact.atype, [])

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
        for rule in trace_rules:
            allowed_target_types.update(rule['targets'])

        for parent in actual_parents:
            if parent.atype not in allowed_target_types:
                self.errors.append(f"Trace from '{artifact.atype}' to '{parent.atype}' is not allowed ({artifact})")

        # 2. Mandatory traces and Mode validation
        for rule in trace_rules:
            targets = set(rule['targets'])
            mode = rule.get('mode', 'timestamp')

            found = False
            for parent in actual_parents:
                if parent.atype in targets:
                    found = True
                    # Validate mode
                    # Find the link in parent_links
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


def analyse_tree(config: Config, artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []

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

    return errors
