"""Plugin: tsv-export

Demonstrates the export_trace hook by writing the trace matrix as a
tab-separated values (TSV) file.

The output file path is taken from params['output'].
"""

import csv
import io
from pathlib import Path

from syntagmax.trace import TraceMatrix


def export_trace(matrix: TraceMatrix, config, params: dict) -> None:
    """Export the trace matrix as a TSV file."""
    output_path = params.get('output', '.syntagmax/reports/trace.tsv')
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')

    # Header
    if matrix.direction == 'forward':
        header = ['RecordNumber', 'ChildID', 'ParentID']
    else:
        header = ['RecordNumber', 'ParentID', 'ChildID']

    header.extend(matrix.attribute_names)
    writer.writerow(header)

    # Data rows
    for record in matrix.records:
        row = [str(record.record_number), record.lead_id, record.linked_id]
        for attr_name in matrix.attribute_names:
            row.append(record.attributes.get(attr_name, ''))
        writer.writerow(row)

    path.write_text(output.getvalue(), encoding='utf-8')
    print(f'TSV trace matrix written to {path} ({len(matrix.records)} records)')
