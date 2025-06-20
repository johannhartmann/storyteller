-- Add summary columns to chapters and scenes tables
-- These store LLM-generated summaries for "what happened until now" context

-- Add summary column to chapters table
ALTER TABLE chapters ADD COLUMN summary TEXT;

-- Add summary column to scenes table  
ALTER TABLE scenes ADD COLUMN summary TEXT;

-- Create indexes for faster retrieval of summaries
CREATE INDEX IF NOT EXISTS idx_chapters_summary ON chapters(chapter_number) WHERE summary IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scenes_summary ON scenes(chapter_id, scene_number) WHERE summary IS NOT NULL;