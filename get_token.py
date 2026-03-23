#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube V2Ray/Clash配置文件自动化助手 v3.3（GitHub Actions版）
功能：完全自动化获取最新视频、下载地址和密码
密码获取方式：下载音频 → whisper识别 → 提取密码
"""

import requests
import re
import sys
import json
import time
import os
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, unquote
from typing import Optional, Dict, List, Tuple

# ================= 配置区域 =================
# YouTube API配置（从环境变量获取）
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
CHANNEL_ID = os.getenv('CHANNEL_ID', '')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '')

# 下载配置
DOWNLOAD_DIR = "v2ray_configs"
AUDIO_DIR = "audio_download"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2

# 视频搜索配置
SEARCH_DAYS = 3
MAX_VIDEOS = 20

# 音频识别配置
USE_AUDIO_RECOGNITION = os.getenv('USE_AUDIO_RECOGNITION', 'true').lower() == 'true'
SPEECH_RECOGNITION_ENGINE = os.getenv('SPEECH_RECOGNITION_ENGINE', 'whisper')
# ===========================================


def setup_encoding():
    """设置UTF-8编码（解决Windows下emoji显示问题）"""
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def create_directories():
    """创建必要的目录"""
    download_path = Path(__file__).parent / DOWNLOAD_DIR
    audio_path = Path(__file__).parent / AUDIO_DIR
    download_path.mkdir(exist_ok=True)
    audio_path.mkdir(exist_ok=True)
    return download_path, audio_path


def fetch_youtube_api(url: str, description: str) -> Optional[Dict]:
    """获取YouTube API数据（带重试机制）"""
    print(f"📡 {description}...")

    for retry in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                print(f"❌ API错误: {data['error'].get('message', '未知错误')}")
                return None

            return data

        except requests.exceptions.RequestException as e:
            error_msg = f"{description}失败 (尝试 {retry}/{MAX_RETRIES}): {e}"
            if retry < MAX_RETRIES:
                print(f"⚠️ {error_msg}, {RETRY_DELAY}秒后重试...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ {error_msg}")
                return None

    return None


def get_channel_id_from_username(username: str) -> Optional[str]:
    """通过用户名获取频道ID"""
    url = f"https://www.googleapis.com/youtube/v3/channels?key={YOUTUBE_API_KEY}&part=id&forHandle={username}"
    data = fetch_youtube_api(url, f"获取频道ID ({username})")

    if data and 'items' in data and len(data['items']) > 0:
        channel_id = data['items'][0]['id']
        print(f"✅ 成功获取频道ID: {channel_id}")
        return channel_id

    return None


def extract_date_from_title(title: str) -> Optional[Tuple[datetime, str]]:
    """从视频标题中提取日期"""
    date_patterns = [
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d'),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y-%m-%d'),
        (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', '%Y-%m-%d'),
        (r'(\d{1,2})月(\d{1,2})日', None),
    ]

    for pattern, date_format in date_patterns:
        match = re.search(pattern, title)
        if match:
            if date_format:
                try:
                    year, month, day = match.groups()
                    date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    date_obj = datetime.strptime(date_str, date_format)
                    return date_obj, date_str
                except ValueError:
                    continue
            else:
                try:
                    month, day = match.groups()
                    current_year = datetime.now().year
                    date_str = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    return date_obj, date_str
                except ValueError:
                    continue

    return None


def get_latest_video_with_date(channel_id: str) -> Optional[Dict]:
    """获取频道中带有日期的最新视频"""
    url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=id,snippet&order=date&maxResults={MAX_VIDEOS}"
    data = fetch_youtube_api(url, "获取频道视频列表")

    if not data or 'items' not in data:
        return None

    print(f"\n🔍 正在分析 {len(data['items'])} 个视频...")

    videos_with_date = []
    for item in data['items']:
        if item['id']['kind'] != 'youtube#video':
            continue

        video_id = item['id']['videoId']
        snippet = item['snippet']
        title = snippet['title']
        published_at = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))

        date_info = extract_date_from_title(title)
        if date_info:
            date_obj, date_str = date_info
            videos_with_date.append({
                'video_id': video_id,
                'title': title,
                'date': date_obj,
                'date_str': date_str,
                'published_at': published_at,
                'url': f"https://www.youtube.com/watch?v={video_id}"
            })
            print(f"  ✅ 找到带日期的视频: {title}")
            print(f"     提取日期: {date_str}")

    if not videos_with_date:
        print("❌ 未找到带有日期的视频")
        return None

    videos_with_date.sort(key=lambda x: x['date'], reverse=True)
    latest_video = videos_with_date[0]

    print(f"\n🎯 自动选择最新视频:")
    print(f"   标题: {latest_video['title']}")
    print(f"   日期: {latest_video['date_str']}")
    print(f"   链接: {latest_video['url']}")

    return latest_video


def get_video_details(video_id: str) -> Optional[Dict]:
    """获取视频详细信息（包括完整描述）"""
    url = f"https://www.googleapis.com/youtube/v3/videos?key={YOUTUBE_API_KEY}&part=snippet&id={video_id}"
    data = fetch_youtube_api(url, f"获取视频详情 ({video_id})")

    if data and 'items' in data and len(data['items']) > 0:
        return data['items'][0]

    return None


def extract_paste_to_url(description: str) -> Optional[str]:
    """从视频描述中提取paste.to下载地址"""
    pattern = r'https://paste\.to/[^\s\n<>"]+'
    matches = re.findall(pattern, description)

    if matches:
        url = matches[0]
        print(f"✅ 成功提取到paste.to下载地址: {url}")
        return url

    print("❌ 未找到paste.to下载地址")
    return None


def download_audio_crawl4ai(video_url: str, audio_dir: Path) -> Optional[Path]:
    """使用crawl4ai爬虫架构下载音频"""
    print("\n🔍 开始下载音频...")
    print("💡 使用crawl4ai爬虫架构（模拟真实浏览器）...")

    try:
        import crawl4ai
        import asyncio
        import re
        import json
        from urllib.parse import urlparse, parse_qs

        # 提取视频ID
        video_id = re.search(r'v=([^&]+)', video_url)
        if not video_id:
            video_id = re.search(r'youtu\.be/([^?]+)', video_url)
        if not video_id:
            print("❌ 无法提取视频ID")
            return None

        video_id = video_id.group(1)
        print(f"   视频ID: {video_id}")

        # 使用crawl4ai获取视频页面
        async def download_with_crawl4ai():
            async with crawl4ai.AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=video_url,
                    wait_for="networkidle",
                    page_timeout=30000,
                    js_code="""
                        // 等待视频加载
                        await new Promise(resolve => setTimeout(resolve, 3000));

                        // 尝试多种方法获取视频数据
                        let videoData = null;

                        // 方法1: 从window对象获取
                        if (typeof ytInitialPlayerResponse !== 'undefined') {
                            videoData = ytInitialPlayerResponse;
                        }

                        // 方法2: 从页面脚本中提取
                        if (!videoData) {
                            const scripts = document.querySelectorAll('script');
                            for (let script of scripts) {
                                const text = script.textContent;
                                if (text && text.includes('ytInitialPlayerResponse')) {
                                    const match = text.match(/var ytInitialPlayerResponse = ({.+?});/);
                                    if (match) {
                                        try {
                                            videoData = JSON.parse(match[1]);
                                            break;
                                        } catch (e) {}
                                    }
                                }
                            }
                        }

                        // 方法3: 从player配置获取
                        if (!videoData && typeof ytplayer !== 'undefined' && ytplayer.config) {
                            videoData = ytplayer.config.args;
                        }

                        return videoData;
                    """,
                    bypass_cache=True,
                    magic=True,
                    simulate_user=True,
                    override_navigator=True,
                )
                return result

        # 运行异步爬虫
        import asyncio
        result = asyncio.run(download_with_crawl4ai())

        if not result.success:
            print(f"❌ 爬虫执行失败: {result.error_message}")
            return None

        print(f"✅ 成功获取视频页面")

        # 解析JavaScript返回的数据
        try:
            video_data = json.loads(result.extracted_content.get('extracted_json', '{}'))
            if not video_data or not isinstance(video_data, dict):
                print("⚠️ 无法解析视频数据，尝试备用方法...")
                return None

            # 获取streamingData
            streaming_data = video_data.get('streamingData', {})
            if not streaming_data:
                print("⚠️ 未找到streamingData")
                return None

        except Exception as e:
            print(f"⚠️ 解析视频数据失败: {e}")
            return None

        # 获取音频流URL
        audio_streams = []
        if 'adaptiveFormats' in streaming_data:
            for format in streaming_data['adaptiveFormats']:
                if format.get('mimeType', '').startswith('audio/'):
                    audio_streams.append(format)

        if not audio_streams:
            print("❌ 未找到音频流")
            return None

        # 选择最佳音频流
        best_audio = max(audio_streams, key=lambda x: x.get('bitrate', 0))
        audio_url = best_audio.get('url')

        if not audio_url:
            print("❌ 音频流URL为空")
            return None

        print(f"✅ 找到音频流，比特率: {best_audio.get('bitrate', 0)}")

        # 下载音频文件
        print(f"📥 开始下载音频...")

        # 获取视频标题作为文件名
        video_title = video_data.get('videoDetails', {}).get('title', 'audio')
        # 清理文件名
        video_title = re.sub(r'[<>:"/\\|?*]', '', video_title)
        video_title = video_title[:100]  # 限制长度

        audio_file = audio_dir / f"{video_title}.m4a"

        # 下载音频
        response = requests.get(audio_url, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with audio_file.open('wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r   下载进度: {progress:.1f}%", end='', flush=True)

        print(f"\n✅ 音频下载成功: {audio_file.name}")
        print(f"   文件大小: {audio_file.stat().st_size / 1024 / 1024:.2f} MB")
        return audio_file

    except ImportError:
        print("❌ 未安装crawl4ai库")
        return None
    except Exception as e:
        print(f"❌ 音频下载失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def download_audio_yt_dlp(video_url: str, audio_dir: Path) -> Optional[Path]:
    """使用yt-dlp下载音频（高级反检测模式）"""
    print("\n🔍 开始下载音频...")
    print("💡 使用高级反检测模式...")

    try:
        import yt_dlp

        # 使用多个User-Agent轮换
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]

        # 尝试使用不同的客户端
        for i, user_agent in enumerate(user_agents):
            try:
                print(f"  尝试方法 {i+1}/{len(user_agents)}...")

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': str(audio_dir / '%(title)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'ignoreerrors': True,
                    'extract_flat': False,
                    'noplaylist': True,
                    'user_agent': user_agent,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],  # 使用多个客户端
                        }
                    },
                    'http_headers': {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    },
                    'retries': 3,
                    'fragment_retries': 3,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    audio_filename = ydl.prepare_filename(info)

                # 查找下载的文件
                audio_files = list(audio_dir.glob('*.mp4')) + list(audio_dir.glob('*.mp3')) + list(audio_dir.glob('*.webm')) + list(audio_dir.glob('*.m4a'))
                if audio_files:
                    audio_file = audio_files[-1]
                    print(f"✅ 音频下载成功: {audio_file.name}")
                    print(f"   文件大小: {audio_file.stat().st_size / 1024 / 1024:.2f} MB")
                    return audio_file

            except Exception as e:
                error_msg = str(e)
                print(f"  方法 {i+1} 失败: {error_msg[:100]}")

                # 如果是机器人检测错误，尝试下一个方法
                if 'bot' in error_msg.lower() or 'sign in' in error_msg.lower():
                    if i < len(user_agents) - 1:
                        print(f"  检测到反爬虫，切换User-Agent...")
                        import time
                        time.sleep(2)
                        continue

        print("❌ 所有下载方法都失败了")
        return None

    except ImportError:
        print("❌ 未安装yt-dlp库")
        return None
    except Exception as e:
        print(f"❌ 音频下载失败: {e}")
        return None


def convert_audio_to_wav(input_file: Path, output_file: Path) -> bool:
    """使用ffmpeg将音频转换为WAV格式（可选，whisper不需要）"""
    print(f"\n🔍 音频格式转换（whisper不需要，跳过）...")
    print(f"💡 whisper可以直接识别mp4/mp3格式，无需转换")
    return False  # 直接返回False，跳过转换


def recognize_audio_whisper(audio_file: Path) -> Optional[str]:
    """使用whisper识别音频（直接识别mp4/mp3，需要FFmpeg解码）"""
    print(f"\n🔍 使用whisper识别音频...")

    try:
        import whisper

        print(f"   音频文件: {audio_file.name}")
        print(f"   文件大小: {audio_file.stat().st_size / 1024 / 1024:.2f} MB")

        # 检查FFmpeg是否可用（whisper需要FFmpeg解码音频）
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                print("❌ whisper需要FFmpeg来解码音频")
                return None
            else:
                print("✅ FFmpeg检测成功")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("❌ whisper需要FFmpeg来解码音频")
            return None

        print(f"\n   加载whisper模型...")
        model_size = 'base'  # 可选: tiny, base, small, medium, large
        print(f"   模型大小: {model_size}")
        print(f"💡 首次运行会自动下载模型，可能需要一些时间")

        model = whisper.load_model(model_size)
        print(f"✅ 模型加载成功")

        print(f"\n   正在识别音频（可能需要几分钟）...")
        print(f"💡 whisper使用FFmpeg解码mp4格式")
        result = model.transcribe(str(audio_file), language='zh')

        text = result['text']
        print(f"✅ 音频识别成功")
        print(f"   识别文字长度: {len(text)} 字符")

        # 显示识别结果的前200个字符
        if len(text) > 200:
            print(f"   识别文字预览: {text[:200]}...")
        else:
            print(f"   识别文字: {text}")

        return text

    except ImportError:
        print("❌ 未安装whisper库")
        return None
    except Exception as e:
        print(f"❌ 音频识别失败: {e}")
        return None


def recognize_audio_speech_recognition(audio_file: Path) -> Optional[str]:
    """使用SpeechRecognition识别音频"""
    print(f"\n🔍 使用SpeechRecognition识别音频...")

    try:
        import speech_recognition as sr

        r = sr.Recognizer()

        print(f"   读取音频文件...")
        with sr.AudioFile(str(audio_file)) as source:
            audio_data = r.record(source)

        print(f"   正在识别音频（需要网络）...")
        try:
            text = r.recognize_google(audio_data, language='zh-CN')
            print(f"✅ 音频识别成功")
            print(f"   识别文字长度: {len(text)} 字符")
            return text
        except sr.UnknownValueError:
            print("❌ 无法识别音频内容")
            return None
        except sr.RequestError as e:
            print(f"❌ 识别服务错误: {e}")
            return None

    except ImportError:
        print("❌ 未安装SpeechRecognition库")
        return None
    except Exception as e:
        print(f"❌ 音频识别失败: {e}")
        return None


def extract_password_from_text(text: str) -> Optional[str]:
    """从文字中提取密码"""
    if not text:
        return None

    print(f"\n🔍 从文字中提取密码...")

    # 常见的密码格式
    password_patterns = [
        r'密码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'提取码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'访问码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'下载密码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'解压密码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'pass\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'password\s*[:：is]\s*([a-zA-Z0-9]+)',
    ]

    for pattern in password_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            password = match.group(1)
            print(f"✅ 找到密码: {password}")
            return password

    print("⚠️ 未找到密码")
    return None


def extract_password_from_description(description: str) -> Optional[str]:
    """从视频描述中提取密码"""
    print(f"\n🔍 从描述中提取密码...")

    password_patterns = [
        r'密码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'提取码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'访问码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'下载密码\s*[:：是]\s*([a-zA-Z0-9]+)',
        r'解压密码\s*[:：是]\s*([a-zA-Z0-9]+)',
    ]

    for pattern in password_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            password = match.group(1)
            print(f"✅ 从描述中找到密码: {password}")
            return password

    print("⚠️ 描述中未找到密码")
    return None


def check_config() -> bool:
    """检查配置是否完整"""
    errors = []

    if not YOUTUBE_API_KEY:
        errors.append("YouTube API密钥未配置（环境变量 YOUTUBE_API_KEY）")

    if not CHANNEL_ID and not CHANNEL_USERNAME:
        errors.append("频道ID或用户名未配置（环境变量 CHANNEL_ID 或 CHANNEL_USERNAME）")

    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"   - {error}")
        return False

    return True


def test_api_connection() -> bool:
    """测试YouTube API连接"""
    print("\n🔍 测试YouTube API连接...")

    if CHANNEL_ID:
        url = f"https://www.googleapis.com/youtube/v3/channels?key={YOUTUBE_API_KEY}&part=snippet&id={CHANNEL_ID}"
    else:
        url = f"https://www.googleapis.com/youtube/v3/channels?key={YOUTUBE_API_KEY}&part=snippet&forHandle={CHANNEL_USERNAME}"

    data = fetch_youtube_api(url, "测试API连接")

    if data and 'items' in data and len(data['items']) > 0:
        channel_title = data['items'][0]['snippet']['title']
        print(f"✅ API连接成功！")
        print(f"   频道名称: {channel_title}")
        return True
    else:
        print("❌ API连接失败")
        return False


def main():
    """主函数 - 完全自动化流程（GitHub Actions版本）"""
    setup_encoding()
    print("=" * 80)
    print("🚀 YouTube V2Ray/Clash配置文件自动化助手 v3.3（GitHub Actions版）")
    print("=" * 80)
    print("⚡ 完全自动化模式：音频下载 + whisper识别 + 密码提取")
    print("💡 使用环境变量传递配置信息")
    print("=" * 80)

    # 检查配置
    if not check_config():
        raise RuntimeError("❌ 配置错误：请检查环境变量")

    # 测试API连接
    if not test_api_connection():
        raise RuntimeError("❌ API连接失败")

    # 创建目录
    download_dir, audio_dir = create_directories()
    print(f"✅ 下载目录: {download_dir}")
    print(f"✅ 音频目录: {audio_dir}")

    # 获取频道ID
    channel_id = CHANNEL_ID
    if CHANNEL_USERNAME and not channel_id:
        print(f"\n🔍 通过用户名获取频道ID: {CHANNEL_USERNAME}")
        channel_id = get_channel_id_from_username(CHANNEL_USERNAME)
        if not channel_id:
            raise RuntimeError("❌ 无法获取频道ID")

    # 步骤1：自动获取最新带日期的视频
    print("\n" + "=" * 80)
    print("📺 步骤1：自动识别最新视频")
    print("=" * 80)

    latest_video = get_latest_video_with_date(channel_id)
    if not latest_video:
        raise RuntimeError("❌ 无法获取最新视频")

    # 获取视频详细信息
    print(f"\n🔍 获取视频详细信息...")
    video_details = get_video_details(latest_video['video_id'])

    if video_details:
        full_description = video_details['snippet'].get('description', '')
    else:
        full_description = ''

    # 步骤2：自动提取paste.to下载地址
    print("\n" + "=" * 80)
    print("📥 步骤2：自动提取下载地址")
    print("=" * 80)

    download_url = extract_paste_to_url(full_description)
    if not download_url:
        raise RuntimeError("❌ 无法提取下载地址")

    # 步骤3：自动获取密码
    print("\n" + "=" * 80)
    print("🔑 步骤3：自动获取密码")
    print("=" * 80)

    password = None

    # 方法1：从描述中获取
    password = extract_password_from_description(full_description)

    # 方法2：使用音频识别
    if not password and USE_AUDIO_RECOGNITION:
        print("\n描述中未找到密码，使用音频识别...")

        # 3.1 下载音频 - 优先使用crawl4ai
        audio_file = download_audio_crawl4ai(latest_video['url'], audio_dir)

        # 如果crawl4ai失败，尝试yt-dlp
        if not audio_file:
            print("\n⚠️ crawl4ai下载失败，尝试yt-dlp...")
            audio_file = download_audio_yt_dlp(latest_video['url'], audio_dir)

        if not audio_file:
            print("⚠️ 音频下载失败（可能是YouTube反爬虫限制）")
            print("💡 尝试其他方法获取密码...")
        else:
            # 3.2 直接使用whisper识别（无需转换）
            if SPEECH_RECOGNITION_ENGINE == "whisper":
                text = recognize_audio_whisper(audio_file)
                if not text:
                    print("⚠️ 音频识别失败")
                else:
                    # 3.3 提取密码
                    password = extract_password_from_text(text)
            else:
                # 如果使用SpeechRecognition，需要转换为WAV格式
                wav_file = audio_dir / f"{audio_file.stem}.wav"
                if convert_audio_to_wav(audio_file, wav_file):
                    text = recognize_audio_speech_recognition(wav_file)
                    if not text:
                        print("⚠️ 音频识别失败")
                    else:
                        # 3.3 提取密码
                        password = extract_password_from_text(text)
                else:
                    print("⚠️ 音频转换失败")

    # 检查密码是否获取成功
    if not password:
        raise RuntimeError("❌ 自动获取密码失败，无法继续执行")

    # 步骤4：保存下载信息
    print("\n" + "=" * 80)
    print("💾 步骤4：保存下载信息")
    print("=" * 80)

    download_info_file = download_dir / "download_info.txt"
    with download_info_file.open("w", encoding="utf-8") as f:
        f.write(f"视频标题: {latest_video['title']}\n")
        f.write(f"视频日期: {latest_video['date_str']}\n")
        f.write(f"视频链接: {latest_video['url']}\n")
        f.write(f"下载地址: {download_url}\n")
        f.write(f"密码: {password}\n")
        f.write(f"获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"✅ 下载信息已保存到: {download_info_file}")

    # 完成
    print("\n" + "=" * 80)
    print("✅ 自动化流程完成！")
    print("=" * 80)
    print(f"\n📋 总结:")
    print(f"   视频标题: {latest_video['title']}")
    print(f"   视频日期: {latest_video['date_str']}")
    print(f"   下载地址: {download_url}")
    print(f"   密码: {password}")
    print(f"\n💡 使用下载地址和密码获取订阅链接")
    print("=" * 80)


if __name__ == "__main__":
    main()
