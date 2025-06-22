#!/usr/bin/env python3
"""
Fix SSML prosody rate values in the database.

This script updates incorrect prosody rate values that were causing
audio to play at double speed. The issue was that rate="90%" means
90% faster, not 90% of normal speed.
"""

import os
import re
import sqlite3
from pathlib import Path

def fix_prosody_rates(ssml_content: str) -> str:
    """
    Fix incorrect prosody rate values in SSML content.
    
    Converts:
    - rate="90%" to rate="-10%" (10% slower)
    - rate="95%" to rate="-5%" (5% slower)
    - rate="slow" remains unchanged (correct)
    """
    if not ssml_content:
        return ssml_content
    
    # Replace rate="90%" with rate="-10%"
    ssml_content = re.sub(r'rate="90%"', 'rate="-10%"', ssml_content)
    
    # Replace rate="95%" with rate="-5%"
    ssml_content = re.sub(r'rate="95%"', 'rate="-5%"', ssml_content)
    
    return ssml_content

def main():
    """Fix SSML prosody rates in the story database."""
    db_path = os.path.expanduser("~/.storyteller/story_database.db")
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return
    
    print("Fixing SSML prosody rates in the database...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all scenes with SSML content
    cursor.execute("""
        SELECT id, content_ssml 
        FROM scenes 
        WHERE content_ssml IS NOT NULL
    """)
    
    scenes = cursor.fetchall()
    updated_count = 0
    
    for scene_id, ssml_content in scenes:
        original = ssml_content
        fixed = fix_prosody_rates(ssml_content)
        
        if original != fixed:
            # Update the scene with fixed SSML
            cursor.execute("""
                UPDATE scenes 
                SET content_ssml = ? 
                WHERE id = ?
            """, (fixed, scene_id))
            updated_count += 1
            
            # Show what was changed
            print(f"\nScene ID {scene_id}:")
            print(f"  Fixed rate=\"90%\" → rate=\"-10%\"" if 'rate="90%"' in original else "")
            print(f"  Fixed rate=\"95%\" → rate=\"-5%\"" if 'rate="95%"' in original else "")
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Fixed prosody rates in {updated_count} scenes")
    print("\nThe SSML content has been updated. Audio generation should now produce normal-speed narration.")

if __name__ == "__main__":
    main()