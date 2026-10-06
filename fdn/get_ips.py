import requests
import os
import json
import time
from collections import Counter
from urllib.parse import urlparse


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
    default_replace = config.get('default_replace')
    default_timeout = _positive(config.get('default_timeout', 15), 15)
    default_retries = _positive_int(config.get('default_retries', 3), 3)
    default_retry_delay = _positive(config.get('default_retry_delay', 2), 2)

    entries = []
    for item in config.get('urls', []):
        url = str(item.get('url', '')).strip()
        if not url:
            continue
        entries.append({
            'url': url,
            'replace': item.get('replace', default_replace),
            'enabled': bool(item.get('enabled', True)),
            'timeout': _positive(item.get('timeout', default_timeout), default_timeout),
            'retries': _positive_int(item.get('retries', default_retries), default_retries),
            'retry_delay': _positive(item.get('retry_delay', default_retry_delay), default_retry_delay),
        })
    return entries


def process_content(content, replace_text):
    """
    逐行处理：保留 # 前内容，将 # 后内容替换为 replace_text；
    没有 # 的行删除。返回处理后的行列表。
    """
    out = []
    for line in content.split('\n'):
        idx = line.find('#')
        if idx == -1:
            continue
        out.append(line[:idx] + '#' + replace_text)
    return out


def get_host(line):
    """
    提取行中主机部分（IP 或域名），用于去重。
    支持 [ipv6]:port、host:port、host 等格式。
    """
    hash_idx = line.find('#')
    prefix = line[:hash_idx] if hash_idx != -1 else line
    prefix = prefix.strip()
    if prefix.startswith('['):
        end = prefix.find(']')
        if end != -1:
            return prefix[1:end]
    colon = prefix.find(':')
    if colon != -1:
        return prefix[:colon]
    return prefix


def dedup_lines(lines):
    """按主机去重，保留第一次出现的行。"""
    seen = set()
    out = []
    for line in lines:
        host = get_host(line)
        if host in seen:
            continue
        seen.add(host)
        out.append(line)
    return out


def add_index_to_names(lines, sep='_'):
    """
    对出现多次的名称加序号（name_1、name_2...）；
    仅出现一次的名称保持原样。
    """
    names = []
    for line in lines:
        idx = line.find('#')
        names.append(line[idx + 1:] if idx != -1 else '')
    counter = Counter(names)
    count_so_far = {}
    out = []
    for line, name in zip(lines, names):
        if counter[name] > 1:
            count_so_far[name] = count_so_far.get(name, 0) + 1
            idx = line.find('#')
            out.append(line[:idx + 1] + name + sep + str(count_so_far[name]))
        else:
            out.append(line)
    return out


def fetch_url(url, timeout=15, retries=3, retry_delay=2):
    """
    访问 URL，失败时按 retries/retry_delay 重试。
    返回 (响应文本, 状态码, 最终URL, 尝试次数)；
    失败时返回 (None, 错误信息, url, 尝试次数)。
    """
    url = (url or '').strip()
    if not url:
        return None, "URL 为空", url, 0

    if not urlparse(url).scheme:
        url = 'http://' + url

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    last_err = "未知错误"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            try:
                if not resp.encoding or resp.encoding.lower() == 'iso-8859-1':
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


def check_files(config_file, output_file):
    """
    运行前预检：config.json 是否存在/可读/JSON 有效/含 urls；
    data.txt 是否可写（存在则可覆盖，不存在则可创建）。
    返回 config dict，失败返回 None。
    """
    if not os.path.exists(config_file):
        print(f"错误: 配置文件 '{config_file}' 不存在，请先创建它。")
        return None
    if not os.access(config_file, os.R_OK):
        print(f"错误: 配置文件 '{config_file}' 不可读。")
        return None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件 JSON 格式不正确: {e}")
        return None
    except Exception as e:
        print(f"错误: 读取配置文件失败: {e}")
        return None

    if not isinstance(config, dict) or not config.get('urls'):
        print(f"错误: 配置文件无效：缺少 'urls' 或 'urls' 为空。")
        return None

    if os.path.exists(output_file):
        if os.path.isdir(output_file):
            print(f"错误: 输出路径 '{output_file}' 是目录而非文件。")
            return None
        if not os.access(output_file, os.W_OK):
            print(f"错误: 输出文件 '{output_file}' 不可写。")
            return None
    else:
        parent = os.path.dirname(output_file) or '.'
        if not os.access(parent, os.W_OK):
            print(f"错误: 输出目录 '{parent}' 不可写，无法创建 '{output_file}'。")
            return None

    return config


def main():
    config_file = 'config.json'
    output_file = 'data.txt'

    print("运行前检查...")
    config = check_files(config_file, output_file)
    if config is None:
        return

    print(f"正在解析 {config_file} ...")
    entries = build_entries(config)

    if not entries:
        print("配置文件中没有有效的 URL。")
        return

    try:
        open(output_file, 'w', encoding='utf-8').close()
    except OSError as e:
        print(f"错误: 无法初始化输出文件 '{output_file}': {e}")
        return

    active = [e for e in entries if e['enabled']]
    print(f"共 {len(entries)} 条配置，启用 {len(active)} 条，跳过 {len(entries) - len(active)} 条。")

    all_lines = []
    success_count = 0
    fail_count = 0
    skip_count = 0
    total = len(entries)

    for i, entry in enumerate(entries, 1):
        url = entry['url']

        if not entry['enabled']:
            print(f"[跳过] ({i}/{total}) {url} (enabled=false)")
            skip_count += 1
            continue

        replace_text = entry['replace']
        content, status, final_url, attempts = fetch_url(
            url, timeout=entry['timeout'], retries=entry['retries'], retry_delay=entry['retry_delay']
        )

        if content is not None:
            if replace_text is not None:
                lines = process_content(content, replace_text)
                tag = f"替换为 '{replace_text}'"
            else:
                lines = [ln for ln in content.split('\n') if ln.strip()]
                tag = "未替换(无 replace 配置)"
            retry_info = f", 尝试 {attempts} 次" if attempts > 1 else ""
            print(f"[成功] ({i}/{total}) {final_url} -> HTTP {status}, 取得 {len(lines)} 行{retry_info}, {tag}")
            all_lines.extend(lines)
            success_count += 1
        else:
            err_msg = status if status else "未知错误"
            print(f"[失败] ({i}/{total}) {final_url} -> {err_msg}（已重试 {attempts} 次）")
            fail_count += 1

    print(f"共取得 {len(all_lines)} 行，开始去重与编号...")

    deduped = dedup_lines(all_lines)
    final_lines = add_index_to_names(deduped)

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in final_lines:
                f.write(line + '\n')
    except OSError as e:
        print(f"错误: 写入输出文件 '{output_file}' 失败: {e}")
        return

    print("-" * 30)
    print(f"任务完成！成功 {success_count}，失败 {fail_count}，跳过 {skip_count}。")
    print(f"去重后 {len(deduped)} 行，最终写入 {len(final_lines)} 行至 {output_file}。")


if __name__ == "__main__":
    main()