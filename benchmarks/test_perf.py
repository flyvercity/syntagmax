import re
import time

_NUM_PATTERN = re.compile(r'\{num(?::(\d+))?\}')


class OriginalValidator:
    def __init__(self):
        self.errors = []

    def validate(self, atype, schema, aid):
        pattern = schema.replace('{atype}', atype)

        num_pattern = re.compile(r'\{num(?::(\d+))?\}')

        def replacer(match):
            padding = match.group(1)
            if padding:
                return rf'\d{{{padding}}}'
            return r'\d+'

        parts = num_pattern.split(pattern)
        regex_parts = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                regex_parts.append(re.escape(part))
            else:
                if part:
                    regex_parts.append(rf'\d{{{part}}}')
                else:
                    regex_parts.append(r'\d+')

        final_pattern = ''
        last_pos = 0
        for match in num_pattern.finditer(pattern):
            final_pattern += re.escape(pattern[last_pos : match.start()])
            padding = match.group(1)
            if padding:
                final_pattern += rf'\d{{{padding}}}'
            else:
                final_pattern += r'\d+'
            last_pos = match.end()
        final_pattern += re.escape(pattern[last_pos:])

        final_pattern = f'^{final_pattern}$'

        if not re.match(final_pattern, aid):
            self.errors.append('error')


class NewValidator:
    def __init__(self):
        self.errors = []
        self._id_schema_cache = {}

    def validate(self, atype, schema, aid):
        cache_key = (atype, schema)
        if cache_key in self._id_schema_cache:
            compiled_pattern = self._id_schema_cache[cache_key]
        else:
            pattern = schema.replace('{atype}', atype)

            final_pattern = ''
            last_pos = 0
            for match in _NUM_PATTERN.finditer(pattern):
                final_pattern += re.escape(pattern[last_pos : match.start()])
                padding = match.group(1)
                if padding:
                    final_pattern += rf'\d{{{padding}}}'
                else:
                    final_pattern += r'\d+'
                last_pos = match.end()
            final_pattern += re.escape(pattern[last_pos:])

            final_pattern = f'^{final_pattern}$'
            compiled_pattern = re.compile(final_pattern)
            self._id_schema_cache[cache_key] = compiled_pattern

        if not compiled_pattern.match(aid):
            self.errors.append('error')


def run_bench():
    atype = 'REQ'
    schema = '{atype}-{num:3}'

    aids = [f'REQ-{i:03d}' for i in range(100000)]

    orig = OriginalValidator()
    start = time.time()
    for aid in aids:
        orig.validate(atype, schema, aid)
    orig_time = time.time() - start

    new_v = NewValidator()
    start = time.time()
    for aid in aids:
        new_v.validate(atype, schema, aid)
    new_time = time.time() - start

    print(f'Original: {orig_time:.4f}s')
    print(f'New: {new_time:.4f}s')


run_bench()
