import os
import requests
from bs4 import BeautifulSoup
import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def fetch_page(url):
    """发送 HTTP 请求并返回页面内容"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            logging.error(f"无法访问页面，状态码: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"请求页面时出错: {e}")
        return None

def parse_links(html, current_date):
    """解析 HTML 并提取符合条件的链接"""
    soup = BeautifulSoup(html, 'html.parser')
    h2_tags = soup.find_all('h2')
    links = []

    for h2 in h2_tags:
        link = h2.find('a')
        if link and link.get('href'):
            try:
                title = h2.get_text(strip=True)
                date_str = title.split(' ')[0]
                if is_recent_date(date_str, current_date):
                    links.append(link['href'])
            except ValueError:
                logging.warning(f"跳过无效标题: {h2.get_text(strip=True)}")
                continue
    return links

def is_recent_date(date_str, current_date):
    """检查日期是否在最近三天内"""
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y年%m月%d日')
        return (current_date - date_obj).days <= 3
    except ValueError:
        return False

def fetch_subscriptions(links):
    """访问链接并提取页面中的三级标题 Base64 订阅地址及其链接"""
    with open("links.txt", "a", encoding="utf-8") as file:
        for link in links:
            try:
                logging.info(f"访问链接: {link}")
                response = requests.get(link)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # 查找三级标题为“Base64 订阅地址”
                    h3_tags = soup.find_all('h3', string=lambda text: text and "Base64 订阅地址" in text)
                    for h3 in h3_tags:
                        logging.info(f"找到三级标题: {h3.get_text(strip=True)}")
                        h3_link = h3.find_next('a')  # 查找紧随其后的链接
                        if h3_link and h3_link.get('href'):
                            link_url = h3_link['href']
                            logging.info(f"链接地址: {link_url}")
                            file.write(link_url + "\n")  # 将链接写入文件
                else:
                    logging.error(f"无法访问链接 {link}，状态码: {response.status_code}")
            except Exception as e:
                logging.error(f"处理链接 {link} 时出错: {e}")

def main():
    url = "https://www.85la.com/internet-access/free-network-nodes"
    current_date = datetime.datetime.now()

    # 获取页面内容
    html = fetch_page(url)
    if html:
        # 解析链接
        links = parse_links(html, current_date)
        for link in links:
            logging.info(f"提取的链接: {link}")
        # 访问链接并提取订阅地址
        fetch_subscriptions(links)

if __name__ == "__main__":
    main()
