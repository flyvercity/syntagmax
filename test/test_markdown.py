from gitreqms.extractors.markdown import extract_from_markdown

MARKDOWN = '''

# Heading 1

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

## Heading 2

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.


```yaml
gitreqms:
  id: VALID-REQ-KC-002
  pid: REQ-KC-002
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
    artifact = extract_from_markdown(MARKDOWN)
    print(artifact)
    assert False
