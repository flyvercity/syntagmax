# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-04
# Description: Trace export - builds and renders traceability matrices.

import csv
import io
from dataclasses import dataclass, field

from syntagmax.artifact import ArtifactMap


@dataclass
class TraceRecord:
    """A single row in the trace matrix."""

    record_number: int        # 1-based sequential row index
    lead_id: str              # ChildID (forward) or ParentID (reverse)
    linked_id: str            # ParentID (forward) or ChildID (reverse) — "; " separated in flat mode, empty if no links
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class TraceMatrix:
    """Complete trace matrix ready for export."""

    direction: str            # "forward" or "reverse"
    child_type: str
    parent_type: str
    attribute_names: list[str] = field(default_factory=list)
    records: list[TraceRecord] = field(default_factory=list)


def _serialize_attribute(value) -> str:
    """Serialize an artifact attribute value to a string for CSV output."""
    if value is None:
        return ''
    if isinstance(value, list):
        return '; '.join(str(v) for v in value)
    return str(value)


def build_trace_matrix(
    artifacts: ArtifactMap,
    child_type: str,
    parent_type: str,
    direction: str = 'forward',
    attributes: list[str] | None = None,
    flat: bool = False,
) -> TraceMatrix:
    """Build a trace matrix from the artifact map.

    Uses left outer join semantics: every lead artifact appears even if it has no links.

    Args:
        artifacts: The resolved artifact map (with parent/child links populated).
        child_type: The atype of child artifacts.
        parent_type: The atype of parent artifacts.
        direction: "forward" (lead=child, linked=parent) or "reverse" (lead=parent, linked=child).
        attributes: Additional lead artifact attributes to include as columns.
        flat: If True, combine multiple linked IDs into semicolon-separated values.

    Returns:
        A TraceMatrix with all records.
    """
    if attributes is None:
        attributes = []

    matrix = TraceMatrix(
        direction=direction,
        child_type=child_type,
        parent_type=parent_type,
        attribute_names=list(attributes),
    )

    record_number = 1

    if direction == 'forward':
        # Lead = child artifacts, linked = their parents of parent_type
        lead_artifacts = sorted(
            [a for a in artifacts.values() if a.atype == child_type],
            key=lambda a: a.aid,
        )

        for lead in lead_artifacts:
            # Find parents of the target type
            linked_ids = []
            for pid in lead.pids:
                if pid in artifacts and artifacts[pid].atype == parent_type:
                    linked_ids.append(pid)
                else:
                    # Unresolved reference or wrong-type parent - include raw ID so broken links are visible
                    linked_ids.append(pid)

            # Serialize attributes
            attrs = {}
            for attr_name in attributes:
                attrs[attr_name] = _serialize_attribute(lead.fields.get(attr_name))

            if flat:
                matrix.records.append(TraceRecord(
                    record_number=record_number,
                    lead_id=lead.aid,
                    linked_id='; '.join(linked_ids) if linked_ids else '',
                    attributes=attrs,
                ))
                record_number += 1
            else:
                if not linked_ids:
                    # Left outer join: emit row with empty linked ID
                    matrix.records.append(TraceRecord(
                        record_number=record_number,
                        lead_id=lead.aid,
                        linked_id='',
                        attributes=attrs,
                    ))
                    record_number += 1
                else:
                    for linked_id in linked_ids:
                        matrix.records.append(TraceRecord(
                            record_number=record_number,
                            lead_id=lead.aid,
                            linked_id=linked_id,
                            attributes=dict(attrs),
                        ))
                        record_number += 1

    elif direction == 'reverse':
        # Lead = parent artifacts, linked = their children of child_type
        lead_artifacts = sorted(
            [a for a in artifacts.values() if a.atype == parent_type],
            key=lambda a: a.aid,
        )

        for lead in lead_artifacts:
            # Find children of the target type
            linked_ids = sorted(
                [cid for cid in lead.children if cid in artifacts and artifacts[cid].atype == child_type]
            )

            # Serialize attributes
            attrs = {}
            for attr_name in attributes:
                attrs[attr_name] = _serialize_attribute(lead.fields.get(attr_name))

            if flat:
                matrix.records.append(TraceRecord(
                    record_number=record_number,
                    lead_id=lead.aid,
                    linked_id='; '.join(linked_ids) if linked_ids else '',
                    attributes=attrs,
                ))
                record_number += 1
            else:
                if not linked_ids:
                    # Left outer join: emit row with empty linked ID
                    matrix.records.append(TraceRecord(
                        record_number=record_number,
                        lead_id=lead.aid,
                        linked_id='',
                        attributes=attrs,
                    ))
                    record_number += 1
                else:
                    for linked_id in linked_ids:
                        matrix.records.append(TraceRecord(
                            record_number=record_number,
                            lead_id=lead.aid,
                            linked_id=linked_id,
                            attributes=dict(attrs),
                        ))
                        record_number += 1

    return matrix


def render_trace_csv(matrix: TraceMatrix, delimiter: str = ',') -> str:
    """Render a TraceMatrix as a delimited string (CSV or TSV).

    Args:
        matrix: The trace matrix to render.
        delimiter: Column delimiter (default: ',' for CSV, use '\\t' for TSV).

    Returns:
        The formatted string with header and data rows.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator='\n')

    # Build header
    if matrix.direction == 'forward':
        header = ['RecordNumber', 'ChildID', 'ParentID']
    else:
        header = ['RecordNumber', 'ParentID', 'ChildID']

    header.extend(matrix.attribute_names)
    writer.writerow(header)

    # Write data rows
    for record in matrix.records:
        row = [str(record.record_number), record.lead_id, record.linked_id]
        for attr_name in matrix.attribute_names:
            row.append(record.attributes.get(attr_name, ''))
        writer.writerow(row)

    return output.getvalue()
