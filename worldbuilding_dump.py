#!/usr/bin/env bash
"exec" "nix" "develop" "-c" "python" "$0" "$@"
# The above line is valid bash AND a Python string that gets ignored

"""
worldbuilding_dump.py - Extract and display worldbuilding data from the story database

A cleaner, more robust replacement for the shell script version.
"""

import argparse
import sqlite3
import os
import sys
import textwrap
from pathlib import Path
from typing import List, Tuple, Optional


# ANSI color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


def get_db_path() -> Path:
    """Get the database path from environment or default location."""
    db_path = os.environ.get('STORY_DATABASE_PATH')
    if db_path:
        return Path(db_path)
    return Path.home() / '.storyteller' / 'story_database.db'


def get_categories(conn: sqlite3.Connection) -> List[str]:
    """Get all available categories from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM world_elements ORDER BY category")
    return [row[0] for row in cursor.fetchall()]


def get_worldbuilding_data(conn: sqlite3.Connection, category: Optional[str] = None) -> List[Tuple[str, str, str]]:
    """Get worldbuilding data from database."""
    cursor = conn.cursor()
    
    query = """
    SELECT category, element_key, element_value
    FROM world_elements
    {}
    ORDER BY 
        CASE category
            WHEN 'geography' THEN 1
            WHEN 'history' THEN 2
            WHEN 'culture' THEN 3
            WHEN 'politics' THEN 4
            WHEN 'economics' THEN 5
            WHEN 'technology_magic' THEN 6
            WHEN 'religion' THEN 7
            WHEN 'daily_life' THEN 8
            ELSE 9
        END,
        element_key
    """
    
    if category:
        query = query.format("WHERE category = ?")
        cursor.execute(query, (category,))
    else:
        query = query.format("")
        cursor.execute(query)
    
    return cursor.fetchall()


def format_content(content: str, width: int = 80, indent: str = "  ") -> str:
    """Format content with proper word wrapping and indentation."""
    if not content or len(content.strip()) < 2:
        return f"{indent}(no content)"
    
    # Split into paragraphs
    paragraphs = content.split('\n\n')
    formatted_paragraphs = []
    
    for para in paragraphs:
        # Wrap each paragraph
        lines = textwrap.fill(para.strip(), width=width - len(indent))
        # Add indentation to each line
        indented_lines = '\n'.join(indent + line for line in lines.split('\n'))
        formatted_paragraphs.append(indented_lines)
    
    return '\n\n'.join(formatted_paragraphs)


def display_full(data: List[Tuple[str, str, str]]) -> None:
    """Display worldbuilding data in full format."""
    print(f"{Colors.BOLD}{Colors.CYAN}=== WORLDBUILDING CONTENT ==={Colors.NC}")
    print()
    
    prev_category = None
    
    for category, element_key, element_value in data:
        # Print category header if it changed
        if prev_category != category:
            if prev_category is not None:  # Add spacing between categories
                print()
            print(f"{Colors.BOLD}{Colors.GREEN}=== {category.upper()} ==={Colors.NC}")
            print()
            prev_category = category
        
        # Print field name
        print(f"{Colors.YELLOW}{element_key}:{Colors.NC}")
        
        # Print formatted content
        print(format_content(element_value))
        print()


def display_summary(conn: sqlite3.Connection, category: Optional[str] = None) -> None:
    """Display summary of worldbuilding data."""
    print(f"{Colors.BOLD}{Colors.CYAN}=== WORLDBUILDING SUMMARY ==={Colors.NC}")
    print()
    
    cursor = conn.cursor()
    
    if category:
        query = """
        SELECT 
            category,
            element_key as field,
            LENGTH(element_value) as content_length,
            datetime(created_at, 'localtime') as created
        FROM world_elements
        WHERE category = ?
        ORDER BY category, element_key
        """
        cursor.execute(query, (category,))
    else:
        query = """
        SELECT 
            category,
            element_key as field,
            LENGTH(element_value) as content_length,
            datetime(created_at, 'localtime') as created
        FROM world_elements
        ORDER BY 
            CASE category
                WHEN 'geography' THEN 1
                WHEN 'history' THEN 2
                WHEN 'culture' THEN 3
                WHEN 'politics' THEN 4
                WHEN 'economics' THEN 5
                WHEN 'technology_magic' THEN 6
                WHEN 'religion' THEN 7
                WHEN 'daily_life' THEN 8
                ELSE 9
            END,
            element_key
        """
        cursor.execute(query)
    
    # Print header
    print(f"{'Category':<20} {'Field':<20} {'Size':<15} {'Created':<20}")
    print("-" * 75)
    
    # Print data
    for row in cursor.fetchall():
        category, field, size, created = row
        print(f"{category:<20} {field:<20} {size:<15,} {created or 'N/A':<20}")


def export_text(data: List[Tuple[str, str, str]], filepath: Path) -> None:
    """Export worldbuilding data to text file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("WORLDBUILDING DATA EXPORT\n")
        f.write(f"Generated: {os.popen('date').read().strip()}\n")
        f.write(f"Database: {get_db_path()}\n")
        f.write("=" * 80 + "\n\n")
        
        prev_category = None
        
        for category, element_key, element_value in data:
            if prev_category != category:
                if prev_category is not None:
                    f.write("\n")
                f.write(f"=== {category.upper()} ===\n\n")
                prev_category = category
            
            f.write(f"{element_key}:\n")
            f.write(format_content(element_value) + "\n\n")


def export_csv(data: List[Tuple[str, str, str]], filepath: Path) -> None:
    """Export worldbuilding data to CSV file."""
    import csv
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['category', 'element_key', 'element_value'])
        writer.writerows(data)


def show_statistics(conn: sqlite3.Connection, category: Optional[str] = None) -> None:
    """Show statistics about the worldbuilding data."""
    cursor = conn.cursor()
    
    if category:
        query = """
        SELECT 
            COUNT(DISTINCT category) as categories,
            COUNT(*) as fields,
            PRINTF('%.1f KB', SUM(LENGTH(element_value))/1024.0) as total_size
        FROM world_elements
        WHERE category = ?
        """
        cursor.execute(query, (category,))
    else:
        query = """
        SELECT 
            COUNT(DISTINCT category) as categories,
            COUNT(*) as fields,
            PRINTF('%.1f KB', SUM(LENGTH(element_value))/1024.0) as total_size
        FROM world_elements
        """
        cursor.execute(query)
    
    result = cursor.fetchone()
    if result:
        categories, fields, total_size = result
        print(f"{Colors.BOLD}{Colors.PURPLE}=== STATISTICS ==={Colors.NC}")
        print(f"Total categories: {categories}, Total fields: {fields}, Total content size: {total_size}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract and display worldbuilding data from the story database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories: geography, history, culture, politics, economics, technology_magic, religion, daily_life

Examples:
  %(prog)s                        # Show all worldbuilding data
  %(prog)s -s                     # Show summary only
  %(prog)s -c geography           # Show only geography
  %(prog)s -e worldbuilding.txt   # Export to text file
  %(prog)s -e worldbuilding.csv   # Export to CSV
        """
    )
    
    parser.add_argument('-s', '--summary', action='store_true',
                        help='Show summary only (category and field names)')
    parser.add_argument('-f', '--full', action='store_true',
                        help='Show full content (default)')
    parser.add_argument('-c', '--category', type=str,
                        help='Show only specific category')
    parser.add_argument('-e', '--export', type=str,
                        help='Export to file (txt or csv)')
    parser.add_argument('-d', '--database', type=str,
                        help='Use specific database file')
    
    args = parser.parse_args()
    
    # Get database path
    db_path = Path(args.database) if args.database else get_db_path()
    
    # Check if database exists
    if not db_path.exists():
        print(f"{Colors.RED}Error: Database not found at {db_path}{Colors.NC}", file=sys.stderr)
        print("Set STORY_DATABASE_PATH environment variable to specify a different location", file=sys.stderr)
        sys.exit(1)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    try:
        # Validate category if specified
        if args.category:
            available_categories = get_categories(conn)
            if args.category not in available_categories:
                print(f"{Colors.RED}Error: Invalid category '{args.category}'{Colors.NC}", file=sys.stderr)
                print(f"Available categories: {', '.join(available_categories)}", file=sys.stderr)
                sys.exit(1)
        
        # Get data
        data = get_worldbuilding_data(conn, args.category)
        
        if not data:
            print(f"{Colors.YELLOW}No worldbuilding data found{Colors.NC}")
            sys.exit(0)
        
        # Handle export
        if args.export:
            export_path = Path(args.export)
            if export_path.suffix.lower() == '.csv':
                export_csv(data, export_path)
                print(f"{Colors.GREEN}Export complete: {export_path}{Colors.NC}")
            elif export_path.suffix.lower() == '.txt':
                export_text(data, export_path)
                print(f"{Colors.GREEN}Export complete: {export_path}{Colors.NC}")
            else:
                print(f"{Colors.RED}Error: Unsupported export format. Use .txt or .csv{Colors.NC}", file=sys.stderr)
                sys.exit(1)
        else:
            # Display to terminal
            if args.summary:
                display_summary(conn, args.category)
            else:
                display_full(data)
            
            # Always show statistics
            print()
            show_statistics(conn, args.category)
    
    finally:
        conn.close()


if __name__ == '__main__':
    main()