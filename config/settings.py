# config/settings.py
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import logging # 為了早期記錄錯誤

# 基本路徑
BASE_DIR = Path(__file__).resolve().parent.parent
# 從 .env 載入環境變數 (例如 API 金鑰), 如果 .env 和環境變數同時存在，優先使用 .env 的值
load_dotenv(override=True)

# 設定一個簡單的早期 Logger, 以便在主 logging 設定前記錄設定檔載入情況
early_logger = logging.getLogger('config_loader')
if not early_logger.handlers: # 防止重複添加 handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    early_logger.addHandler(handler)
    early_logger.setLevel(logging.INFO)

# --- API 金鑰 (從 .env 讀取) ---
VIMEO_ACCESS_TOKEN = os.getenv("VIMEO_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- 輸入設定 (從 VIMEO_TO_PROCESS.json 載入) ---
VIMEO_LIST_JSON_PATH = BASE_DIR / "VIMEO_TO_PROCESS.json"
VIMEO_TO_PROCESS = [] # 預設為空列表

early_logger.info(f"Attempting to load VIMEO_TO_PROCESS from: {VIMEO_LIST_JSON_PATH}")
try:
    with open(VIMEO_LIST_JSON_PATH, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
        if isinstance(loaded_data, list):
            VIMEO_TO_PROCESS = loaded_data
            early_logger.info(f"Successfully loaded {len(VIMEO_TO_PROCESS)} items from {VIMEO_LIST_JSON_PATH}")
        else:
            # 如果 JSON 頂層不是列表，則視為無效
            early_logger.error(f"Content in {VIMEO_LIST_JSON_PATH} is not a valid JSON list. Using empty list.")
            VIMEO_TO_PROCESS = []
except FileNotFoundError:
    early_logger.warning(f"Configuration file {VIMEO_LIST_JSON_PATH} not found. Proceeding with an empty process list.")
    VIMEO_TO_PROCESS = []
except json.JSONDecodeError as e:
    early_logger.error(f"Failed to parse {VIMEO_LIST_JSON_PATH}. Invalid JSON format: {e}. Proceeding with an empty process list.")
    VIMEO_TO_PROCESS = []
except Exception as e:
    # 捕捉其他可能的讀取錯誤
    early_logger.error(f"An unexpected error occurred while loading {VIMEO_LIST_JSON_PATH}: {e}. Proceeding with an empty process list.")
    VIMEO_TO_PROCESS = []

# --- 輸出目錄設定 ---
DATA_DIR = BASE_DIR / "data"
VIDEO_DIR = DATA_DIR / "videos"
MP3_DIR = DATA_DIR / "mp3s"
SRT_DIR = DATA_DIR / "srts"
JSON_DIR = DATA_DIR / "jsons"
LOG_DIR = DATA_DIR / "logs"

# --- 日誌檔案名稱 ---
LOG_FILENAME = "pipeline.log"
LOG_FILE = LOG_DIR / LOG_FILENAME # 完整日誌檔案路徑

# --- 轉錄輸出格式設定 ---
# 直接修改此列表以控制要產生的轉錄檔案類型。
# 可能的設定值：
#   ["srt", "json"]  # 產生 SRT 和 JSON 檔案
#   ["srt"]          # 只產生 SRT 檔案
#   ["json"]         # 只產生 JSON 檔案
#   []               # 不產生任何轉錄檔
#
# *** 請在這裡修改為您需要的值 ***
_configured_output_formats = ["srt", "json"] # <-- **修改此處** 以設定所需輸出格式

# --- 驗證轉錄輸出格式設定 (保留驗證以提高穩健性) ---
ALLOWED_FORMATS = {"srt", "json"}
DEFAULT_FALLBACK_FORMATS = ["srt", "json"] # 如果設定值無效時使用的預設值

if isinstance(_configured_output_formats, list) and all(fmt in ALLOWED_FORMATS for fmt in _configured_output_formats):
    # 使用去重後且排序的值，確保順序一致性並移除重複項
    TRANSCRIPTION_OUTPUTS = sorted(list(set(_configured_output_formats)))
    early_logger.info(f"Using configured TRANSCRIPTION_OUTPUTS: {TRANSCRIPTION_OUTPUTS}")
else:
    early_logger.warning(f"Invalid value configured for output formats: '{_configured_output_formats}'. "
                         f"Expected a list containing only elements from {list(ALLOWED_FORMATS)}. "
                         f"Falling back to default: {DEFAULT_FALLBACK_FORMATS}")
    TRANSCRIPTION_OUTPUTS = DEFAULT_FALLBACK_FORMATS

# --- 其他可選設定 ---
# LOGGING_LEVEL 可以透過環境變數 LOGGING_LEVEL 控制 (見 main.py 的 logging.basicConfig)
# MAX_TRANSCRIPTION_RETRIES = 3 # 例如：可在此添加其他流程參數
