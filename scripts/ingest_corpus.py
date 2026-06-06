"""Build Bridge's local policy RAG corpus.

The default path attempts to refresh official sources and falls back to the
curated source notes in data/sources.yml when the network or optional parsers are
not available. Use --no-fetch for deterministic offline demo indexing.
"""

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.rag.corpus import build_corpus  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        type=Path,
        default=ROOT / "data" / "sources.yml",
        help="YAML source registry path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "processed",
        help="Output directory for local corpus index.",
    )
    parser.add_argument(
        "--fetch",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download official source pages/resources before falling back to seed notes.",
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Exit non-zero if no chunks are produced.",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Exit non-zero unless every registered source produced live extracted chunks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_corpus(args.sources, fetch=args.fetch, output_dir=args.output)

    print(f"Sources: {args.sources}")
    print(f"Output: {args.output}")
    print(f"Chunks: {len(report.chunks)}")
    for source_id, status in sorted(report.source_status.items()):
        print(f"- {source_id}: {status}")

    if args.fail_on_empty and not report.chunks:
        raise SystemExit("No corpus chunks produced.")
    if args.require_live:
        not_live = {
            source_id: status
            for source_id, status in report.source_status.items()
            if status != "live"
        }
        if not_live:
            summary = ", ".join(f"{source_id}={status}" for source_id, status in sorted(not_live.items()))
            raise SystemExit(f"Live refresh incomplete: {summary}")


if __name__ == "__main__":
    main()
