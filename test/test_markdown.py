from syntagmax.extractors.markdown import MarkdownExtractor

MARKDOWN = '''

# Heading 1

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

## Heading 2

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.


```yaml
syntagmax:
  id: VALID-REQ-KC-002
  pid:
    - REQ-KC-002
    - REQ-KC-003
  desc: TKM-list validation
```

# Heading 3

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

```yaml
someotheryaml:
  field1: value1
  field2: value2
```
'''


def test_extract_from_markdown():
    extractor = MarkdownExtractor({})  # type: ignore
    artifacts, errors = extractor._extract_from_markdown('test', MARKDOWN)  # type: ignore
    print(artifacts)
    print(errors)
    assert len(artifacts) == 1
    assert len(errors) == 0
    artifact = artifacts[0]
    assert artifact.atype == 'VALID'
    assert artifact.aid == 'REQ-KC-002'
    assert artifact.desc == 'TKM-list validation'
    assert len(artifact.pids) == 2
    assert artifact.pids[0].aid == 'KC-002'
    assert artifact.pids[1].aid == 'KC-003'
