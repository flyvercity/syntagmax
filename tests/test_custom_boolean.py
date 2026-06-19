# SPDX-License-Identifier: MIT
from syntagmax.analyse import ArtifactValidator
from syntagmax.artifact import Artifact, FileLocation
from syntagmax.metamodel import load_metamodel

def test_custom_boolean_parsing(tmp_path):
    model_file = tmp_path / "model.syntagmax"
    model_file.write_text("""
artifact REQ:
    id is string
    attribute active is mandatory boolean [true: "yes", "on", false: "no", "off"]
    attribute contents is mandatory string
""", encoding="utf-8")

    errors = []
    metamodel = load_metamodel(model_file, errors)
    assert not errors

    attr_rules = metamodel['artifacts']['REQ']['attributes']['active']
    assert len(attr_rules) == 1
    type_info = attr_rules[0]['type_info']
    assert type_info['type'] == 'boolean'
    assert type_info['custom_values'] == {'true': ['yes', 'on'], 'false': ['no', 'off']}

def test_custom_boolean_validation(tmp_path):
    model_file = tmp_path / "model.syntagmax"
    model_file.write_text("""
artifact REQ:
    id is string
    attribute active is mandatory boolean [true: "yes", "on", false: "no", "off"]
    attribute contents is mandatory string
""", encoding="utf-8")

    errors = []
    metamodel = load_metamodel(model_file, errors)

    # Valid values
    for val in ["yes", "on", "no", "off", "YES", "Off"]:
        art = Artifact(None)
        art.atype = "REQ"
        art.aid = "R1"
        art.fields = {"id": "R1", "active": val, "contents": "hello"}
        art.location = FileLocation("f1.md")

        validator = ArtifactValidator(metamodel, {"R1": art})
        val_errors = validator.validate(art)
        assert not val_errors, f"Value {val} should be valid"

    # Invalid values
    for val in ["true", "false", "1", "0", "maybe"]:
        art = Artifact(None)
        art.atype = "REQ"
        art.aid = "R1"
        art.fields = {"id": "R1", "active": val, "contents": "hello"}
        art.location = FileLocation("f1.md")

        validator = ArtifactValidator(metamodel, {"R1": art})
        val_errors = validator.validate(art)
        assert val_errors, f"Value {val} should be invalid"
        assert "is not a valid boolean (expected yes, on / no, off)" in val_errors[0]

def test_custom_boolean_condition(tmp_path):
    model_file = tmp_path / "model.syntagmax"
    model_file.write_text("""
artifact REQ:
    id is string
    attribute active is mandatory boolean [true: "yes", false: "no"]
    attribute note is optional string if active
    attribute contents is mandatory string
""", encoding="utf-8")

    errors = []
    metamodel = load_metamodel(model_file, errors)

    # Condition met (active=yes)
    art1 = Artifact(None)
    art1.atype = "REQ"
    art1.aid = "R1"
    art1.fields = {"id": "R1", "active": "yes", "note": "active note", "contents": "hello"}
    art1.location = FileLocation("f1.md")
    validator1 = ArtifactValidator(metamodel, {"R1": art1})
    assert not validator1.validate(art1)

    # Condition not met (active=no), so 'note' is not allowed
    art2 = Artifact(None)
    art2.atype = "REQ"
    art2.aid = "R2"
    art2.fields = {"id": "R2", "active": "no", "note": "should not be here", "contents": "hello"}
    art2.location = FileLocation("f1.md")
    validator2 = ArtifactValidator(metamodel, {"R2": art2})
    val_errors2 = validator2.validate(art2)
    assert any("Attribute 'note' is not allowed" in e for e in val_errors2)

    # Standard boolean should NOT work if custom ones are defined
    art3 = Artifact(None)
    art3.atype = "REQ"
    art3.aid = "R3"
    art3.fields = {"id": "R3", "active": "true", "note": "active note", "contents": "hello"}
    art3.location = FileLocation("f1.md")
    validator3 = ArtifactValidator(metamodel, {"R3": art3})
    val_errors3 = validator3.validate(art3)
    # active=true is invalid boolean -> condition evaluates to False -> note not allowed
    assert any("active' value 'true' is not a valid boolean" in e for e in val_errors3)
    assert any("Attribute 'note' is not allowed" in e for e in val_errors3)
