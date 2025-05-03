# vimeo_processor/vimeo_downloader.py
import requests
import json
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# 常數 (可移至 config/settings.py 如果多處使用)
VIMEO_API_BASE_URL = "https://api.vimeo.com/videos/"
DEFAULT_API_TIMEOUT = 30
DEFAULT_DOWNLOAD_TIMEOUT = 600
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024 # 8 MB

# 使用模組級別的 logger
# 建議在您的主應用程式中配置 logger，例如：
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # 獲取名為 'vimeo_processor.vimeo_downloader' 的 logger

def download_vimeo_video(
    video_id: str,
    access_token: str,
    save_directory: str, # 接收字串路徑以保持相容性
    filename: Optional[str] = None, # 設為可選參數
    api_timeout: int = DEFAULT_API_TIMEOUT,
    download_timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Optional[str]:
    """
    根據影片 ID 和 Access Token 從 Vimeo 下載影片。

    Args:
        video_id (str): 要下載的 Vimeo 影片 ID。
        access_token (str): 您的 Vimeo API Access Token。
        save_directory (str): 用於儲存下載影片的目錄路徑 (字串)。
        filename (Optional[str], optional):
            期望儲存的檔案名稱 (包含或不含副檔名)。
            如果提供，將優先使用此名稱的基本部分。
            若未提供副檔名，或提供的副檔名與 API 推斷不同，
            將自動使用(或覆蓋為) API 推斷的副檔名。
            如果為 None 或空字串，將使用預設檔名 `video_id.ext`。
            預設為 None。
        api_timeout (int): API 請求的超時時間 (秒)。
        download_timeout (int): 影片下載流的超時時間 (秒)。
        chunk_size (int): 下載影片時使用的區塊大小 (位元組)。

    Returns:
        Optional[str]: 如果下載成功，返回儲存影片的完整檔案路徑(字串)；如果失敗，返回 None。
    """
    logger.info(f"--- 開始處理 Vimeo 影片 ID: {video_id} ---")
    save_dir_path = Path(save_directory) # 內部轉換為 Path 物件

    # 確保儲存目錄存在
    try:
        save_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"儲存目錄確認/建立成功: {save_dir_path}")
    except OSError as e:
        logger.error(f"無法建立或確認儲存目錄 {save_dir_path}: {e}")
        return None

    headers: Dict[str, str] = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.vimeo.*+json;version=3.4",
    }
    api_url: str = f"{VIMEO_API_BASE_URL}{video_id}"
    logger.info(f"正在從 Vimeo API 取得影片資訊：{api_url}")

    try:
        response = requests.get(api_url, headers=headers, timeout=api_timeout)
        response.raise_for_status() # 檢查 HTTP 錯誤 (4xx 或 5xx)
        video_data: Dict[str, Any] = response.json()
        logger.info(f"成功取得影片資訊 (ID: {video_id})。")

        download_info = video_data.get("download")
        if isinstance(download_info, list) and download_info:
            download_link: Optional[str] = None
            file_extension: str = ".mp4" # 預設副檔名
            best_quality_item = None

            # --- 尋找最佳下載連結和推斷副檔名 ---
            # 嘗試尋找最高品質的 mp4 (HD 或 source 優先)
            for item in download_info:
                link = item.get("link")
                quality = item.get("quality")
                item_type = item.get('type')
                if link and item_type and 'mp4' in item_type.lower():
                    if quality == 'hd' or quality == 'source':
                         best_quality_item = item
                         break # 找到 HD/Source MP4 就用它
                    elif not best_quality_item: # 如果還沒有找到，先記錄第一個 MP4
                         best_quality_item = item

            # 如果沒找到 MP4，退而求其次找第一個可用的連結
            if not best_quality_item:
                 for item in download_info:
                     if item.get("link"):
                         best_quality_item = item
                         break

            if best_quality_item:
                download_link = best_quality_item.get("link")
                item_type = best_quality_item.get('type')
                if isinstance(item_type, str) and '/' in item_type:
                    potential_ext = item_type.split('/')[-1].lower()
                    allowed_extensions = ['mp4', 'mov', 'avi', 'wmv', 'mkv', 'webm']
                    if potential_ext in allowed_extensions:
                        file_extension = f".{potential_ext}"
                logger.info(f"選擇的下載品質: {best_quality_item.get('quality', 'N/A')}, "
                            f"類型: {item_type}, 推斷副檔名: {file_extension}")
            # --- 副檔名推斷結束 ---


            if download_link:
                logger.info(f"找到下載連結 (ID: {video_id})")

                # --- 決定最終檔案名稱 ---
                final_filename_str: str
                if filename: # 如果使用者提供了 filename
                    user_filename = filename.strip()
                    if user_filename:
                        base, ext = os.path.splitext(user_filename)
                        # 清理 base，防止像 "myvideo." 這樣的情況
                        if base.endswith('.'):
                             base = base[:-1]
                        # 如果分離後 base 為空 (例如檔名是 ".mp4") 或 base 仍為空，則退回預設
                        if not base:
                             logger.warning(f"使用者提供的檔名 '{filename}' 格式不尋常 (缺少有效基本名稱)，將使用預設檔名。")
                             final_filename_str = f"{video_id}{file_extension}"
                        elif not ext: # 使用者提供的檔名沒有副檔名
                            final_filename_str = f"{base}{file_extension}" # 使用者的 base + 推斷的 ext
                            logger.info(f"使用者提供的檔名 '{user_filename}' 無副檔名，將附加推斷的副檔名: {file_extension}")
                        elif ext.lower() != file_extension.lower():
                            # 使用者副檔名與推斷不同，使用使用者的 base + 推斷的 ext
                            logger.warning(f"使用者提供的檔名 '{user_filename}' 的副檔名 '{ext}' 與推斷的 '{file_extension}' 不同。將強制使用推斷的副檔名。")
                            final_filename_str = f"{base}{file_extension}"
                        else: # 使用者提供的檔名包含正確的副檔名
                            final_filename_str = user_filename # 使用者提供的完整名稱
                        logger.info(f"將使用最終檔名：{final_filename_str}")
                    else: # 使用者提供的檔名是空字串或只有空白
                         final_filename_str = f"{video_id}{file_extension}"
                         logger.warning(f"使用者提供的檔名 '{filename}' 為空或僅包含空白，將使用預設檔名。")
                         logger.info(f"將使用預設檔名：{final_filename_str}")
                else: # 使用者未提供 filename (為 None)
                    final_filename_str = f"{video_id}{file_extension}"
                    logger.info(f"未指定檔名，將使用預設檔名：{final_filename_str}")

                save_path: Path = save_dir_path / final_filename_str # 使用最終決定的檔名
                # --- 檔名決定結束 ---

                logger.info(f"準備下載檔案到：{save_path}")

                # --- 下載邏輯 ---
                bytes_downloaded: int = 0
                try:
                    logger.info(f"開始下載檔案 (ID: {video_id})...")
                    download_response = requests.get(download_link, stream=True, timeout=download_timeout)
                    download_response.raise_for_status() # 再次檢查下載連結是否有效
                    total_size_in_bytes_str = download_response.headers.get('content-length')
                    total_size_in_bytes: Optional[int] = None
                    if total_size_in_bytes_str and total_size_in_bytes_str.isdigit():
                        total_size_in_bytes = int(total_size_in_bytes_str)
                        logger.info(f"檔案大小: {total_size_in_bytes / (1024*1024):.2f} MB")
                    else:
                        logger.info("無法從 Header 取得或解析檔案大小。")

                    # 進度顯示相關
                    last_logged_progress = -1

                    with open(save_path, "wb") as f:
                        for chunk in download_response.iter_content(chunk_size=chunk_size):
                            if chunk: # 過濾掉 keep-alive new chunks
                                f.write(chunk)
                                bytes_downloaded += len(chunk)

                                # 簡易進度日誌 (例如每 10% 紀錄一次)
                                if total_size_in_bytes:
                                    progress_percent = int(100 * bytes_downloaded / total_size_in_bytes)
                                    # 每 10% 記錄一次日誌，避免過於頻繁
                                    current_progress_interval = (progress_percent // 10) * 10
                                    if current_progress_interval > last_logged_progress:
                                        logger.info(f"下載進度 (ID: {video_id}): {bytes_downloaded / (1024*1024):.2f} MB / {total_size_in_bytes / (1024*1024):.2f} MB ({progress_percent}%)")
                                        last_logged_progress = current_progress_interval

                    # 下載完成後的驗證與日誌
                    if total_size_in_bytes is not None:
                        if total_size_in_bytes != bytes_downloaded:
                             logger.warning(f"下載完成 (ID: {video_id})，但檔案大小不符。預期: {total_size_in_bytes} bytes, 實際下載: {bytes_downloaded} bytes ({bytes_downloaded / (1024*1024):.2f} MB).")
                        else:
                             logger.info(f"下載完成 (ID: {video_id}) 且檔案大小符合預期 ({bytes_downloaded / (1024*1024):.2f} MB)。")
                    else:
                         logger.info(f"下載完成 (ID: {video_id})，總共下載 {bytes_downloaded / (1024*1024):.2f} MB (無法驗證 Header 大小)。")

                    logger.info(f"影片成功下載並儲存於：{save_path}")
                    return str(save_path) # 返回儲存路徑的字串

                except requests.exceptions.RequestException as e:
                    logger.error(f"下載影片檔案 (ID: {video_id}) 時發生網路或請求錯誤：{e}", exc_info=False) # 通常不需要完整 Traceback
                    if save_path.exists() and bytes_downloaded > 0: # 如果有部分下載
                        try:
                            save_path.unlink()
                            logger.info(f"已刪除下載失敗產生的不完整檔案：{save_path.name}")
                        except OSError as rm_err:
                            logger.warning(f"無法刪除不完整的檔案 {save_path.name}: {rm_err}")
                    return None
                except IOError as e:
                     logger.error(f"寫入檔案到 {save_path} 時發生 IO 錯誤：{e}", exc_info=True)
                     if save_path.exists() and bytes_downloaded > 0: # 同上，嘗試清理
                         try:
                            save_path.unlink()
                            logger.info(f"已刪除寫入失敗產生的不完整檔案：{save_path.name}")
                         except OSError as rm_err:
                            logger.warning(f"無法刪除不完整的檔案 {save_path.name}: {rm_err}")
                     return None
                # --- 下載邏輯結束 ---
            else:
                 logger.error(f"在 API 回應中 (ID: {video_id}) 找到 'download' 資訊，但無法篩選出有效的下載連結。請檢查影片權限或 API 回應內容。")
                 return None
        else:
            # 處理 API 回應中沒有 'download' 資訊的情況
            reason = video_data.get("reason")
            error_msg = video_data.get("error")
            developer_message = video_data.get("developer_message") # 有時會有更詳細的錯誤
            if reason:
                 logger.error(f"無法取得影片下載資訊 (ID: {video_id})。原因：{reason}")
            elif error_msg:
                 logger.error(f"無法取得影片下載資訊 (ID: {video_id})。錯誤訊息：{error_msg}")
            elif developer_message:
                 logger.error(f"無法取得影片下載資訊 (ID: {video_id})。開發者訊息：{developer_message}")
            else:
                 logger.error(f"無法取得影片下載資訊 (ID: {video_id})。API 回應缺少 'download' 資訊或格式不符。請檢查 API Token 權限或影片設定。回應: {str(video_data)[:300]}...") # Log 前 300 字元的回應
            return None

    # --- 例外處理 ---
    except requests.exceptions.Timeout:
        logger.error(f"連線到 Vimeo API ({api_url}) 時超時 (設定 >{api_timeout}秒)。請檢查網路連線或增加 api_timeout。")
        return None
    except requests.exceptions.HTTPError as e:
        # HTTP 錯誤 (例如 401 Unauthorized, 403 Forbidden, 404 Not Found, 5xx Server Error)
        status_code = e.response.status_code
        log_message = f"存取 Vimeo API (ID: {video_id}) 時發生 HTTP 錯誤：{status_code} {e.response.reason}."
        try:
            error_details = e.response.json()
            log_message += f" API 錯誤詳情: {error_details}"
        except json.JSONDecodeError:
             log_message += f" 無法解析 API 錯誤回應內容: {e.response.text[:200]}..."
        logger.error(log_message, exc_info=False) # 通常不需要 traceback

        if status_code == 401 or status_code == 403:
             logger.error("請檢查您的 Access Token 是否有效、是否具有下載權限，以及影片是否允許被您的應用程式存取。")
        elif status_code == 404:
             logger.error(f"找不到指定的影片 ID ({video_id})。請確認影片 ID 是否正確。")

        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"存取 Vimeo API (ID: {video_id}) 時發生連線或其他請求錯誤：{e}", exc_info=True) # 包含 Traceback 可能有助於診斷網路問題
        return None
    except json.JSONDecodeError as e:
        logger.error(f"無法解析 Vimeo API (ID: {video_id}) 的 JSON 回應: {e}。原始回應(前200字元): {response.text[:200]}...", exc_info=True)
        return None
    except Exception as e:
        # 捕捉所有其他未預期的錯誤
        logger.error(f"處理 Vimeo 影片 (ID: {video_id}) 時發生未預期的錯誤：{e}", exc_info=True) # 包含 Traceback 以便除錯
        return None

# --- 可選的測試區塊 ---
if __name__ == '__main__':
    # 設定基本的日誌記錄器以進行測試
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)] # 將日誌輸出到控制台
    )

    # --- 請替換為您的實際資訊 ---
    TEST_VIDEO_ID = "YOUR_TEST_VIDEO_ID"  # 替換成一個你可以存取的影片 ID
    TEST_ACCESS_TOKEN = "YOUR_VIMEO_ACCESS_TOKEN" # 替換成你的 Access Token
    TEST_SAVE_DIR = "./vimeo_downloads_test" # 測試用的下載目錄
    # ---

    if TEST_VIDEO_ID == "YOUR_TEST_VIDEO_ID" or TEST_ACCESS_TOKEN == "YOUR_VIMEO_ACCESS_TOKEN":
        logger.warning("請在程式碼中設定有效的 TEST_VIDEO_ID 和 TEST_ACCESS_TOKEN 以進行測試。")
    else:
        logger.info(f"--- 開始測試下載 (Video ID: {TEST_VIDEO_ID}) ---")

        # 測試案例 1: 不指定檔名 (使用預設檔名)
        logger.info("\n--- 測試案例 1: 不指定檔名 ---")
        download_path1 = download_vimeo_video(
            video_id=TEST_VIDEO_ID,
            access_token=TEST_ACCESS_TOKEN,
            save_directory=TEST_SAVE_DIR
        )
        if download_path1:
            logger.info(f"測試 1 成功，檔案儲存於: {download_path1}")
        else:
            logger.error("測試 1 失敗。")

        # 測試案例 2: 指定檔名 (無副檔名)
        logger.info("\n--- 測試案例 2: 指定檔名 'custom_video_name' ---")
        download_path2 = download_vimeo_video(
            video_id=TEST_VIDEO_ID,
            access_token=TEST_ACCESS_TOKEN,
            save_directory=TEST_SAVE_DIR,
            filename="custom_video_name"
        )
        if download_path2:
            logger.info(f"測試 2 成功，檔案儲存於: {download_path2}")
        else:
            logger.error("測試 2 失敗。")

        # 測試案例 3: 指定檔名 (含錯誤副檔名)
        logger.info("\n--- 測試案例 3: 指定檔名 'another_name.avi' (假設推斷為 .mp4) ---")
        download_path3 = download_vimeo_video(
            video_id=TEST_VIDEO_ID,
            access_token=TEST_ACCESS_TOKEN,
            save_directory=TEST_SAVE_DIR,
            filename="another_name.avi"
        )
        if download_path3:
            logger.info(f"測試 3 成功，檔案儲存於: {download_path3} (應已強制使用推斷副檔名)")
        else:
            logger.error("測試 3 失敗。")

        # 測試案例 4: 指定檔名 (含正確副檔名 - 假設推斷為 .mp4)
        logger.info("\n--- 測試案例 4: 指定檔名 'final_video.mp4' ---")
        # 注意：這裡假設推斷副檔名為 .mp4，如果實際不同，結果會是警告+強制副檔名
        download_path4 = download_vimeo_video(
            video_id=TEST_VIDEO_ID,
            access_token=TEST_ACCESS_TOKEN,
            save_directory=TEST_SAVE_DIR,
            filename="final_video.mp4"
        )
        if download_path4:
             logger.info(f"測試 4 成功，檔案儲存於: {download_path4}")
        else:
             logger.error("測試 4 失敗。")

        logger.info("\n--- 所有測試執行完畢 ---")
