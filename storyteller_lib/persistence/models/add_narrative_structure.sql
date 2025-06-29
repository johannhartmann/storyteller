-- Add narrative structure fields to story_config table
-- These fields support flexible story structures beyond just Hero's Journey

-- Add narrative structure column
ALTER TABLE story_config ADD COLUMN narrative_structure TEXT DEFAULT 'auto';

-- Add story length configuration
ALTER TABLE story_config ADD COLUMN story_length TEXT DEFAULT 'auto';
ALTER TABLE story_config ADD COLUMN target_chapters INTEGER;
ALTER TABLE story_config ADD COLUMN target_scenes_per_chapter INTEGER;
ALTER TABLE story_config ADD COLUMN target_words_per_scene INTEGER;

-- Add structure metadata for storing structure-specific details
ALTER TABLE story_config ADD COLUMN structure_metadata TEXT; -- JSON

-- Add book-level instructions column if it doesn't exist
ALTER TABLE story_config ADD COLUMN book_level_instructions TEXT;

-- Create index for narrative structure
CREATE INDEX IF NOT EXISTS idx_story_config_structure ON story_config(narrative_structure);