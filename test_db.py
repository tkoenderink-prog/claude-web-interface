#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test database connection."""

import os
from pathlib import Path

# Test different URI formats
base_dir = Path(__file__).parent
db_path = base_dir / 'data' / 'claude_clone.db'

print(f"Base dir: {base_dir}")
print(f"DB path: {db_path}")
print(f"DB path exists: {db_path.parent.exists()}")

# Create directory if needed
db_path.parent.mkdir(parents=True, exist_ok=True)

# Test URI formats
uris = [
    f'sqlite:///{db_path}',
    f'sqlite:////{db_path}',
    f'sqlite:///{str(db_path).replace(" ", "%20")}',
    'sqlite:///data/claude_clone.db',
]

from sqlalchemy import create_engine, text

for uri in uris:
    print(f"\nTrying URI: {uri[:50]}...")
    try:
        engine = create_engine(uri)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("  ✓ Success!")
    except Exception as e:
        print(f"  ✗ Error: {e}")