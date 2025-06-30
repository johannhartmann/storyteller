# Worldbuilding System Documentation

## Overview

The StoryCraft Agent includes a sophisticated worldbuilding system that creates rich, detailed fictional worlds for stories. The system supports both standard worldbuilding and research-enhanced worldbuilding that uses web searches to ground fictional elements in real-world knowledge.

## Worldbuilding Categories

The system generates eight distinct categories of worldbuilding elements:

1. **Geography** - Locations, climate, landmarks, and physical features
2. **History** - Timeline of events, historical figures, past conflicts
3. **Culture** - Languages, traditions, values, and social customs
4. **Politics** - Government systems, power structures, laws, and factions
5. **Economics** - Trade, currency, resources, and wealth distribution
6. **Technology/Magic** - Technological advancement or magical systems
7. **Religion** - Belief systems, religious practices, and spiritual elements
8. **Daily Life** - Food, clothing, housing, work, and everyday activities

## Standard Worldbuilding Process

### 1. Initialization
The worldbuilding process begins after the story outline is generated. The system uses the genre, tone, author style, and story outline to create contextually appropriate world elements.

### 2. Category Generation
Each category is generated using:
- **Structured Output**: Pydantic models ensure consistent data structure
- **Template-Based Prompts**: Language-specific templates guide the LLM
- **Context Awareness**: Previous categories inform subsequent ones

### 3. Data Storage
All worldbuilding elements are stored in the SQLite database at `~/.storyteller/story_database.db`:

#### Database Schema
```sql
CREATE TABLE world_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,      -- geography, history, culture, politics, etc.
    element_key TEXT NOT NULL,   -- specific element identifier
    element_value TEXT NOT NULL, -- JSON for complex data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, element_key)
);
```

#### Storage Process
1. Each worldbuilding category (Geography, History, etc.) is stored separately
2. The `save_worldbuilding()` method in `database.py` iterates through all categories
3. Each field within a category becomes a row in the `world_elements` table:
   - `category`: The worldbuilding category name (e.g., "geography")
   - `element_key`: The field name (e.g., "locations", "climate", "landmarks")
   - `element_value`: The actual content (stored as text or JSON)

#### Example Storage
For a Geography object with fields:
```python
Geography(
    locations="The Northern Kingdoms sprawl across...",
    climate="Harsh winters dominate the northern regions...",
    landmarks="The Crystal Spire rises from...",
    relevance="The mountain passes control trade..."
)
```

This creates 4 rows in the database:
```
| category  | element_key | element_value                        |
|-----------|-------------|--------------------------------------|
| geography | locations   | "The Northern Kingdoms sprawl..."    |
| geography | climate     | "Harsh winters dominate..."          |
| geography | landmarks   | "The Crystal Spire rises..."         |
| geography | relevance   | "The mountain passes control..."     |
```

#### Accessing World Elements
To query world elements from the database:
```sql
-- Get all geography elements
SELECT * FROM world_elements WHERE category = 'geography';

-- Get specific element
SELECT element_value FROM world_elements 
WHERE category = 'history' AND element_key = 'timeline';

-- Get all world elements
SELECT category, element_key, element_value 
FROM world_elements 
ORDER BY category, element_key;
```

## Research-Enhanced Worldbuilding

### Enabling Research Mode
Add the `--research-worldbuilding` flag when running the storyteller:
```bash
python run_storyteller.py --research-worldbuilding
```

### Research Process

#### 1. Initial Context Research
- Generates 3-5 search queries based on genre, tone, and story concept
- Searches for broad contextual information
- Synthesizes initial insights to guide category-specific research

#### 2. Category-Specific Research
For each worldbuilding category:
- **Query Generation**: Creates targeted search queries using category strategies
- **Web Search**: Uses Tavily API to find relevant real-world information
- **Content Extraction**: Retrieves full content from top 3 results (not just snippets)
- **Synthesis**: Extracts detailed, paragraph-length insights from research

#### 3. Research-Informed Generation
- Worldbuilding templates incorporate research findings
- Real-world examples inspire fictional elements
- Historical patterns inform world history
- Cultural practices ground fictional societies

### Research Configuration

Configure research behavior in your story YAML:
```yaml
world_building_research:
  enable_research: true
  research_depth: "medium"  # shallow, medium, or deep
  search_apis: ["tavily"]
  parallel_research: true
  include_sources: true
```

Or use environment variables:
```bash
TAVILY_API_KEY=your-api-key
TAVILY_CACHE_ENABLED=true
TAVILY_CACHE_TTL_DAYS=30
```

## Database Integration

### DatabaseManager Class
The `DatabaseManager` in `storyteller_lib/persistence/database.py` handles all worldbuilding storage:

```python
# Save worldbuilding elements
db_manager = get_db_manager()
db_manager.save_worldbuilding(world_elements)

# Retrieve world elements (via direct SQL query)
with db_manager._db._get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM world_elements WHERE category = ?", ("geography",))
    geography_data = cursor.fetchall()
```

### Storage Flow
1. **Worldbuilding Generation** → Pydantic models (Geography, History, etc.)
2. **Model Serialization** → Convert to dictionary via `model_dump()`
3. **Database Storage** → Each field stored as separate row
4. **Retrieval** → Query by category and reconstruct objects

## Technical Architecture

### Core Components

#### 1. World Builder (`storyteller_lib/universe/world/builder.py`)
- Defines Pydantic models for each category
- Orchestrates the generation process
- Handles database persistence

#### 2. Research Integration (`storyteller_lib/universe/world/research_integration.py`)
- Bridges research and worldbuilding systems
- Manages research-enhanced generation flow
- Falls back to standard generation if research fails

#### 3. World Building Researcher (`storyteller_lib/universe/world/researcher.py`)
- Generates search queries using LLM
- Manages research workflow
- Synthesizes insights from search results

#### 4. Search Utilities (`storyteller_lib/universe/world/search_utils.py`)
- Tavily API integration
- Two-step search process (search + extract)
- Result filtering and deduplication

#### 5. Cache System (`storyteller_lib/universe/world/cache.py`)
- SQLite-based persistent cache
- Separate caches for search and extract operations
- Configurable TTL and automatic cleanup

### Data Flow

```
Story Outline
    ↓
Research Toggle Check
    ↓
[If Research Enabled]
    ↓
Initial Context Research
    ↓
Category Loop:
    - Generate Search Queries
    - Execute Web Searches
    - Extract Full Content
    - Synthesize Insights
    - Generate World Elements
    ↓
[If Research Disabled]
    ↓
Direct Generation
    ↓
Store in Database
```

## Template System

### Prompt Templates
Located in `storyteller_lib/prompts/templates/`:

#### Standard Worldbuilding
- `worldbuilding.jinja2` - Base template
- Language-specific versions in subdirectories

#### Research Templates
- `worldbuilding_research_*.jinja2` - Category-specific generation
- `research_synthesis_*.jinja2` - Extract insights from research
- `research_queries_*.jinja2` - Generate search queries

### Template Features
- Multi-language support (English, German, etc.)
- Structured output instructions
- Research context integration
- Detailed content requirements (3-5 paragraphs per field)

## Caching System

### Tavily Cache
- **Purpose**: Avoid duplicate API calls
- **Storage**: SQLite database at `~/.storyteller/cache/tavily_cache.db`
- **Cache Keys**: Based on query content, not timestamp
- **Benefits**:
  - Faster iteration during development
  - Reduced API costs
  - Deterministic results for testing

### Cache Management
```bash
# View cache statistics
python manage_tavily_cache.py stats

# Clear old entries
python manage_tavily_cache.py clear --days 7

# Clear all cache
python manage_tavily_cache.py clear --all
```

## Best Practices

### 1. Research Depth Selection
- **Shallow**: Quick searches, 2-3 results per query
- **Medium**: Balanced approach, 5 results per query (default)
- **Deep**: Comprehensive research, 10 results per query

### 2. Category Dependencies
- Geography influences everything
- History shapes current politics and culture
- Economics affects daily life and technology
- Religion impacts culture and politics

### 3. Consistency
- World elements reference each other
- Historical events explain current situations
- Cultural values align with religious beliefs
- Technology level matches economic development

## Troubleshooting

### Common Issues

1. **"Research-based worldbuilding not available"**
   - Check TAVILY_API_KEY is set
   - Verify Tavily package is installed
   - Check network connectivity

2. **Empty or Generic World Elements**
   - Ensure research is finding relevant results
   - Check prompt templates are properly formatted
   - Verify structured output models match templates

3. **Slow Research Process**
   - Enable caching (TAVILY_CACHE_ENABLED=true)
   - Use parallel research (default)
   - Consider reducing research depth

### Debug Logging
Enable debug logging to see research queries and results:
```python
# In storyteller_lib/core/logger.py
logging.getLogger("storyteller_lib.universe.world").setLevel(logging.DEBUG)
```

## Future Enhancements

Potential improvements to the worldbuilding system:

1. **Additional Search APIs**: Wikipedia, academic databases
2. **Image Research**: Visual references for locations and artifacts
3. **Interactive Refinement**: User feedback on world elements
4. **World Bibles**: Export comprehensive world documentation
5. **Consistency Validation**: Automated checks for contradictions