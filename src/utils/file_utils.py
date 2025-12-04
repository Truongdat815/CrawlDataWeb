# -*- coding: utf-8 -*-
"""
File utilities - Common functions for saving crawled data to files
"""

import os
import json
from typing import List, Dict, Any, Optional


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """
    Sanitize string to be safe for Windows/Linux filenames
    
    Args:
        name: Original filename
        max_length: Max length of result
        
    Returns:
        Safe filename string
    """
    if not name:
        return "unknown"
    
    # Replace invalid characters for Windows
    invalid_chars = ['/', '\\', '|', '?', '*', '"', '<', '>', ':']
    safe_name = name
    for char in invalid_chars:
        safe_name = safe_name.replace(char, '_')
    
    # Truncate if too long
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]
    
    return safe_name


def save_story_to_json(story_data: Dict[str, Any], output_dir: str = 'data/json') -> Optional[str]:
    """
    Save single story to JSON file
    
    Args:
        story_data: Story data dict
        output_dir: Output directory
        
    Returns:
        Saved filepath or None if failed
    """
    # Use webStoryId for filename (original Wattpad ID is more readable)
    story_id = story_data.get('webStoryId', story_data.get('storyId', 'unknown'))
    story_name = story_data.get('storyName', 'Unknown')
    
    if story_id == 'unknown':
        return None
    
    # Create safe filename
    safe_name = sanitize_filename(story_name)
    filename = f"{story_id}_{safe_name}.json"
    
    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2, default=str)
        return filepath
    except Exception as e:
        print(f"⚠️ Error saving {story_id}: {e}")
        return None


def save_stories_to_json(stories: List[Dict[str, Any]], output_dir: str = 'data/json') -> int:
    """
    Save multiple stories to JSON files
    
    Args:
        stories: List of story data dicts
        output_dir: Output directory
        
    Returns:
        Number of successfully saved files
    """
    saved_count = 0
    
    for story in stories:
        filepath = save_story_to_json(story, output_dir)
        if filepath:
            saved_count += 1
            # Extract filename from path
            filename = os.path.basename(filepath)
            print(f"   ✅ Saved: {filename}")
    
    return saved_count


def load_story_from_json(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Load story from JSON file
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Story data dict or None if failed
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading {filepath}: {e}")
        return None


def load_stories_from_directory(directory: str = 'data/json') -> List[Dict[str, Any]]:
    """
    Load all story JSON files from directory
    
    Args:
        directory: Directory containing JSON files
        
    Returns:
        List of story data dicts
    """
    stories = []
    
    if not os.path.exists(directory):
        return stories
    
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            story = load_story_from_json(filepath)
            if story:
                stories.append(story)
    
    return stories
