"""Record Agent.

The record is intentionally deterministic for demo mode: it consumes the same
event log as the UI and writes a structured JSON record plus readable HTML.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bridge.bus.events import BridgeEvent, RecordSnapshotEvent
from bridge.records import BridgeRecord, build_record, render_record_html, write_record_artifacts


DEFAULT_RECORD_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "records" / "generated"


@dataclass(frozen=True)
class RecordAgent:
    output_dir: Path = DEFAULT_RECORD_OUTPUT_DIR

    def build(self, events: list[BridgeEvent | dict[str, Any]]) -> BridgeRecord:
        return build_record(events)

    def render_html(self, events: list[BridgeEvent | dict[str, Any]]) -> str:
        return render_record_html(self.build(events))

    def generate_snapshot(self, events: list[BridgeEvent | dict[str, Any]]) -> RecordSnapshotEvent:
        record = self.build(events)
        json_path, html_path = write_record_artifacts(record, self.output_dir)
        return RecordSnapshotEvent(
            session_id=record["session_id"],
            record_id=record["record_id"],
            status="ready",
            summary=record["session_summary"],
            html_path=str(html_path),
            json_path=str(json_path),
        )


def generate_record_snapshot(
    events: list[BridgeEvent | dict[str, Any]],
    *,
    output_dir: Path = DEFAULT_RECORD_OUTPUT_DIR,
) -> RecordSnapshotEvent:
    return RecordAgent(output_dir=output_dir).generate_snapshot(events)
