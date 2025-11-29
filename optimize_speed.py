"""
Script helper để tối ưu tốc độ crawl/sync
Cung cấp các tùy chọn tối ưu dễ dàng
"""
import sys
import shutil
from pathlib import Path

def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

def backup_config():
    """Backup config hiện tại"""
    config_path = Path("src/config.py")
    backup_path = Path("src/config_backup.py")
    
    if config_path.exists():
        shutil.copy(config_path, backup_path)
        safe_print("✅ Đã backup config hiện tại → src/config_backup.py")
        return True
    return False

def restore_config():
    """Khôi phục config từ backup"""
    backup_path = Path("src/config_backup.py")
    config_path = Path("src/config.py")
    
    if backup_path.exists():
        shutil.copy(backup_path, config_path)
        safe_print("✅ Đã khôi phục config từ backup")
        return True
    else:
        safe_print("❌ Không tìm thấy backup config")
        return False

def apply_performance_config():
    """Áp dụng config performance"""
    perf_config = Path("src/config_performance.py")
    config_path = Path("src/config.py")
    
    if not perf_config.exists():
        safe_print("❌ Không tìm thấy src/config_performance.py")
        safe_print("   Hãy tạo file đó trước")
        return False
    
    # Backup trước
    backup_config()
    
    # Copy config performance
    shutil.copy(perf_config, config_path)
    safe_print("✅ Đã áp dụng config performance")
    safe_print("   ⚠️ Lưu ý: Tốc độ cao hơn nhưng có thể bị ban IP")
    return True

def show_current_config():
    """Hiển thị config hiện tại"""
    config_path = Path("src/config.py")
    
    if not config_path.exists():
        safe_print("❌ Không tìm thấy src/config.py")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Tìm các giá trị quan trọng
    lines = content.split('\n')
    safe_print("\n📊 Cấu hình hiện tại:")
    safe_print("=" * 60)
    
    for line in lines:
        if any(keyword in line for keyword in [
            'DELAY_BETWEEN_CHAPTERS',
            'DELAY_BETWEEN_REQUESTS',
            'MAX_WORKERS',
            'MAX_FICTION_WORKERS',
            'TIMEOUT'
        ]):
            # Loại bỏ comment
            clean_line = line.split('#')[0].strip()
            if clean_line:
                safe_print(f"   {clean_line}")
    
    safe_print("=" * 60)

def manual_optimize():
    """Hướng dẫn tối ưu thủ công"""
    safe_print("\n🔧 Hướng dẫn tối ưu thủ công:")
    safe_print("=" * 60)
    safe_print("1. Mở file: src/config.py")
    safe_print("2. Tìm và chỉnh sửa các giá trị sau:")
    safe_print("")
    safe_print("   DELAY_BETWEEN_REQUESTS = 5  →  DELAY_BETWEEN_REQUESTS = 1")
    safe_print("   DELAY_BETWEEN_CHAPTERS = 2  →  DELAY_BETWEEN_CHAPTERS = 0.5")
    safe_print("   MAX_WORKERS = 3            →  MAX_WORKERS = 8")
    safe_print("")
    safe_print("3. Lưu file và chạy lại")
    safe_print("=" * 60)
    safe_print("⚠️ Lưu ý: Giảm delays có thể tăng rủi ro bị ban IP")
    safe_print("✅ Khuyến nghị: Test với số lượng nhỏ trước")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Tối ưu tốc độ crawl/sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python optimize_speed.py --apply-performance    # Áp dụng config performance
  python optimize_speed.py --show                  # Xem config hiện tại
  python optimize_speed.py --restore               # Khôi phục config gốc
        """
    )
    
    parser.add_argument(
        "--apply-performance",
        action="store_true",
        help="Áp dụng config performance (tốc độ cao)"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Hiển thị config hiện tại"
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Khôi phục config từ backup"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup config hiện tại"
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Hướng dẫn tối ưu thủ công"
    )
    
    args = parser.parse_args()
    
    if args.apply_performance:
        apply_performance_config()
    elif args.show:
        show_current_config()
    elif args.restore:
        restore_config()
    elif args.backup:
        backup_config()
    elif args.manual:
        manual_optimize()
    else:
        # Hiển thị menu
        safe_print("🚀 Tối ưu Tốc độ Crawl/Sync")
        safe_print("=" * 60)
        safe_print("1. --apply-performance  : Áp dụng config performance")
        safe_print("2. --show               : Xem config hiện tại")
        safe_print("3. --backup              : Backup config hiện tại")
        safe_print("4. --restore             : Khôi phục config gốc")
        safe_print("5. --manual              : Hướng dẫn tối ưu thủ công")
        safe_print("=" * 60)
        safe_print("\n💡 Ví dụ: python optimize_speed.py --apply-performance")

if __name__ == "__main__":
    main()

