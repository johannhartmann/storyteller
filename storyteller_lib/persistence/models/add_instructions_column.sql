-- Add instructions column to scenes table
-- This stores the synthesized scene instructions to avoid regeneration

-- Add instructions column to scenes table
ALTER TABLE scenes ADD COLUMN instructions TEXT;

-- Create index for faster retrieval of instructions
CREATE INDEX IF NOT EXISTS idx_scenes_instructions ON scenes(chapter_id, scene_number) WHERE instructions IS NOT NULL;