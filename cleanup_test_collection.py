"""
Script để xóa test_collection và đảm bảo reviews collection được tạo
"""
from src.handlers.mongo_handler import MongoHandler
from src.utils import safe_print

def cleanup_and_setup():
    """Xóa test_collection và đảm bảo reviews collection được tạo"""
    try:
        mongo = MongoHandler()
        
        if not mongo.mongo_client:
            safe_print("❌ Không thể kết nối MongoDB")
            return
        
        db = mongo.mongo_client[mongo.mongo_db.name]
        
        # Xóa test_collection nếu có
        try:
            if "test_collection" in db.list_collection_names():
                db.drop_collection("test_collection")
                safe_print("✅ Đã xóa collection 'test_collection'")
            else:
                safe_print("ℹ️ Collection 'test_collection' không tồn tại")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi xóa test_collection: {e}")
        
        # Đảm bảo reviews collection được tạo (bằng cách insert và xóa một document test)
        try:
            if "reviews" not in db.list_collection_names():
                # Tạo collection bằng cách insert một document test rồi xóa
                test_doc = {"_test": True}
                db.reviews.insert_one(test_doc)
                db.reviews.delete_one({"_test": True})
                safe_print("✅ Đã tạo collection 'reviews'")
            else:
                safe_print("ℹ️ Collection 'reviews' đã tồn tại")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi tạo reviews collection: {e}")
        
        # Hiển thị danh sách collections
        collections = db.list_collection_names()
        safe_print(f"\n📊 Danh sách collections hiện tại:")
        for coll in sorted(collections):
            count = db[coll].count_documents({})
            safe_print(f"   - {coll}: {count} documents")
        
        mongo.close()
        safe_print("\n✅ Hoàn thành!")
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())

if __name__ == "__main__":
    cleanup_and_setup()

