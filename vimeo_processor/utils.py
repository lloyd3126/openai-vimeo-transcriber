# vimeo_processor/utils.py
import logging
import sys
from pathlib import Path

# 使用模組級別的 logger
logger = logging.getLogger(__name__)

def ensure_dir_exists(directory_path: Path):
    """
    確保指定的目錄存在，如果不存在則建立。

    Args:
        directory_path (Path): 要檢查或建立的目錄的 Path 物件。

    Raises:
        SystemExit: 如果路徑存在但不是一個目錄。
    """
    try:
        if not directory_path.exists():
            logger.info(f"建立資料夾: {directory_path}")
            directory_path.mkdir(parents=True, exist_ok=True)
        elif not directory_path.is_dir():
            logger.error(f"路徑 {directory_path} 已存在但不是一個資料夾。")
            sys.exit(1) # 在這種嚴重錯誤情況下可以退出
        # else: 目錄已存在且是目錄，不做任何事
    except OSError as e:
        logger.error(f"建立或存取目錄 {directory_path} 時發生錯誤: {e}", exc_info=True)
        sys.exit(1) # 建立或存取失敗也退出
    except Exception as e:
        logger.error(f"檢查目錄 {directory_path} 時發生未預期錯誤: {e}", exc_info=True)
        sys.exit(1)

# 你可以在這裡加入其他共用的輔助函數
