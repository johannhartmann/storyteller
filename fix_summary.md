# Pydantic Structured Output Fix Summary

## Problem
The system was using a nested dictionary structure `character_knowledge_changes: Dict[str, List[str]]` in the Pydantic models, which caused errors with LLM structured output:

```
Error generating chapter data with Pydantic: Error code: 400 - {'error': {'message': "Invalid schema for response_format 'ChapterPlan': In context=(), 'required' is required to be supplied and to be an array including every key in properties. Extra required key 'character_knowledge_changes' supplied."
```

## Solution
Simplified the Pydantic model by replacing the nested dictionary with a simple list of formatted strings:

### Before:
```python
character_knowledge_changes: Dict[str, List[str]]  # {"Felix": ["about the mission", "about the danger"]}
```

### After:
```python
character_learns: List[str]  # ["Felix: about the mission", "Felix: about the danger"]
```

## Files Modified

1. **storyteller_lib/outline.py**
   - Updated `SceneSpec` model to use `character_learns: List[str]`
   - Already had the correct structure (line 632)

2. **storyteller_lib/scene_brainstorm.py**
   - Updated to use `character_learns` instead of `character_knowledge_changes` (line 160)
   - Already had the correct structure

3. **storyteller_lib/scene_writer.py**
   - Updated scene specifications initialization (lines 495, 506)
   - Updated character knowledge guidance generation (lines 778-815)
   - Updated character knowledge tracking after scene writing (lines 973-1010)
   - Added parsing logic to convert "CharacterName: knowledge" strings back to character-knowledge pairs

4. **storyteller_lib/scene_validation.py**
   - Updated validation logic to use `character_learns` (lines 50-84)
   - Added parsing logic to handle the new format

5. **storyteller_lib/templates/base/chapter_extraction.jinja2**
   - Template already uses the correct format (line 11)
   - No changes needed

6. **storyteller_lib/templates/base/chapter_planning.jinja2**
   - Template already uses the correct format (line 24)
   - No changes needed

## Key Changes
1. Replaced all references to `character_knowledge_changes` with `character_learns`
2. Added parsing logic where needed to convert "CharacterName: knowledge" strings into character-knowledge mappings
3. Maintained backward compatibility by keeping the same functionality, just with a simpler data structure

## Testing
Created `test_pydantic_fix.py` to verify that the simplified structure works with LLM structured output.

## Result
The system now uses a simpler, flat data structure that is compatible with LLM structured output requirements while maintaining all the original functionality for tracking what characters learn in each scene.