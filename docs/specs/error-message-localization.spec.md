# Error Message Localization — Implementation Specification

## Problem Statement

While the i18n infrastructure for report headers and labels is fully functional (via `i18n.py`, `change_render.py`, `report.j2`), the actual error messages that appear in analysis reports remain hardcoded in English. Additionally, 5 AI Analysis strings in `report.j2` have no catalog entries, and one orphaned entry exists. Users running `--lang ru` see Russian section headers but English error bodies — an inconsistent experience.

## Requirements

- Localize all error message templates across the analysis pipeline: `analyse.py`, `tree.py`, `extract.py`, `metrics.py`, `artifact.py`, and all extractor modules (`extractors/*.py`)
- Use proper gettext format strings (`_("template {name}").format(name=val)`) so translators can reorder placeholders for grammatical correctness
- Add the 5 missing AI Analysis strings (`AI Analysis`, `Ambiguity`, `Completeness`, `Verifiability`, `Singularity`) to both `.po` catalogs
- Remove the orphaned `msgid "errors"` entry
- Provide complete Russian translations for all new entries
- Recompile `.mo` catalogs
- Update `babel.cfg` to extract from all source files that now use `_()`
- Add tests verifying localized error rendering
- Existing English behavior must be byte-for-byte identical (regression safety)

## Background

- `i18n.py` exposes `setup_i18n(language)`, `_()`, `get_translations()` — fully functional
- Currently only `change_render.py`, `report.py`, and `report.j2` import `_()` from `syntagmax.i18n`
- Error-producing modules have no i18n usage whatsoever
- Error messages use f-strings with interpolated artifact IDs, file paths, attribute names, values, and exception messages
- The `.po` catalogs have 85 entries; this spec adds ~40 new ones
- `babel.cfg` currently extracts only from `change_render.py`, `report.py`, and `resources/*.j2`
- `report.j2` has an `{% if report.ai_results %}` section using `_("AI Analysis")` etc. but the strings have no catalog entry
- `msgid "errors"` (lowercase) is in both catalogs but never referenced in code

## Design Decisions

1. **Format-string gettext** — All error messages with dynamic data use `_("Message with {placeholder}").format(placeholder=value)`. This gives translators full control over word order. Placeholders use descriptive names (`{attr_name}`, `{atype}`, `{aid}`), not positional indices.
2. **Translate at point of creation** — Errors are translated when the `ReportError` is constructed (or when the `ErrorBlock.message` is set), not at render time. This is simpler and consistent with the existing architecture where `Report.render()` just formats pre-built error objects.
3. **Driver prefix preserved** — Sidecar/text driver errors use a format like `'{driver} :: {message}'`. The driver name stays untranslated (it's a technical identifier), but the message portion is localized.
4. **Exception messages stay English** — When an error wraps a Python exception (`{e}`), the exception text is not translated (it comes from libraries). The surrounding template is translated.
5. **Single catalog** — All new strings go into the existing `messages` domain. No new domains needed.
6. **babel.cfg expanded** — Add extraction rules for all Python files that now use `_()`.


## Proposed Solution

### Scope

| Module | Error templates | Category |
|--------|----------------|----------|
| `analyse.py` | ~15 | Metamodel validation (attribute, schema, reference, trace) |
| `tree.py` | 3 | Tree building (circular refs, conflicting revisions, link errors) |
| `extract.py` | 2 | Extraction (missing ID, duplicates) |
| `metrics.py` | 1 | Metrics (no requirements found) |
| `artifact.py` | 5 | Builder validation (duplicate AID/field, missing required fields) |
| `extractors/markdown.py` | 7 | Obsidian driver (NBSP, YAML, parse errors) |
| `extractors/sidecar.py` | 7 | Sidecar driver (orphaned, missing, malformed) |
| `extractors/text.py` | 1 (template) | Text driver (format_error wrapper) |
| `extractors/simple_markdown.py` | 1 | Simple markdown driver (malformed YAML) |
| `extractors/markdown_markers.py` | 1 | Marker extractor (invalid block ID) |
| `extractors/ipynb.py` | 1 | IPython notebook driver |
| `report.j2` | 5 (missing) | AI Analysis section headers |
| **Total** | **~49** | |

### Pattern

Before:
```python
self.errors.append(self._make_error(
    artifact,
    f"Missing mandatory attribute: '{attr_name}'",
    CAT_ATTRIBUTE,
))
```

After:
```python
from syntagmax.i18n import _

self.errors.append(self._make_error(
    artifact,
    _("Missing mandatory attribute: '{attr_name}'").format(attr_name=attr_name),
    CAT_ATTRIBUTE,
))
```

### babel.cfg Update

```ini
[python: src/syntagmax/analyse.py]
[python: src/syntagmax/tree.py]
[python: src/syntagmax/extract.py]
[python: src/syntagmax/metrics.py]
[python: src/syntagmax/artifact.py]
[python: src/syntagmax/extractors/*.py]
[python: src/syntagmax/change_render.py]
[python: src/syntagmax/report.py]
[jinja2: src/syntagmax/resources/*.j2]
encoding = utf-8
silent = false
```


---

## Task Breakdown

### Task 1: Localize `analyse.py` — Metamodel Validation Errors

**Objective:** Convert all ~15 error message templates in `ArtifactValidator` to gettext format strings.

**Implementation:**
- Add `from syntagmax.i18n import _` at the top of `analyse.py`
- Convert each f-string error to `_("...").format(...)`:

| Original | Localized |
|----------|-----------|
| `f"Unknown artifact type: '{artifact.atype}'"` | `_("Unknown artifact type: '{atype}'").format(atype=artifact.atype)` |
| `f"Artifact ID '{artifact.aid}' does not match schema '{schema}' for type '{artifact.atype}'"` | `_("Artifact ID '{aid}' does not match schema '{schema}' for type '{atype}'").format(aid=artifact.aid, schema=schema, atype=artifact.atype)` |
| `f"Attribute '{extra}' is not allowed for artifact '{atype}'"` | `_("Attribute '{attr_name}' is not allowed for artifact '{atype}'").format(attr_name=extra, atype=artifact.atype)` |
| `f"Missing mandatory attribute: '{attr_name}'"` | `_("Missing mandatory attribute: '{attr_name}'").format(attr_name=attr_name)` |
| `f"Attribute '{attr_name}' must be a list (multiple=True)"` | `_("Attribute '{attr_name}' must be a list (multiple=True)").format(attr_name=attr_name)` |
| `f"Attribute '{attr_name}' must not be a list (multiple=False)"` | `_("Attribute '{attr_name}' must not be a list (multiple=False)").format(attr_name=attr_name)` |
| `f"Attribute '{attr_name}' value '{val}' cannot be converted to an integer"` | `_("Attribute '{attr_name}' value '{val}' cannot be converted to an integer").format(attr_name=attr_name, val=val)` |
| `f"Attribute '{attr_name}' value '{val}' is not a valid boolean ({expected_str})"` | `_("Attribute '{attr_name}' value '{val}' is not a valid boolean ({expected})").format(attr_name=attr_name, val=val, expected=expected_str)` |
| `f"Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed}"` | `_("Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed}").format(attr_name=attr_name, val=val, allowed=allowed)` |
| `f"Attribute '{attr_name}' value '{val}' is a malformed reference (expected ID string)"` | `_("Attribute '{attr_name}' value '{val}' is a malformed reference (expected ID string)").format(attr_name=attr_name, val=val)` |
| `f"Attribute '{attr_name}' value '{val}' refers to an unknown artifact ID '{aid}'"` | `_("Attribute '{attr_name}' value '{val}' refers to an unknown artifact ID '{aid}'").format(attr_name=attr_name, val=val, aid=aid)` |
| `f"Attribute '{attr_name}' value '{val}' refers to an artifact with unknown type '{atype}'"` | `_("Attribute '{attr_name}' value '{val}' refers to an artifact with unknown type '{atype}'").format(attr_name=attr_name, val=val, atype=ref_artifact.atype)` |
| `f"Trace from '{artifact.atype}' to '{parent.atype}' is not allowed"` | `_("Trace from '{from_type}' to '{to_type}' is not allowed").format(from_type=artifact.atype, to_type=parent.atype)` |
| `f"Trace from '{artifact.atype}' to '{parent.atype}' is 'by timestamp', but revision was specified: '{link.pid}@{link.nominal_revision}'"` | `_("Trace from '{from_type}' to '{to_type}' is 'by timestamp', but revision was specified: '{ref}'").format(from_type=artifact.atype, to_type=parent.atype, ref=f'{link.pid}@{link.nominal_revision}')` |
| `f"Trace from '{artifact.atype}' to '{parent.atype}' is 'by commit', but no revision was specified for parent '{parent.aid}'"` | `_("Trace from '{from_type}' to '{to_type}' is 'by commit', but no revision was specified for parent '{parent_aid}'").format(from_type=artifact.atype, to_type=parent.atype, parent_aid=parent.aid)` |
| `f"Missing mandatory trace from '{artifact.atype}' to {target_str}"` | `_("Missing mandatory trace from '{from_type}' to {targets}").format(from_type=artifact.atype, targets=target_str)` |
| `'Must have exactly one root artifact'` | `_("Must have exactly one root artifact")` |

**Test requirements:**
- All existing validation tests in `tests/test_metamodel*.py` pass unchanged
- New test: with `setup_i18n('ru')`, call `ArtifactValidator.validate()` on an artifact missing a mandatory attribute → error message is in Russian
- New test: with `setup_i18n('en')`, same scenario → English output identical to current behavior

**Demo:** `syntagmax --lang ru analyze` shows `"Отсутствует обязательный атрибут: 'status'"` instead of `"Missing mandatory attribute: 'status'"`.


---

### Task 2: Localize `tree.py` and `extract.py` — Tree Building and Extraction Errors

**Objective:** Localize ~5 error message templates in tree construction and artifact map building.

**Implementation:**
- Add `from syntagmax.i18n import _` to both `tree.py` and `extract.py`
- `tree.py` conversions:

| Original | Localized |
|----------|-----------|
| `f"Conflicting nominal revisions for parent '{aid}' in artifact '{a.aid}': '{existing.nominal_revision}' vs '{nominal_revision}'"` | `_("Conflicting nominal revisions for parent '{parent_id}' in artifact '{artifact_id}': '{existing}' vs '{nominal}'").format(parent_id=aid, artifact_id=a.aid, existing=existing_link.nominal_revision, nominal=nominal_revision)` |
| `f"Error processing parent link '{actual_ref}' for artifact '{a.aid}': {e}"` | `_("Error processing parent link '{ref}' for artifact '{artifact_id}': {error}").format(ref=actual_ref, artifact_id=a.aid, error=str(e))` |
| `f'Circular reference detected with {artifacts[ref].aid}'` | `_("Circular reference detected with {aid}").format(aid=artifacts[ref].aid)` |

- `extract.py` conversions:

| Original | Localized |
|----------|-----------|
| `f'Artifact {a.atype} at {a.location} has no ID'` | `_("Artifact {atype} at {location} has no ID").format(atype=a.atype, location=a.location)` |
| `f'Duplicate artifact ID: {a.aid} at {a.location} (already defined at {artifacts[a.aid].location})'` | `_("Duplicate artifact ID: {aid} at {location} (already defined at {other_location})").format(aid=a.aid, location=a.location, other_location=artifacts[a.aid].location)` |

**Test requirements:**
- Existing tree/extraction tests pass unchanged
- New test: with Russian locale, duplicate artifact ID error renders in Russian
- New test: circular reference error renders in Russian

**Demo:** Duplicate ID error shows `"Дублирующийся идентификатор артефакта: REQ-001 ..."` in Russian.


---

### Task 3: Localize `metrics.py` and `artifact.py` — Metrics and Builder Errors

**Objective:** Localize 1 static message in metrics and 5 builder validation messages in artifact.

**Implementation:**
- Add `from syntagmax.i18n import _` to both files
- `metrics.py`:
  - `'Metrics: No requirements found'` → `_("Metrics: No requirements found")`
- `artifact.py` — the `_build_error` wrapper and `ValidationError` messages:
  - Change `_build_error` to accept a pre-translated message (callers pass `_("...")`):
    ```python
    def _build_error(self, message: str) -> str:
        return _('Driver "{driver}": {location}: {message}').format(
            driver=self.artifact.driver,
            location=self.artifact.location,
            message=message,
        )
    ```
  - Convert callers:
    - `'Duplicate AID'` → `_("Duplicate AID")`
    - `f'Duplicate field "{field}"'` → `_('Duplicate field "{field}"').format(field=field)`
    - `'Location is required'` → `_("Location is required")`
    - `'AType is required'` → `_("AType is required")`
    - `'AID is required'` → `_("AID is required")`

**Test requirements:**
- Existing tests pass unchanged (metrics, extraction tests use `ArtifactBuilder`)
- New test: `setup_i18n('ru')` + `ArtifactBuilder.build()` without location → Russian error
- New test: metrics with empty input → Russian "no requirements found" message

**Demo:** `"Метрики: Требования не найдены"` appears in Russian analysis report.


---

### Task 4: Localize Extractor Modules

**Objective:** Localize ~15 error message templates across all extractor drivers.

**Implementation:**
- Add `from syntagmax.i18n import _` to each extractor module

**`extractors/markdown.py`** (~7 messages):

| Original | Localized |
|----------|-----------|
| `f'Non-breaking space (NBSP) detected in requirement at line {start_line} in {filepath}'` | `_("Non-breaking space (NBSP) detected in requirement at line {line} in {file}").format(line=start_line, file=filepath)` |
| `f'Invalid metadata in YAML at line {start_line}'` | `_("Invalid metadata in YAML at line {line}").format(line=start_line)` |
| `f'Missing ID in metadata at line {start_line}'` | `_("Missing ID in metadata at line {line}").format(line=start_line)` |
| `f'Parse error in requirement at line {start_line} in {filepath}'` | `_("Parse error in requirement at line {line} in {file}").format(line=start_line, file=filepath)` |
| `f'Error processing requirement at line {start_line} in {filepath}'` | `_("Error processing requirement at line {line} in {file}").format(line=start_line, file=filepath)` |
| `f'Unclosed YAML block in requirement at line {start_line} in {filepath}'` | `_("Unclosed YAML block in requirement at line {line} in {file}").format(line=start_line, file=filepath)` |
| `f'Unterminated requirement at line {start_line} in {filepath}'` | `_("Unterminated requirement at line {line} in {file}").format(line=start_line, file=filepath)` |

**`extractors/sidecar.py`** (~7 messages):

| Original | Localized |
|----------|-----------|
| `f'{self.driver()} :: Orphaned sidecar file {path} without matching original file'` | `_("{driver} :: Orphaned sidecar file {path} without matching original file").format(driver=self.driver(), path=sidecar_path)` |
| `f'{self.driver()} :: Both .stmx and .syntagmax sidecars are present for {filepath}'` | `_("{driver} :: Both .stmx and .syntagmax sidecars are present for {file}").format(driver=self.driver(), file=filepath)` |
| `f'{self.driver()} :: Missing sidecar file for {filepath}'` | `_("{driver} :: Missing sidecar file for {file}").format(driver=self.driver(), file=filepath)` |
| `f'{self.driver()} :: Malformed YAML in sidecar {path}: {e}'` | `_("{driver} :: Malformed YAML in sidecar {path}: {error}").format(driver=self.driver(), path=sidecar_path, error=str(e))` |
| `f'{self.driver()} :: Could not read sidecar {path}: {e}'` | `_("{driver} :: Could not read sidecar {path}: {error}").format(driver=self.driver(), path=sidecar_path, error=str(e))` |
| `f'{self.driver()} :: Sidecar {path} does not contain a valid YAML dictionary'` | `_("{driver} :: Sidecar {path} does not contain a valid YAML dictionary").format(driver=self.driver(), path=sidecar_path)` |
| `f'{self.driver()} :: Missing required "id" field in sidecar {path}'` | `_("{driver} :: Missing required 'id' field in sidecar {path}").format(driver=self.driver(), path=sidecar_path)` |

**`extractors/text.py`** (1 template method):
- Convert `_format_error`:
  ```python
  def _format_error(self, error_type: str, location, section_start_string: str, message: str) -> str:
      return _('Driver "text": {error_type} in {location}\n'
               'While analyzing {section}\n'
               'Reason: {message}').format(
          error_type=error_type, location=location,
          section=section_start_string, message=message,
      )
  ```

**`extractors/simple_markdown.py`** (1 message):
- `f'{self.driver()} :: Malformed YAML frontmatter in {filepath}: {e}'` → `_("{driver} :: Malformed YAML frontmatter in {file}: {error}").format(driver=self.driver(), file=filepath, error=str(e))`

**`extractors/markdown_markers.py`** (1 message, used 3 times):
- `f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]'` → `_('Invalid block ID "{block_id}" for marker [{marker}] — IDs must match [a-zA-Z0-9_.-]').format(block_id=raw_id, marker=marker_name)`

**`extractors/ipynb.py`** (1 message):
- `f'Error extracting from {filepath}: {e}'` → `_("Error extracting from {file}: {error}").format(file=filepath, error=str(e))`

**Test requirements:**
- All existing extraction tests pass
- New test: with Russian locale, create a sidecar extraction scenario that triggers "Missing sidecar file" → verify Russian message
- New test: markdown extraction with NBSP → verify Russian error message

**Demo:** Sidecar driver error shows `"sidecar :: Отсутствует файл метаданных для image.png"` in Russian.


---

### Task 5: Add Missing AI Analysis Strings and Clean Up Orphan

**Objective:** Add the 5 missing `report.j2` strings to both `.po` catalogs and remove the orphaned entry.

**Implementation:**
- Add to `ru/LC_MESSAGES/messages.po`:
  ```po
  msgid "AI Analysis"
  msgstr "Анализ ИИ"

  msgid "Ambiguity"
  msgstr "Двусмысленность"

  msgid "Completeness"
  msgstr "Полнота"

  msgid "Verifiability"
  msgstr "Проверяемость"

  msgid "Singularity"
  msgstr "Единичность"
  ```
- Add to `en/LC_MESSAGES/messages.po` (identity translations):
  ```po
  msgid "AI Analysis"
  msgstr "AI Analysis"

  msgid "Ambiguity"
  msgstr "Ambiguity"

  msgid "Completeness"
  msgstr "Completeness"

  msgid "Verifiability"
  msgstr "Verifiability"

  msgid "Singularity"
  msgstr "Singularity"
  ```
- Remove from both catalogs:
  ```po
  msgid "errors"
  msgstr "ошибок"
  ```

**Test requirements:**
- `setup_i18n('ru'); _("AI Analysis")` returns `"Анализ ИИ"`
- `setup_i18n('ru'); _("Ambiguity")` returns `"Двусмысленность"`
- No entry for `"errors"` remains in catalogs

**Demo:** When AI analysis is enabled, Russian report shows `## Анализ ИИ` and localized column headers.


---

### Task 6: Russian Translations for All New Error Messages

**Objective:** Populate the Russian `.po` file with complete translations for all ~35 new error message templates.

**Implementation:**
- Update `babel.cfg` with expanded extraction rules (see Proposed Solution above)
- Run `pybabel extract -F babel.cfg -o messages.pot .` to generate updated POT
- Run `pybabel update -i messages.pot -d src/syntagmax/resources/locales` to merge
- Fill in Russian translations. Key entries:

**analyse.py translations:**

| msgid | msgstr |
|-------|--------|
| `"Unknown artifact type: '{atype}'"` | `"Неизвестный тип артефакта: '{atype}'"` |
| `"Artifact ID '{aid}' does not match schema '{schema}' for type '{atype}'"` | `"Идентификатор артефакта '{aid}' не соответствует схеме '{schema}' для типа '{atype}'"` |
| `"Attribute '{attr_name}' is not allowed for artifact '{atype}'"` | `"Атрибут '{attr_name}' недопустим для артефакта '{atype}'"` |
| `"Missing mandatory attribute: '{attr_name}'"` | `"Отсутствует обязательный атрибут: '{attr_name}'"` |
| `"Attribute '{attr_name}' must be a list (multiple=True)"` | `"Атрибут '{attr_name}' должен быть списком (multiple=True)"` |
| `"Attribute '{attr_name}' must not be a list (multiple=False)"` | `"Атрибут '{attr_name}' не должен быть списком (multiple=False)"` |
| `"Attribute '{attr_name}' value '{val}' cannot be converted to an integer"` | `"Значение '{val}' атрибута '{attr_name}' не может быть преобразовано в целое число"` |
| `"Attribute '{attr_name}' value '{val}' is not a valid boolean ({expected})"` | `"Значение '{val}' атрибута '{attr_name}' не является допустимым булевым ({expected})"` |
| `"Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed}"` | `"Значение '{val}' атрибута '{attr_name}' недопустимо. Допустимые значения: {allowed}"` |
| `"Attribute '{attr_name}' value '{val}' is a malformed reference (expected ID string)"` | `"Значение '{val}' атрибута '{attr_name}' — некорректная ссылка (ожидается строка ID)"` |
| `"Attribute '{attr_name}' value '{val}' refers to an unknown artifact ID '{aid}'"` | `"Значение '{val}' атрибута '{attr_name}' ссылается на неизвестный ID артефакта '{aid}'"` |
| `"Attribute '{attr_name}' value '{val}' refers to an artifact with unknown type '{atype}'"` | `"Значение '{val}' атрибута '{attr_name}' ссылается на артефакт с неизвестным типом '{atype}'"` |
| `"Trace from '{from_type}' to '{to_type}' is not allowed"` | `"Трассировка от '{from_type}' к '{to_type}' не разрешена"` |
| `"Trace from '{from_type}' to '{to_type}' is 'by timestamp', but revision was specified: '{ref}'"` | `"Трассировка от '{from_type}' к '{to_type}' задана 'по метке времени', но указана ревизия: '{ref}'"` |
| `"Trace from '{from_type}' to '{to_type}' is 'by commit', but no revision was specified for parent '{parent_aid}'"` | `"Трассировка от '{from_type}' к '{to_type}' задана 'по коммиту', но не указана ревизия для родителя '{parent_aid}'"` |
| `"Missing mandatory trace from '{from_type}' to {targets}"` | `"Отсутствует обязательная трассировка от '{from_type}' к {targets}"` |
| `"Must have exactly one root artifact"` | `"Должен быть ровно один корневой артефакт"` |

**tree.py / extract.py translations:**

| msgid | msgstr |
|-------|--------|
| `"Conflicting nominal revisions for parent '{parent_id}' in artifact '{artifact_id}': '{existing}' vs '{nominal}'"` | `"Конфликт номинальных ревизий для родителя '{parent_id}' в артефакте '{artifact_id}': '{existing}' и '{nominal}'"` |
| `"Error processing parent link '{ref}' for artifact '{artifact_id}': {error}"` | `"Ошибка обработки родительской связи '{ref}' для артефакта '{artifact_id}': {error}"` |
| `"Circular reference detected with {aid}"` | `"Обнаружена циклическая ссылка: {aid}"` |
| `"Artifact {atype} at {location} has no ID"` | `"Артефакт {atype} в {location} не имеет идентификатора"` |
| `"Duplicate artifact ID: {aid} at {location} (already defined at {other_location})"` | `"Дублирующийся идентификатор артефакта: {aid} в {location} (уже определен в {other_location})"` |

**metrics.py / artifact.py translations:**

| msgid | msgstr |
|-------|--------|
| `"Metrics: No requirements found"` | `"Метрики: Требования не найдены"` |
| `'Driver "{driver}": {location}: {message}'` | `'Драйвер "{driver}": {location}: {message}'` |
| `"Duplicate AID"` | `"Дублирующийся AID"` |
| `'Duplicate field "{field}"'` | `'Дублирующееся поле "{field}"'` |
| `"Location is required"` | `"Местоположение обязательно"` |
| `"AType is required"` | `"Тип артефакта обязателен"` |
| `"AID is required"` | `"Идентификатор артефакта обязателен"` |

**Extractor translations:**

| msgid | msgstr |
|-------|--------|
| `"Non-breaking space (NBSP) detected in requirement at line {line} in {file}"` | `"Обнаружен неразрывный пробел (NBSP) в требовании на строке {line} в {file}"` |
| `"Invalid metadata in YAML at line {line}"` | `"Некорректные метаданные YAML на строке {line}"` |
| `"Missing ID in metadata at line {line}"` | `"Отсутствует ID в метаданных на строке {line}"` |
| `"Parse error in requirement at line {line} in {file}"` | `"Ошибка разбора требования на строке {line} в {file}"` |
| `"Error processing requirement at line {line} in {file}"` | `"Ошибка обработки требования на строке {line} в {file}"` |
| `"Unclosed YAML block in requirement at line {line} in {file}"` | `"Незакрытый блок YAML в требовании на строке {line} в {file}"` |
| `"Unterminated requirement at line {line} in {file}"` | `"Незавершённое требование на строке {line} в {file}"` |
| `"{driver} :: Orphaned sidecar file {path} without matching original file"` | `"{driver} :: Файл метаданных {path} без соответствующего основного файла"` |
| `"{driver} :: Both .stmx and .syntagmax sidecars are present for {file}"` | `"{driver} :: Оба файла .stmx и .syntagmax присутствуют для {file}"` |
| `"{driver} :: Missing sidecar file for {file}"` | `"{driver} :: Отсутствует файл метаданных для {file}"` |
| `"{driver} :: Malformed YAML in sidecar {path}: {error}"` | `"{driver} :: Некорректный YAML в файле метаданных {path}: {error}"` |
| `"{driver} :: Could not read sidecar {path}: {error}"` | `"{driver} :: Не удалось прочитать файл метаданных {path}: {error}"` |
| `"{driver} :: Sidecar {path} does not contain a valid YAML dictionary"` | `"{driver} :: Файл метаданных {path} не содержит корректного YAML-словаря"` |
| `"{driver} :: Missing required 'id' field in sidecar {path}"` | `"{driver} :: Отсутствует обязательное поле 'id' в файле метаданных {path}"` |
| `'Driver "text": {error_type} in {location}\nWhile analyzing {section}\nReason: {message}'` | `'Драйвер "text": {error_type} в {location}\nПри анализе {section}\nПричина: {message}'` |
| `"{driver} :: Malformed YAML frontmatter in {file}: {error}"` | `"{driver} :: Некорректный YAML-заголовок в {file}: {error}"` |
| `'Invalid block ID "{block_id}" for marker [{marker}] — IDs must match [a-zA-Z0-9_.-]'` | `'Некорректный ID блока "{block_id}" для маркера [{marker}] — ID должен соответствовать [a-zA-Z0-9_.-]'` |
| `"Error extracting from {file}: {error}"` | `"Ошибка извлечения из {file}: {error}"` |

**Test requirements:**
- No empty `msgstr` for any msgid used in code
- All format placeholders in translations match those in the source msgid

**Demo:** Complete Russian `.po` with all entries translated.


---

### Task 7: Recompile `.mo` and Add Integration Tests

**Objective:** Ensure compiled catalogs are up to date and add comprehensive i18n testing for error messages.

**Implementation:**
- Run `pybabel compile -d src/syntagmax/resources/locales` to regenerate `.mo` files
- Commit updated `.mo` files
- Add tests to `tests/test_i18n.py`:

```python
class TestErrorMessageTranslation:
    """Tests for localized error messages."""

    def test_analyse_missing_attribute_ru(self):
        setup_i18n('ru')
        msg = _("Missing mandatory attribute: '{attr_name}'").format(attr_name='status')
        assert 'Отсутствует обязательный атрибут' in msg
        assert 'status' in msg

    def test_analyse_unknown_type_ru(self):
        setup_i18n('ru')
        msg = _("Unknown artifact type: '{atype}'").format(atype='FOO')
        assert 'Неизвестный тип артефакта' in msg
        assert 'FOO' in msg

    def test_tree_circular_reference_ru(self):
        setup_i18n('ru')
        msg = _("Circular reference detected with {aid}").format(aid='REQ-001')
        assert 'циклическая ссылка' in msg
        assert 'REQ-001' in msg

    def test_extract_duplicate_id_ru(self):
        setup_i18n('ru')
        msg = _("Duplicate artifact ID: {aid} at {location} (already defined at {other_location})").format(
            aid='REQ-001', location='file-a.md', other_location='file-b.md'
        )
        assert 'Дублирующийся идентификатор' in msg
        assert 'REQ-001' in msg

    def test_metrics_no_requirements_ru(self):
        setup_i18n('ru')
        assert _("Metrics: No requirements found") == "Метрики: Требования не найдены"

    def test_ai_analysis_strings_ru(self):
        setup_i18n('ru')
        assert _("AI Analysis") == "Анализ ИИ"
        assert _("Ambiguity") == "Двусмысленность"
        assert _("Completeness") == "Полнота"
        assert _("Verifiability") == "Проверяемость"
        assert _("Singularity") == "Единичность"

    def test_format_placeholders_survive_translation(self):
        """All translated messages must produce valid output with .format()."""
        setup_i18n('ru')
        # Should not raise KeyError or ValueError
        _("Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed}").format(
            attr_name='status', val='foo', allowed=['active', 'draft']
        )
        _("Trace from '{from_type}' to '{to_type}' is not allowed").format(
            from_type='REQ', to_type='SYS'
        )
        _("{driver} :: Missing sidecar file for {file}").format(
            driver='sidecar', file='image.png'
        )

    def test_english_error_messages_unchanged(self):
        """English locale must produce identical output to pre-i18n behavior."""
        setup_i18n('en')
        msg = _("Missing mandatory attribute: '{attr_name}'").format(attr_name='status')
        assert msg == "Missing mandatory attribute: 'status'"
```

- Add a catalog completeness test:

```python
class TestCatalogCompleteness:
    """Ensure all code strings have translations."""

    def test_no_empty_msgstr_in_russian_po(self):
        """Every msgid used in code must have a non-empty Russian translation."""
        import re
        from pathlib import Path

        po_path = Path('src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.po')
        content = po_path.read_text(encoding='utf-8')

        # Find all msgid/msgstr pairs
        entries = re.findall(
            r'^msgid "([^"]+)"\nmsgstr "([^"]*)"',
            content, re.MULTILINE,
        )

        empty = [(msgid, msgstr) for msgid, msgstr in entries if not msgstr]
        assert empty == [], f"Empty translations found: {[m[0] for m in empty]}"
```

**Test requirements:**
- All existing tests pass unchanged
- All new `TestErrorMessageTranslation` tests pass
- Catalog completeness test passes
- `uv run pytest tests/test_i18n.py -v` shows green

**Demo:** `uv run pytest tests/test_i18n.py -v` with all error message translation tests passing.
