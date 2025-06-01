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
    """从原始订阅内容中提取所有节点链接（支持更多特殊字符）"""
    # 扩展正则匹配范围，包含?&@#.:%等常见特殊字符
    node_pattern = r'vmess://[\w\-+\/=?&@#.:%]+|vless://[\w\-+\/=?&@#.:%]+|trojan://[\w\-+\/=?&@#.:%]+|ss://[\w\-+\/=?&@#.:%]+|hysteria2://[\w\-+\/=?&@#.:%]+'
    return re.findall(node_pattern, content)

def get_subscription_links():
    # 删除旧文件（如果存在）
    for filename in ["base64.txt", "temp_subscription.txt"]:
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"已删除旧文件: {filename}")

    today = datetime.now()
    min_nodes = 1000  # 目标最小节点数（累计去重后）
    max_days_ago = 10  # 最多向前查找10天
    total_raw_nodes = 0  # 累计原始节点数（未去重）

    for days_ago in range(max_days_ago):
        target_date = today - timedelta(days=days_ago)
        month = target_date.month
        day = target_date.day
        date_str = f"{month}{day}"
        url = f"https://shz.al/~{date_str}-tg@pgkj666"
        logger.info(f"尝试日期: {target_date.date()}，生成URL: {url}")

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            subscription_content = response.text

            # 追加保存原始订阅内容到临时文件（累计所有日期）
            with open("temp_subscription.txt", "a", encoding="utf-8") as f:
                f.write(subscription_content + "\n")  # 换行分隔不同日期内容
            logger.info("订阅内容已追加到临时文件 temp_subscription.txt")

            # 提取当前日期的原始节点数并累计
            current_raw_nodes = extract_nodes(subscription_content)
            current_raw_count = len(current_raw_nodes)
            total_raw_nodes += current_raw_count
            logger.info(f"当前日期原始节点数: {current_raw_count}，累计原始节点数: {total_raw_nodes}")

            # 仅当累计原始节点数≥1000时，触发去重检查
            if total_raw_nodes >= min_nodes:
                # 读取所有累计的订阅内容
                with open("temp_subscription.txt", "r", encoding="utf-8") as f:
                    all_content = f.read()
                # 提取所有节点（不进行去重）
                all_raw_nodes = extract_nodes(all_content)
                raw_node_count = len(all_raw_nodes)
                if raw_node_count >= min_nodes:
                    # 不进行去重，直接使用原始节点
                    logger.info(f"原始节点数: {raw_node_count}")
                    # 转换原始节点为Base64并保存（修复：使用all_raw_nodes替代未定义的raw_nodes）
                    raw_content = "\n".join(all_raw_nodes)  # 合并原始节点文本
                    base64_content = base64.b64encode(raw_content.encode("utf-8")).decode("utf-8")
                    with open("base64.txt", "w", encoding="utf-8") as f:
                        f.write(base64_content)
                    logger.info(f"原始节点数达标（{raw_node_count}≥{min_nodes}），已保存到 base64.txt")
                    return  # 任务完成，退出循环
                else:
                    logger.info(f"原始节点数不足（{raw_node_count}<{min_nodes}），继续查找前一天...")

        except requests.exceptions.RequestException as e:
            logger.error(f"请求 {url} 失败: {str(e)}，继续查找前一天...")
            continue
        except Exception as e:
            logger.error(f"处理日期 {date_str} 时发生异常: {str(e)}，继续查找前一天...")
            continue

    logger.warning(f"已尝试前 {max_days_ago} 天，累计去重后节点数不足 {min_nodes}")

if __name__ == "__main__":
    get_subscription_links()
