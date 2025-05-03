# vimeo_processor/mp3_to_srt.py
import logging
import time
from pathlib import Path
from openai import OpenAI, APIError

# 使用模組級別的 logger
logger = logging.getLogger(__name__)

# OpenAI 模型設定 (建議未來移至統一的 config/settings.py 管理)
OPENAI_MODEL = "whisper-1"

def transcribe_mp3_to_srt(
    client: OpenAI,
    mp3_path: Path,
    srt_path: Path,
    max_retries: int = 3,
    initial_delay: int = 5
) -> bool:
    """
    使用 OpenAI API 將 MP3 檔案轉錄為 SRT 格式。

    Args:
        client (OpenAI): 初始化的 OpenAI 客戶端實例。
        mp3_path (Path): 輸入 MP3 檔案的 Path 物件。
        srt_path (Path): 輸出 SRT 檔案的 Path 物件。
        max_retries (int): API 錯誤時的最大重試次數。
        initial_delay (int): 第一次重試前的初始延遲秒數（之後會指數增長）。

    Returns:
        bool: 如果轉錄並成功儲存 SRT 檔案則返回 True，否則返回 False。
    """
    if not mp3_path.is_file():
        logger.error(f"MP3 檔案不存在或不是一個檔案，無法轉錄: {mp3_path}")
        return False

    retries = 0
    delay = initial_delay
    while retries < max_retries:
        try:
            logger.info(f"開始轉錄 MP3: {mp3_path.name} -> {srt_path.name} (模型: {OPENAI_MODEL}, 嘗試 {retries + 1}/{max_retries})")

            srt_path.parent.mkdir(parents=True, exist_ok=True)

            with open(mp3_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=OPENAI_MODEL,
                    file=audio_file,
                    response_format="srt" # 直接請求 SRT 格式輸出
                )

            # 當 response_format 是 'srt' 時，API 的回應直接就是 SRT 格式的字串內容
            srt_content = transcription

            with open(srt_path, "w", encoding="utf-8") as srt_file:
                srt_file.write(srt_content)

            logger.info(f"成功儲存 SRT: {srt_path.name}")
            return True

        except APIError as e:
            logger.warning(f"OpenAI API 錯誤 (嘗試 {retries + 1}/{max_retries}) for {mp3_path.name}: Status={e.status_code} Message={e.message}")
            retries += 1
            if retries < max_retries:
                logger.info(f"將在 {delay} 秒後重試...")
                time.sleep(delay)
                delay *= 2 # 指數退避 (Exponential backoff)
            else:
                logger.error(f"已達最大重試次數 ({max_retries})，放棄轉錄 SRT: {mp3_path.name}")
                return False
        except Exception as e:
            logger.error(f"轉錄 MP3 {mp3_path.name} 為 SRT 時發生非預期錯誤: {e}", exc_info=True)
            # 對於非 API 或預期內的錯誤，通常不重試，直接失敗
            return False

    # 僅在重試次數耗盡後才會執行到此處
    return False
