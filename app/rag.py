"""RAG (Retrieval Augmented Generation) service for Knowledge Garden."""
from __future__ import annotations

import json
import logging
from typing import Optional

from flask import Flask
from sqlalchemy import and_

from .embeddings import cosine_similarity, generate_embedding
from .models import DocumentEmbedding, FileAsset, db

logger = logging.getLogger(__name__)


def retrieve_relevant_documents(
    query: str,
    top_k: int = 5,
    min_similarity: float = 0.5,
    app: Optional[Flask] = None
) -> list[tuple[FileAsset, str, float]]:
    """
    Retrieve the most relevant document chunks for a query using RAG.

    Args:
        query: The user's question or prompt
        top_k: Number of top results to return
        min_similarity: Minimum similarity threshold (0-1)
        app: Flask app instance (optional, for context)

    Returns:
        List of (file_asset, chunk_content, similarity_score) tuples, sorted by relevance
    """
    try:
        # Generate embedding for the query
        query_embedding = generate_embedding(query)
        logger.info("Generated query embedding for: '%s...'", query[:50])

        # Get all document embeddings from database
        embeddings = DocumentEmbedding.query.all()

        if not embeddings:
            logger.warning("No document embeddings found in database")
            return []

        logger.info("Searching through %d document chunks", len(embeddings))

        # Calculate similarity scores
        results = []
        for doc_emb in embeddings:
            try:
                # Parse stored embedding from JSON
                stored_embedding = json.loads(doc_emb.embedding)

                # Calculate cosine similarity
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity >= min_similarity:
                    results.append((
                        doc_emb.file_asset,
                        doc_emb.content,
                        similarity
                    ))

            except Exception as exc:
                logger.error("Error processing embedding %d: %s", doc_emb.id, exc)
                continue

        # Sort by similarity (highest first) and take top_k
        results.sort(key=lambda x: x[2], reverse=True)
        top_results = results[:top_k]

        logger.info(
            "Found %d relevant chunks (min similarity: %.2f)",
            len(top_results),
            min_similarity
        )

        return top_results

    except Exception as exc:
        logger.error("Failed to retrieve documents: %s", exc)
        return []


def build_rag_context(query: str, top_k: int = 3) -> tuple[str, list[dict]]:
    """
    Build a context string from relevant documents for RAG.

    Args:
        query: The user's question
        top_k: Number of documents to include

    Returns:
        Tuple of (formatted_context_string, list_of_source_dicts)
    """
    # Quick check: if no embeddings exist, skip expensive operations
    embedding_count = DocumentEmbedding.query.count()
    if embedding_count == 0:
        logger.info("No document embeddings found - skipping RAG")
        return "", []

    results = retrieve_relevant_documents(query, top_k=top_k)

    if not results:
        return "", []

    context_parts = ["Context from Knowledge Garden:\n"]
    sources = []

    for i, (file_asset, chunk_content, similarity) in enumerate(results, 1):
        context_parts.append(
            f"\n[Source {i}: {file_asset.display_name} (relevance: {similarity:.2f})]"
        )
        context_parts.append(chunk_content)
        context_parts.append("")  # Empty line between chunks

        # Build source reference
        sources.append({
            "id": file_asset.id,
            "name": file_asset.display_name,
            "url": f"/files/preview/{file_asset.id}",
            "relevance": round(similarity, 2)
        })

    context_parts.append("\n---\n")
    context_parts.append("Please cite sources in your response by referring to [Source 1], [Source 2], etc.\n")

    return "\n".join(context_parts), sources


def index_file(file_asset: FileAsset, chunk_size: int = 512, overlap: int = 128) -> int:
    """
    Index a file by generating and storing embeddings for its content.

    Args:
        file_asset: The FileAsset to index
        chunk_size: Size of text chunks
        overlap: Overlap between chunks

    Returns:
        Number of chunks indexed
    """
    from .embeddings import embed_document

    try:
        # Read file content
        content = file_asset.read_text_safe()
        if not content:
            logger.warning("File %s has no readable content", file_asset.display_name)
            return 0

        # Clean null bytes just in case (belt and suspenders)
        content = content.replace('\x00', '')

        logger.info("Indexing file: %s (%d chars)", file_asset.display_name, len(content))

        # Delete existing embeddings for this file
        DocumentEmbedding.query.filter_by(file_asset_id=file_asset.id).delete()
        db.session.commit()  # Commit deletion before proceeding

        # Generate embeddings
        chunk_embeddings = embed_document(content, chunk_size, overlap)

        # Store in database
        for chunk_index, (chunk_text, embedding) in enumerate(chunk_embeddings):
            # Clean chunk text of null bytes
            chunk_text_clean = chunk_text.replace('\x00', '')

            doc_emb = DocumentEmbedding(
                file_asset_id=file_asset.id,
                chunk_index=chunk_index,
                content=chunk_text_clean,
                embedding=json.dumps(embedding)  # Store as JSON array
            )
            db.session.add(doc_emb)

        db.session.commit()

        logger.info(
            "Indexed %d chunks for file: %s",
            len(chunk_embeddings),
            file_asset.display_name
        )

        return len(chunk_embeddings)

    except Exception as exc:
        logger.error("Failed to index file %s: %s", file_asset.display_name, exc, exc_info=True)
        db.session.rollback()
        return 0


def index_all_files(folder_id: Optional[int] = None) -> dict[str, int]:
    """
    Index all files in the Knowledge Garden (or a specific folder).

    Args:
        folder_id: Optional folder ID to index (None = all files)

    Returns:
        Dict with stats: {"indexed": count, "failed": count, "skipped": count}
    """
    stats = {"indexed": 0, "failed": 0, "skipped": 0}

    # Get files to index
    query = FileAsset.query
    if folder_id is not None:
        query = query.filter_by(folder_id=folder_id)

    files = query.all()
    logger.info("Starting indexing of %d files", len(files))

    # Supported file extensions (now includes images for OCR)
    supported_extensions = (
        '.txt', '.md', '.pdf', '.doc', '.docx', '.csv', '.json', '.xml', '.html', '.htm',
        '.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.scss', '.yaml', '.yml',
        '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'  # Images with OCR
    )

    for file_asset in files:
        # Skip unsupported files
        if not file_asset.display_name.lower().endswith(supported_extensions):
            logger.debug("Skipping unsupported file: %s", file_asset.display_name)
            stats["skipped"] += 1
            continue

        try:
            logger.info("Indexing file: %s", file_asset.display_name)
            chunks_indexed = index_file(file_asset)
            if chunks_indexed > 0:
                stats["indexed"] += 1
                logger.info("Successfully indexed %s (%d chunks)", file_asset.display_name, chunks_indexed)
            else:
                logger.warning("No content extracted from %s", file_asset.display_name)
                stats["skipped"] += 1

        except Exception as exc:
            logger.error("Failed to index %s: %s", file_asset.display_name, exc, exc_info=True)
            stats["failed"] += 1

    logger.info(
        "Indexing complete: indexed=%d, failed=%d, skipped=%d",
        stats["indexed"],
        stats["failed"],
        stats["skipped"]
    )

    return stats
