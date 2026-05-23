from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryChunk:
    id: str
    source: str
    module: str
    title: str
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class MemoryIndex:
    embedding_model: str
    embedding_dimensions: int | None
    chunks: list[MemoryChunk]

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


@dataclass(frozen=True)
class RuntimeArchive:
    runtime_prompt: str
    memory_index: MemoryIndex


def load_runtime_archive(runtime_prompt_path: Path, memory_index_path: Path) -> RuntimeArchive:
    if not runtime_prompt_path.exists():
        raise FileNotFoundError(f"Missing runtime prompt: {runtime_prompt_path}")

    if not memory_index_path.exists():
        raise FileNotFoundError(f"Missing memory index: {memory_index_path}")

    runtime_prompt = runtime_prompt_path.read_text(encoding="utf-8")

    with memory_index_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    chunks = [
        MemoryChunk(
            id=item["id"],
            source=item["source"],
            module=item["module"],
            title=item["title"],
            text=item["text"],
            embedding=[float(value) for value in item["embedding"]],
        )
        for item in payload.get("chunks", [])
    ]

    memory_index = MemoryIndex(
        embedding_model=payload["embedding_model"],
        embedding_dimensions=payload.get("embedding_dimensions"),
        chunks=chunks,
    )

    return RuntimeArchive(runtime_prompt=runtime_prompt, memory_index=memory_index)
