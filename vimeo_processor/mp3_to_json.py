# mp3_to_json.py
import logging
import time
import json
from pathlib import Path
from openai import OpenAI, APIError

# 使用模組級別的 logger
logger = logging.getLogger(__name__)

OPENAI_MODEL = "gpt-4o-transcribe"
RESPONSE_FORMAT = "json"

def transcribe_mp3_to_json(
    client: OpenAI,
    prompt: str,
    mp3_path: Path,
    json_path: Path,
    max_retries: int = 3,
    initial_delay: int = 5
) -> bool:
    """
    使用 OpenAI API 將 MP3 檔案轉錄為 JSON 格式。

    Args:
        client (OpenAI): 初始化的 OpenAI 客戶端實例。
        prompt (str): 提供給模型的提示，用以改善特定詞彙或風格的辨識。
        mp3_path (Path): 輸入 MP3 檔案的 Path 物件。
        json_path (Path): 輸出 JSON 檔案的 Path 物件。
        max_retries (int): API 錯誤時的最大重試次數。
        initial_delay (int): 第一次重試前的初始延遲秒數（之後會指數增長）。

    Returns:
        bool: 如果轉錄並成功儲存 JSON 檔案則返回 True，否則返回 False。
    """
    if not mp3_path.is_file():
        logger.error(f"MP3 檔案不存在或不是一個檔案，無法轉錄: {mp3_path}")
        return False

    retries = 0
    delay = initial_delay
    while retries < max_retries:
        try:
            logger.info(f"開始轉錄 MP3: {mp3_path.name} -> {json_path.name} (模型: {OPENAI_MODEL}, 格式: {RESPONSE_FORMAT}, 嘗試 {retries + 1}/{max_retries})")

            json_path.parent.mkdir(parents=True, exist_ok=True)

            with open(mp3_path, "rb") as audio_file:
                transcription_result = client.audio.transcriptions.create(
                    model=OPENAI_MODEL,
                    file=audio_file,
                    prompt=prompt,
                    response_format=RESPONSE_FORMAT
                )

            # transcription_result 通常是 OpenAI v1+ 的 Pydantic 模型物件
            # 需要轉換為字典才能序列化為 JSON
            try:
                # 使用 .model_dump() (Pydantic v2+) 或 .dict() (舊版)
                if hasattr(transcription_result, "model_dump"):
                    response_data = transcription_result.model_dump()
                elif hasattr(transcription_result, "dict"): # 兼容舊版 Pydantic
                    response_data = transcription_result.dict()
                else: # 如果不是預期的 Pydantic 模型
                     raise AttributeError("Response object has no 'model_dump' or 'dict' method.")

            except AttributeError:
                 # 若回應非 Pydantic 模型，嘗試直接處理
                 if isinstance(transcription_result, dict):
                     response_data = transcription_result
                 else:
                     # 檢查是否為可直接序列化的基本類型
                     if isinstance(transcription_result, (list, str, int, float, bool, type(None))):
                         logger.warning(f"回應非預期 Pydantic 模型，但為可序列化類型 {type(transcription_result)}，嘗試直接儲存。")
                         response_data = transcription_result
                     else: # 如果是無法序列化的物件，則記錄錯誤並引發 TypeError
                          logger.error(f"無法序列化的回應類型: {type(transcription_result)}")
                          raise TypeError(f"Unexpected response type for JSON serialization: {type(transcription_result)}")

            with open(json_path, "w", encoding="utf-8") as json_file:
                json.dump(response_data, json_file, ensure_ascii=False, indent=4)

            logger.info(f"成功儲存 JSON: {json_path.name}")
            return True

        except APIError as e:
            logger.warning(f"OpenAI API 錯誤 (嘗試 {retries + 1}/{max_retries}) for {mp3_path.name}: Status={e.status_code} Message={e.message}")
            retries += 1
            if retries < max_retries:
                logger.info(f"將在 {delay} 秒後重試...")
                time.sleep(delay)
                delay *= 2 # 指數退避 (Exponential backoff)
            else:
                logger.error(f"已達最大重試次數 ({max_retries})，放棄轉錄 JSON: {mp3_path.name}")
                return False
        except (TypeError, Exception) as e: # 包含 JSON 序列化或類型轉換的 TypeError
            logger.error(f"轉錄 MP3 {mp3_path.name} 為 JSON 時發生非預期錯誤: {e}", exc_info=True)
            # 對於非 API 或預期內的錯誤，通常不重試，直接失敗
            return False

    return False # 理論上只有在重試耗盡後才可能到達這裡
