#!/usr/bin/env python3
"""
Migration script to switch to the simplified v2 workflow.
This updates the necessary imports and configurations.
"""

import os
import shutil
from datetime import datetime


def backup_file(filepath):
    """Create a backup of a file before modifying it."""
    backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"Backed up {filepath} to {backup_path}")
    return backup_path


def update_storyteller_imports():
    """Update storyteller.py to use v2 modules."""
    filepath = "storyteller_lib/storyteller.py"
    
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return
    
    # Read the current content
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if already using v2
    if "from storyteller_lib.graph_v2" in content:
        print("storyteller.py already using v2 modules")
        return
    
    # Backup the file
    backup_file(filepath)
    
    # Replace imports
    replacements = [
        ("from storyteller_lib.graph import create_graph", 
         "from storyteller_lib.graph_v2 import create_simplified_graph as create_graph"),
        ("from storyteller_lib.scenes import", 
         "from storyteller_lib.scenes_v2 import"),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    # Write updated content
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Updated {filepath} to use v2 modules")


def update_run_storyteller():
    """Update run_storyteller.py to optionally use v2."""
    filepath = "run_storyteller.py"
    
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return
    
    # Read the current content
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if we need to add v2 option
    if "--use-v2" in content:
        print("run_storyteller.py already has v2 option")
        return
    
    # Backup the file
    backup_file(filepath)
    
    # Add import for v2
    import_line = "from storyteller_lib.storyteller import generate_story"
    v2_import = "from storyteller_lib.storyteller_v2 import generate_story_simplified"
    
    if import_line in content and v2_import not in content:
        content = content.replace(
            import_line,
            f"{import_line}\n{v2_import}"
        )
    
    # Add command line argument
    if 'parser.add_argument("--author"' in content:
        author_line_end = content.find('\n', content.find('parser.add_argument("--author"'))
        if author_line_end != -1:
            content = content[:author_line_end + 1] + \
                     '    parser.add_argument("--use-v2", action="store_true",\n' + \
                     '                        help="Use simplified v2 workflow (faster, cleaner)")\n' + \
                     content[author_line_end + 1:]
    
    # Update the story generation call
    generate_call = "story, state = generate_story("
    if generate_call in content:
        # Find the function call and wrap it
        call_start = content.find(generate_call)
        call_end = content.find(")", call_start)
        
        # Extract the parameters
        params = content[call_start + len(generate_call):call_end]
        
        # Create conditional call
        new_call = f"""if args.use_v2:
            story, state = generate_story_simplified(
{params}
            )
        else:
            story, state = generate_story(
{params}
            )"""
        
        # Replace the call
        content = content[:call_start] + new_call + content[call_end + 1:]
    
    # Write updated content
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Updated {filepath} with --use-v2 option")


def create_test_script():
    """Create a test script for the v2 workflow."""
    test_content = '''#!/usr/bin/env python3
"""
Test script for the simplified v2 workflow.
"""

import sys
import time
from storyteller_lib.storyteller_v2 import generate_story_simplified

def test_v2_workflow():
    """Test the simplified workflow with a small story."""
    print("Testing simplified v2 workflow...")
    
    start_time = time.time()
    
    try:
        # Generate a short test story
        story, state = generate_story_simplified(
            genre="fantasy",
            tone="adventurous",
            num_chapters=3,  # Small for testing
            language="english"
        )
        
        elapsed = time.time() - start_time
        
        print(f"\\nTest completed in {elapsed:.2f} seconds")
        print(f"Generated {len(story.split())} words")
        print(f"Chapters: {len(state.get('chapters', {}))}")
        
        # Save test output
        with open("test_story_v2.md", "w") as f:
            f.write(story)
        print("\\nTest story saved to test_story_v2.md")
        
        return True
        
    except Exception as e:
        print(f"\\nTest failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_v2_workflow()
    sys.exit(0 if success else 1)
'''
    
    with open("test_v2_workflow.py", "w") as f:
        f.write(test_content)
    
    os.chmod("test_v2_workflow.py", 0o755)
    print("Created test_v2_workflow.py")


def main():
    """Run the migration."""
    print("=== StoryCraft V2 Migration ===\n")
    
    print("This will update your codebase to use the simplified v2 workflow.")
    print("The original workflow will still be available.\n")
    
    # Update files
    update_storyteller_imports()
    update_run_storyteller()
    create_test_script()
    
    print("\n=== Migration Complete ===")
    print("\nYou can now:")
    print("1. Run stories with the v2 workflow: python run_storyteller.py --use-v2 ...")
    print("2. Test the v2 workflow: python test_v2_workflow.py")
    print("3. Original workflow is still available without --use-v2")
    print("\nBackups of modified files have been created.")


if __name__ == "__main__":
    main()