-- StoryCraft Agent Database Schema
-- Version: 2.0
-- Description: SQLite schema for tracking story entities (single story)

-- 1. Story configuration (single row)
CREATE TABLE IF NOT EXISTS story_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    title TEXT,
    genre TEXT,
    tone TEXT,
    author TEXT,
    language TEXT DEFAULT 'english',
    initial_idea TEXT,
    global_story TEXT,
    narrative_structure TEXT DEFAULT 'auto',
    story_length TEXT DEFAULT 'auto',
    target_chapters INTEGER,
    target_scenes_per_chapter INTEGER,
    target_words_per_scene INTEGER,
    target_pages INTEGER,
    structure_metadata TEXT, -- JSON
    book_level_instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Characters table
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL UNIQUE, -- e.g., 'hero', 'mentor', 'villain'
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    backstory TEXT,
    personality TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. World elements table
CREATE TABLE IF NOT EXISTS world_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, -- geography, history, culture, politics, etc.
    element_key TEXT NOT NULL, -- specific element identifier
    element_value TEXT NOT NULL, -- JSON for complex data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, element_key)
);

-- 4. Locations table (specific world element type)
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    location_type TEXT, -- city, country, planet, etc.
    parent_location_id INTEGER,
    properties TEXT, -- JSON for additional properties
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_location_id) REFERENCES locations(id) ON DELETE SET NULL
);

-- 5. Plot threads table
CREATE TABLE IF NOT EXISTS plot_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    thread_type TEXT, -- main_plot, subplot, character_arc, mystery, relationship
    importance TEXT, -- major, minor, background
    status TEXT, -- introduced, developed, resolved, abandoned
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Character relationships
CREATE TABLE IF NOT EXISTS character_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character1_id INTEGER NOT NULL,
    character2_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL, -- friend, enemy, lover, family, etc.
    description TEXT,
    properties TEXT, -- JSON for additional properties
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character1_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (character2_id) REFERENCES characters(id) ON DELETE CASCADE,
    CHECK (character1_id < character2_id), -- Ensure no duplicate relationships
    UNIQUE(character1_id, character2_id)
);

-- 7. Character-Location associations
CREATE TABLE IF NOT EXISTS character_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    association_type TEXT, -- birthplace, residence, workplace, etc.
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    UNIQUE(character_id, location_id, association_type)
);

-- 8. Chapters table
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_number INTEGER NOT NULL UNIQUE,
    title TEXT,
    outline TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Scenes table
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    description TEXT,
    content TEXT,
    summary TEXT,
    content_ssml TEXT,
    scene_type TEXT DEFAULT 'exploration',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    UNIQUE(chapter_id, scene_number)
);

-- 10. Character states by scene
CREATE TABLE IF NOT EXISTS character_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    emotional_state TEXT,
    physical_location_id INTEGER,
    evolution_notes TEXT,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    FOREIGN KEY (physical_location_id) REFERENCES locations(id) ON DELETE SET NULL,
    UNIQUE(character_id, scene_id)
);

-- 11. Character knowledge tracking
CREATE TABLE IF NOT EXISTS character_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    knowledge_type TEXT, -- fact, secret, rumor, etc.
    knowledge_content TEXT,
    source TEXT, -- how they learned it
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- 12. Entity changes log
CREATE TABLE IF NOT EXISTS entity_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL, -- character, location, world_element, etc.
    entity_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    change_type TEXT NOT NULL, -- created, modified, revealed, etc.
    change_description TEXT,
    old_value TEXT, -- JSON
    new_value TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- 13. Scene-Entity associations
CREATE TABLE IF NOT EXISTS scene_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL, -- character, location, world_element
    entity_id INTEGER NOT NULL,
    involvement_type TEXT, -- present, mentioned, affected
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    UNIQUE(scene_id, entity_type, entity_id)
);

-- 14. Plot thread developments
CREATE TABLE IF NOT EXISTS plot_thread_developments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_thread_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    development_type TEXT, -- introduced, advanced, resolved, etc.
    description TEXT,
    FOREIGN KEY (plot_thread_id) REFERENCES plot_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- 15. Character plot thread involvement
CREATE TABLE IF NOT EXISTS character_plot_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    plot_thread_id INTEGER NOT NULL,
    involvement_role TEXT, -- protagonist, antagonist, catalyst, witness, etc.
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (plot_thread_id) REFERENCES plot_threads(id) ON DELETE CASCADE,
    UNIQUE(character_id, plot_thread_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_scenes_chapter_id ON scenes(chapter_id);
CREATE INDEX IF NOT EXISTS idx_character_states_scene_id ON character_states(scene_id);
CREATE INDEX IF NOT EXISTS idx_character_knowledge_scene_id ON character_knowledge(scene_id);
CREATE INDEX IF NOT EXISTS idx_entity_changes_scene_id ON entity_changes(scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_entities_scene_id ON scene_entities(scene_id);
CREATE INDEX IF NOT EXISTS idx_plot_thread_developments_scene_id ON plot_thread_developments(scene_id);

-- 16. Used Content Registry (for preventing repetition)
CREATE TABLE IF NOT EXISTS used_content_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL, -- description, event, action, revelation, metaphor, scene_structure
    content_hash TEXT NOT NULL, -- hash of the content for quick lookup
    content_text TEXT NOT NULL, -- the actual content
    chapter_id INTEGER,
    scene_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    UNIQUE(content_type, content_hash)
);

-- Create indexes for the registry
CREATE INDEX IF NOT EXISTS idx_registry_content_type ON used_content_registry(content_type);
CREATE INDEX IF NOT EXISTS idx_registry_scene_id ON used_content_registry(scene_id);

-- 17. Memories table (generic key-value storage)
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    namespace TEXT DEFAULT 'storyteller',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(key, namespace)
);

-- Create indexes for memories table
CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);

-- Trigger to update the updated_at timestamp on story_config
CREATE TRIGGER IF NOT EXISTS update_story_config_timestamp 
AFTER UPDATE ON story_config
BEGIN
    UPDATE story_config SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to update the updated_at timestamp on memories
CREATE TRIGGER IF NOT EXISTS update_memories_timestamp 
AFTER UPDATE ON memories
BEGIN
    UPDATE memories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 18. LLM Evaluations table (for intelligent analysis)
CREATE TABLE IF NOT EXISTS llm_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_type TEXT NOT NULL, -- repetition, scene_quality, character_development, pacing, etc.
    scene_id INTEGER,
    chapter_id INTEGER,
    evaluated_content TEXT, -- what was evaluated
    evaluation_result TEXT, -- JSON result from LLM
    genre TEXT,
    tone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- 19. Character promises table
CREATE TABLE IF NOT EXISTS character_promises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    promise_type TEXT NOT NULL, -- growth, revelation, relationship, skill, conflict
    promise_description TEXT NOT NULL,
    introduced_chapter INTEGER,
    expected_resolution TEXT, -- early, middle, late, ongoing
    fulfilled BOOLEAN DEFAULT FALSE,
    fulfilled_scene_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (fulfilled_scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

-- 20. Story events table (for tracking what happens)
CREATE TABLE IF NOT EXISTS story_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_number INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    event_type TEXT NOT NULL, -- action, dialogue, reflection, revelation, etc.
    event_description TEXT,
    participants TEXT, -- JSON array of character IDs
    location_id INTEGER,
    plot_threads_affected TEXT, -- JSON array of plot thread IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
);

-- 21. Scene quality metrics table
CREATE TABLE IF NOT EXISTS scene_quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    prose_quality_score REAL, -- 0-1 score
    pacing_appropriateness REAL, -- 0-1 score
    character_consistency REAL, -- 0-1 score
    genre_alignment REAL, -- 0-1 score
    reader_engagement_estimate REAL, -- 0-1 score
    evaluation_notes TEXT, -- JSON with detailed feedback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    UNIQUE(scene_id)
);

-- 22. Narrative patterns table
CREATE TABLE IF NOT EXISTS narrative_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL, -- recurring_theme, character_catchphrase, stylistic_element, structural_pattern
    pattern_description TEXT,
    occurrences TEXT, -- JSON array of scene IDs where it appears
    is_intentional BOOLEAN DEFAULT FALSE,
    narrative_purpose TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for new tables
CREATE INDEX IF NOT EXISTS idx_llm_evaluations_type ON llm_evaluations(evaluation_type);
CREATE INDEX IF NOT EXISTS idx_llm_evaluations_scene_id ON llm_evaluations(scene_id);
CREATE INDEX IF NOT EXISTS idx_character_promises_character_id ON character_promises(character_id);
CREATE INDEX IF NOT EXISTS idx_story_events_chapter_scene ON story_events(chapter_number, scene_number);
CREATE INDEX IF NOT EXISTS idx_scene_quality_scene_id ON scene_quality_metrics(scene_id);
CREATE INDEX IF NOT EXISTS idx_narrative_patterns_type ON narrative_patterns(pattern_type);

-- 23. Plot progressions table (for tracking specific plot points)
CREATE TABLE IF NOT EXISTS plot_progressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    progression_key TEXT UNIQUE NOT NULL, -- e.g., "felix_learns_about_mission"
    chapter_number INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for plot progressions
CREATE INDEX IF NOT EXISTS idx_plot_progressions_key ON plot_progressions(progression_key);
CREATE INDEX IF NOT EXISTS idx_plot_progressions_chapter_scene ON plot_progressions(chapter_number, scene_number);

-- Create indexes for narrative structure fields
CREATE INDEX IF NOT EXISTS idx_story_config_structure ON story_config(narrative_structure);
CREATE INDEX IF NOT EXISTS idx_chapters_summary ON chapters(chapter_number) WHERE summary IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scenes_summary ON scenes(chapter_id, scene_number) WHERE summary IS NOT NULL;

-- 24. SSML Repair Log table (for tracking repair attempts)
CREATE TABLE IF NOT EXISTS ssml_repair_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    error_code INTEGER,
    error_message TEXT,
    repair_attempt INTEGER,
    original_ssml TEXT,
    repaired_ssml TEXT,
    repair_successful BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- Create indexes for SSML repair log
CREATE INDEX IF NOT EXISTS idx_repair_log_scene_id ON ssml_repair_log(scene_id);
CREATE INDEX IF NOT EXISTS idx_repair_log_error_code ON ssml_repair_log(error_code);