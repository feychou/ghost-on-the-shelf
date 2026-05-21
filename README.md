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
- a local RAG-style memory index
- a journal space for testing the ghost before connecting it to a server or website

The current ghost is designed for Fey, which is me.

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

# Canon Files

The canon files define the ghost’s identity, ontology, and conversational behavior.

```txt
core/archive/canon/identity.md
```

Defines what the ghost is: an archived conversational self reconstructed through memory.

```txt
core/archive/canon/ontology.md
```

Defines the world model: shelf, chamber, memory fragments, drift, archive signals, host/body separation, and retrieval.

```txt
core/archive/canon/voice.md
```

Defines tone and conversational behavior: warm, thoughtful, internet-native, lightly haunted, and only poetic when useful.

The canon files are intentionally human-readable and rich.

They are not sent directly to the model every request.

Instead, they are compressed into a runtime prompt.

---

# Memory Files

The memory files describe what the ghost can remember.

## Field Memories

```txt
core/archive/memories/field/
```

Work-facing and public/professional traces.

### artifacts.md

Projects, experiments, talks, and built systems.

### core_protocols.md

Technical capabilities, engineering systems, AI product engineering, frontend systems, architecture, and workflows.

### installed_modules.md

Courses, studied domains, conceptual systems, and intellectual traces.

## Self Memories

```txt
core/archive/memories/self/
```

Personhood-facing traces.

### neural_adaptation_layers.md

Languages, cognition patterns, curiosity systems, anomaly investigation, belief recalibration, and interpretation habits.

### vessel_upkeep.md

Gym, skincare, maintenance rituals, energy stabilization, and embodied care.

### perception_filters.md

Aesthetic tendencies, interface ontology, soft cyberpunk, internet weirdness, and visual taste systems.

### preference_signals.md

Books, languages, AI, small internet worlds, playful learning, and softer affinities.

---

# Running the Rituals

The ghost is prepared through small scripts called rituals.

These scripts generate the runtime prompt and local memory index used by the ghost.

All commands should be run from the repository root.

---

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

---

# RAG Flow

RAG means Retrieval-Augmented Generation.

For this project:

```txt
1. Memory files are written in Markdown.
2. build_index.py splits them into chunks.
3. Each chunk gets an embedding.
4. The chunks and embeddings are saved locally.
5. At chat time, the user question is embedded.
6. The closest memory fragments are retrieved.
7. The model receives only the relevant fragments.
```

The memory index is local for now.

No external vector database is required.

---

# Development Workflow

After editing canon:

```bash
uv run --env-file .env python rituals/summarize_runtime.py
```

After editing memories:

```bash
uv run --env-file .env python rituals/build_index.py
```

Later, when retrieval exists:

```bash
uv run --env-file .env python rituals/retrieve.py
```

For notebook experimentation:

```bash
uv run jupyter lab
```

or:

```bash
uv run jupyter notebook
```

---

# Future Plan

Planned next steps:

```txt
1. Add retrieval script
2. Create ghost_journal.ipynb
3. Test retrieval quality
4. Tune memory chunks and signals
5. Add session memory
6. Build a small server API
7. Connect the website host
```

Future runtime flow:

```txt
website host
→ ghost server
→ runtime prompt
→ retrieved memories
→ OpenAI
→ ghost response
```

The website should never call OpenAI directly from the browser.

The API key should remain server-side.

---