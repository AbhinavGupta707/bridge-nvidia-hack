#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services" / "api"
sys.path.insert(0, str(API_ROOT))

from bridge.config import load_settings  # noqa: E402
from bridge.demo.runner import build_demo_events, dump_events  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Print deterministic Bridge demo events.")
    parser.add_argument("--session-id", default="demo-001")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    events = dump_events(build_demo_events(settings, session_id=args.session_id))
    indent = None if args.compact else 2
    print(json.dumps(events, ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
