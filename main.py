import re
import requests
import os
import sys
import uuid
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置 ---
YUQUE_CDN_DOMAIN = 'cdn.nlark.com'  # 记录一下, 虽然没什么用
IMAGE_DIR_SUFFIX = '_images'
IMAGE_FILE_PREFIX = 'image-'

# Separate log files
MAIN_LOG_FILE_NAME = 'yuque_processor_main.log'
DOWNLOAD_LOG_FILE_NAME = 'yuque_processor_downloads.log'

EXTERNAL_IMAGE_PREFIXES_TO_SKIP = [
    './',
    '../',
    'http://localhost',
    'https://example.com/my-internal-images/'
]

# --- 日志配置 ---
download_logger = logging.getLogger('download_logger')
main_logger = logging.getLogger('main_logger')

def setup_logging(target_root_path):
    """
    配置日志系统，将日志同时输出到文件和控制台。
    现在分为两个独立的logger，分别写入不同的文件。
    """
    for handler in main_logger.handlers[:]:
        main_logger.removeHandler(handler)
    for handler in download_logger.handlers[:]:
        download_logger.removeHandler(handler)

    main_logger.setLevel(logging.INFO)
    main_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    main_file_handler = logging.FileHandler(os.path.join(target_root_path, MAIN_LOG_FILE_NAME), encoding='utf-8')
    main_file_handler.setFormatter(main_formatter)
    main_logger.addHandler(main_file_handler)

    main_console_handler = logging.StreamHandler(sys.stdout)
    main_console_handler.setFormatter(main_formatter)
    main_logger.addHandler(main_console_handler)


    download_logger.setLevel(logging.INFO)
    download_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')

    download_file_handler = logging.FileHandler(os.path.join(target_root_path, DOWNLOAD_LOG_FILE_NAME), encoding='utf-8')
    download_file_handler.setFormatter(download_formatter)
    download_logger.addHandler(download_file_handler)


# --- 核心功能 ---
def deal_yuque(md_file_path, image_rename_mode):
    total_images_in_md = 0
    processed_images_count = 0
    newly_downloaded_images_count = 0

    output_content = []

    md_dir = os.path.dirname(md_file_path)
    md_name_without_ext = os.path.splitext(os.path.basename(md_file_path))[0]
    image_dir_for_current_md = os.path.join(md_dir, md_name_without_ext + IMAGE_DIR_SUFFIX)
    image_url_prefix_for_current_md = f'./{md_name_without_ext}{IMAGE_DIR_SUFFIX}/'

    main_logger.info(f"处理文件: {md_file_path}")

    os.makedirs(image_dir_for_current_md, exist_ok=True)

    markdown_url_regex = re.compile(r'(!?\[.*?\]\s*\()([^)]+)(\))')
    image_extensions = ('.png', '.jpeg', '.jpg', '.gif', '.webp', '.bmp', '.svg')

    with open(md_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f.readlines()):
            processed_line = re.sub(r'png#(.*)+', 'png)', line)

            matches = list(markdown_url_regex.finditer(processed_line))

            if not matches:
                output_content.append(processed_line)
                continue

            for match in reversed(matches):
                extracted_url = match.group(2)

                is_http_url = extracted_url.lower().startswith('http://') or extracted_url.lower().startswith(
                    'https://')
                is_image_ext = any(extracted_url.lower().endswith(ext) for ext in image_extensions)

                if is_image_ext:
                    total_images_in_md += 1

                if is_http_url and is_image_ext:
                    image_url = extracted_url

                    if any(image_url.startswith(prefix) for prefix in EXTERNAL_IMAGE_PREFIXES_TO_SKIP):
                        processed_images_count += 1
                        continue

                    suffix = ''
                    for ext in image_extensions:
                        if image_url.lower().endswith(ext):
                            suffix = ext
                            break

                    new_image_name = ""
                    if image_rename_mode == 'uuid':
                        new_image_name = str(uuid.uuid4()) + suffix
                    elif image_rename_mode == 'asc':
                        new_image_name = IMAGE_FILE_PREFIX + str(newly_downloaded_images_count) + suffix # Use newly_downloaded_images_count for asc
                    else:
                        original_name_from_url = image_url.split('/')[-1].split('?')[0]
                        if not original_name_from_url.lower().endswith(suffix.lower()):
                            new_image_name = original_name_from_url + suffix
                        else:
                            new_image_name = original_name_from_url

                    image_local_path = os.path.join(image_dir_for_current_md, new_image_name)

                    if not os.path.exists(image_local_path):
                        download_success = download_image(image_url, image_dir_for_current_md, new_image_name)
                        if download_success:
                            new_image_relative_url = os.path.join(image_url_prefix_for_current_md,
                                                                  new_image_name).replace('\\', '/')
                            processed_line = processed_line[:match.start(2)] + new_image_relative_url + processed_line[
                                                                                                        match.end(2):]
                            newly_downloaded_images_count += 1
                            processed_images_count += 1
                        else:
                            download_logger.warning(
                                f"图片下载失败: {image_url} (文件: {os.path.basename(md_file_path)}, 行: {line_num + 1})"
                            )
                    else:
                        download_logger.info(f"图片已存在，跳过下载: {image_local_path}")
                        new_image_relative_url = os.path.join(image_url_prefix_for_current_md, new_image_name).replace(
                            '\\', '/')
                        processed_line = processed_line[:match.start(2)] + new_image_relative_url + processed_line[
                                                                                                    match.end(2):]
                        processed_images_count += 1


            output_content.append(processed_line)

    with open(md_file_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.writelines(output_content)
    main_logger.info(
        f"文件 '{os.path.basename(md_file_path)}' 处理完成。共发现 {total_images_in_md} 张图片，下载/更新了 {processed_images_count} 张图片，其中新增下载 {newly_downloaded_images_count} 张。"
    )
    return newly_downloaded_images_count, image_dir_for_current_md

def download_image(image_url, image_dir, image_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }

    try:
        r = requests.get(image_url, stream=True, timeout=15, headers=headers)
        if r.status_code == 200:
            image_path = os.path.join(image_dir, image_name)
            with open(image_path, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
            download_logger.info(f"图片下载成功: {image_path}")
            return True
        else:
            download_logger.error(f"图片下载失败: {image_url} (状态码: {r.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        download_logger.error(f"图片下载异常: {image_url} ({type(e).__name__} - {e})")
        return False
    finally:
        if 'r' in locals() and r:
            r.close()

def process_target_directory_multithreaded(target_root_path, image_rename_mode, max_workers):
    main_logger.info(f"启动扫描并使用 {max_workers} 个线程处理目录: {target_root_path}")

    md_files_to_process = []
    all_image_directories = set()

    for dirpath, dirnames, filenames in os.walk(target_root_path):
        for f in filenames:
            if f.endswith('.md'):
                md_files_to_process.append(os.path.join(dirpath, f))

    processed_files_count = 0
    total_images_downloaded = 0

    if not md_files_to_process:
        main_logger.info("未找到Markdown文件。")
        return

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='Worker') as executor:
        futures = {executor.submit(deal_yuque, md_file_path, image_rename_mode): md_file_path
                   for md_file_path in md_files_to_process}

        for future in as_completed(futures):
            md_file_path = futures[future]
            try:
                cnt, image_dir_path = future.result()
                total_images_downloaded += cnt
                processed_files_count += 1
                all_image_directories.add(image_dir_path)
            except Exception as e:
                main_logger.error(f"处理文件 {md_file_path} 异常: {type(e).__name__} - {e}")

    main_logger.info(f"\n--- 处理完成 ---")
    main_logger.info(f"共处理 {processed_files_count} 个文件。")
    main_logger.info(f"共新增 {total_images_downloaded} 张图片。")

    main_logger.info("正在检查并删除空图片目录...")
    removed_empty_dirs_count = 0
    for img_dir in all_image_directories:
        if os.path.exists(img_dir) and not os.listdir(img_dir):
            try:
                os.rmdir(img_dir)
                main_logger.info(f"已删除空图片目录: {img_dir}")
                removed_empty_dirs_count += 1
            except OSError as e:
                main_logger.error(f"删除空目录 {img_dir} 失败: {e}")
    main_logger.info(f"已删除 {removed_empty_dirs_count} 个空图片目录。")


# --- 主程序入口 ---
def main():
    target_root_path = 'C:/xxx'

    image_rename_mode = 'original'

    max_threads = 4

    os.makedirs(target_root_path, exist_ok=True)
    setup_logging(target_root_path)

    main_logger.info("启动语雀 Markdown 处理器。")
    main_logger.info(f"目标目录: {target_root_path}")
    main_logger.info(f"图片命名模式: {image_rename_mode}")
    main_logger.info(f"最大线程数: {max_threads}")
    main_logger.warning("提示：脚本高速运行，可能触发服务器限流。")

    process_target_directory_multithreaded(target_root_path, image_rename_mode, max_threads)

if __name__ == '__main__':
    main()