import requests
import os

def read_links(file_path):
    """读取links.txt中的URL，过滤空行并按首次出现顺序去重"""
    if not os.path.exists(file_path):
        print("错误：links.txt文件不存在")
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        # 读取所有行并去除首尾空格，过滤空行
        raw_links = [line.strip() for line in f.readlines() if line.strip()]
    
    # 按首次出现顺序去重（保留第一个出现的链接）
    seen = set()
    unique_links = []
    for link in raw_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    return unique_links

def check_link_valid(link, timeout=10):
    """检测单个链接是否有效（返回数据非空）"""
    try:
        response = requests.get(link, timeout=timeout)
        # 检查响应状态码是否为2xx且内容非空
        return response.ok and len(response.text) > 0
    except requests.exceptions.RequestException:
        return False

def save_valid_links(file_path, valid_links):
    """将有效链接保存回links.txt"""
    with open(file_path, "w", encoding="utf-8") as f:
        for link in valid_links:
            f.write(link + "\n")
    print(f"已保存有效链接，共 {len(valid_links)} 条")

if __name__ == "__main__":
    links_path = os.path.join(os.path.dirname(__file__), "links.txt")
    
    # 读取并按首次出现顺序去重
    all_links = read_links(links_path)
    if not all_links:
        print("links.txt无有效链接或文件不存在")
        exit()
    
    # 统计总链接数
    total_links = len(all_links)
    print(f"开始检测，当前links.txt共有 {total_links} 条唯一链接（去重后）")

    # 逐个检测并统计有效/无效链接
    valid_count = 0
    invalid_count = 0
    valid_links = []
    
    for idx, link in enumerate(all_links, 1):
        if check_link_valid(link):
            valid_links.append(link)
            valid_count += 1
            print(f"链接 {idx}/{total_links} 有效: {link}")
        else:
            invalid_count += 1
            print(f"链接 {idx}/{total_links} 无效（无数据或请求失败）: {link}")
    
    # 保存有效链接并输出汇总结果
    save_valid_links(links_path, valid_links)
    print(f"检测完成！总链接数：{total_links}，可用链接数：{valid_count}，已删除无效链接数：{invalid_count}")
