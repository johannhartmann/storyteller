-- Add book_level_instructions column to story_config table
-- This stores the synthesized writing instructions for the entire book

ALTER TABLE story_config ADD COLUMN book_level_instructions TEXT;