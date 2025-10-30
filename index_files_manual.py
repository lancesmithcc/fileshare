#!/usr/bin/env python3
"""Manual script to index all files in Knowledge Garden for RAG."""

import logging
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.rag import index_all_files

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Index all files in Knowledge Garden."""
    logger.info("Starting Knowledge Garden indexing...")

    # Create Flask app context
    app = create_app()

    with app.app_context():
        try:
            # Index all files
            logger.info("Indexing files...")
            stats = index_all_files()

            logger.info("=" * 60)
            logger.info("INDEXING COMPLETE!")
            logger.info("=" * 60)
            logger.info(f"✅ Indexed: {stats['indexed']} files")
            logger.info(f"⏭️  Skipped: {stats['skipped']} files")
            logger.info(f"❌ Failed:  {stats['failed']} files")
            logger.info("=" * 60)

            if stats['indexed'] > 0:
                logger.info("RAG is now ready to use!")
                logger.info("Ask the AI questions about your documents in chat.")
            else:
                logger.warning("No files were indexed. Check logs above for errors.")

        except Exception as exc:
            logger.error("Indexing failed: %s", exc, exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()
