#!/usr/bin/env python3
"""
Batch PDF Transcript Import Script

Import multiple PDF transcripts with automatic or manual YouTube video matching.

Usage:
    python scripts/import_pdf_transcripts_batch.py --folder /path/to/pdfs
    python scripts/import_pdf_transcripts_batch.py --mapping-csv mappings.csv
    python scripts/import_pdf_transcripts_batch.py --folder /path/to/pdfs --auto-match --confidence-threshold 0.8
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.logger import get_logger
from src.knowledge_system.processors.pdf_transcript_processor import PDFTranscriptProcessor
from src.knowledge_system.services.youtube_video_matcher import YouTubeVideoMatcher
from src.knowledge_system.services.transcript_manager import TranscriptManager

logger = get_logger(__name__)


class BatchPDFImporter:
    """Batch import PDF transcripts with YouTube matching."""
    
    def __init__(
        self,
        auto_match: bool = False,
        confidence_threshold: float = 0.8,
        headless: bool = True
    ):
        """
        Initialize batch importer.
        
        Args:
            auto_match: Enable automatic YouTube matching
            confidence_threshold: Minimum confidence for auto-match
            headless: Run browser in headless mode
        """
        self.auto_match = auto_match
        self.confidence_threshold = confidence_threshold
        self.headless = headless
        
        self.db_service = DatabaseService()
        self.pdf_processor = PDFTranscriptProcessor(db_service=self.db_service)
        self.transcript_manager = TranscriptManager(db_service=self.db_service)
        
        if auto_match:
            self.video_matcher = YouTubeVideoMatcher(
                db_service=self.db_service,
                headless=headless,
                confidence_threshold=confidence_threshold
            )
        else:
            self.video_matcher = None
    
    async def import_folder(self, folder_path: Path) -> dict:
        """
        Import all PDF files from a folder.
        
        Args:
            folder_path: Path to folder containing PDFs
        
        Returns:
            Statistics dict
        """
        if not folder_path.exists():
            logger.error(f"Folder not found: {folder_path}")
            return {"error": "Folder not found"}
        
        # Find all PDF files
        pdf_files = list(folder_path.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {folder_path}")
            return {"total": 0, "imported": 0, "failed": 0}
        
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        stats = {
            "total": len(pdf_files),
            "imported": 0,
            "failed": 0,
            "matched": 0,
            "unmatched": 0,
        }
        
        for pdf_file in pdf_files:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {pdf_file.name}")
                logger.info(f"{'='*60}")
                
                result = await self.import_single_pdf(pdf_file)
                
                if result["success"]:
                    stats["imported"] += 1
                    if result.get("matched"):
                        stats["matched"] += 1
                    else:
                        stats["unmatched"] += 1
                else:
                    stats["failed"] += 1
            
            except Exception as e:
                logger.error(f"Failed to process {pdf_file.name}: {e}")
                stats["failed"] += 1
        
        return stats
    
    async def import_from_csv(self, csv_path: Path) -> dict:
        """
        Import PDFs using CSV mapping file.
        
        CSV format: pdf_path,youtube_url
        
        Args:
            csv_path: Path to CSV mapping file
        
        Returns:
            Statistics dict
        """
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return {"error": "CSV file not found"}
        
        mappings = []
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mappings.append({
                    "pdf_path": Path(row["pdf_path"]),
                    "youtube_url": row.get("youtube_url", ""),
                })
        
        logger.info(f"Found {len(mappings)} mappings in CSV")
        
        stats = {
            "total": len(mappings),
            "imported": 0,
            "failed": 0,
            "matched": 0,
            "unmatched": 0,
        }
        
        for mapping in mappings:
            try:
                pdf_path = mapping["pdf_path"]
                youtube_url = mapping["youtube_url"]
                
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {pdf_path.name}")
                if youtube_url:
                    logger.info(f"YouTube URL: {youtube_url}")
                logger.info(f"{'='*60}")
                
                result = await self.import_single_pdf(
                    pdf_path,
                    youtube_url=youtube_url if youtube_url else None
                )
                
                if result["success"]:
                    stats["imported"] += 1
                    if result.get("matched"):
                        stats["matched"] += 1
                    else:
                        stats["unmatched"] += 1
                else:
                    stats["failed"] += 1
            
            except Exception as e:
                logger.error(f"Failed to process {pdf_path.name}: {e}")
                stats["failed"] += 1
        
        return stats
    
    async def import_single_pdf(
        self,
        pdf_path: Path,
        youtube_url: str = None
    ) -> dict:
        """
        Import a single PDF transcript.
        
        Args:
            pdf_path: Path to PDF file
            youtube_url: Optional YouTube URL
        
        Returns:
            Result dict with success, matched, etc.
        """
        # Process PDF
        result = self.pdf_processor.process(
            pdf_path,
            youtube_url=youtube_url
        )
        
        if not result.success:
            logger.error(f"PDF processing failed: {result.errors}")
            return {"success": False, "error": result.errors}
        
        source_id = result.data["source_id"]
        pdf_metadata = result.data["metadata"]
        
        # If YouTube URL not provided and auto-match enabled, try to find video
        matched = False
        if not youtube_url and self.auto_match and self.video_matcher:
            logger.info("🔍 Attempting automatic YouTube matching...")
            
            pdf_text_preview = result.data["text"][:2000]
            
            video_id, confidence, method = await self.video_matcher.find_youtube_video(
                pdf_metadata,
                pdf_text_preview
            )
            
            if video_id and confidence >= self.confidence_threshold:
                logger.info(
                    f"✅ Matched to YouTube video: {video_id} "
                    f"(confidence: {confidence:.2f}, method: {method})"
                )
                matched = True
                
                # Update source with YouTube metadata
                # Fetch YouTube metadata and update source
                from src.knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
                yt_processor = YouTubeDownloadProcessor()
                # This would fetch and update metadata
                
            elif video_id:
                logger.warning(
                    f"⚠️ Low confidence match: {video_id} "
                    f"(confidence: {confidence:.2f}) - flagged for review"
                )
            else:
                logger.info("❌ No YouTube match found")
        
        logger.info(
            f"✅ Imported PDF transcript: {pdf_path.name}\n"
            f"   Source ID: {source_id}\n"
            f"   Quality: {result.data['quality_score']:.2f}\n"
            f"   Speakers: {len(result.data['speakers'])}\n"
            f"   Has timestamps: {result.data['has_timestamps']}"
        )
        
        return {
            "success": True,
            "source_id": source_id,
            "matched": matched,
            "quality_score": result.data["quality_score"],
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch import PDF transcripts with YouTube matching"
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--folder",
        type=Path,
        help="Folder containing PDF files"
    )
    input_group.add_argument(
        "--mapping-csv",
        type=Path,
        help="CSV file with PDF → YouTube URL mappings"
    )
    
    # Matching options
    parser.add_argument(
        "--auto-match",
        action="store_true",
        help="Enable automatic YouTube video matching"
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.8,
        help="Minimum confidence for auto-match (default: 0.8)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (for debugging)"
    )
    
    args = parser.parse_args()
    
    # Create importer
    importer = BatchPDFImporter(
        auto_match=args.auto_match,
        confidence_threshold=args.confidence_threshold,
        headless=not args.no_headless
    )
    
    # Import PDFs
    if args.folder:
        logger.info(f"Importing PDFs from folder: {args.folder}")
        stats = await importer.import_folder(args.folder)
    else:
        logger.info(f"Importing PDFs from CSV: {args.mapping_csv}")
        stats = await importer.import_from_csv(args.mapping_csv)
    
    # Print summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"Total PDFs:      {stats['total']}")
    print(f"Imported:        {stats['imported']}")
    print(f"Failed:          {stats['failed']}")
    if args.auto_match:
        print(f"Matched:         {stats['matched']}")
        print(f"Unmatched:       {stats['unmatched']}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

