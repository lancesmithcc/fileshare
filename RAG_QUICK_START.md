# RAG with Source Links - Quick Start Guide

## ✅ What's Implemented

Your AI is now connected to the Knowledge Garden file share with **source attribution**!

### Features:
- 🔍 **RAG (Retrieval Augmented Generation)** - AI retrieves relevant context from your files
- 📚 **Source Links** - Every AI response shows which files were used
- 🎯 **Smart Chunking** - Documents split into 512-char chunks with 128-char overlap
- ⚡ **Fast Embeddings** - Using OpenAI's `text-embedding-3-small` model
- 💬 **Chat Integration** - Archdruid bot cites sources in chat messages
- 📊 **API Endpoint** - `/ai/insight` returns both response and sources

## 🚀 Getting Started

### 1. Index Your Files

First, index all files in your Knowledge Garden:

```bash
curl -X POST https://www.awen01.cc/ai/index-files \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{}'
```

Or index a specific folder:

```bash
curl -X POST https://www.awen01.cc/ai/index-files \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"folder_id": 1}'
```

### 2. Check RAG Status

```bash
curl https://www.awen01.cc/ai/rag-status \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

Response:
```json
{
  "enabled": true,
  "total_files": 5,
  "indexed_files": 3,
  "total_chunks": 42,
  "config": {
    "top_k": 3,
    "chunk_size": 512,
    "chunk_overlap": 128
  }
}
```

### 3. Test the AI

Ask the Archdruid bot a question in chat that relates to your files. The response will include:
- The AI-generated answer
- Source citations like: `[Source 1], [Source 2]`
- A footer with clickable file links:
  ```
  📚 Sources:
  • document.txt (relevance: 0.85) - /files/preview/1
  • notes.md (relevance: 0.72) - /files/preview/2
  ```

## 📋 API Response Format

The `/ai/insight` endpoint now returns:

```json
{
  "insight": "Based on the documents, here's what I found...",
  "sources": [
    {
      "id": 1,
      "name": "document.txt",
      "url": "/files/preview/1",
      "relevance": 0.85
    },
    {
      "id": 2,
      "name": "notes.md",
      "url": "/files/preview/2",
      "relevance": 0.72
    }
  ]
}
```

## ⚙️ Configuration

Edit `.env` to customize RAG behavior:

```bash
# Enable/disable RAG
NEO_DRUIDIC_RAG_ENABLED=true

# Number of relevant chunks to retrieve
NEO_DRUIDIC_RAG_TOP_K=3

# Size of text chunks (characters)
NEO_DRUIDIC_RAG_CHUNK_SIZE=512

# Overlap between chunks (characters)
NEO_DRUIDIC_RAG_CHUNK_OVERLAP=128
```

## 🔧 How It Works

1. **Question Asked**: User asks the AI a question
2. **Embedding Generated**: Question is converted to a vector (1536 dimensions)
3. **Similarity Search**: System finds the 3 most similar document chunks
4. **Context Building**: Relevant chunks are formatted with source labels:
   ```
   Context from Knowledge Garden:

   [Source 1: document.txt (relevance: 0.85)]
   <chunk content>

   [Source 2: notes.md (relevance: 0.72)]
   <chunk content>

   ---
   Please cite sources in your response...
   ```
5. **AI Generation**: OpenAI generates response using the context
6. **Source Attribution**: Response includes source links

## 📁 File Types Supported

Currently indexes text-based files:
- `.txt` - Plain text
- `.md` - Markdown
- `.pdf` - PDF documents
- `.doc`, `.docx` - Word documents
- `.csv` - CSV files
- `.json` - JSON files
- `.xml` - XML files
- `.html` - HTML files

## 🎯 Best Practices

1. **Re-index After Uploads**: Run `/ai/index-files` whenever you add new documents
2. **Monitor Status**: Check `/ai/rag-status` to see indexing progress
3. **Keep Files Organized**: Use folders to organize Knowledge Garden
4. **File Naming**: Use descriptive names - they appear in source citations
5. **File Size**: Large files are truncated to 10MB max per file

## 🐛 Troubleshooting

**No sources shown?**
- Check if files are indexed: `/ai/rag-status`
- Verify RAG is enabled in `.env`
- Check that OPENAI_API_KEY is set

**Relevance too low?**
- Files may not contain relevant content
- Try more specific questions
- Lower `min_similarity` in code if needed

**Chat not showing sources?**
- Hard refresh browser (Ctrl+Shift+R)
- Check Flask logs: `tail -f logs/flask.log`

## 📊 Database

Sources are stored in the `document_embeddings` table:
- `file_asset_id` - Links to file
- `chunk_index` - Chunk number in file
- `content` - The text chunk
- `embedding` - Vector embedding (JSON array)
- `created_at` - Timestamp

To see what's indexed:
```sql
SELECT fa.original_name, COUNT(de.id) as chunks
FROM file_assets fa
JOIN document_embeddings de ON de.file_asset_id = fa.id
GROUP BY fa.original_name;
```

## 🎉 Next Steps

1. Index your Knowledge Garden files
2. Ask the AI questions about your documents
3. Click source links to view the original files
4. Enjoy context-aware AI responses!

---

*Generated for Neo-Druidic Society RAG implementation*
*Using OpenAI embeddings + GPT-4o-mini for fast, cited responses*
