# Vimeo 影片自動下載與轉錄工具

## 簡介

這個 Python 專案旨在自動化從 Vimeo 下載影片、將其轉換為 MP3 音訊檔，並使用 OpenAI 的 Whisper API 將音訊轉錄為文字稿（SRT 或 JSON 格式）。使用者可以透過設定檔輕鬆管理要處理的影片清單和輸出選項。

## 功能特色

*   **Vimeo 影片下載**: 自動從 Vimeo 下載指定的影片。
*   **MP3 轉換**: 將下載的影片檔案轉換為 MP3 音訊格式。
*   **OpenAI 轉錄**: 使用 OpenAI Whisper API 將 MP3 檔案轉錄為 SRT 或 JSON 格式的文字稿。
*   **可配置**: 透過設定檔輕鬆指定要處理的影片、API 金鑰和輸出格式。
*   **日誌記錄**: 詳細記錄處理過程中的每個步驟和結果。

## 專案結構

```
openai-vimeo-transcriber/
├── .gitignore             # Git 忽略設定檔
├── .env                   # <--- API 金鑰設定檔 (需手動建立)
├── VIMEO_TO_PROCESS.json  # <--- 待處理影片清單 (需手動建立/編輯)
├── README.md              # 專案說明文件 (就是您正在閱讀的檔案)
├── requirements.txt       # Python 依賴套件列表
├── main.py                # 主要執行腳本
├── config/                # 設定相關模組
│   ├── __init__.py
│   └── settings.py        # 載入設定、定義輸出目錄等
├── vimeo_processor/       # Vimeo 處理核心邏輯
│   ├── __init__.py
│   ├── vimeo_downloader.py # 下載模組
│   ├── video_to_mp3.py     # 影片轉 MP3 模組
│   ├── mp3_to_srt.py       # MP3 轉 SRT 模組
│   ├── mp3_to_json.py    # MP3 轉 JSON 模組
│   └── utils.py          # 工具函式
└── data/                  # <--- 執行後自動產生的輸出目錄
    ├── videos/            #   (存放下載的影片)
    ├── mp3s/              #   (存放轉換的 MP3)
    ├── srts/              #   (存放產生的 SRT)
    ├── jsons/             #   (存放產生的 JSON)
    └── logs/              #   (存放日誌檔案)
```

## 環境需求

*   **Python**: 建議使用 Python 3.9 或更高版本。
*   **FFmpeg**: `moviepy` 套件需要 FFmpeg 來處理影音檔案。請確保您的系統已安裝 FFmpeg 並將其加入環境變數 PATH。
    *   [FFmpeg 官方網站](https://ffmpeg.org/download.html)
*   **uv**: 推薦使用 `uv` 來管理 Python 虛擬環境和安裝套件。
    *   [uv 安裝指南](https://github.com/astral-sh/uv#installation)

## 安裝與設定

1.  **複製專案**:
    ```bash
    git clone <repository_url> # 將 <repository_url> 替換為實際的 Git 倉庫 URL
    cd openai-vimeo-transcriber # 進入專案目錄
    ```

2.  **使用 uv 建立並啟用虛擬環境**:
    ```bash
    # 安裝 uv (如果尚未安裝)
    # macOS / Linux:
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Windows:
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

    # 建立虛擬環境
    uv venv

    # 啟用虛擬環境 (根據您的 Shell 選擇對應指令)
    # macOS / Linux (bash/zsh):
    source .venv/bin/activate
    # Windows (Command Prompt):
    .venv\Scripts\activate.bat
    # Windows (PowerShell):
    .venv\Scripts\Activate.ps1
    # Fish shell:
    source .venv/bin/activate.fish
    ```

3.  **安裝依賴套件**:
    ```bash
    uv pip install -r requirements.txt
    ```

4.  **設定 API 金鑰**:
    *   建立一個名為 `.env` 的檔案於專案根目錄。
    *   在 `.env` 檔案中加入以下內容，並填入您的金鑰：
        ```dotenv
        VIMEO_ACCESS_TOKEN="YOUR_VIMEO_ACCESS_TOKEN"
        OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
        ```
    *   **注意**: `.env` 檔案包含敏感資訊，請確保已將其加入 `.gitignore`，不要提交到版本控制系統。

5.  **設定處理清單**:
    *   編輯專案根目錄下的 `VIMEO_TO_PROCESS.json` 檔案。
    *   依照以下格式加入您想處理的影片資訊（可以有多個物件）：
        ```json
        [
          {
            "filename": "影片輸出檔名基礎 (無副檔名)",
            "vimeo_id": "Vimeo影片ID",
            "prompt": "給 OpenAI 的轉錄提示 (可選，例如指定語言或專有名詞)"
          }
        ]
        ```
    *   `filename` 將用於命名下載的影片、轉換的 MP3 以及最終的轉錄檔案。
    *   `prompt` 是選填的，可以用來提高特定術語或語言的轉錄準確度，但因為 srt 目前只能使用 whisper 模型生成，但官方有提到 prompt 對該模型的效果不佳，因此目前只支援用 4o 轉錄的 json。

6.  **(可選) 設定輸出格式**:
    *   開啟 `config/settings.py` 檔案。
    *   找到 `_configured_output_formats` 變數。
    *   修改列表內容以指定您想要的輸出格式：
        *   `["srt"]`: 只產生 SRT 字幕檔 (目前預設)。
        *   `["json"]`: 只產生包含詳細時間戳和文字的 JSON 檔案。
        *   `["srt", "json"]`: 同時產生 SRT 和 JSON 檔案。
        *   `[]`: 不產生任何轉錄檔。

## 如何執行

確保您已完成上述所有安裝與設定步驟，並且虛擬環境已啟用。然後在專案根目錄執行：

```bash
python main.py
```

程式將會開始處理 `VIMEO_TO_PROCESS.json` 中定義的每個影片項目。處理進度和結果會顯示在終端機，並記錄到日誌檔案中。

## 設定說明

*   **`.env`**: 存放敏感的 API 金鑰，不應公開。
*   **`VIMEO_TO_PROCESS.json`**: 定義要處理的 Vimeo 影片清單，包含輸出檔名、Vimeo ID 和可選的轉錄提示。
*   **`config/settings.py`**:
    *   `TRANSCRIPTION_OUTPUTS`: 控制最終轉錄輸出的檔案格式。
    *   `VIDEO_DIR`, `MP3_DIR`, `SRT_DIR`, `JSON_DIR`, `LOG_DIR`: 定義各類輸出檔案存放的目錄路徑，預設都在 `data/` 資料夾下。

## 輸出檔案

所有處理過程中產生的檔案都會存放在專案根目錄下的 `data/` 資料夾內，並根據檔案類型分類：

*   `data/videos/`: 下載的原始影片檔案 (例如 `.mp4`, `.mov`)。
*   `data/mp3s/`: 從影片轉換而來的 MP3 音訊檔案。
*   `data/srts/`: 產生的 SRT 字幕檔案 (如果設定需要)。
*   `data/jsons/`: 產生的 JSON 轉錄檔案 (如果設定需要)。
*   `data/logs/`: 處理過程的日誌檔案 (`pipeline.log`)。

## 日誌記錄

詳細的執行日誌會記錄在 `data/logs/pipeline.log` 檔案中。當執行出現問題或需要追蹤處理細節時，可以查看此檔案。
