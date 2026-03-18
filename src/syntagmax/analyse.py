# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

from syntagmax.artifact import ArtifactMap, Artifact
from syntagmax.config import Config


class ArtifactValidator:
    def __init__(self, metamodel, errors: list[str] = []):
        # Index rules by artifact name for fast lookup
        self._metamodel = metamodel
        self.errors = errors

    def validate(self, artifact: Artifact):
        if artifact.atype not in self._metamodel:
            return [f"Unknown artifact type: '{artifact.atype}'"]

        artifact_rules = self._metamodel[artifact.atype]['attributes']

        # 1. Map rules by attribute name
        rule_map = {r['name']: r for r in artifact_rules}
        mandatory_names = {r['name'] for r in artifact_rules if r['presence'] == 'mandatory'}
        all_allowed_names = set(rule_map.keys())

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
            if name not in rule_map:
                continue  # Already caught by extra_fields check

            type_info = rule_map[name]['type_info']
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

            # -- STRING CHECK --
            # No conversion needed for 'string' as input is already dict[str, str]

        return self.errors


def analyse_tree(config: Config, artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []
    validator = ArtifactValidator(config.metamodel, errors)

    for artifact in artifacts.values():
        validator.validate(artifact)

    errors.extend(check_single_root(artifacts))
    return errors


def check_single_root(artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []
    root_count = 0
    for a in artifacts.values():
        if a.atype == 'ROOT':
            root_count += 1

    if root_count != 1:
        errors.append('Must have exactly one root artifact')

    return errors
