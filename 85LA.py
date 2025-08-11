import time
import re
import os
import datetime
import chromedriver_autoinstaller
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

class SimpleBrowserCrawler:
    """简化的模拟浏览器访问爬虫"""
    
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome浏览器驱动，自动安装匹配版本ChromeDriver"""
        try:
            # 自动安装匹配版本的chromedriver
            chromedriver_autoinstaller.install()

            # Chrome选项配置
            chrome_options = Options()
            
            # 基本设置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            
            # 无头模式设置
            if self.headless:
                chrome_options.add_argument('--headless')
            
            # 用户代理设置
            chrome_options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 窗口设置
            chrome_options.add_argument('--window-size=1920,1080')
            
            # 语言设置
            chrome_options.add_argument('--lang=zh-CN')
            
            # 创建WebDriver，使用undetected_chromedriver
            self.driver = uc.Chrome(options=chrome_options)
            
            print("✅ Chrome浏览器驱动初始化成功")
            
        except Exception as e:
            print(f"❌ 浏览器驱动初始化失败: {e}")
            print("💡 请确保已安装Chrome浏览器，并尝试安装chromedriver-autoinstaller和undetected-chromedriver库")
            self.driver = None
    
    def wait_for_page_load(self, timeout=30):
        """等待页面加载完成"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            print("⚠️ 页面加载超时")
            return False
    
    def get_page_content(self, url, wait_time=5):
        """获取页面内容"""
        if not self.driver:
            print("❌ 浏览器驱动未初始化")
            return None
        
        try:
            print(f"🌐 正在访问: {url}")
            
            # 访问页面
            self.driver.get(url)
            
            # 等待页面加载
            if not self.wait_for_page_load():
                print("⚠️ 页面加载可能不完整")
            
            # 等待一下让JavaScript执行
            time.sleep(wait_time)
            
            # 滚动页面以触发动态内容
            print("📜 滚动页面...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # 获取页面源码
            page_source = self.driver.page_source
            
            print(f"✅ 页面获取成功")
            print(f"  源码长度: {len(page_source)} 字符")
            
            return page_source
            
        except Exception as e:
            print(f"❌ 获取页面内容失败: {e}")
            return None
    
    def save_to_temp_file(self, content, filename="temp_page.html"):
        """保存内容到临时文件"""
        if not content:
            print("❌ 没有内容可保存")
            return False
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ 页面内容已保存到临时文件 {filename}")
            return True
            
        except Exception as e:
            print(f"❌ 保存内容失败: {e}")
            return False
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("🔒 浏览器已关闭")

def extract_recent_links(html_file, days=3):
    """从HTML文件中提取最近几天的链接"""
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        today = datetime.datetime.now()
        links = []
        
        pattern = r'<span class="layui-badge layui-bg-cyan x">(\d{4}/\d{1,2}/\d{1,2})</span>[\s\S]*?<div class="index-post-img-small"><a href="([^"]+)"'
        matches = re.findall(pattern, content)
        
        for date_str, link in matches:
            try:
                date_parts = date_str.split('/')
                post_date = datetime.datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]))
                delta = today - post_date
                if delta.days < days:
                    links.append(link)
                    print(f"找到最近{days}天内的链接: {link} (发布日期: {date_str})")
            except Exception as e:
                print(f"解析日期失败: {date_str}, 错误: {e}")
                continue
        
        return links
    
    except Exception as e:
        print(f"提取链接失败: {e}")
        return []

def save_links_to_file(links, filename="url.txt"):
    """保存链接到文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for link in links:
                f.write(f"{link}\n")
        
        print(f"✅ 已将{len(links)}个链接保存到 {filename}")
        return True
    
    except Exception as e:
        print(f"❌ 保存链接失败: {e}")
        return False

def extract_v2ray_links(html_content):
    """从HTML内容中提取V2ray订阅地址"""
    v2ray_links = []
    pattern = r'V2ray 订阅地址.*?href="(https?://[^\s"]+\.txt)"'
    match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
    if match:
        link = match.group(1)
        v2ray_links.append(link)
        print(f"找到V2ray订阅链接: {link}")
    else:
        print("⚠️ 未找到V2ray订阅链接")
    return v2ray_links

def process_links_from_file(links_file, crawler, delete_temp_files=True):
    """从url.txt文件中读取链接并逐个访问"""
    try:
        with open(links_file, 'r', encoding='utf-8') as f:
            links = [line.strip() for line in f if line.strip()]
        
        print(f"\n🔍 开始处理 {len(links)} 个链接")
        
        v2ray_output_file = "links.txt"

        for i, link in enumerate(links, 1):
            print(f"\n🔄 正在处理第 {i}/{len(links)} 个链接: {link}")
            page_content = crawler.get_page_content(link)
            
            if page_content:
                temp_file = f"temp_page_{i}.html"
                if crawler.save_to_temp_file(page_content, temp_file):
                    print(f"✅ 页面内容已保存到 {temp_file}")
                    extracted_v2ray_links = extract_v2ray_links(page_content)
                    if extracted_v2ray_links:
                        with open(v2ray_output_file, 'a', encoding='utf-8') as f_v2ray:
                            for v2ray_link in extracted_v2ray_links:
                                f_v2ray.write(f"{v2ray_link}\n")
                        print(f"✅ 已将 {len(extracted_v2ray_links)} 个V2ray链接追加到 {v2ray_output_file}")
                    else:
                        print(f"⚠️ 未在 {temp_file} 中找到V2ray订阅链接")

                    if delete_temp_files:
                        try:
                            os.remove(temp_file)
                            print(f"✅ 临时文件 {temp_file} 已删除")
                        except Exception as e:
                            print(f"⚠️ 删除临时文件 {temp_file} 失败: {e}")

                else:
                    print(f"❌ 保存页面内容到 {temp_file} 失败")
            else:
                print(f"❌ 无法获取 {link} 的页面内容")
        
        return True
    
    except Exception as e:
        print(f"❌ 处理链接文件失败: {e}")
        return False

def main():
    print("🚀 85LA网站链接提取工具")
    print("=" * 60)
    
    url = "https://www.85la.com/"
    temp_file = "temp_page.html"
    links_file = "url.txt"
    v2ray_output_file = "links.txt"
    days = 3
    
    crawler = SimpleBrowserCrawler(headless=True)
    
    if not crawler.driver:
        print("❌ 无法启动浏览器，请检查Chrome和ChromeDriver安装")
        return
    
    should_delete_temp_html = False  # 调试时False，发布时True

    try:
        page_content = crawler.get_page_content(url)
        
        if page_content:
            if crawler.save_to_temp_file(page_content, temp_file):
                recent_links = extract_recent_links(temp_file, days)
                
                if recent_links:
                    save_links_to_file(recent_links, links_file)
                    process_links_from_file(links_file, crawler, should_delete_temp_html)
                else:
                    print(f"⚠️ 未找到最近{days}天内的链接")
                
                try:
                    os.remove(temp_file)
                    print(f"✅ 临时文件 {temp_file} 已删除")
                except Exception as e:
                    print(f"⚠️ 删除临时文件失败: {e}")
            else:
                print("❌ 保存页面内容到临时文件失败")
        else:
            print("❌ 无法获取页面内容")
    
    except Exception as e:
        print(f"❌ 处理过程中出错: {e}")
    
    finally:
        crawler.close()
        try:
            if os.path.exists(links_file):
                os.remove(links_file)
                print(f"✅ 临时文件 {links_file} 已删除")
        except Exception as e:
            print(f"⚠️ 删除临时文件 {links_file} 失败: {e}")

    print("\n" + "=" * 60)
    print("链接提取和处理完成")

if __name__ == "__main__":
    main()
