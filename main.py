# main.py
import logging
import sys
from pathlib import Path
from openai import OpenAI
from typing import Optional, List
import os

# --- 匯入設定模組，並進行早期錯誤檢查 ---
try:
    from config import settings
    if not isinstance(getattr(settings, 'VIMEO_TO_PROCESS', None), list):
         raise TypeError("'VIMEO_TO_PROCESS' 在 config/settings.py 中未定義或不是列表。")
    if not isinstance(getattr(settings, 'TRANSCRIPTION_OUTPUTS', None), list):
         raise TypeError("'TRANSCRIPTION_OUTPUTS' 在 config/settings.py 中未定義或不是列表。")

except ImportError:
    # 這裡 logging 可能還沒完全設定好，所以用 print
    print("CRITICAL: 找不到 config/settings.py 或其目錄結構不正確。請確認您已建立該檔案。", file=sys.stderr)
    sys.exit(1)
except TypeError as e:
    print(f"CRITICAL: {e}", file=sys.stderr)
    if "'VIMEO_TO_PROCESS'" in str(e):
        print("VIMEO_TO_PROCESS 列表應包含字典，每個字典需有 'filename' 和 'vimeo_id' 鍵，或列表可為空。", file=sys.stderr)
    elif "'TRANSCRIPTION_OUTPUTS'" in str(e):
         print("TRANSCRIPTION_OUTPUTS 應為列表，例如 ['srt'], ['json'], 或 ['srt', 'json']。", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"CRITICAL: 載入 config/settings.py 時發生錯誤: {e}", file=sys.stderr)
    sys.exit(1)

# --- 設定日誌 (settings 可用後) ---
try:
    log_dir = getattr(settings, 'LOG_DIR', Path("./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / getattr(settings, 'LOG_FILENAME', "pipeline.log")
except Exception as e:
    print(f"CRITICAL: 無法建立或確認日誌目錄 {log_dir}: {e}", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOGGING_LEVEL", "INFO").upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s [%(name)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- 匯入 vimeo_processor (logging 設定後) ---
try:
    from vimeo_processor import vimeo_downloader, video_to_mp3, mp3_to_srt, mp3_to_json, utils
    logger.info("成功匯入 vimeo_processor 套件模組。")
except ImportError as e:
    logger.critical(f"無法從 vimeo_processor 套件匯入模組: {e}。請確認套件結構和 __init__.py 檔案。", exc_info=True)
    sys.exit(1)


# --- 主要處理流程 ---
def run_pipeline():
    logger.info("=" * 30)
    logger.info("=== 開始執行 Vimeo -> MP3 -> 指定格式轉錄處理流程 ===")
    logger.info("=" * 30)

    vimeo_token = getattr(settings, 'VIMEO_ACCESS_TOKEN', None)
    openai_key = getattr(settings, 'OPENAI_API_KEY', None)
    # 使用 getattr 以防萬一 settings 中沒有這個屬性 (雖然前面有檢查)
    output_formats: List[str] = getattr(settings, 'TRANSCRIPTION_OUTPUTS', ["srt", "json"])
    logger.info(f"將會產生的轉錄格式: {output_formats}")

    error_flag = False
    if not vimeo_token:
        logger.error("錯誤：找不到 Vimeo Access Token。請檢查 .env 檔案和 config/settings.py。")
        error_flag = True
    if not openai_key:
        logger.error("錯誤：找不到 OpenAI API Key。請檢查 .env 檔案和 config/settings.py。")
        error_flag = True
    if error_flag:
        return

    try:
        openai_client = OpenAI(api_key=openai_key)
        logger.info("OpenAI 客戶端初始化成功。")
    except Exception as e:
        logger.error(f"初始化 OpenAI 客戶端失敗: {e}", exc_info=True)
        return

    try:
        video_dir = getattr(settings, 'VIDEO_DIR', Path("./data/videos"))
        mp3_dir = getattr(settings, 'MP3_DIR', Path("./data/mp3s"))
        srt_dir = getattr(settings, 'SRT_DIR', Path("./data/srts"))
        json_dir = getattr(settings, 'JSON_DIR', Path("./data/jsons"))

        logger.info(f"確保輸出目錄存在: Video={video_dir}, MP3={mp3_dir}, SRT={srt_dir}, JSON={json_dir}")
        utils.ensure_dir_exists(video_dir)
        utils.ensure_dir_exists(mp3_dir)
        # 只有在需要時才確保目錄存在
        if "srt" in output_formats:
            utils.ensure_dir_exists(srt_dir)
        if "json" in output_formats:
            utils.ensure_dir_exists(json_dir)

    except SystemExit: # ensure_dir_exists 內部可能會 sys.exit
        logger.critical("無法建立必要的輸出目錄，流程終止。")
        return
    except Exception as e:
        logger.critical(f"檢查或建立輸出目錄時發生未預期錯誤: {e}", exc_info=True)
        return

    # 處理計數器
    success_count = 0
    skip_mp3_count = 0
    download_failures = 0
    conversion_failures = 0
    srt_transcription_failures = 0
    json_transcription_failures = 0
    skip_srt_count = 0
    skip_json_count = 0
    skip_srt_config_count = 0
    skip_json_config_count = 0
    invalid_item_count = 0
    processed_items = 0
    vimeo_to_process_list = settings.VIMEO_TO_PROCESS
    total_items = len(vimeo_to_process_list)

    if total_items == 0:
        logger.warning("在 VIMEO_TO_PROCESS.json 或設定中沒有找到任何處理項目。")
        return

    logger.info(f"準備處理 {total_items} 個 Vimeo 影片項目。")

    for index, item in enumerate(vimeo_to_process_list):
        processed_items += 1
        logger.info("-" * 20)

        if not isinstance(item, dict) or "filename" not in item or "vimeo_id" not in item:
            logger.error(f"處理進度: [{index + 1}/{total_items}] - 項目格式錯誤，已跳過: {item}")
            invalid_item_count += 1
            continue
        output_filename_stem = item.get("filename", "").strip()
        vimeo_id = str(item.get("vimeo_id", "")).strip()
        prompt = item.get("prompt", "").strip() # Prompt 主要用於 JSON

        if not output_filename_stem or not vimeo_id:
             logger.error(f"處理進度: [{index + 1}/{total_items}] - 'filename' 或 'vimeo_id' 不可為空，已跳過: {item}")
             invalid_item_count += 1
             continue

        logger.info(f"處理進度: [{index + 1}/{total_items}] - 目標檔名: '{output_filename_stem}', Vimeo ID: {vimeo_id}")
        if prompt:
            logger.info(f"  使用提示 (Prompt): '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")

        target_mp3_path = mp3_dir / f"{output_filename_stem}.mp3"
        target_srt_path = srt_dir / f"{output_filename_stem}.srt"
        target_json_path = json_dir / f"{output_filename_stem}.json"

        # 階段 1: 取得影片檔案
        actual_video_path: Optional[Path] = None
        target_video_pattern = f"{output_filename_stem}.*" # 允許不同副檔名
        try:
            found_videos = [f for f in video_dir.glob(target_video_pattern) if f.is_file()]
            if found_videos:
                actual_video_path = found_videos[0]
                logger.info(f"找到符合目標名稱的本地影片檔案: {actual_video_path.name}")
            else:
                logger.info(f"未找到符合 '{output_filename_stem}' 的本地影片，嘗試從 Vimeo 下載 (ID: {vimeo_id})...")
                downloaded_path_str = vimeo_downloader.download_vimeo_video(
                    video_id=vimeo_id,
                    access_token=vimeo_token,
                    save_directory=str(video_dir),
                    filename=output_filename_stem
                )
                if downloaded_path_str:
                    actual_video_path = Path(downloaded_path_str)
                    if not actual_video_path.is_file():
                         logger.error(f"下載器聲稱成功，但找不到檔案 {actual_video_path} (ID: {vimeo_id})。")
                         actual_video_path = None
                    else:
                         logger.info(f"Vimeo 影片下載成功並儲存為: {actual_video_path.name}")
                else:
                    logger.warning(f"Vimeo 影片下載失敗 (ID: {vimeo_id})。跳過此影片的所有後續步驟。")
                    download_failures += 1
                    continue

            if actual_video_path is None:
                # 這個情況理論上在上面 else 分支中處理了，但為了健壯性再檢查一次
                logger.error(f"無法取得有效的影片檔案 (ID: {vimeo_id}, 目標名稱: {output_filename_stem})。跳過此項目。")
                 # 確保只有在下載失敗時才計數，避免重複計數
                if not downloaded_path_str:
                    download_failures += 1
                continue

        except Exception as e:
            logger.error(f"在取得影片檔案階段 (ID: {vimeo_id}, 目標名稱: {output_filename_stem}) 發生未預期錯誤: {e}", exc_info=True)
            download_failures += 1
            continue

        # 階段 2: 轉換為 MP3
        mp3_ready = False
        try:
            if target_mp3_path.exists() and target_mp3_path.is_file():
                logger.info(f"找到已存在的目標 MP3 檔案: {target_mp3_path.name}")
                mp3_ready = True
                skip_mp3_count += 1
            elif actual_video_path and actual_video_path.is_file():
                logger.info(f"從影片轉換 MP3: {actual_video_path.name} -> {target_mp3_path.name}")
                if video_to_mp3.convert_video_to_mp3(actual_video_path, target_mp3_path):
                    mp3_ready = True
                    if not target_mp3_path.is_file():
                         logger.error(f"轉換聲稱成功，但 MP3 檔案未找到: {target_mp3_path.name}")
                         mp3_ready = False
                         conversion_failures += 1
                    else:
                         logger.info(f"成功轉換 MP3: {target_mp3_path.name}")

                else:
                    logger.warning(f"影片轉換 MP3 失敗: {actual_video_path.name}。")
                    conversion_failures += 1
            else:
                 logger.warning(f"由於缺少有效的來源影片檔案，無法進行 MP3 轉換 (目標 MP3: {target_mp3_path.name})")
                 conversion_failures += 1

        except Exception as e:
             logger.error(f"在轉換 MP3 階段 (目標: {target_mp3_path.name}) 發生未預期錯誤: {e}", exc_info=True)
             conversion_failures += 1

        # 階段 3: 轉錄 (如果 MP3 就緒)
        if mp3_ready:
            if not target_mp3_path.is_file():
                logger.error(f"MP3 檔案 {target_mp3_path.name} 不存在或不是檔案，無法進行任何轉錄。")
                if "srt" in output_formats: srt_transcription_failures += 1
                if "json" in output_formats: json_transcription_failures += 1
                continue

            srt_generated_this_run = False
            json_generated_this_run = False
            srt_skipped_exists = False
            json_skipped_exists = False
            srt_skipped_config = False
            json_skipped_config = False

            # 處理 SRT
            if "srt" in output_formats:
                try:
                    if target_srt_path.exists() and target_srt_path.is_file():
                        logger.info(f"目標 SRT 檔案 {target_srt_path.name} 已存在，跳過 SRT 轉錄。")
                        skip_srt_count += 1
                        srt_skipped_exists = True
                    else:
                        logger.info(f"開始轉錄 MP3 -> SRT: {target_mp3_path.name} -> {target_srt_path.name}")
                        if mp3_to_srt.transcribe_mp3_to_srt(openai_client, target_mp3_path, target_srt_path):
                            logger.info(f"成功產生 SRT 檔案: {target_srt_path.name}")
                            srt_generated_this_run = True
                        else:
                            logger.warning(f"MP3 轉錄 SRT 失敗: {target_mp3_path.name}。")
                            srt_transcription_failures += 1
                except Exception as e:
                     logger.error(f"在轉錄 SRT 階段 (來源: {target_mp3_path.name}) 發生未預期錯誤: {e}", exc_info=True)
                     srt_transcription_failures += 1
            else:
                logger.info(f"根據設定，跳過產生 SRT 檔案 ({target_srt_path.name})。")
                srt_skipped_config = True
                skip_srt_config_count += 1

            # 處理 JSON
            if "json" in output_formats:
                try:
                    if target_json_path.exists() and target_json_path.is_file():
                        logger.info(f"目標 JSON 檔案 {target_json_path.name} 已存在，跳過 JSON 轉錄。")
                        skip_json_count += 1
                        json_skipped_exists = True
                    else:
                        logger.info(f"開始轉錄 MP3 -> JSON: {target_mp3_path.name} -> {target_json_path.name}")
                        # 確保 prompt 被傳遞給 mp3_to_json
                        if mp3_to_json.transcribe_mp3_to_json(openai_client, prompt, target_mp3_path, target_json_path):
                            logger.info(f"成功產生 JSON 檔案: {target_json_path.name}")
                            json_generated_this_run = True
                        else:
                            logger.warning(f"MP3 轉錄 JSON 失敗: {target_mp3_path.name}。")
                            json_transcription_failures += 1
                except Exception as e:
                     logger.error(f"在轉錄 JSON 階段 (來源: {target_mp3_path.name}) 發生未預期錯誤: {e}", exc_info=True)
                     json_transcription_failures += 1
            else:
                logger.info(f"根據設定，跳過產生 JSON 檔案 ({target_json_path.name})。")
                json_skipped_config = True
                skip_json_config_count += 1

            # 更新總體成功計數
            # 只要這次運行成功產生了 *任何一個被要求的* 新檔案，就計為成功
            if srt_generated_this_run or json_generated_this_run:
                success_count += 1
                logger.info(f"成功完成項目 '{output_filename_stem}' (Vimeo ID: {vimeo_id}) 的部分或全部新轉錄處理。")
            elif (srt_skipped_exists or srt_skipped_config) and (json_skipped_exists or json_skipped_config):
                all_skipped = True
                if "srt" in output_formats and not srt_skipped_exists and not srt_skipped_config: all_skipped = False
                if "json" in output_formats and not json_skipped_exists and not json_skipped_config: all_skipped = False

                if all_skipped:
                    requested_and_skipped_msg = []
                    if "srt" in output_formats: requested_and_skipped_msg.append(f"SRT ({'已存在' if srt_skipped_exists else '未請求'})")
                    if "json" in output_formats: requested_and_skipped_msg.append(f"JSON ({'已存在' if json_skipped_exists else '未請求'})")
                    # 如果 output_formats 是空的 (雖然設定檔驗證會阻止)
                    if not requested_and_skipped_msg:
                         logger.info(f"項目 '{output_filename_stem}' 未請求任何輸出格式。")
                    else:
                        logger.info(f"項目 '{output_filename_stem}' (Vimeo ID: {vimeo_id}) 的請求格式均已跳過: {', '.join(requested_and_skipped_msg)}。")

            elif not (srt_generated_this_run or json_generated_this_run or srt_skipped_exists or json_skipped_exists or srt_skipped_config or json_skipped_config):
                 failed_formats = []
                 if "srt" in output_formats and not srt_generated_this_run and not srt_skipped_exists: failed_formats.append("SRT")
                 if "json" in output_formats and not json_generated_this_run and not json_skipped_exists: failed_formats.append("JSON")
                 if failed_formats:
                    logger.warning(f"項目 '{output_filename_stem}' (Vimeo ID: {vimeo_id}) 未能成功產生請求的轉錄檔案 ({', '.join(failed_formats)}) (請查看之前的錯誤)。")

        # else: MP3 未就緒，在其階段已記錄警告/錯誤，不進行轉錄

    # 最終摘要
    logger.info("=" * 30)
    logger.info(f"=== 處理流程結束 (請求格式: {output_formats}) ===")
    logger.info(f"總共檢查的項目數量: {processed_items} / {total_items}")
    logger.info(f"格式錯誤或缺少資訊而跳過的項目數: {invalid_item_count}")
    logger.info(f"成功產生至少一個新請求轉錄檔的項目數量: {success_count}")
    logger.info("-" * 10 + " 跳過計數 " + "-" * 10)
    logger.info(f"因 MP3 已存在而跳過轉換: {skip_mp3_count}")
    if "srt" in output_formats:
        logger.info(f"因 SRT 已存在而跳過 SRT 轉錄: {skip_srt_count}")
    else:
        logger.info(f"因設定未要求而跳過 SRT 轉錄: {skip_srt_config_count}")
    if "json" in output_formats:
        logger.info(f"因 JSON 已存在而跳過 JSON 轉錄: {skip_json_count}")
    else:
        logger.info(f"因設定未要求而跳過 JSON 轉錄: {skip_json_config_count}")
    logger.info("-" * 10 + " 失敗計數 " + "-" * 10)
    logger.info(f"Vimeo 影片獲取/下載失敗數量: {download_failures}")
    logger.info(f"影片 -> MP3 轉換失敗數量: {conversion_failures}")
    # (僅在請求時計算)
    logger.info(f"MP3 -> SRT 轉錄失敗數量: {srt_transcription_failures}")
    logger.info(f"MP3 -> JSON 轉錄失敗數量: {json_transcription_failures}")
    logger.info("=" * 30)


if __name__ == "__main__":
    logger.info("主程式開始執行...")
    run_pipeline()
    logger.info("主程式執行完畢。")
