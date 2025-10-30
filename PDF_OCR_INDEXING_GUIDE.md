# PDF & OCR Indexing Guide

## 🔍 Problem Fixed!

Your RAG wasn't working because **no files were indexed yet**. The system now has:

1. ✅ **PDF Text Extraction** - Extracts text from PDF files
2. ✅ **OCR Support** - Reads text from scanned PDFs and images
3. ✅ **Multiple Methods** - PyPDF2 → pdfplumber → PaddleOCR → Tesseract

## 📁 Your Files

You have 5 files in Knowledge Garden that need indexing:
- `Mycelium_Running.pdf` (25 MB)
- `permaculture-a-designers-manual.pdf` (21 MB)
- `thegameoflife.pdf` (277 KB)
- `bare_jrnl.pdf` (701 KB)
- `owl.png` (3.2 MB)

## 🚀 How to Index Your Files

### Option 1: Using the API (Recommended)

```bash
curl -X POST https://www.awen01.cc/ai/index-files \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{}'
```

### Option 2: Manual Script (More Verbose)

```bash
cd /home/lanc3lot/neo-druidic-society
.venv/bin/python index_files_manual.py
```

This will show detailed progress:
```
2025-10-29 22:30:15 - INFO - Starting Knowledge Garden indexing...
2025-10-29 22:30:16 - INFO - Indexing file: Mycelium_Running.pdf
2025-10-29 22:30:20 - INFO - Extracted 50000 chars from PDF using PyPDF2
2025-10-29 22:30:21 - INFO - Successfully indexed Mycelium_Running.pdf (98 chunks)
...
============================================================
INDEXING COMPLETE!
============================================================
✅ Indexed: 5 files
⏭️  Skipped: 0 files
❌ Failed:  0 files
============================================================
RAG is now ready to use!
```

## 📦 Required System Packages

For PDF to image conversion (needed for OCR):
```bash
sudo apt install -y poppler-utils tesseract-ocr
```

These are optional but recommended for better OCR performance.

## 🔧 How It Works

### Text PDFs (Fast Method)
```
PDF File → PyPDF2/pdfplumber → Extract Text → Done
```

### Scanned PDFs or Images (OCR Method)
```
PDF/Image → Convert to Images → PaddleOCR → Extract Text → Done
                                  ↓ (if fails)
                               Tesseract
```

### Extraction Priority:
1. **PyPDF2** - Fastest, for text-based PDFs
2. **pdfplumber** - Better text extraction for complex PDFs
3. **PaddleOCR** - AI-powered OCR for scanned documents
4. **Tesseract** - Fallback OCR engine

## 📊 What Gets Indexed

**Supported File Types:**
- ✅ PDFs (`.pdf`)
- ✅ Images (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`, `.gif`)
- ✅ Text files (`.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`)
- ✅ Code files (`.py`, `.js`, `.ts`, `.css`, etc.)
- ✅ Word documents (`.docx`)

**Processing:**
- Files are split into 512-character chunks
- Each chunk has 128-character overlap
- Chunks are embedded using OpenAI's `text-embedding-3-small`
- Embeddings stored in `document_embeddings` table

## ⚡ Performance Notes

**Large PDFs:**
- Your PDFs are 20-25 MB each
- Text extraction: ~5-10 seconds per PDF
- OCR (if needed): ~30-60 seconds per PDF
- Total indexing time: ~5-10 minutes for all files

**Memory Usage:**
- PaddleOCR: ~500 MB RAM
- Large PDFs: ~100-200 MB RAM per file
- Total: ~1-2 GB RAM during indexing

## 🧪 Testing After Indexing

Once files are indexed, test the RAG:

```bash
# Check status
curl https://www.awen01.cc/ai/rag-status -H "Cookie: session=YOUR_SESSION"
```

Expected response:
```json
{
  "enabled": true,
  "total_files": 5,
  "indexed_files": 5,
  "total_chunks": 450,
  "config": {"top_k": 3, "chunk_size": 512, "chunk_overlap": 128}
}
```

Then ask the AI:
- "What does Mycelium Running say about mushrooms?"
- "What are the principles in the permaculture manual?"
- "Explain the game of life"

The AI will cite sources like:
```
Based on the permaculture manual [Source 1], the key principles are...

📚 Sources:
• permaculture-a-designers-manual.pdf (relevance: 0.89) - /files/preview/3
• Mycelium_Running.pdf (relevance: 0.72) - /files/preview/6
```

## 🐛 Troubleshooting

**"No content extracted from file"**
- PDF may be image-based → Install poppler-utils and tesseract-ocr
- File may be corrupted
- Check logs: `tail -f logs/flask.log`

**"PaddleOCR failed"**
- PaddleOCR packages still installing (check background process)
- Will fall back to Tesseract automatically
- Still works, just slightly less accurate

**"Tesseract extraction failed"**
- tesseract-ocr not installed: `sudo apt install tesseract-ocr`
- Or continue without OCR for text-based PDFs

**Slow indexing?**
- Normal for large PDFs with OCR
- Run `index_files_manual.py` to see detailed progress
- Can take 5-10 minutes for your 5 files

## 📝 Current Package Status

Installing (running in background):
- ✅ PyPDF2 (installed)
- ✅ pdfplumber (installed)
- ✅ pdf2image (installed)
- ✅ python-docx (installed)
- 🔄 PaddleOCR (installing... large package ~500MB)
- 🔄 pytesseract (installing...)

**You can start indexing now!** It will work with PyPDF2/pdfplumber for text PDFs. OCR will activate when PaddleOCR finishes installing.

## 🎯 Next Steps

1. Wait for packages to finish installing (~5 more minutes)
2. Install system dependencies (optional but recommended):
   ```bash
   sudo apt install -y poppler-utils tesseract-ocr
   ```
3. Index your files:
   ```bash
   .venv/bin/python index_files_manual.py
   ```
4. Test RAG by asking questions about your PDFs
5. See sources cited in AI responses!

---

*Note: The system will automatically re-extract text when you re-index. If OCR wasn't working the first time, just re-run indexing after installing Tesseract.*
