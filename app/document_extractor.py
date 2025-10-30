"""Document text extraction with OCR support for PDFs and images."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF with OCR fallback.

    Tries multiple methods:
    1. PyPDF2 for text-based PDFs
    2. pdfplumber for better text extraction
    3. PaddleOCR for scanned/image PDFs
    4. Tesseract as final fallback

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text content
    """
    text_parts = []

    # Method 1: Try PyPDF2 (fast, works for text PDFs)
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text)

        if text_parts:
            extracted = '\n\n'.join(text_parts)
            # Remove null bytes which PostgreSQL doesn't allow
            extracted = extracted.replace('\x00', '')
            if len(extracted.strip()) > 100:  # At least 100 chars = likely good extraction
                logger.info("Extracted %d chars from PDF using PyPDF2", len(extracted))
                return extracted
    except Exception as exc:
        logger.warning("PyPDF2 extraction failed: %s", exc)

    # Method 2: Try pdfplumber (better text extraction)
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text)

        if text_parts:
            extracted = '\n\n'.join(text_parts)
            # Remove null bytes which PostgreSQL doesn't allow
            extracted = extracted.replace('\x00', '')
            if len(extracted.strip()) > 100:
                logger.info("Extracted %d chars from PDF using pdfplumber", len(extracted))
                return extracted
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)

    # Method 3: Try PaddleOCR (for scanned PDFs/images)
    try:
        from paddleocr import PaddleOCR
        from pdf2image import convert_from_path

        logger.info("PDF appears to be scanned, trying PaddleOCR...")

        # Convert PDF pages to images
        images = convert_from_path(file_path, dpi=200)

        # Initialize PaddleOCR (English)
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

        text_parts = []
        for i, image in enumerate(images):
            # Save temp image
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                image.save(tmp.name)
                tmp_path = tmp.name

            # Run OCR
            result = ocr.ocr(tmp_path, cls=True)

            # Extract text from result
            if result and result[0]:
                page_text = ' '.join([line[1][0] for line in result[0]])
                text_parts.append(page_text)

            # Clean up temp file
            Path(tmp_path).unlink()

        if text_parts:
            extracted = '\n\n'.join(text_parts)
            # Remove null bytes which PostgreSQL doesn't allow
            extracted = extracted.replace('\x00', '')
            logger.info("Extracted %d chars from PDF using PaddleOCR", len(extracted))
            return extracted

    except Exception as exc:
        logger.warning("PaddleOCR extraction failed: %s", exc)

    # Method 4: Try Tesseract OCR as final fallback
    try:
        from pdf2image import convert_from_path
        import pytesseract
        from PIL import Image

        logger.info("Trying Tesseract OCR as fallback...")

        images = convert_from_path(file_path, dpi=200)
        text_parts = []

        for image in images:
            page_text = pytesseract.image_to_string(image)
            if page_text and page_text.strip():
                text_parts.append(page_text)

        if text_parts:
            extracted = '\n\n'.join(text_parts)
            # Remove null bytes which PostgreSQL doesn't allow
            extracted = extracted.replace('\x00', '')
            logger.info("Extracted %d chars from PDF using Tesseract", len(extracted))
            return extracted

    except Exception as exc:
        logger.warning("Tesseract extraction failed: %s", exc)

    logger.error("All PDF extraction methods failed for: %s", file_path)
    return ""


def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from image using OCR.

    Tries PaddleOCR first, then Tesseract as fallback.

    Args:
        file_path: Path to the image file

    Returns:
        Extracted text content
    """
    # Method 1: Try PaddleOCR (more accurate)
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        result = ocr.ocr(file_path, cls=True)

        if result and result[0]:
            text = ' '.join([line[1][0] for line in result[0]])
            # Remove null bytes which PostgreSQL doesn't allow
            text = text.replace('\x00', '')
            logger.info("Extracted %d chars from image using PaddleOCR", len(text))
            return text

    except Exception as exc:
        logger.warning("PaddleOCR image extraction failed: %s", exc)

    # Method 2: Try Tesseract as fallback
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)

        if text and text.strip():
            # Remove null bytes which PostgreSQL doesn't allow
            text = text.replace('\x00', '')
            logger.info("Extracted %d chars from image using Tesseract", len(text))
            return text

    except Exception as exc:
        logger.warning("Tesseract image extraction failed: %s", exc)

    logger.error("All image extraction methods failed for: %s", file_path)
    return ""


def extract_text_from_file(file_path: str, mime_type: Optional[str] = None) -> str:
    """
    Extract text from any supported file type.

    Supports:
    - Plain text (.txt, .md, .csv, .json, .xml, .html, .py, .js, etc.)
    - PDFs (.pdf) with OCR fallback
    - Images (.png, .jpg, .jpeg, .tiff, .bmp) with OCR
    - Word documents (.docx) - future enhancement

    Args:
        file_path: Path to the file
        mime_type: Optional MIME type hint

    Returns:
        Extracted text content
    """
    path = Path(file_path)

    if not path.exists():
        logger.error("File not found: %s", file_path)
        return ""

    # Get file extension
    ext = path.suffix.lower()

    # PDF files
    if ext == '.pdf' or (mime_type and 'pdf' in mime_type.lower()):
        return extract_text_from_pdf(file_path)

    # Image files
    if ext in ('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'):
        return extract_text_from_image(file_path)

    # Word documents (DOCX)
    if ext == '.docx':
        try:
            from docx import Document
            doc = Document(file_path)
            text = '\n\n'.join([para.text for para in doc.paragraphs if para.text])
            # Remove null bytes which PostgreSQL doesn't allow
            text = text.replace('\x00', '')
            logger.info("Extracted %d chars from DOCX", len(text))
            return text
        except Exception as exc:
            logger.warning("DOCX extraction failed: %s", exc)
            return ""

    # Plain text files
    text_extensions = (
        '.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm',
        '.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.scss',
        '.yaml', '.yml', '.ini', '.conf', '.log', '.sql', '.sh'
    )

    if ext in text_extensions or (mime_type and 'text' in mime_type.lower()):
        try:
            # Try UTF-8 first
            text = path.read_text(encoding='utf-8')
            # Remove null bytes which PostgreSQL doesn't allow
            text = text.replace('\x00', '')
            logger.info("Extracted %d chars from text file", len(text))
            return text
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                text = path.read_text(encoding='latin-1')
                # Remove null bytes which PostgreSQL doesn't allow
                text = text.replace('\x00', '')
                logger.info("Extracted %d chars from text file (latin-1)", len(text))
                return text
            except Exception as exc:
                logger.error("Text file reading failed: %s", exc)
                return ""

    logger.warning("Unsupported file type: %s (ext=%s, mime=%s)", file_path, ext, mime_type)
    return ""
