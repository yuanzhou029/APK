#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ProxyIP 项目共享配置文件

此配置文件被以下脚本共享使用：
- download_and_extract.py: 下载并解压IP源数据
- ip.py: 代理IP检测

修改此文件中的配置，两个脚本会自动同步。
"""

# ==================== 端口配置 ====================
# 检测端口列表
# - download_and_extract.py: 从这些端口目录读取IP文件
# - ip.py: 使用这些端口进行代理检测
# - PROXY_PORTS = [443, 2053, 2083, 2087, 2096, 8443]
PROXY_PORTS = [443]

# ==================== 国家配置 ====================
# 国家筛选配置
# - 键(Key): 国家代码，对应IP源文件名（如 TW.txt, JP.txt）
# - 值(Value): 中文名称，用于ip.py的国家筛选和输出文件名
#
# 如果要添加新国家，只需在此添加映射即可
COUNTRY_CONFIG = {
    "KR": "韩国",
    "JP": "日本",
    "HK": "香港",
    "SG": "新加坡",
    "US": "美国",
}

# 从配置生成筛选列表（供ip.py使用）
FILTER_COUNTRIES = list(COUNTRY_CONFIG.values())

# 从配置生成国家代码列表（供download_and_extract.py使用）
COUNTRY_CODES = list(COUNTRY_CONFIG.keys())

# ==================== 目录配置 ====================
# IP源目录（download_and_extract.py 解压后的目录）
IP_SOURCE_DIR = "source_ips"

# 输出目录（ip.py 保存有效代理的目录）
OUTPUT_DIR = "valid_proxies"

# ==================== 下载配置 ====================
# IP源下载URL
DOWNLOAD_URL = "https://zip.yh-iot.pp.ua/zip/ip.zip"

# ==================== API配置 ====================
# 代理检测API
# CHECK_API = "https://proxyip.yuanzhou04-764.workers.dev/check"
CHECK_API = "https://check.proxyip.cmliussss.net/check"

# https://proxyip.yuanzhou04-764.workers.dev/check
# https://cf.090227.xyz/check

# ==================== 性能配置 ====================
# 并发线程数
MAX_THREADS = 30

# TCP握手超时秒数
TCP_TIMEOUT = 2

# API响应超时秒数
API_TIMEOUT = 5

# ==================== 功能开关 True False====================
# 是否进行二次验证
ENABLE_SECOND_VERIFY = False

# 是否输出每个IP的检测结果
VERBOSE_OUTPUT = False



