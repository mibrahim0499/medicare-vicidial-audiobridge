#!/usr/bin/env python3
"""
Script to update existing 'active' calls to 'completed' status.

Usage:
    python scripts/update_active_calls.py              # Dry run (shows what would be updated)
    python scripts/update_active_calls.py --execute     # Actually update the database
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.database.connection import AsyncSessionLocal
from app.database.models import Call as DBCall
from app.models.call import CallStatus


async def update_active_calls(dry_run: bool = True):
    """Update all active calls to completed status"""
    
    async with AsyncSessionLocal() as session:
        # Find all active calls
        result = await session.execute(
            select(DBCall).where(DBCall.status == CallStatus.ACTIVE)
        )
        active_calls = result.scalars().all()
        
        if not active_calls:
            print("✅ No active calls found in database.")
            return
        
        print(f"\n📊 Found {len(active_calls)} active call(s) to update:\n")
        
        updated_count = 0
        for call in active_calls:
            # Calculate duration if start_time exists
            duration = None
            if call.start_time:
                # Use end_time if exists, otherwise use updated_at or current time
                end_time = call.end_time or call.updated_at or datetime.utcnow()
                duration = int((end_time - call.start_time).total_seconds())
            
            # Set end_time if missing
            end_time = call.end_time or call.updated_at or datetime.utcnow()
            
            print(f"  Call ID: {call.call_id}")
            print(f"    Channel: {call.channel_id or 'N/A'}")
            print(f"    From: {call.caller_number or 'N/A'} → To: {call.callee_number or 'N/A'}")
            print(f"    Start: {call.start_time}")
            print(f"    End: {end_time}")
            print(f"    Duration: {duration}s" if duration else "    Duration: N/A")
            print()
            
            if not dry_run:
                # Update the call
                await session.execute(
                    update(DBCall)
                    .where(DBCall.id == call.id)
                    .values(
                        status=CallStatus.COMPLETED,
                        end_time=end_time,
                        duration=duration,
                        updated_at=datetime.utcnow()
                    )
                )
                updated_count += 1
        
        if dry_run:
            print(f"\n⚠️  DRY RUN: Would update {len(active_calls)} call(s).")
            print("   Run with --execute flag to actually update the database.")
        else:
            await session.commit()
            print(f"\n✅ Successfully updated {updated_count} call(s) to 'completed' status.")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Update active calls to completed status"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually update the database (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 Running in DRY RUN mode (no changes will be made)")
    else:
        print("⚠️  EXECUTE mode: Will update the database")
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            return
    
    try:
        await update_active_calls(dry_run=dry_run)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

