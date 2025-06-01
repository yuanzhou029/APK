import requests
import base64
from datetime import datetime, timedelta
import logging
import re
import os

# 配置日志（替换print，更清晰）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_nodes(content):
    """从原始订阅内容中提取所有节点链接（支持vmess、vless等协议）"""
    # 正则匹配所有协议链接（精确匹配完整链接，避免部分匹配）
    node_pattern = r'vmess://[\w\-+\/=]+|vless://[\w\-+\/=]+|trojan://[\w\-+\/=]+|ss://[\w\-+\/=]+|hysteria2://[\w\-+\/=]+'
    return re.findall(node_pattern, content)

def get_subscription_links():
    # 删除旧文件（如果存在）
    for filename in ["base64.txt", "temp_subscription.txt"]:
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"已删除旧文件: {filename}")

    today = datetime.now()
    min_nodes = 1000  # 目标最小节点数
    max_days_ago = 10  # 最多向前查找10天

    for days_ago in range(max_days_ago):
        # 生成两位的月份和日期（如01月05日 -> 0105）
        target_date = today - timedelta(days=days_ago)
        date_str = target_date.strftime("%m%d")  # 修正为两位数字格式
        url = f"https://shz.al/~{date_str}-tg@pgkj666"
        logger.info(f"尝试日期: {target_date.date()}，生成URL: {url}")

        try:
            # 获取订阅内容（带超时）
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            subscription_content = response.text

            # 保存原始订阅内容到临时文件
            with open("temp_subscription.txt", "w", encoding="utf-8") as f:
                f.write(subscription_content)
            logger.info("订阅内容已保存到临时文件 temp_subscription.txt")

            # 提取原始节点（未去重）
            raw_nodes = extract_nodes(subscription_content)
            raw_node_count = len(raw_nodes)
            logger.info(f"原始节点数（未去重）: {raw_node_count}")

            if raw_node_count >= min_nodes:
                # 去重处理
                unique_nodes = list(set(raw_nodes))  # 去重
                unique_node_count = len(unique_nodes)
                logger.info(f"去重后节点数: {unique_node_count}")

                if unique_node_count >= min_nodes:
                    # 去重后满足条件，转换为Base64并保存
                    unique_content = "\n".join(unique_nodes)  # 合并为文本
                    base64_content = base64.b64encode(unique_content.encode("utf-8")).decode("utf-8")
                    with open("base64.txt", "w", encoding="utf-8") as f:
                        f.write(base64_content)
                    logger.info(f"去重后节点数达标（{unique_node_count}≥{min_nodes}），已保存到 base64.txt")
                    return  # 任务完成，退出循环
                else:
                    logger.info(f"去重后节点数不足（{unique_node_count}<{min_nodes}），继续查找前一天...")
            else:
                logger.info(f"原始节点数不足（{raw_node_count}<{min_nodes}），继续查找前一天...")

        except requests.exceptions.RequestException as e:
            logger.error(f"请求 {url} 失败: {str(e)}，继续查找前一天...")
            continue
        except Exception as e:
            logger.error(f"处理日期 {date_str} 时发生异常: {str(e)}，继续查找前一天...")
            continue

    logger.warning(f"已尝试前 {max_days_ago} 天，未找到满足条件的节点（去重后不足 {min_nodes}）")

if __name__ == "__main__":
    get_subscription_links()
