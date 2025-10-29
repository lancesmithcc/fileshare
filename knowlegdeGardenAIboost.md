# Knowledge Garden AI Boost with RAG

## Goal
Enhance the Archdruid AI bot with RAG (Retrieval Augmented Generation) using pgvector to provide context from the Knowledge Garden file share.

## Architecture

### 1. Vector Database (pgvector)
- Store embeddings of file contents in PostgreSQL
- Enable semantic search for relevant documents
- Fast similarity queries using pgvector indexes

### 2. Embedding Service
- Use sentence-transformers for local embedding generation
- Model: `all-MiniLM-L6-v2` (fast, 384 dimensions)
- Generate embeddings for file chunks

### 3. RAG Pipeline
```
User Question
    �
Generate Query Embedding
    �
Search Similar Documents (pgvector)
    �
Retrieve Top-K Most Relevant Chunks
    �
Augment AI Prompt with Context
    �
Generate Response with Context
```

### 4. AI Model Strategy
**Option A: Fast API-based (Recommended)**
- Use OpenAI/Anthropic API for instant responses
- Much faster than local LLaMA
- Handles context well

**Option B: Optimized Local Model**
- Switch to smaller, faster model (TinyLlama-1.1B)
- Add timeout and error handling
- Use for privacy-sensitive responses

### 5. Integration Points
- **Chat**: Archdruid bot uses RAG for contextual responses
- **Feed**: AI insights enhanced with relevant documents
- **Auto-indexing**: New files automatically embedded on upload

## Implementation Steps

1.  Install pgvector extension
2. � Create document embeddings table
3. � Build embedding service
4. � Implement RAG retrieval
5. � Switch AI model to API or fix local
6. � Integrate RAG into chat responses
7. � Integrate RAG into feed insights
8. � Add file upload auto-indexing
9. � Test and optimize

## Database Schema

```sql
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    file_asset_id INTEGER REFERENCES file_assets(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- all-MiniLM-L6-v2 dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_asset_id, chunk_index)
);

CREATE INDEX ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
```

## Usage Example

```python
# User asks in chat: "What are the key points about quantum entanglement?"
#
# System:
# 1. Generate embedding for question
# 2. Query pgvector for similar document chunks
# 3. Find: "quantum_physics.pdf chunks 5, 12, 23"
# 4. Build prompt:
#    """
#    Context from Knowledge Garden:
#    [Chunk from quantum_physics.pdf]
#    [Chunk from quantum_physics.pdf]
#
#    User question: What are the key points about quantum entanglement?
#    """
# 5. AI generates contextual answer
```

## Configuration

Add to Flask config:
```python
# AI Model
AI_PROVIDER = "openai"  # or "anthropic" or "local"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# RAG Settings
RAG_ENABLED = True
RAG_TOP_K = 5  # Number of relevant chunks to retrieve
RAG_CHUNK_SIZE = 512  # Characters per chunk
RAG_CHUNK_OVERLAP = 128  # Overlap between chunks
```
Feature: Knowledge Boost (RAG with pgvector + OCR ingest)
1. Goal

Give tinyllama smarter answers by letting it pull real context from your shared files.

We will:

Index the content of your shared file folder (including PDFs).

Store that content in Postgres with pgvector.

At question time, grab the most relevant chunks and send them along with the user’s question to tinyllama.

Keep the whole thing local/private on your Bodhi Linux box.

This becomes the memory for tinyllama. No cloud.

2. User story / flow

You drop files (txt, md, pdf, etc.) into the shared file area on awen01.cc.

You run the ingest job (script now, button later).

The ingest job:

reads those files

does OCR for PDFs if needed

cuts them into chunks

embeds those chunks

stores them in Postgres with pgvector

You open your chat with tinyllama and ask a question.

Before tinyllama answers:

the system searches pgvector for the closest chunks

adds those chunks into the prompt to tinyllama

tinyllama answers using your own data.

So tinyllama is “boosted” by your knowledge base.

3. Scope

In scope:

Postgres + pgvector setup.

A new table rag_chunks to hold content and embeddings.

An ingest script in Python that:

walks the shared folder

extracts text (OCR if needed)

chunks text

embeds text

writes to pgvector

A retriever function that runs a similarity search in pgvector and returns top chunks.

An update to the chat pipeline so tinyllama sees those chunks.

Out of scope (for now):

UI for ingest (can come later in steward panel).

Per-user access control to knowledge.

Auto-reingest on file change.

Full table/figure reconstruction like high-end DeepSeek OCR (we’ll leave that for future).

4. System layout

The feature is made of 3 main parts:

A) Postgres with pgvector
B) Ingest pipeline (file → chunks → embeddings → pgvector)
C) Retrieval pipeline (question → pgvector search → tinyllama prompt)

A) Postgres with pgvector
Purpose

Store text chunks from your files plus their embedding vectors. Let us do similarity search using SQL.

Setup

Install pgvector on the Bodhi Linux box’s Postgres. This step is done manually with sudo on the box one time before we build the remote tunnel. After pgvector is installed and CREATE EXTENSION vector; succeeds, we don’t need sudo for normal use.

In your Postgres DB (awen01 or a new db if we want isolation), run:

CREATE EXTENSION IF NOT EXISTS vector;


Create table:

CREATE TABLE rag_chunks (
  id SERIAL PRIMARY KEY,
  file_path TEXT NOT NULL,      -- where we got this text
  page_or_section TEXT,         -- page number or section label for PDFs
  chunk_index INT NOT NULL,     -- order within that file/section
  content TEXT NOT NULL,        -- the actual text chunk
  embedding vector(768),        -- embedding for this chunk (dim must match model)
  created_at TIMESTAMP DEFAULT NOW()
);


Create index for nearest-neighbor:

CREATE INDEX rag_chunks_embedding_idx
ON rag_chunks
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);


We may need to ANALYZE rag_chunks after inserts so the planner understands the index.

Why this design

file_path shows origin for debugging.

page_or_section helps when the source is a PDF so we can trace back to a page.

chunk_index lets us later reconstruct order within the file if we want a longer answer.

embedding is the semantic vector for fast lookup.

B) Ingest pipeline
Goal

Read every allowed file in the shared folder, turn it into a bunch of searchable chunks, and load them into Postgres.

File types we handle

.txt

.md

.pdf

We can add others later.

Steps for each file

The ingest script will run something like this for each file:

Step 1. Load raw text

If file is .txt or .md:

read file directly as UTF-8 text.

If file is .pdf:

Try to extract text layer using a PDF text extractor (like pdfminer.six or similar Python lib).

If we get meaningful text: use that.

If the PDF has no selectable text (it’s just scanned images or garbage layout):

We switch to OCR.

Step 2. OCR path (PDF only)

We will OCR scanned pages using PaddleOCR first, and Tesseract only if PaddleOCR fails.

Pipeline:

For each page image in that PDF:

Run PaddleOCR in CPU mode to get the text lines.

Join those lines into a single clean block of text for that page.

If PaddleOCR throws or can’t decode (blank result), then:

Use Tesseract (pytesseract) as fallback for that page.

So: PaddleOCR is our main OCR engine (better accuracy than Tesseract on messy scans, still CPU-friendly), and Tesseract is our safety net.

This gives us page-level text, private on your box, no cloud calls.

We then combine all page strings into a final text body for that PDF. We also keep track of which page each chunk came from so we can store page_or_section in the DB.

Step 3. Clean text

We do a cleanup pass before chunking:

Remove repeated headers/footers.

Fix hard line breaks mid sentence.

Merge hyphenated words split at line ends.

Collapse multiple blank lines.

This gives nicer context text for tinyllama later.

Step 4. Chunking

We split the cleaned text into chunks sized for retrieval. Target:

~500 tokens each, or ~1000-1500 characters each, whichever is easier to implement.

We number them chunk_index = 0, 1, 2...

For PDFs:

We can include page info in the chunk metadata, like:

page_or_section = "page 12"
For plain text:

page_or_section can be null or a section header if you parse markdown headers.

Step 5. Embedding

For each chunk:

Run an embedding model to produce a vector (dim 768 is example, final dim must match table schema).

This embedding model should be local if possible. If a remote embedding API is used, that leaks data. We want local to keep privacy intact.

We store:

the chunk text

its vector

source file path

page info

chunk index

Step 6. Insert into Postgres

For each chunk, insert:

INSERT INTO rag_chunks (
  file_path,
  page_or_section,
  chunk_index,
  content,
  embedding
) VALUES ($1, $2, $3, $4, $5);


The $5 is the vector for pgvector.

Step 7. Rebuild logic / updates

Before inserting for a given file, the script should delete old rows for that file so we don’t get duplicates.

Example:

DELETE FROM rag_chunks
WHERE file_path = $1;


Then insert fresh rows.

This lets you re-run ingest any time you update a doc.

Step 8. Post-ingest analyze

After a batch ingest, run:

ANALYZE rag_chunks;


to help Postgres use the ivfflat index for searches.

Where the ingest script lives

Put it in /neo-druidic-society/ (for example /neo-druidic-society/rag_ingest.py)

It should accept:

base folder path for the shared files

DB creds

optional flags like --rebuild-all or --rebuild file.pdf

Access / safety

Only you run ingest.

No public route calls ingest.

Ingest script is allowed to read the file share folder and write to DB.

It is not exposed through Cloudflare Tunnel.

It stays offline / local on your Bodhi box.

C) Retrieval pipeline
Goal

When you (or later, a user) ask a question, we grab the most relevant chunks from the DB and feed them into tinyllama’s prompt so it can answer grounded in your data.

Steps

Take user question q.

Embed it using the same embedding model we used in ingest. This keeps vector spaces consistent.

Run a pgvector query like:

SELECT content, file_path, page_or_section
FROM rag_chunks
ORDER BY embedding <-> $EMBED_VECTOR
LIMIT 5;


<-> is the distance operator provided by pgvector.

LIMIT 5 gives top 5 chunks. We can tune that number.

Build context block for tinyllama. For example:

System instructions for tinyllama:

“Use the provided context to answer the question. If the context does not include the answer, say you don’t know. Do not invent.”

Context block:

Chunk 1 (with source info)

Chunk 2

Chunk 3

Chunk 4

Chunk 5

User message:

The actual question q

Send that final combined prompt to tinyllama (your local model runner).

tinyllama responds. You show that answer in your chat UI.

Privacy

We do not send the chunks to any third-party API.

We keep it local.

If later you expose this chat to users, you should gate it so only trusted users can ask. Because the model will sometimes leak parts of the source chunks in its answer, which is what you want for you, but you might not want for randoms.

Roles and access control

Two layers of control:

Ingest control

Only steward/admin (you) can trigger ingest.

Ingest script is not callable from the public site.

Ingest runs on the Bodhi box directly.

Ask-a-question

Chat with tinyllama + Knowledge Boost can later be exposed to normal users if you want.

Or it can stay steward-only at first, so no one else can query your stash.

This prevents someone from using RAG as a search engine to mine private files unless you actually want that.

Security model

Hard rules:

pgvector setup happens on the Linux box under your control. We do that BEFORE we add the remote shell tunnel feature. That way the DB is already structured and ready.

Postgres never gets exposed over Cloudflare Tunnel. The DB port stays on localhost / LAN only.

The ingest script runs locally and touches the file share directly. No outside user input here.

OCR pipeline:

PaddleOCR first, Tesseract only if PaddleOCR fails.

All OCR happens local. No page images leave the box.

This means even scanned PDFs with very personal info end up in pgvector without leaving home.

Cleanup / chunking removes headers/footers and fixes broken lines, but does not try to “beautify” meaning. We want accuracy in recall, not marketing fluff.

We include file_path and page_or_section in the DB row so we can trace any given answer back to source if we ever need receipts.

We do not store API keys, wallet seeds, or secrets in this shared folder if we don’t want them to show up in answers later. We can add skip rules: skip any file path that matches *.secret.* or folders like /private/ if you want a safe zone.

Audit: The ingest script should print a small log to console (and optionally a log file) with:

which files were just indexed

number of chunks created per file

OCR warnings (if OCR had to fall back to Tesseract)

This lets you see what went into tinyllama’s “memory.”

Done when

Knowledge Boost feature counts as done when:

pgvector is installed and rag_chunks table + ivfflat index exist in Postgres.

We can run rag_ingest.py and it:

walks the shared folder

extracts text from .txt / .md

extracts text from .pdf:

uses PDF text layer if available

else uses PaddleOCR per page

else falls back to Tesseract per page

cleans text (remove headers/footers, merge lines)

chunks text and embeds chunks

inserts rows (text + vector) into Postgres

logs what it did

We can ask tinyllama a question through a RAG-aware chat call and:

the retriever does an embedding on the question

pgvector returns top chunks

those chunks get added to tinyllama’s prompt

tinyllama answers using that info

All of this runs 100 percent on your Bodhi Linux box, with no outside network calls, and does not depend on the future Cloudflare tunnel / QR shell feature.

Once this is live, tinyllama becomes a context boosted ass assistant that knows your PDFs, your notes, and anything else you put in the shared folder.