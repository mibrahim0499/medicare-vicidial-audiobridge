#!/usr/bin/env python3
"""
Script to list and display information about saved audio chunks.

Usage:
    python scripts/list_audio_chunks.py                    # Show all chunks
    python scripts/list_audio_chunks.py --call-id CALL_ID  # Show chunks for specific call
    python scripts/list_audio_chunks.py --summary          # Show summary only
    python scripts/list_audio_chunks.py --filesystem       # Show filesystem chunks only
    python scripts/list_audio_chunks.py --database         # Show database chunks only
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import json

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from app.database.connection import AsyncSessionLocal
from app.database.models import Call as DBCall, AudioStream as DBAudioStream, AudioChunk as DBAudioChunk
from app.config import settings


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def scan_filesystem_chunks(call_id: Optional[str] = None) -> Dict[str, List[Dict]]:
    """Scan filesystem for audio chunks"""
    storage_path = Path(settings.AUDIO_STORAGE_PATH)
    
    if not storage_path.exists():
        return {}
    
    chunks_by_call = {}
    
    # If specific call_id, only scan that directory
    if call_id:
        call_dirs = [storage_path / call_id] if (storage_path / call_id).exists() else []
    else:
        call_dirs = [d for d in storage_path.iterdir() if d.is_dir()]
    
    for call_dir in call_dirs:
        call_id_key = call_dir.name
        chunks = []
        
        for chunk_file in sorted(call_dir.glob("chunk_*.raw")):
            try:
                stat = chunk_file.stat()
                chunks.append({
                    "path": str(chunk_file),
                    "filename": chunk_file.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime)
                })
            except Exception as e:
                chunks.append({
                    "path": str(chunk_file),
                    "filename": chunk_file.name,
                    "size": 0,
                    "error": str(e)
                })
        
        if chunks:
            chunks_by_call[call_id_key] = chunks
    
    return chunks_by_call


async def get_database_chunks(call_id: Optional[str] = None) -> Dict[str, List[Dict]]:
    """Get audio chunks from database"""
    async with AsyncSessionLocal() as session:
        query = select(DBAudioChunk)
        
        if call_id:
            query = query.where(DBAudioChunk.call_id == call_id)
        
        query = query.order_by(DBAudioChunk.call_id, DBAudioChunk.chunk_index)
        
        result = await session.execute(query)
        chunks = result.scalars().all()
        
        chunks_by_call = {}
        for chunk in chunks:
            if chunk.call_id not in chunks_by_call:
                chunks_by_call[chunk.call_id] = []
            
            chunks_by_call[chunk.call_id].append({
                "id": chunk.id,
                "stream_id": chunk.stream_id,
                "chunk_index": chunk.chunk_index,
                "size": chunk.size,
                "data_path": chunk.data_path,
                "timestamp": chunk.timestamp,
                "created_at": chunk.created_at
            })
        
        return chunks_by_call


async def get_chunk_statistics(call_id: Optional[str] = None) -> Dict:
    """Get statistics about chunks"""
    async with AsyncSessionLocal() as session:
        # Database statistics
        query = select(
            func.count(DBAudioChunk.id).label("total_chunks"),
            func.sum(DBAudioChunk.size).label("total_size"),
            func.count(func.distinct(DBAudioChunk.call_id)).label("total_calls")
        )
        
        if call_id:
            query = query.where(DBAudioChunk.call_id == call_id)
        
        result = await session.execute(query)
        stats = result.first()
        
        db_stats = {
            "total_chunks": stats.total_chunks or 0,
            "total_size": stats.total_size or 0,
            "total_calls": stats.total_calls or 0
        }
        
        # Filesystem statistics
        fs_chunks = scan_filesystem_chunks(call_id)
        fs_total_chunks = 0
        fs_total_size = 0
        fs_total_calls = len(fs_chunks)
        
        for call_chunks in fs_chunks.values():
            fs_total_chunks += len(call_chunks)
            fs_total_size += sum(c.get("size", 0) for c in call_chunks)
        
        return {
            "database": db_stats,
            "filesystem": {
                "total_chunks": fs_total_chunks,
                "total_size": fs_total_size,
                "total_calls": fs_total_calls
            }
        }


def print_chunks_table(chunks_by_call: Dict[str, List[Dict]], source: str = "filesystem"):
    """Print chunks in a formatted table"""
    if not chunks_by_call:
        print(f"\n📭 No {source} chunks found.")
        return
    
    total_chunks = 0
    total_size = 0
    
    for call_id, chunks in sorted(chunks_by_call.items()):
        call_size = sum(c.get("size", 0) for c in chunks)
        total_chunks += len(chunks)
        total_size += call_size
        
        print(f"\n📞 Call ID: {call_id}")
        print(f"   Chunks: {len(chunks)} | Total Size: {format_size(call_size)}")
        print(f"   {'─' * 80}")
        
        if source == "filesystem":
            print(f"   {'Filename':<40} {'Size':<15} {'Modified':<20}")
            print(f"   {'─' * 80}")
            for chunk in chunks[:20]:  # Show first 20 chunks
                filename = chunk.get("filename", "unknown")
                size = format_size(chunk.get("size", 0))
                modified = chunk.get("modified", datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
                print(f"   {filename:<40} {size:<15} {modified:<20}")
            
            if len(chunks) > 20:
                print(f"   ... and {len(chunks) - 20} more chunks")
        
        elif source == "database":
            print(f"   {'Index':<8} {'Stream ID':<30} {'Size':<15} {'Timestamp':<20}")
            print(f"   {'─' * 80}")
            for chunk in chunks[:20]:  # Show first 20 chunks
                idx = chunk.get("chunk_index", 0)
                stream_id = chunk.get("stream_id", "unknown")
                size = format_size(chunk.get("size", 0))
                timestamp = chunk.get("timestamp", datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
                print(f"   {idx:<8} {stream_id:<30} {size:<15} {timestamp:<20}")
            
            if len(chunks) > 20:
                print(f"   ... and {len(chunks) - 20} more chunks")
    
    print(f"\n{'=' * 80}")
    print(f"📊 Total: {total_chunks} chunks | {format_size(total_size)}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="List and display information about saved audio chunks"
    )
    parser.add_argument(
        "--call-id",
        type=str,
        help="Show chunks for a specific call ID only"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics only"
    )
    parser.add_argument(
        "--filesystem",
        action="store_true",
        help="Show filesystem chunks only"
    )
    parser.add_argument(
        "--database",
        action="store_true",
        help="Show database chunks only"
    )
    
    args = parser.parse_args()
    
    # Default: show both
    show_filesystem = not args.database
    show_database = not args.filesystem
    
    if args.summary:
        # Show summary only
        stats = await get_chunk_statistics(args.call_id)
        
        print("\n" + "=" * 80)
        print("📊 AUDIO CHUNKS SUMMARY")
        print("=" * 80)
        
        print("\n💾 Database:")
        db = stats["database"]
        print(f"   Total Calls: {db['total_calls']}")
        print(f"   Total Chunks: {db['total_chunks']}")
        print(f"   Total Size: {format_size(db['total_size'])}")
        
        print("\n📁 Filesystem:")
        fs = stats["filesystem"]
        print(f"   Total Calls: {fs['total_calls']}")
        print(f"   Total Chunks: {fs['total_chunks']}")
        print(f"   Total Size: {format_size(fs['total_size'])}")
        
        print("\n" + "=" * 80)
        return
    
    # Show detailed chunks
    if args.call_id:
        print(f"\n🔍 Showing chunks for Call ID: {args.call_id}")
    else:
        print(f"\n🔍 Showing all chunks")
    
    if show_filesystem:
        print("\n" + "=" * 80)
        print("📁 FILESYSTEM CHUNKS")
        print("=" * 80)
        fs_chunks = scan_filesystem_chunks(args.call_id)
        print_chunks_table(fs_chunks, source="filesystem")
    
    if show_database:
        print("\n" + "=" * 80)
        print("💾 DATABASE CHUNKS")
        print("=" * 80)
        db_chunks = await get_database_chunks(args.call_id)
        print_chunks_table(db_chunks, source="database")
    
    # Show summary at the end
    if not args.summary:
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        stats = await get_chunk_statistics(args.call_id)
        
        print("\n💾 Database:")
        db = stats["database"]
        print(f"   Total Calls: {db['total_calls']}")
        print(f"   Total Chunks: {db['total_chunks']}")
        print(f"   Total Size: {format_size(db['total_size'])}")
        
        print("\n📁 Filesystem:")
        fs = stats["filesystem"]
        print(f"   Total Calls: {fs['total_calls']}")
        print(f"   Total Chunks: {fs['total_chunks']}")
        print(f"   Total Size: {format_size(fs['total_size'])}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

