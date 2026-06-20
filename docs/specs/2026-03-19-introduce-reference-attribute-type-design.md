# Design Document: Introduce "multiple" Attribute Modifier

## 1. Overview
The "multiple" modifier for artifact attributes allows them to store a list of values instead of a single string. This is useful for tags, parent IDs, or any other attribute that can have multiple occurrences.

## 2. Metamodel (DSL)
- `metamodel.lark` grammar will be updated to support the `multiple` keyword in the `rule` definition.
- `rule: "attribute" name "is" PRESENCE ["multiple"] type _NL`
- `metamodel.py` will store `multiple: True/False` in the attribute definition dict.

## 3. Artifact Representation
- `Artifact.fields` will store a `list[str]` for `multiple` attributes and a `str` for non-multiple ones.
- For `optional multiple` attributes that are not provided in the source, the value will be an empty list `[]`.

## 4. Extraction Logic
- `extract()` in `extract.py` will pass `config.metamodel` to all extractors.
- `Extractor` base class will store `self._metamodel`.
- `ArtifactBuilder` will be initialized with `metamodel`.
- `ArtifactBuilder.add_field(field, value)` will:
    - Check the multiplicity of the field in the metamodel for the current artifact type.
    - If `multiple`, append to a list.
    - If not `multiple`, raise `ValidationError` on duplicate.
- `ArtifactBuilder.build()` will ensure `optional multiple` attributes are initialized as `[]` if missing.

### Specific Extractor Changes:
- `TextExtractor`:
    - Update `text.lark` to support arbitrary `NAME=VALUE` directives.
    - `TextTransformer` and `TextExtractor.extract_from_file` will use `builder.add_field` for each directive found.
- `ObsidianExtractor`:
    - Instead of building an `attrs` dict first, it will call `builder.add_field` for each field and YAML attribute.
    - This allows `ArtifactBuilder` to handle multiplicity correctly.

## 5. Validation Logic
- `ArtifactValidator` in `analyse.py` will:
    - Verify that `multiple` attributes contain a list of values.
    - Verify that each element in the list conforms to the expected type (integer, boolean, reference, enum, string).
    - Verify that non-multiple attributes contain a single string.

## 6. Testing Strategy
- Add unit tests to `tests/test_metamodel.py` for the new DSL syntax.
- Add unit tests to `tests/test_extractors.py` for multiple attribute extraction.
- Add unit tests to `tests/test_reference_validation.py` (or a new file) for validation of multiple attributes.

## 7. Documentation
- Update `README.md` with the new syntax and examples.
