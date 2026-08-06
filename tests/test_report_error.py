# SPDX-License-Identifier: MIT

from syntagmax.report import ReportError, CAT_SCHEMA, CAT_STRUCTURE
from syntagmax.config import ReportConfig


class TestReportErrorStr:
    def test_full_metadata(self):
        err = ReportError(
            message='Missing attribute',
            category=CAT_SCHEMA,
            input_record='requirements',
            artifact_id='REQ-001',
            artifact_type='REQ',
            file_path='reqs/file.md',
            line_range=(10, 15),
        )
        result = str(err)
        assert result == 'Missing attribute (REQ\u1362REQ-001\u1362reqs/file.md:10-15)'

    def test_partial_metadata_no_file_path(self):
        err = ReportError(
            message='Bad reference',
            category=CAT_SCHEMA,
            artifact_id='SYS-002',
            artifact_type='SYS',
        )
        result = str(err)
        assert result == 'Bad reference (SYS\u1362SYS-002)'

    def test_no_metadata(self):
        err = ReportError(
            message='Something went wrong',
            category=CAT_STRUCTURE,
        )
        result = str(err)
        assert result == 'Something went wrong'

    def test_file_path_only(self):
        err = ReportError(
            message='Parse error',
            category=CAT_STRUCTURE,
            file_path='docs/spec.md',
        )
        result = str(err)
        assert result == 'Parse error (docs/spec.md)'


class TestReportErrorFromAny:
    def test_from_string(self):
        err = ReportError.from_any('plain error message')
        assert isinstance(err, ReportError)
        assert err.message == 'plain error message'
        assert err.category == CAT_STRUCTURE
        assert err.artifact_id is None

    def test_from_report_error(self):
        original = ReportError(
            message='existing error',
            category=CAT_SCHEMA,
            artifact_id='REQ-005',
            artifact_type='REQ',
        )
        result = ReportError.from_any(original)
        assert result is original


class TestReportConfig:
    def test_default_instantiation(self):
        cfg = ReportConfig()
        assert cfg.path_as_links is False
        assert cfg.wiki_links is False

    def test_custom_values(self):
        cfg = ReportConfig(path_as_links=True, wiki_links=True)
        assert cfg.path_as_links is True
        assert cfg.wiki_links is True



class TestFormatError:
    def test_format_error_no_config(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='reqs/file.md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(10, 20),
        )
        result = format_error(err, None)
        assert result == str(err)

    def test_format_error_links_disabled(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=False)
        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='reqs/file.md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(10, 20),
        )
        result = format_error(err, cfg)
        assert result == str(err)

    def test_format_error_markdown_links(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=True, wiki_links=False)
        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='reqs/file.md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(10, 20),
        )
        result = format_error(err, cfg)
        assert '[file.md](reqs/file.md#L10):10-20' in result
        assert 'REQ:REQ-001' in result
        assert 'test msg' in result

    def test_format_error_wiki_links(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=True, wiki_links=True)
        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='reqs/file.md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(10, 20),
        )
        result = format_error(err, cfg)
        assert '[[reqs/file.md]]:10-20' in result
        assert 'REQ:REQ-001' in result
        assert '#L' not in result

    def test_format_error_no_file_path(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=True, wiki_links=False)
        err = ReportError(message='test msg', category=CAT_ATTRIBUTE)
        result = format_error(err, cfg)
        assert result == str(err)

    def test_format_error_markdown_links_with_spaces(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=True, wiki_links=False)
        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='Описание проекта/4 content.md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(10, 20),
        )
        result = format_error(err, cfg)
        assert '%20' in result
        assert 'Описание' not in result.split('](')[1].split(')')[0]  # Cyrillic is encoded in URL
        assert '#L10' in result
        assert 'REQ:REQ-001' in result

    def test_format_error_markdown_links_with_parentheses(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=True, wiki_links=False)
        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='dir/file (copy).md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(5, 10),
        )
        result = format_error(err, cfg)
        # Parentheses must be encoded
        assert '%28' in result
        assert '%29' in result

    def test_format_error_wiki_links_not_encoded(self):
        from syntagmax.report import format_error, CAT_ATTRIBUTE

        cfg = ReportConfig(path_as_links=True, wiki_links=True)
        err = ReportError(
            message='test msg',
            category=CAT_ATTRIBUTE,
            file_path='Описание проекта/4 content.md',
            artifact_type='REQ',
            artifact_id='REQ-001',
            line_range=(10, 20),
        )
        result = format_error(err, cfg)
        # Wiki links should NOT be encoded
        assert '[[Описание проекта/4 content.md]]' in result
        assert '%20' not in result
