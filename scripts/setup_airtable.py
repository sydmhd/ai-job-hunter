"""
scripts/setup_airtable.py — Verify Airtable connection and print schema instructions.

Usage: python scripts/setup_airtable.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from tools.airtable_tool import setup_airtable_schema, get_table
from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME


def test_connection():
    print("\n🔌 Testing Airtable connection...")
    try:
        table = get_table()
        # Try to list records (will fail if table doesn't exist yet)
        records = table.all(max_records=1)
        print(f"✅ Connected to Airtable!")
        print(f"   Base ID: {AIRTABLE_BASE_ID}")
        print(f"   Table: {AIRTABLE_TABLE_NAME}")
        print(f"   Existing records: {len(records)}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"\n   Make sure:")
        print(f"   1. AIRTABLE_API_KEY is set in .env")
        print(f"   2. AIRTABLE_BASE_ID is correct (from your base URL)")
        print(f"   3. Table '{AIRTABLE_TABLE_NAME}' exists in your base")
        return False


def test_log_sample():
    """Insert a test record and then delete it."""
    from tools.airtable_tool import log_application, get_table
    print("\n🧪 Testing record creation...")
    try:
        record_id = log_application(
            company="TEST COMPANY",
            role="TEST ROLE",
            platform="LinkedIn",
            jd_url="https://example.com",
            relevance_score=9,
            notes="This is a test record — safe to delete",
        )
        print(f"✅ Test record created: {record_id}")

        # Clean up
        table = get_table()
        table.delete(record_id)
        print(f"✅ Test record deleted — Airtable integration working!\n")
        return True
    except Exception as e:
        print(f"❌ Record creation failed: {e}\n")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  Airtable Setup & Verification")
    print("=" * 60)

    # Print schema
    setup_airtable_schema()

    # Test connection
    connected = test_connection()
    if connected:
        test_log_sample()
    else:
        print("\nFix the connection issues above, then re-run this script.")
        sys.exit(1)
