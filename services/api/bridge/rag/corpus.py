from __future__ import annotations

import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import yaml


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class SourceResource:
    title: str
    type: str
    url: str


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    type: str
    url: str
    domain: str
    authority: str
    priority: str
    status: str | None = None
    resources: tuple[SourceResource, ...] = ()
    local_seed_text: str | None = None


@dataclass(frozen=True)
class CorpusChunk:
    chunk_id: str
    source_id: str
    source_title: str
    source_url: str
    authority: str
    domain: str
    priority: str
    source_type: str
    source_status: str
    content: str
    content_hash: str
    chunk_index: int
    heading: str | None = None
    page: int | None = None
    fetched_at: str | None = None
    token_count: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "authority": self.authority,
            "domain": self.domain,
            "priority": self.priority,
            "source_type": self.source_type,
            "source_status": self.source_status,
            "content": self.content,
            "content_hash": self.content_hash,
            "chunk_index": self.chunk_index,
            "heading": self.heading,
            "page": self.page,
            "fetched_at": self.fetched_at,
            "token_count": self.token_count,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CorpusChunk:
        return cls(**data)


@dataclass(frozen=True)
class IngestReport:
    chunks: list[CorpusChunk]
    source_status: dict[str, str] = field(default_factory=dict)
    output_dir: Path | None = None


class MainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0
        self._current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
        self._current_tag = tag
        if tag in {"p", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")
        self._current_tag = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._current_tag in {"nav", "footer"}:
            return
        self.parts.append(text)

    def text(self) -> str:
        return clean_text(" ".join(self.parts))


def load_sources(path: Path) -> list[Source]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources: list[Source] = []
    for item in payload.get("sources", []):
        resources = tuple(SourceResource(**resource) for resource in item.get("resources", []))
        sources.append(
            Source(
                id=item["id"],
                title=item["title"],
                type=item["type"],
                url=item["url"],
                domain=item["domain"],
                authority=item["authority"],
                priority=item["priority"],
                status=item.get("status"),
                resources=resources,
                local_seed_text=item.get("local_seed_text"),
            )
        )
    return sources


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"[\u201c\u201d]", '"', text)
    return WHITESPACE_RE.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def fetch_bytes(url: str, timeout: int = 15) -> bytes:
    request = Request(url, headers={"User-Agent": "BridgePolicyRAG/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def extract_html_text(data: bytes) -> str:
    parser = MainTextHTMLParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    return parser.text()


def extract_csv_text(data: bytes) -> str:
    return clean_text(data.decode("utf-8", errors="replace"))


def extract_xlsx_text(data: bytes, max_cells: int = 5000) -> str:
    values: list[str] = []
    with zipfile.ZipFile(BytesIO(data)) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        sheet_names = [
            name for name in archive.namelist() if name.startswith("xl/worksheets/sheet")
        ]
        for sheet_name in sheet_names:
            root = ElementTree.fromstring(archive.read(sheet_name))
            for cell in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                value_node = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                if value_node is None or value_node.text is None:
                    continue
                raw = value_node.text.strip()
                cell_type = cell.attrib.get("t")
                if cell_type == "s" and raw.isdigit():
                    value = shared_strings[int(raw)] if int(raw) < len(shared_strings) else raw
                else:
                    value = raw
                if value:
                    values.append(value)
                if len(values) >= max_cells:
                    return clean_text(" ".join(values))
    return clean_text(" ".join(values))


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for item in root.iter(f"{ns}si"):
        strings.append(clean_text(" ".join(node.text or "" for node in item.iter(f"{ns}t"))))
    return strings


def extract_pdf_text(data: bytes) -> str:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        return extract_pdf_text_with_pdftotext(data)

    with fitz.open(stream=data, filetype="pdf") as document:
        return clean_text(" ".join(page.get_text("text") for page in document))


def extract_pdf_text_with_pdftotext(data: bytes) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    with tempfile.TemporaryDirectory(prefix="bridge-rag-pdf-") as temp_dir:
        pdf_path = Path(temp_dir) / "source.pdf"
        text_path = Path(temp_dir) / "source.txt"
        pdf_path.write_bytes(data)
        completed = subprocess.run(
            [pdftotext, "-layout", str(pdf_path), str(text_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if completed.returncode != 0 or not text_path.exists():
            return ""
        return clean_text(text_path.read_text(encoding="utf-8", errors="replace"))


def extract_text(data: bytes, source_type: str) -> str:
    if source_type == "html" or source_type == "dataset":
        return extract_html_text(data)
    if source_type == "csv":
        return extract_csv_text(data)
    if source_type == "xlsx":
        return extract_xlsx_text(data)
    if source_type == "pdf":
        return extract_pdf_text(data)
    return clean_text(data.decode("utf-8", errors="replace"))


def chunk_text(text: str, max_tokens: int = 420, overlap: int = 80) -> list[str]:
    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_count = 0

    for sentence in sentences:
        sentence_tokens = tokenize(sentence)
        if not sentence_tokens:
            continue
        if current and current_count + len(sentence_tokens) > max_tokens:
            chunks.append(clean_text(" ".join(current)))
            overlap_words = tokenize(" ".join(current))[-overlap:]
            current = [" ".join(overlap_words)] if overlap_words else []
            current_count = len(overlap_words)
        current.append(sentence)
        current_count += len(sentence_tokens)

    if current:
        chunks.append(clean_text(" ".join(current)))
    return [chunk for chunk in chunks if len(tokenize(chunk)) >= 12]


def build_chunks_for_source(
    source: Source,
    *,
    fetch: bool,
    raw_dir: Path | None = None,
    fetched_at: str | None = None,
) -> tuple[list[CorpusChunk], str]:
    fetched_at = fetched_at or datetime.now(UTC).isoformat()
    extracted_texts: list[tuple[str, str, str, str]] = []
    status = "seeded"
    attempted_fetch = False
    fetched_targets = 0

    if fetch:
        for title, source_type, url in _source_fetch_targets(source):
            attempted_fetch = True
            try:
                data = fetch_bytes(url)
            except (TimeoutError, URLError, OSError):
                continue
            fetched_targets += 1
            if raw_dir:
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_name = f"{source.id}_{safe_file_slug(title)}"
                (raw_dir / raw_name).write_bytes(data)
            text = extract_text(data, source_type)
            if text:
                extracted_texts.append((title, source_type, url, text))
                status = "live"

    if not extracted_texts and source.local_seed_text:
        if attempted_fetch:
            status = "fetch_empty_seeded" if fetched_targets else "fetch_failed_seeded"
        extracted_texts.append((source.title, source.type, source.url, source.local_seed_text))

    chunks: list[CorpusChunk] = []
    for title, source_type, url, text in extracted_texts:
        for index, content in enumerate(chunk_text(text)):
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            chunk_id = f"{source.id}:{content_hash[:12]}:{index}"
            chunks.append(
                CorpusChunk(
                    chunk_id=chunk_id,
                    source_id=source.id,
                    source_title=title,
                    source_url=url,
                    authority=source.authority,
                    domain=source.domain,
                    priority=source.priority,
                    source_type=source_type,
                    source_status=status if status != "seeded" else source.status or "seeded",
                    content=content,
                    content_hash=content_hash,
                    chunk_index=index,
                    heading=None,
                    page=None,
                    fetched_at=fetched_at if status == "live" else None,
                    token_count=len(tokenize(content)),
                )
            )
    return chunks, status if chunks else "empty"


def _source_fetch_targets(source: Source) -> list[tuple[str, str, str]]:
    targets = [(source.title, source.type, source.url)]
    targets.extend((resource.title, resource.type, resource.url) for resource in source.resources)
    return targets


def safe_file_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9.]+", "-", value).strip("-").lower()
    return slug or "source"


def build_corpus(
    sources_path: Path,
    *,
    fetch: bool,
    output_dir: Path | None = None,
) -> IngestReport:
    sources = load_sources(sources_path)
    chunks: list[CorpusChunk] = []
    source_status: dict[str, str] = {}
    raw_dir = output_dir / "raw" if output_dir else None
    fetched_at = datetime.now(UTC).isoformat()

    for source in sources:
        source_chunks, status = build_chunks_for_source(
            source,
            fetch=fetch,
            raw_dir=raw_dir,
            fetched_at=fetched_at,
        )
        source_status[source.id] = status
        chunks.extend(source_chunks)

    if output_dir:
        write_index(chunks, output_dir, source_status=source_status, sources_path=sources_path)
    return IngestReport(chunks=chunks, source_status=source_status, output_dir=output_dir)


def write_index(
    chunks: list[CorpusChunk],
    output_dir: Path,
    *,
    source_status: dict[str, str],
    sources_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = output_dir / "corpus_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "sources_path": str(sources_path),
        "chunk_count": len(chunks),
        "source_status": source_status,
        "token_count": sum(chunk.token_count for chunk in chunks),
        "index_kind": "local_hybrid_lexical_chargram",
        "embedding_model": "char_3gram_hash",
        "bm25": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_index(output_dir: Path) -> list[CorpusChunk]:
    chunks_path = output_dir / "corpus_chunks.jsonl"
    if not chunks_path.exists():
        return []
    chunks: list[CorpusChunk] = []
    with chunks_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                chunks.append(CorpusChunk.from_json(json.loads(line)))
    return chunks


def hashed_char_ngrams(text: str, buckets: int = 256) -> dict[int, float]:
    normalized = clean_text(text.lower())
    vector: dict[int, float] = {}
    for index in range(max(0, len(normalized) - 2)):
        gram = normalized[index : index + 3]
        if " " in gram:
            continue
        bucket = int(hashlib.sha1(gram.encode("utf-8")).hexdigest(), 16) % buckets
        vector[bucket] = vector.get(bucket, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm:
        vector = {key: value / norm for key, value in vector.items()}
    return vector


def cosine(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())
