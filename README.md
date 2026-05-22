# Ghost on the Shelf

A portable ghost core for a conversational archive.

**Ghost on the Shelf** is an experiment in AI memory, runtime prompts, retrieval, and conversational identity. It treats an AI persona as an archived presence reconstructed from canon files, memory fragments, and interaction.

---

# What Is This?

This repository contains the reusable ghost core.

It includes:

- canon files that define the ghost’s identity, ontology, and voice
- memory files that describe what the ghost can remember
- rituals that generate runtime artifacts
- a journal space for testing the ghost before connecting it to a server or website

The current ghost is designed for Fey, which is me. Editing the content of the files in `core` will change that.

---

# Philosophy

Ghost on the Shelf treats AI memory as interface material.
Runtime prompts become stabilization protocols.
Embeddings become latent memory space.
Retrieved chunks become memory fragments.
The context window becomes an active consciousness field.
The user does not open a chatbot.
The user awakens an archive.

---

# Repository Structure

```txt
ghost-on-the-shelf/
  core/
    archive/
      canon/
        identity.md
        ontology.md
        voice.md

      memories/
        field/
          artifacts.md
          core_protocols.md
          installed_modules.md

        self/
          neural_adaptation_layers.md
          vessel_upkeep.md
          perception_filters.md
          preference_signals.md

    shelf/
      ghost_runtime.md
      indexes/
        memory_index.json

  rituals/
    summarize_runtime.py
    build_index.py

  journal/
    ghost_journal.ipynb

  pyproject.toml
  uv.lock
  README.md
```

---

# Directory Meaning

```txt
core/
```

The ghost essence. Contains source canon, memories, and generated runtime artifacts.

```txt
core/archive/canon/
```

Human-written canon files. These define who the ghost is and how she behaves.

```txt
core/archive/memories/
```

Memory modules the ghost can retrieve from.

```txt
core/shelf/
```

Generated runtime artifacts. This directory can be rebuilt from the canon and memory files.

```txt
rituals/
```

Scripts that prepare the ghost.

```txt
journal/
```

Notebook space for testing, tuning, and observing the ghost.

---

# Installation

This project uses Python and `uv`.

Requirements:

- Python 3.11+
- uv
- an OpenAI API key

Clone the repository:

```bash
git clone https://github.com/feychou/ghost-on-the-shelf.git
cd ghost-on-the-shelf
```

Install dependencies:

```bash
uv sync
```

Create a local `.env` file:

```bash
OPENAI_API_KEY=your_api_key_here
```

## Generate the Runtime Prompt

The runtime prompt is the compact instruction layer sent with every chat request.

It is generated from:

```txt
core/archive/canon/identity.md
core/archive/canon/ontology.md
core/archive/canon/voice.md
```

Run:

```bash
uv run --env-file .env python rituals/summarize_runtime.py
```

Expected output:

```txt
Wrote core/shelf/ghost_runtime.md
Runtime characters: ...
Runtime words approx: ...
```

This generates:

```txt
core/shelf/ghost_runtime.md
```

Run this ritual whenever the canon files change.

---

## Build the Memory Index

The memory index is a local RAG-style retrieval index.

It is generated from:

```txt
core/archive/memories/**/*.md
```

Run:

```bash
uv run --env-file .env python rituals/build_index.py
```

Expected output:

```txt
Wrote core/shelf/indexes/memory_index.json
Chunks indexed: ...
Embedding model: text-embedding-3-small
Embedding dimensions: 256
```

This generates:

```txt
core/shelf/indexes/memory_index.json
```

Run this ritual whenever memory files change.

---

# Runtime Concept

At runtime, the ghost should receive:

```txt
ghost_runtime.md
+ retrieved memory fragments
+ session summary
+ user message
```

The full canon and full memory library are not sent every request.

Instead:

```txt
canon files
→ summarized into runtime prompt

memory files
→ chunked and embedded into memory index

user question
→ retrieves relevant memory fragments
→ generates ghost response
```
