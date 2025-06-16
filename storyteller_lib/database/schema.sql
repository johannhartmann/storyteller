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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Scenes table
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    outline TEXT,
    content TEXT,
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
    knowledge_state TEXT, -- JSON array of what character knows
    revealed_secrets TEXT, -- JSON array of revealed secrets
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

-- 17. Memories table (replaces LangMem functionality)
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