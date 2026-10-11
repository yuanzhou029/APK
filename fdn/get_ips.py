import os
import json
import time
import argparse
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests

# 设置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("get_ips")


def _positive(value, default):
    """校验为正数，否则返回 default。"""
    try:
        v = float(value)
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def _positive_int(value, default):
    """校验为正整数，否则返回 default。"""
    try:
        v = int(value)
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def build_entries(config):
    """
    从 config dict 构建 entries 列表。
    每项含 url/replace/enabled/timeout/retries/retry_delay（已合并默认值）。
    """
    default_replace = config.get("default_replace")
    default_timeout = _positive(config.get("default_timeout", 15), 15)
    default_retries = _positive_int(config.get("default_retries", 3), 3)
    default_retry_delay = _positive(config.get("default_retry_delay", 2), 2)

    entries = []
    for item in config.get("urls", []):
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        entries.append({
            "url": url,
            "replace": item.get("replace", default_replace),
            "enabled": bool(item.get("enabled", True)),
            "timeout": _positive(item.get("timeout", default_timeout), default_timeout),
            "retries": _positive_int(item.get("retries", default_retries), default_retries),
            "retry_delay": _positive(item.get("retry_delay", default_retry_delay), default_retry_delay),
        })
    return entries


def process_content(content, replace_text):
    """
    逐行处理：若含有 '#'，保留 '#' 前内容并替换/保留名称；
    若没有 '#' 且设置了 replace_text，追加 '#' + replace_text；
    若 replace_text 为 None 则保持原样。过滤空行。
    """
    out = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if replace_text is not None:
            idx = line.find("#")
            host_part = line[:idx] if idx != -1 else line
            out.append(f"{host_part}#{replace_text}")
        else:
            out.append(line)
    return out


def get_host(line):
    """
    提取行中主机部分（IP 或域名），用于去重。
    支持 [ipv6]:port、host:port、host 等格式。
    """
    hash_idx = line.find("#")
    prefix = line[:hash_idx] if hash_idx != -1 else line
    prefix = prefix.strip()
    if prefix.startswith("["):
        end = prefix.find("]")
        if end != -1:
            return prefix[1:end]
    colon = prefix.find(":")
    if colon != -1:
        return prefix[:colon]
    return prefix


def dedup_lines(lines):
    """按主机去重，保留第一次出现的行。"""
    seen = set()
    out = []
    for line in lines:
        host = get_host(line)
        if not host:
            continue
        if host in seen:
            continue
        seen.add(host)
        out.append(line)
    return out


def add_index_to_names(lines, sep="_"):
    """
    对出现多次的名称加序号（name_1、name_2...）；
    仅出现一次的名称保持原样。
    """
    names = []
    for line in lines:
        idx = line.find("#")
        names.append(line[idx + 1:] if idx != -1 else "")
    counter = Counter(names)
    count_so_far = {}
    out = []
    for line, name in zip(lines, names):
        if counter[name] > 1:
            count_so_far[name] = count_so_far.get(name, 0) + 1
            idx = line.find("#")
            out.append(f"{line[:idx + 1]}{name}{sep}{count_so_far[name]}")
        else:
            out.append(line)
    return out


def fetch_url(url, timeout=15, retries=3, retry_delay=2, session=None):
    """
    访问 URL，失败时按 retries/retry_delay 重试。
    返回 (响应文本, 状态码, 最终URL, 尝试次数)；
    失败时返回 (None, 错误信息, url, 尝试次数)。
    """
    url = (url or "").strip()
    if not url:
        return None, "URL 为空", url, 0

    if not urlparse(url).scheme:
        url = "http://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    requester = session or requests
    last_err = "未知错误"
    for attempt in range(1, retries + 1):
        try:
            resp = requester.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            try:
                if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                    resp.encoding = resp.apparent_encoding
            except Exception:
                pass
            return resp.text, resp.status_code, url, attempt
        except requests.exceptions.Timeout:
            last_err = "请求超时"
        except requests.exceptions.RequestException as e:
            last_err = f"请求失败: {e}"
        except Exception as e:
            last_err = f"错误: {e}"
        if attempt < retries:
            time.sleep(retry_delay)

    return None, last_err, url, retries


def _process_single_entry(item):
    """工作线程处理单个 entry 的抓取与文本解析"""
    index, entry, total = item
    url = entry["url"]

    if not entry["enabled"]:
        return {
            "index": index,
            "status": "skipped",
            "url": url,
            "message": "enabled=false",
            "lines": [],
        }

    content, status, final_url, attempts = fetch_url(
        url,
        timeout=entry["timeout"],
        retries=entry["retries"],
        retry_delay=entry["retry_delay"],
    )

    if content is not None:
        replace_text = entry["replace"]
        lines = process_content(content, replace_text)
        tag = f"替换为 '{replace_text}'" if replace_text is not None else "未替换(无 replace 配置)"
        retry_info = f", 尝试 {attempts} 次" if attempts > 1 else ""
        msg = f"HTTP {status}, 取得 {len(lines)} 行{retry_info}, {tag}"
        return {
            "index": index,
            "status": "success",
            "url": final_url,
            "message": msg,
            "lines": lines,
        }
    else:
        err_msg = status if status else "未知错误"
        msg = f"{err_msg}（已重试 {attempts} 次）"
        return {
            "index": index,
            "status": "failed",
            "url": final_url,
            "message": msg,
            "lines": [],
        }


def check_files(config_file, output_file):
    """
    运行前预检：config.json 是否存在/可读/JSON 有效/含 urls；
    data.txt 是否可写（存在则可覆盖，不存在则可创建）。
    返回 config dict，失败返回 None。
    """
    if not os.path.exists(config_file):
        logger.error(f"配置文件 '{config_file}' 不存在，请先创建它。")
        return None
    if not os.access(config_file, os.R_OK):
        logger.error(f"配置文件 '{config_file}' 不可读。")
        return None

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"配置文件 JSON 格式不正确: {e}")
        return None
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return None

    if not isinstance(config, dict) or not config.get("urls"):
        logger.error("配置文件无效：缺少 'urls' 或 'urls' 为空。")
        return None

    if os.path.exists(output_file):
        if os.path.isdir(output_file):
            logger.error(f"输出路径 '{output_file}' 是目录而非文件。")
            return None
        if not os.access(output_file, os.W_OK):
            logger.error(f"输出文件 '{output_file}' 不可写。")
            return None
    else:
        parent = os.path.dirname(output_file) or "."
        if not os.access(parent, os.W_OK):
            logger.error(f"输出目录 '{parent}' 不可写，无法创建 '{output_file}'。")
            return None

    return config


def parse_args():
    parser = argparse.ArgumentParser(description="获取并处理 IP 节点配置文件")
    parser.add_argument("--config", "-c", default="config.json", help="配置文件路径 (默认: config.json)")
    parser.add_argument("--output", "-o", default="data.txt", help="输出文件路径 (默认: data.txt)")
    parser.add_argument("--workers", "-w", type=int, default=5, help="并发抓取线程数 (默认: 5)")
    return parser.parse_args()


def main():
    args = parse_args()
    config_file = args.config
    output_file = args.output
    workers = max(1, args.workers)

    logger.info("运行前检查...")
    config = check_files(config_file, output_file)
    if config is None:
        return

    logger.info(f"正在解析配置文件 '{config_file}' ...")
    entries = build_entries(config)

    if not entries:
        logger.warning("配置文件中没有有效的 URL。")
        return

    active = [e for e in entries if e["enabled"]]
    total = len(entries)
    logger.info(f"共 {total} 条配置，启用 {len(active)} 条，跳过 {total - len(active)} 条。")

    tasks = [(i, entry, total) for i, entry in enumerate(entries, 1)]
    results = []

    # 多线程并发下载
    logger.info(f"开始抓取节点（并发线程数: {workers}）...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_single_entry, task): task[0] for task in tasks}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)

    # 按照原本配置的顺序排序，保证输出顺序可预测
    results.sort(key=lambda x: x["index"])

    all_lines = []
    success_count = 0
    fail_count = 0
    skip_count = 0

    for res in results:
        i = res["index"]
        url = res["url"]
        status = res["status"]
        msg = res["message"]

        if status == "skipped":
            logger.info(f"[跳过] ({i}/{total}) {url} ({msg})")
            skip_count += 1
        elif status == "success":
            logger.info(f"[成功] ({i}/{total}) {url} -> {msg}")
            all_lines.extend(res["lines"])
            success_count += 1
        else:
            logger.error(f"[失败] ({i}/{total}) {url} -> {msg}")
            fail_count += 1

    logger.info(f"共取得 {len(all_lines)} 行数据，开始去重与编号...")

    deduped = dedup_lines(all_lines)
    final_lines = add_index_to_names(deduped)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            for line in final_lines:
                f.write(line + "\n")
    except OSError as e:
        logger.error(f"写入输出文件 '{output_file}' 失败: {e}")
        return

    logger.info("-" * 40)
    logger.info(f"任务完成！成功 {success_count}，失败 {fail_count}，跳过 {skip_count}。")
    logger.info(f"去重后 {len(deduped)} 行，最终写入 {len(final_lines)} 行至 '{output_file}'。")


if __name__ == "__main__":
    main()
