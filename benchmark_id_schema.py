import timeit
import re

_NUM_PATTERN = re.compile(r'\{num(?::(\d+))?\}')


def current_implementation(pattern):
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
    return f'^{final_pattern}$'


def optimized_implementation(pattern):
    final_pattern_parts = []
    last_pos = 0
    for match in _NUM_PATTERN.finditer(pattern):
        final_pattern_parts.append(re.escape(pattern[last_pos : match.start()]))
        padding = match.group(1)
        if padding:
            final_pattern_parts.append(rf'\d{{{padding}}}')
        else:
            final_pattern_parts.append(r'\d+')
        last_pos = match.end()
    final_pattern_parts.append(re.escape(pattern[last_pos:]))
    return f'^{"".join(final_pattern_parts)}$'


# Test with various lengths of patterns to see the difference
patterns = [
    'REQ-{num}',
    'REQ-{num:3}',
    'PREFIX-{num:3}-MIDDLE-{num:4}-SUFFIX-{num}-END',
    'A-{num}-B-{num}-C-{num}-D-{num}-E-{num}-F-{num}-G-{num}-H-{num}-I-{num}-J-{num}',
]

for p in patterns:
    print(f'Pattern: {p}')
    curr_time = timeit.timeit(lambda: current_implementation(p), number=100000)
    opt_time = timeit.timeit(lambda: optimized_implementation(p), number=100000)
    print(f'Current: {curr_time:.6f}s')
    print(f'Optimized: {opt_time:.6f}s')
    print(f'Improvement: {(curr_time - opt_time) / curr_time * 100:.2f}%')
    print()
