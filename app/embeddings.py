"""Embedding service for RAG using OpenAI embeddings API."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# OpenAI client (lazy loaded)
_openai_client = None


def _get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _openai_client
    if _openai_client is None:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _openai_client = openai.OpenAI(api_key=api_key)
    return _openai_client


def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for text using OpenAI API.

    Args:
        text: The text to embed

    Returns:
        List of floats representing the embedding vector (1536 dimensions for text-embedding-3-small)

    Raises:
        Exception: If embedding generation fails
    """
    try:
        client = _get_openai_client()

        # Use OpenAI's text-embedding-3-small model (fast and cheap)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )

        embedding = response.data[0].embedding
        logger.info("Generated embedding with %d dimensions", len(embedding))
        return embedding

    except Exception as exc:
        logger.error("Failed to generate embedding: %s", exc)
        raise


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 128) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Args:
        text: The text to chunk
        chunk_size: Maximum size of each chunk in characters
        overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary
        if end < len(text):
            # Look for sentence endings near the chunk boundary
            for punct in ['. ', '! ', '? ', '\n\n', '\n']:
                punct_pos = text.rfind(punct, start, end)
                if punct_pos > start + chunk_size // 2:  # Don't break too early
                    end = punct_pos + len(punct)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward, accounting for overlap
        start = end - overlap if end < len(text) else len(text)

    return chunks


def embed_document(content: str, chunk_size: int = 512, overlap: int = 128) -> list[tuple[str, list[float]]]:
    """
    Embed a document by chunking and generating embeddings for each chunk.

    Args:
        content: The document content
        chunk_size: Maximum size of each chunk
        overlap: Overlap between chunks

    Returns:
        List of (chunk_text, embedding_vector) tuples
    """
    chunks = chunk_text(content, chunk_size, overlap)
    logger.info("Split document into %d chunks", len(chunks))

    results = []
    for i, chunk in enumerate(chunks):
        try:
            embedding = generate_embedding(chunk)
            results.append((chunk, embedding))
            logger.debug("Embedded chunk %d/%d", i + 1, len(chunks))
        except Exception as exc:
            logger.error("Failed to embed chunk %d: %s", i, exc)
            # Continue with other chunks even if one fails

    return results


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0-1)
    """
    import math

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)
