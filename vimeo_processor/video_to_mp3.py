# vimeo_processor/video_to_mp3.py
import os
import logging
from pathlib import Path
# 在匯入 moviepy 前設定環境變數以隱藏 pygame 的歡迎訊息
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
try:
    from moviepy import VideoFileClip
except ImportError:
    logging.error("MoviePy 函式庫未找到。請安裝: pip install moviepy")
    raise

# 使用模組級別的 logger
logger = logging.getLogger(__name__)

def convert_video_to_mp3(video_path: Path, mp3_path: Path) -> bool:
    """
    將影片檔案轉換為 MP3 格式。

    Args:
        video_path (Path): 輸入影片檔案的 Path 物件。
        mp3_path (Path): 輸出 MP3 檔案的 Path 物件。

    Returns:
        bool: 如果轉換成功返回 True，否則返回 False。
    """
    video_clip = None
    audio_clip = None
    try:
        if not video_path.is_file(): # 檢查是否為檔案
            logger.error(f"影片檔案不存在或不是一個檔案: {video_path}")
            return False

        logger.info(f"開始轉換影片: {video_path.name} -> {mp3_path.name}")
        # 確保路徑是字串，因為 moviepy 可能需要
        video_clip = VideoFileClip(str(video_path))
        audio_clip = video_clip.audio

        if audio_clip is None:
            logger.warning(f"影片 {video_path.name} 沒有音軌，跳過轉換。")
            return False # 將無音軌視為轉換失敗

        # 在寫入前確保輸出目錄存在
        mp3_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用 logger=None 關閉 moviepy 在控制台輸出的進度條
        audio_clip.write_audiofile(str(mp3_path), codec='mp3', logger=None)
        logger.info(f"成功轉換 MP3: {mp3_path.name}")
        return True
    except Exception as e:
        logger.error(f"轉換影片 {video_path.name} 時發生錯誤: {e}", exc_info=True)
        # 清理可能部分建立的 mp3 檔案
        if mp3_path.exists():
            try:
                mp3_path.unlink()
                logger.info(f"已刪除轉換失敗產生的不完整 MP3 檔案: {mp3_path.name}")
            except OSError as rm_err:
                logger.warning(f"無法刪除轉換失敗產生的 MP3 檔案 {mp3_path.name}: {rm_err}")
        return False
    finally:
        # 確保資源被釋放
        if audio_clip:
            try:
                audio_clip.close()
            except Exception as e:
                logger.debug(f"關閉 audio_clip 時發生錯誤: {e}")
        if video_clip:
            try:
                video_clip.close()
            except Exception as e:
                logger.debug(f"關閉 video_clip 時發生錯誤: {e}")
