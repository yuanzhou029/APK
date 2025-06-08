import requests
import os
import logging

# 配置日志（仅输出到终端，GitHub Actions 控制台直接查看）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]  # 移除文件日志，避免工作流中文件路径问题
)
logger = logging.getLogger(__name__)

def write_links_to_cf_kv():
    """
    将 links.txt 内容写入 Cloudflare KV 存储的函数（适配 GitHub Actions）
    依赖：requests 库、GitHub Secrets 提供的环境变量
    """
    # 从环境变量读取 Cloudflare 参数（需在 GitHub Secrets 中配置）
    cf_email = os.getenv("CF_EMAIL")
    cf_api_key = os.getenv("CF_API_KEY")
    cf_account_id = os.getenv("CF_ACCOUNT_ID")
    cf_kv_namespace_id = os.getenv("CF_KV_NAMESPACE_ID")
    kv_key = os.getenv("CF_KV_KEY", "LINK.txt")  # 默认值 LINK.txt

    # 校验环境变量是否存在
    if not all([cf_email, cf_api_key, cf_account_id, cf_kv_namespace_id]):
        logger.error("⚠️ 未配置 Cloudflare 环境变量，请检查 GitHub Secrets")
        return False

    # 读取 links.txt 内容（使用工作流当前目录路径）
    links_file = os.path.join(os.getcwd(), "links.txt")  # GitHub Actions 工作目录为仓库根路径
    try:
        with open(links_file, "r", encoding="utf-8") as f:
            links_content = f.read().strip()
            if not links_content:
                logger.warning("links.txt 内容为空，将写入空字符串到 KV")
    except FileNotFoundError:
        logger.error(f"错误：未找到文件 {links_file}（请确保仓库中包含此文件）")
        return False
    except UnicodeDecodeError:
        logger.error(f"文件 {links_file} 编码非 UTF-8，请检查文件编码")
        return False
    except Exception as e:
        logger.error(f"读取文件失败：{str(e)}")
        return False

    # 校验命名空间 ID 长度
    if len(cf_kv_namespace_id) != 32:
        logger.error(f"命名空间 ID 长度错误（当前 {len(cf_kv_namespace_id)} 位，需 32 位）")
        return False

    # 构造 API URL 和请求头
    api_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/"
        f"storage/kv/namespaces/{cf_kv_namespace_id}/values/{kv_key}"
    )
    headers = {
        "X-Auth-Email": cf_email,
        "X-Auth-Key": cf_api_key,
        "Content-Type": "text/plain"
    }

    # 发送 PUT 请求
    try:
        response = requests.put(api_url, headers=headers, data=links_content)
        response.raise_for_status()
        api_response = response.json()
        
        if api_response.get("success"):
            logger.info(f"成功写入 Cloudflare KV！键：{kv_key}，内容长度：{len(links_content)} 字符")
            return True
        else:
            logger.error(f"API 响应失败：{api_response.get('errors', '无错误信息')}")
            return False
    except requests.exceptions.HTTPError as http_e:
        logger.error(f"HTTP 请求失败（状态码 {response.status_code}）：{response.text}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("无法连接到 Cloudflare API，请检查网络或 API 地址")
        return False
    except Exception as e:
        logger.error(f"写入失败，其他错误：{str(e)}")
        return False

if __name__ == "__main__":
    write_links_to_cf_kv()
