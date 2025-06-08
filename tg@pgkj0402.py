import requests
from datetime import datetime, timedelta
import logging
import os

# 配置日志（替换print，更清晰）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_valid_urls():
    # 确认 links.txt 是否存在（同目录下）
    links_path = os.path.join(os.path.dirname(__file__), "links.txt")
    if not os.path.exists(links_path):
        # 不存在则创建空文件（避免后续追加时报错）
        with open(links_path, "w", encoding="utf-8") as f:
            pass
        logger.info("links.txt 文件不存在，已创建新文件")
    else:
        logger.info("links.txt 文件已存在")

    today = datetime.now()
    max_days_ago = 10  # 最多向前查找10天（保持原参数）

    for days_ago in range(max_days_ago):
        target_date = today - timedelta(days=days_ago)
        month = target_date.month
        day = target_date.day
        date_str = f"{month}{day}"
        
        # 生成两个URL后缀（原'tg'和新'TG'）
        url_suffixes = ['tg', 'TG']
        for suffix in url_suffixes:
            url = f"https://shz.al/~{date_str}-{suffix}@pgkj0402"
            logger.info(f"尝试日期: {target_date.date()}，生成URL（后缀-{suffix}）: {url}")

            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()  # 验证URL有效性（HTTP状态码2xx）
                
                # 有效URL追加到links.txt（不覆盖原有数据）
                with open(links_path, "a", encoding="utf-8") as f:
                    f.write(url + "\n")  # 每个URL占一行
                logger.info(f"URL有效，已保存到links.txt: {url}")

            except requests.exceptions.RequestException as e:
                logger.error(f"请求URL（后缀-{suffix}）失败: {str(e)}，跳过该URL...")
                continue  # 单个URL失败，继续尝试下一个

    logger.info("所有日期URL验证完成，有效URL已追加到links.txt")

if __name__ == "__main__":
    get_valid_urls()
