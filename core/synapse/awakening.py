from __future__ import annotations

from typing import Any

from core.synapse.protocol import SynapseProtocol
from core.synapse.runtime import RuntimeArchive


def probe_openai_for_awakening(client: Any, protocol: SynapseProtocol, archive: RuntimeArchive) -> None:
    embedding_kwargs: dict[str, Any] = {
        "model": archive.memory_index.embedding_model,
        "input": "awakening probe",
    }

    if archive.memory_index.embedding_dimensions:
        embedding_kwargs["dimensions"] = archive.memory_index.embedding_dimensions

    client.embeddings.create(**embedding_kwargs)
    client.responses.create(
        model=protocol.chat_model,
        instructions="Return only the word awake.",
        input="Awakening probe.",
        max_output_tokens=protocol.awakening_probe_output_tokens,
        reasoning={"effort": protocol.reasoning_effort},
        store=False,
    )
