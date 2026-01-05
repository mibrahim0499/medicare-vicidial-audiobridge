#!/usr/bin/env python3
"""Test script to verify Asterisk ARI connection"""

import asyncio
import sys
from app.config import settings
from app.services.asterisk_client import AsteriskARIClient


async def test_ari_connection():
    """Test ARI connection and basic operations"""
    print("Testing Asterisk ARI Connection...")
    print(f"Host: {settings.ASTERISK_HOST}:{settings.ASTERISK_PORT}")
    print(f"Username: {settings.ASTERISK_USERNAME}")
    print("-" * 50)
    
    client = AsteriskARIClient()
    
    try:
        # Connect
        print("1. Connecting to ARI...")
        await client.connect()
        print("   ✓ Connected successfully")
        
        # Get channels
        print("2. Getting active channels...")
        channels = await client.get_channels()
        print(f"   ✓ Found {len(channels)} active channels")
        
        if channels:
            # Test getting channel details
            channel_id = channels[0].get("id")
            print(f"3. Getting details for channel {channel_id}...")
            channel = await client.get_channel(channel_id)
            if channel:
                print("   ✓ Channel details retrieved")
                print(f"   - State: {channel.get('state')}")
                print(f"   - Name: {channel.get('name')}")
            else:
                print("   ✗ Failed to get channel details")
        
        print("-" * 50)
        print("ARI connection test completed successfully!")
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("-" * 50)
        print("ARI connection test failed!")
        return False
    
    finally:
        await client.disconnect()


if __name__ == "__main__":
    success = asyncio.run(test_ari_connection())
    sys.exit(0 if success else 1)

