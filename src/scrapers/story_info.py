"""
Story Info scraper module - handles story statistics and metrics for Wattpad.
Responsible for: views, votes, ratings, scores, reader stats, etc.
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config
from src.utils.validation import validate_against_schema
from src.schemas.story_info_schema import STORY_INFO_SCHEMA
from src.scrapers.website import WebsiteScraper


class StoryInfoScraper(BaseScraper):
    """Scraper for story info/stats (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"story_info": "story_info"})
    
    @staticmethod
    def map_api_to_story_info(story_data):
        """
        Map API response to Wattpad story info schema
        
        Args:
            story_data: API response from /api/v3/stories/{id}
        
        Returns:
            story_info dict with statistics
        """
        try:
            web_story_id = str(story_data.get("id"))  # Original Wattpad ID
            story_id = WebsiteScraper.generate_story_id(web_story_id, prefix="wp")
            
            # Generate infoId based on story_id (deterministic, 1 info per story)
            info_id = WebsiteScraper.generate_info_id(story_id, prefix="wp")
            
            # Map stats from API response
            processed_info = {
                "infoId": info_id,                   # wp_uuid_v7 (generated)
                "storyId": story_id,                 # wp_uuid_v7 (matches story collection)
                "websiteId": None,                   # To be set when website collection is implemented
                "totalViews": story_data.get("readCount", 0),
                "averageViews": None,                # Calculate: totalViews / numParts
                "followers": None,                   # Not available in Wattpad API
                "favorites": None,                   # Not available
                "pageViews": None,                   # Not available
                "overallScore": story_data.get("rating"),
                "styleScore": None,                  # Not available in Wattpad
                "storyScore": None,                  # Not available
                "grammarScore": None,                # Not available
                "characterScore": None,              # Not available
                "stabilityOfUpdates": None,          # Not available
                "voted": story_data.get("voteCount", 0),
                "freeChapter": not story_data.get("isPaywalled", False),
                "time": story_data.get("createDate"),
                "releaseRate": None,                 # Not available
                "numberOfReader": None,              # Not available
                "ratingTotal": None,                 # Not available
                "totalViewsChapters": None,          # Sum of chapter views (calculate separately)
                "totalWord": story_data.get("length"),
                "averageWords": None,                # Calculate: length / numParts
                "lastUpdated": story_data.get("modifyDate"),
                "totalReviews": None,                # Not available in Wattpad
                "userReading": None,                 # Not available
                "userPlanToRead": None,              # Not available
                "userCompleted": None,               # Not available
                "userPaused": None,                  # Not available
                "userDropped": None,                 # Not available
            }
            
            # Calculate averages if possible
            num_parts = story_data.get("numParts", 0)
            if num_parts > 0:
                if processed_info["totalViews"]:
                    processed_info["averageViews"] = processed_info["totalViews"] / num_parts
                if processed_info["totalWord"]:
                    processed_info["averageWords"] = processed_info["totalWord"] / num_parts
            
            # Validate before return
            validated = validate_against_schema(processed_info, STORY_INFO_SCHEMA, strict=False)
            return validated
            
        except Exception as e:
            safe_print(f"⚠️ Story info validation failed: {e}")
            return None
    
    def save_story_info(self, story_info_data):
        """
        Save story info to MongoDB
        
        Args:
            story_info_data: Story info dict
        """
        if not story_info_data:
            return
        
        try:
            collection = self.collections.get("story_info")
            if collection is None:
                safe_print("⚠️ story_info collection not found")
                return
            
            info_id = story_info_data.get("infoId")
            if info_id:
                # Upsert based on infoId (unique per story)
                collection.update_one(
                    {"infoId": info_id},
                    {"$set": story_info_data},
                    upsert=True
                )
                safe_print(f"   ✅ Saved story info: {info_id}")
        except Exception as e:
            safe_print(f"⚠️ Error saving story info: {e}")
