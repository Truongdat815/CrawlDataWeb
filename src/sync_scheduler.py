"""
Sync Scheduler
Chạy các sync workers định kỳ trong background.
Có thể chạy như một service hoặc cronjob.
"""
import time
import sys
import threading
from datetime import datetime
from src.sync_metadata_worker import MetadataSyncWorker
from src.sync_chapter_worker import ChapterSyncWorker

# Helper function để print an toàn với encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

class SyncScheduler:
    """
    Scheduler để chạy các sync workers định kỳ.
    """
    
    def __init__(self):
        self.running = False
        self.metadata_worker = None
        self.chapter_worker = None
        self.metadata_thread = None
        self.chapter_thread = None
        
        # Cấu hình intervals (giây)
        self.metadata_sync_interval = 600  # 10 phút
        self.chapter_sync_interval = 1800   # 30 phút
        
        # Cấu hình batch sizes
        self.metadata_batch_size = 10
        self.chapter_batch_size = 5
        self.chapters_per_fiction = 10
    
    def start(self):
        """Khởi động scheduler"""
        if self.running:
            safe_print("⚠️ Scheduler đã đang chạy")
            return
        
        self.running = True
        safe_print("🚀 Sync Scheduler đã khởi động!")
        safe_print(f"   Metadata sync: mỗi {self.metadata_sync_interval} giây")
        safe_print(f"   Chapter sync: mỗi {self.chapter_sync_interval} giây")
        
        # Khởi động metadata sync thread
        self.metadata_thread = threading.Thread(target=self._metadata_sync_loop, daemon=True)
        self.metadata_thread.start()
        
        # Khởi động chapter sync thread
        self.chapter_thread = threading.Thread(target=self._chapter_sync_loop, daemon=True)
        self.chapter_thread.start()
        
        safe_print("✅ Các sync workers đã được khởi động trong background")
    
    def stop(self):
        """Dừng scheduler"""
        if not self.running:
            return
        
        self.running = False
        safe_print("🛑 Đang dừng Sync Scheduler...")
        
        # Đợi threads kết thúc
        if self.metadata_thread:
            self.metadata_thread.join(timeout=5)
        if self.chapter_thread:
            self.chapter_thread.join(timeout=5)
        
        # Đóng workers
        if self.metadata_worker:
            self.metadata_worker.stop()
        if self.chapter_worker:
            self.chapter_worker.stop()
        
        safe_print("✅ Sync Scheduler đã dừng")
    
    def _metadata_sync_loop(self):
        """Loop chạy metadata sync định kỳ"""
        while self.running:
            try:
                safe_print(f"\n{'='*60}")
                safe_print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu Metadata Sync...")
                
                # Tạo worker mới cho mỗi lần sync (để tránh browser bị treo)
                self.metadata_worker = MetadataSyncWorker()
                self.metadata_worker.start()
                
                try:
                    self.metadata_worker.sync_batch(
                        num_fictions=self.metadata_batch_size,
                        max_age_hours=24
                    )
                finally:
                    self.metadata_worker.stop()
                    self.metadata_worker = None
                
                safe_print(f"✅ Metadata Sync hoàn thành. Đợi {self.metadata_sync_interval} giây...")
                
            except Exception as e:
                safe_print(f"❌ Lỗi trong metadata sync loop: {e}")
            
            # Đợi interval
            time.sleep(self.metadata_sync_interval)
    
    def _chapter_sync_loop(self):
        """Loop chạy chapter sync định kỳ"""
        while self.running:
            try:
                safe_print(f"\n{'='*60}")
                safe_print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu Chapter Sync...")
                
                # Tạo worker mới cho mỗi lần sync
                self.chapter_worker = ChapterSyncWorker()
                self.chapter_worker.start()
                
                try:
                    self.chapter_worker.sync_batch(
                        num_fictions=self.chapter_batch_size,
                        max_chapters_per_fiction=self.chapters_per_fiction
                    )
                finally:
                    self.chapter_worker.stop()
                    self.chapter_worker = None
                
                safe_print(f"✅ Chapter Sync hoàn thành. Đợi {self.chapter_sync_interval} giây...")
                
            except Exception as e:
                safe_print(f"❌ Lỗi trong chapter sync loop: {e}")
            
            # Đợi interval
            time.sleep(self.chapter_sync_interval)
    
    def run_once(self):
        """
        Chạy sync một lần (không loop).
        Hữu ích cho testing hoặc manual trigger.
        """
        safe_print("🔄 Chạy sync một lần...")
        
        # Metadata sync
        safe_print("\n📊 Metadata Sync:")
        metadata_worker = MetadataSyncWorker()
        metadata_worker.start()
        try:
            metadata_worker.sync_batch(
                num_fictions=self.metadata_batch_size,
                max_age_hours=24
            )
        finally:
            metadata_worker.stop()
        
        # Chapter sync
        safe_print("\n📖 Chapter Sync:")
        chapter_worker = ChapterSyncWorker()
        chapter_worker.start()
        try:
            chapter_worker.sync_batch(
                num_fictions=self.chapter_batch_size,
                max_chapters_per_fiction=self.chapters_per_fiction
            )
        finally:
            chapter_worker.stop()
        
        safe_print("\n✅ Hoàn thành sync một lần!")

def main():
    """Main function - có thể chạy scheduler hoặc sync một lần"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync Scheduler cho RoyalRoad Crawler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Chạy sync một lần rồi thoát (không loop)"
    )
    parser.add_argument(
        "--metadata-interval",
        type=int,
        default=600,
        help="Interval cho metadata sync (giây, mặc định: 600 = 10 phút)"
    )
    parser.add_argument(
        "--chapter-interval",
        type=int,
        default=1800,
        help="Interval cho chapter sync (giây, mặc định: 1800 = 30 phút)"
    )
    
    args = parser.parse_args()
    
    scheduler = SyncScheduler()
    
    if args.metadata_interval:
        scheduler.metadata_sync_interval = args.metadata_interval
    if args.chapter_interval:
        scheduler.chapter_sync_interval = args.chapter_interval
    
    try:
        if args.once:
            # Chạy một lần
            scheduler.run_once()
        else:
            # Chạy scheduler (loop)
            scheduler.start()
            
            # Giữ main thread chạy
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                safe_print("\n⚠️ Nhận tín hiệu dừng (Ctrl+C)...")
                scheduler.stop()
    
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        scheduler.stop()

if __name__ == "__main__":
    main()

