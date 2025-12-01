"""
Score scraper module - handles rating/score data storage.
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class ScoreScraper(BaseScraper):
    """Scraper for story scores (overall, style, story, grammar, character)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"scores": "scores"})
    
    def save_score_to_mongo(self, score_id, style_score, story_score, grammar_score, character_score):
        """
        Lưu score vào MongoDB
        
        Args:
            score_id: Unique ID cho score (ví dụ: story_id_score)
            style_score, story_score, grammar_score, character_score: Các điểm
        """
        if not score_id or not self.collection_exists("scores"):
            return
        
        try:
            collection = self.get_collection("scores")
            score_data = {
                "score_id": score_id,
                "style_score": style_score,
                "story_score": story_score,
                "grammar_score": grammar_score,
                "character_score": character_score
            }
            
            existing = collection.find_one({"score_id": score_id})
            if existing:
                collection.update_one(
                    {"score_id": score_id},
                    {"$set": score_data}
                )
            else:
                collection.insert_one(score_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu score vào MongoDB: {e}")
