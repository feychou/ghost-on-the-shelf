from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from openai import OpenAI

client = OpenAI()

ROOT = Path(__file__).resolve().parents[1]

MEMORIES_DIR = ROOT / "core" / "archive" / "memories"
OUTPUT_FILE = ROOT / "core" / "shelf" / "indexes" / "memory_index.json"

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 256


@dataclass
class MemoryChunk:
    id: str
    source: str
    module: str
    title: str
    text: str
    embedding: list[float]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "untitled"


def stable_id(source: str, title: str, text: str) -> str:
    raw = f"{source}:{title}:{text}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{source}#{slugify(title)}-{digest}"


def discover_memory_files() -> list[Path]:
    if not MEMORIES_DIR.exists():
        raise FileNotFoundError(f"Missing memories directory: {MEMORIES_DIR}")

    return sorted(MEMORIES_DIR.glob("**/*.md"))


def split_markdown_by_headings(markdown: str) -> list[tuple[str, str]]:
    """
    Splits markdown into chunks by H2 sections.

    Example:
      # Artifacts
      intro...

      ## Ghost on the Shelf
      content...

    Produces:
      ("Introduction", "# Artifacts\\nintro...")
      ("Ghost on the Shelf", "## Ghost on the Shelf\\ncontent...")
    """
    lines = markdown.splitlines()

    chunks: list[tuple[str, list[str]]] = []
    current_title = "Introduction"
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                chunks.append((current_title, current_lines))

            current_title = line.replace("## ", "", 1).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append((current_title, current_lines))

    return [
        (title, "\n".join(chunk_lines).strip())
        for title, chunk_lines in chunks
        if "\n".join(chunk_lines).strip()
    ]


def module_name_for(path: Path) -> str:
    """
    core/archive/memories/field/artifacts.md -> field
    core/archive/memories/self/vessel_upkeep.md -> self
    """
    relative = path.relative_to(MEMORIES_DIR)
    return relative.parts[0] if len(relative.parts) > 1 else "default"


def source_name_for(path: Path) -> str:
    return str(path.relative_to(ROOT))


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    return [item.embedding for item in response.data]


def build_chunks() -> list[MemoryChunk]:
    memory_files = discover_memory_files()
    pending: list[dict[str, str]] = []

    for path in memory_files:
        markdown = path.read_text(encoding="utf-8")
        source = source_name_for(path)
        module = module_name_for(path)

        sections = split_markdown_by_headings(markdown)

        for title, text in sections:
            pending.append(
                {
                    "id": stable_id(source, title, text),
                    "source": source,
                    "module": module,
                    "title": title,
                    "text": text,
                }
            )

    embeddings = embed_texts([item["text"] for item in pending])
    chunks: list[MemoryChunk] = []

    for item, embedding in zip(pending, embeddings):
        chunks.append(
            MemoryChunk(
                id=item["id"],
                source=item["source"],
                module=item["module"],
                title=item["title"],
                text=item["text"],
                embedding=embedding,
            )
        )

    return chunks


def write_index(chunks: Iterable[MemoryChunk]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    chunk_list = [asdict(chunk) for chunk in chunks]

    payload = {
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "chunk_count": len(chunk_list),
        "chunks": chunk_list,
    }

    OUTPUT_FILE.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    chunks = build_chunks()
    write_index(chunks)

    print(f"Wrote {OUTPUT_FILE}")
    print(f"Chunks indexed: {len(chunks)}")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")


if __name__ == "__main__":
    main()