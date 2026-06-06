"""Placeholder corpus ingestion entrypoint.

Agent C should replace this with downloading, parsing, chunking, embedding, and
indexing based on data/sources.yml.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sources_path = ROOT / "data" / "sources.yml"
    print(f"Corpus source registry: {sources_path}")
    print("Ingestion implementation pending.")


if __name__ == "__main__":
    main()

