# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

import logging as lg

from syntagmax.artifact import ArtifactMap, Artifact
from syntagmax.config import Config


class ArtifactValidator:
    def __init__(self, metamodel, errors: list[str] | None = None):
        # Index rules by artifact name for fast lookup
        if metamodel is not None and 'artifacts' in metamodel:
            self._artifacts = metamodel['artifacts']
            self._traces = metamodel.get('traces', {})
        else:
            # Backward compatibility
            self._artifacts = metamodel
            self._traces = {}

        self.errors = errors if errors is not None else []

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

        # 4. Type Conversion and Value Validation
        for name, value in artifact.fields.items():
            if name not in artifact_rules:
                continue  # Already caught by extra_fields check

            type_info = artifact_rules[name]['type_info']
            expected_type = type_info['type']

            # -- INTEGER CHECK --
            if expected_type == 'integer':
                try:
                    int(value)
                except (ValueError, TypeError):
                    self.errors.append(
                        f"Attribute '{name}' value '{value}' cannot be converted to an integer ({artifact})"
                    )

            # -- BOOLEAN CHECK --
            elif expected_type == 'boolean':
                # Analysts use various strings for booleans; we define a strict valid set
                truthy = {'true', 'yes', '1'}
                falsy = {'false', 'no', '0'}
                if value.lower() not in truthy | falsy:
                    self.errors.append(
                        f"Attribute '{name}' value '{value}' is not a valid boolean (expected true/false, yes/no, 1/0) ({artifact})"
                    )

            # -- ENUM CHECK --
            elif expected_type == 'enum':
                allowed = type_info['allowed']
                if value not in allowed:
                    self.errors.append(
                        f"Attribute '{name}' value '{value}' is invalid. Allowed values: {allowed} ({artifact})"
                    )

            # -- REFERENCE CHECK --
            elif expected_type == 'reference':
                if '-' not in value:
                    self.errors.append(
                        f"Attribute '{name}' value '{value}' is a malformed reference (expected TYPE-ID) ({artifact})"
                    )
                else:
                    ref_atype = value.split('-', 1)[0]
                    if ref_atype not in self._artifacts:
                        self.errors.append(
                            f"Attribute '{name}' value '{value}' refers to an unknown artifact type '{ref_atype}' ({artifact})"
                        )

            # -- STRING CHECK --
            # No conversion needed for 'string' as input is already dict[str, str]

    def _validate_traces(self, artifact: Artifact):
        trace_rules = self._traces.get(artifact.atype, [])

        # Filter out ROOT from parents for validation, it's always allowed
        actual_parents = [p for p in artifact.pids if p.atype != 'ROOT']

        # 1. Forbidden undeclared traces
        # Collect all allowed target types from all rules for this artifact type
        allowed_target_types = set()
        for rule in trace_rules:
            allowed_target_types.update(rule['targets'])

        for parent in actual_parents:
            if parent.atype not in allowed_target_types:
                self.errors.append(f"Trace from '{artifact.atype}' to '{parent.atype}' is not allowed ({artifact})")

        # 2. Mandatory traces
        for rule in trace_rules:
            if rule['presence'] == 'mandatory':
                # Check if at least one parent matches any of the targets in this mandatory rule
                targets = set(rule['targets'])
                found = any(p.atype in targets for p in actual_parents)
                if not found:
                    target_str = ' or '.join(f"'{t}'" for t in targets)
                    self.errors.append(f"Missing mandatory trace from '{artifact.atype}' to {target_str} ({artifact})")


def analyse_tree(config: Config, artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []

    validator = ArtifactValidator(config.metamodel, errors)

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
