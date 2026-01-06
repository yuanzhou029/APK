#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP源数据下载与解压工具

功能：
1. 从配置的URL下载IP源数据压缩包
2. 解压到 source_ips 目录
3. 根据配置的端口和国家代码筛选文件

配置文件：config.py
"""

import os
import sys
import re
import zipfile
import tarfile
import shutil
import logging
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import Optional, Tuple, Set
from collections import defaultdict

# 导入共享配置
try:
    from config import (
        DOWNLOAD_URL,
        IP_SOURCE_DIR,
        PROXY_PORTS,
        COUNTRY_CODES,
        COUNTRY_CONFIG
    )
except ImportError:
    print("错误：无法导入 config.py，请确保配置文件存在")
    sys.exit(1)

# 第三方库
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("正在安装 requests 库...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("正在安装 beautifulsoup4 库...")
    os.system(f"{sys.executable} -m pip install beautifulsoup4")
    from bs4 import BeautifulSoup

try:
    from tqdm import tqdm
except ImportError:
    print("正在安装 tqdm 库...")
    os.system(f"{sys.executable} -m pip install tqdm")
    from tqdm import tqdm

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DownloadExtractor:
    """下载并解压文件的类"""
    
    # 支持的压缩格式
    ARCHIVE_EXTENSIONS = {
        '.zip': 'zip',
        '.tar.gz': 'tar.gz',
        '.tgz': 'tar.gz',
        '.tar.bz2': 'tar.bz2',
        '.tbz2': 'tar.bz2',
        '.tar': 'tar',
        '.gz': 'gzip',
        '.7z': '7z',
        '.rar': 'rar'
    }
    
    def __init__(self, 
                 url: str, 
                 output_dir: str = None,
                 timeout: int = 30,
                 max_retries: int = 3,
                 verify_ssl: bool = True):
        self.url = url
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.session = self._create_session()
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_session(self) -> requests.Session:
        """创建带有重试机制的会话"""
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置请求头
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        return session
    
    def _get_filename_from_response(self, response: requests.Response, url: str) -> str:
        """从响应头或URL中提取文件名"""
        # 尝试从Content-Disposition头获取文件名
        content_disposition = response.headers.get('Content-Disposition', '')
        if content_disposition:
            matches = re.findall(r'filename[*]?=["\']?([^"\';\n]+)', content_disposition)
            if matches:
                return matches[0].strip()
        
        # 从URL路径获取文件名
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path:
            filename = os.path.basename(path)
            if filename and filename != '/':
                return filename
        
        # 默认文件名
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'downloaded_file_{timestamp}'
    
    def _get_unique_filepath(self, file_path: Path) -> Path:
        """获取唯一的文件路径"""
        if not file_path.exists():
            return file_path
        
        base = file_path.stem
        suffix = file_path.suffix
        parent = file_path.parent
        counter = 1
        
        while True:
            new_path = parent / f"{base}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
    
    def _get_archive_type(self, filename: str) -> Optional[str]:
        """根据文件名判断压缩类型"""
        filename_lower = filename.lower()
        
        for ext, archive_type in self.ARCHIVE_EXTENSIONS.items():
            if filename_lower.endswith(ext):
                return archive_type
        
        return None
    
    def _detect_archive_type_by_magic(self, file_path: Path) -> Optional[str]:
        """通过文件魔术字节检测压缩类型"""
        MAGIC_SIGNATURES = {
            b'PK\x03\x04': 'zip',
            b'PK\x05\x06': 'zip',
            b'PK\x07\x08': 'zip',
            b'\x1f\x8b': 'gzip',
            b'BZh': 'tar.bz2',
            b'\xfd7zXZ\x00': 'xz',
            b'7z\xbc\xaf\x27\x1c': '7z',
            b'Rar!\x1a\x07': 'rar',
        }
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            
            for magic, archive_type in MAGIC_SIGNATURES.items():
                if header.startswith(magic):
                    return archive_type
            
            with open(file_path, 'rb') as f:
                f.seek(257)
                if f.read(5) == b'ustar':
                    return 'tar'
        except Exception:
            pass
        
        return None
    
    def download(self) -> Tuple[Path, str]:
        """下载文件"""
        logger.info(f"开始访问: {self.url}")
        
        try:
            head_response = self.session.head(
                self.url, 
                timeout=self.timeout, 
                verify=self.verify_ssl,
                allow_redirects=True
            )
            content_type = head_response.headers.get('Content-Type', '')
            
            if 'text/html' in content_type:
                logger.info("检测到HTML页面，正在提取下载链接...")
                response = self.session.get(
                    self.url, 
                    timeout=self.timeout, 
                    verify=self.verify_ssl
                )
                response.raise_for_status()
                
                download_url = self._find_download_link(response.text, self.url)
                if download_url:
                    logger.info(f"找到下载链接: {download_url}")
                    self.url = download_url
                else:
                    logger.warning("未找到明确的下载链接，尝试直接下载当前URL")
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"HEAD请求失败: {e}，尝试直接GET请求")
        
        logger.info(f"开始下载: {self.url}")
        
        response = self.session.get(
            self.url, 
            timeout=self.timeout, 
            verify=self.verify_ssl,
            stream=True
        )
        response.raise_for_status()
        
        filename = self._get_filename_from_response(response, self.url)
        file_path = self.output_dir / filename
        file_path = self._get_unique_filepath(file_path)
        filename = file_path.name
        
        total_size = int(response.headers.get('content-length', 0))
        
        logger.info(f"文件名: {filename}")
        if total_size:
            logger.info(f"文件大小: {total_size / 1024 / 1024:.2f} MB")
        
        with open(file_path, 'wb') as f:
            if total_size:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        logger.info(f"下载完成: {file_path}")
        return file_path, filename
    
    def _find_download_link(self, html_content: str, base_url: str) -> Optional[str]:
        """从HTML页面中查找下载链接"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        download_patterns = [
            ('a', {'href': re.compile(r'.*\.(zip|tar\.gz|tgz|tar\.bz2|tbz2|tar|7z|rar)$', re.I)}),
            ('a', {'download': True}),
            ('a', {'href': True}),
        ]
        
        for tag, attrs in download_patterns:
            elements = soup.find_all(tag, attrs)
            for elem in elements:
                href = elem.get('href')
                if href:
                    if any(href.lower().endswith(ext) for ext in self.ARCHIVE_EXTENSIONS.keys()):
                        return urljoin(base_url, href)
                    text = elem.get_text().lower()
                    if 'download' in text or '下载' in text:
                        return urljoin(base_url, href)
        
        meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
        if meta_refresh:
            content = meta_refresh.get('content', '')
            match = re.search(r'url=(.+)', content, re.I)
            if match:
                return urljoin(base_url, match.group(1))
        
        return None
    
    def extract(self, file_path: Path, extract_dir: Path = None, archive_type: str = None) -> Path:
        """解压文件"""
        if extract_dir is None:
            base_name = file_path.stem
            if base_name.endswith('.tar'):
                base_name = base_name[:-4]
            extract_dir = file_path.parent / base_name
        
        extract_dir = Path(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        if archive_type is None:
            archive_type = self._get_archive_type(file_path.name)
        
        logger.info(f"开始解压: {file_path}")
        logger.info(f"解压目录: {extract_dir}")
        logger.info(f"压缩类型: {archive_type}")
        
        try:
            if archive_type == 'zip':
                self._extract_zip(file_path, extract_dir)
            elif archive_type in ('tar.gz', 'tar.bz2', 'tar'):
                self._extract_tar(file_path, extract_dir)
            elif archive_type == 'gzip':
                self._extract_gzip(file_path, extract_dir)
            elif archive_type == '7z':
                self._extract_7z(file_path, extract_dir)
            elif archive_type == 'rar':
                self._extract_rar(file_path, extract_dir)
            else:
                logger.warning(f"未知的压缩格式，尝试作为zip解压")
                self._extract_zip(file_path, extract_dir)
            
            logger.info(f"解压完成: {extract_dir}")
            return extract_dir
            
        except Exception as e:
            logger.error(f"解压失败: {e}")
            raise
    
    def _extract_zip(self, file_path: Path, extract_dir: Path):
        """解压ZIP文件"""
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            with tqdm(total=len(file_list), desc="解压中", unit="文件") as pbar:
                for file in file_list:
                    zip_ref.extract(file, extract_dir)
                    pbar.update(1)
    
    def _extract_tar(self, file_path: Path, extract_dir: Path):
        """解压TAR文件"""
        mode = 'r'
        if file_path.name.endswith('.gz') or file_path.name.endswith('.tgz'):
            mode = 'r:gz'
        elif file_path.name.endswith('.bz2') or file_path.name.endswith('.tbz2'):
            mode = 'r:bz2'
        
        with tarfile.open(file_path, mode) as tar_ref:
            members = tar_ref.getmembers()
            with tqdm(total=len(members), desc="解压中", unit="文件") as pbar:
                for member in members:
                    tar_ref.extract(member, extract_dir)
                    pbar.update(1)
    
    def _extract_gzip(self, file_path: Path, extract_dir: Path):
        """解压GZIP文件"""
        import gzip
        output_file = extract_dir / file_path.stem
        with gzip.open(file_path, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    def _extract_7z(self, file_path: Path, extract_dir: Path):
        """解压7Z文件"""
        try:
            import py7zr
        except ImportError:
            logger.info("正在安装 py7zr 库...")
            os.system(f"{sys.executable} -m pip install py7zr")
            import py7zr
        
        with py7zr.SevenZipFile(file_path, mode='r') as z:
            z.extractall(path=extract_dir)
    
    def _extract_rar(self, file_path: Path, extract_dir: Path):
        """解压RAR文件"""
        try:
            import rarfile
        except ImportError:
            logger.info("正在安装 rarfile 库...")
            os.system(f"{sys.executable} -m pip install rarfile")
            import rarfile
        
        try:
            with rarfile.RarFile(file_path, 'r') as rar_ref:
                file_list = rar_ref.namelist()
                with tqdm(total=len(file_list), desc="解压中", unit="文件") as pbar:
                    for file in file_list:
                        rar_ref.extract(file, extract_dir)
                        pbar.update(1)
        except Exception as e:
            raise RuntimeError(f"RAR解压失败: {e}")


def merge_ip_files(source_dir: Path, output_dir: Path, ports: list, country_codes: list) -> dict:
    """
    合并并去重IP文件
    
    Args:
        source_dir: 解压后的源目录
        output_dir: 输出目录
        ports: 端口列表
        country_codes: 国家代码列表
        
    Returns:
        dict: 合并统计信息
    """
    logger.info("开始合并IP文件...")
    
    # 统计信息
    stats = {
        'total_files': 0,
        'total_ips_before': 0,
        'total_ips_after': 0,
        'by_country': {}
    }
    
    # 按国家代码收集IP
    country_ips: dict[str, Set[str]] = defaultdict(set)
    
    # 遍历每个端口目录
    for port in ports:
        port_dir = source_dir / str(port)
        if not port_dir.exists():
            logger.warning(f"端口目录不存在: {port_dir}")
            continue
        
        logger.info(f"处理端口目录: {port}")
        
        # 遍历每个国家代码文件
        for country_code in country_codes:
            file_path = port_dir / f"{country_code}.txt"
            if not file_path.exists():
                continue
            
            stats['total_files'] += 1
            
            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            stats['total_ips_before'] += 1
                            # 提取IP（去掉端口号，如果有的话）
                            ip = line.split(':')[0] if ':' in line else line
                            country_ips[country_code].add(ip)
            except Exception as e:
                logger.error(f"读取文件失败 {file_path}: {e}")
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存合并后的文件
    for country_code, ips in country_ips.items():
        output_file = output_dir / f"{country_code}.txt"
        
        # 排序并保存
        sorted_ips = sorted(ips)
        with open(output_file, 'w', encoding='utf-8') as f:
            for ip in sorted_ips:
                f.write(f"{ip}\n")
        
        stats['total_ips_after'] += len(ips)
        stats['by_country'][country_code] = {
            'count': len(ips),
            'name': COUNTRY_CONFIG.get(country_code, country_code)
        }
        
        logger.info(f"  {country_code} ({COUNTRY_CONFIG.get(country_code, country_code)}): {len(ips)} 个IP")
    
    return stats


def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    
    # 临时下载目录
    temp_download_dir = script_dir / "temp_downloads"
    
    # 临时解压目录
    temp_extract_dir = script_dir / "temp_extract"
    
    # 最终输出目录（从配置读取）
    output_dir = script_dir / IP_SOURCE_DIR
    
    print("=" * 60)
    print("🚀 IP源数据下载与解压工具")
    print("=" * 60)
    print(f"📥 下载URL: {DOWNLOAD_URL}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🔌 配置端口: {PROXY_PORTS}")
    print(f"🌍 配置国家: {', '.join([f'{k}({v})' for k, v in COUNTRY_CONFIG.items()])}")
    print("=" * 60)
    
    try:
        # 清理临时目录
        for temp_dir in [temp_download_dir, temp_extract_dir]:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 清空输出目录
        if output_dir.exists():
            logger.info(f"清空输出目录: {output_dir}")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建下载器实例
        downloader = DownloadExtractor(
            url=DOWNLOAD_URL,
            output_dir=str(temp_download_dir),
            timeout=60,
            max_retries=3,
            verify_ssl=False
        )
        
        # 下载文件
        file_path, filename = downloader.download()
        
        # 检测压缩类型
        archive_type = downloader._get_archive_type(filename)
        if not archive_type:
            logger.info("文件名无法识别压缩类型，尝试通过文件内容检测...")
            archive_type = downloader._detect_archive_type_by_magic(file_path)
            if archive_type:
                logger.info(f"通过文件内容检测到压缩类型: {archive_type}")
        
        if archive_type:
            # 解压到临时目录
            extract_result = downloader.extract(
                file_path, 
                extract_dir=temp_extract_dir, 
                archive_type=archive_type
            )
            
            # 删除下载的压缩文件
            logger.info(f"删除压缩文件: {file_path}")
            file_path.unlink()
            
            # 合并IP文件
            print("\n" + "=" * 60)
            print("📊 合并IP文件")
            print("=" * 60)
            
            stats = merge_ip_files(
                source_dir=temp_extract_dir,
                output_dir=output_dir,
                ports=PROXY_PORTS,
                country_codes=COUNTRY_CODES
            )
            
            # 清理临时解压目录
            shutil.rmtree(temp_extract_dir)
            
            # 输出统计信息
            print("\n" + "=" * 60)
            print("✅ 操作完成!")
            print("=" * 60)
            print(f"📁 处理文件数: {stats['total_files']}")
            print(f"📊 合并前IP数: {stats['total_ips_before']}")
            print(f"📊 合并后IP数: {stats['total_ips_after']}")
            print(f"🔄 去重数量: {stats['total_ips_before'] - stats['total_ips_after']}")
            print(f"📂 输出目录: {output_dir}")
            
            print("\n🌍 各国家IP统计:")
            for code, info in stats['by_country'].items():
                print(f"   {code} ({info['name']}): {info['count']} 个IP")
            
        else:
            logger.error("无法识别下载文件的压缩类型")
            sys.exit(1)
        
        # 清理临时下载目录
        if temp_download_dir.exists():
            shutil.rmtree(temp_download_dir)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logger.exception("详细错误信息:")
        sys.exit(1)


if __name__ == "__main__":
    main()
