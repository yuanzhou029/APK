const puppeteer = require('puppeteer');
const fs = require('fs');

async function run() {
  try {
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();

    // 随机User-Agent
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    // 模拟浏览行为
    await page.goto('https://www.85la.com/', { waitUntil: 'networkidle2' });
    await new Promise(resolve => setTimeout(resolve, 2000));

    // 访问目标页面
    await page.goto('https://www.85la.com/internet-access/free-network-nodes', { waitUntil: 'networkidle2' });
    await new Promise(resolve => setTimeout(resolve, 3000));

    // 提取链接
    const links = await page.evaluate(() => {
      const elements = document.querySelectorAll('h2 a');
      return Array.from(elements).map(el => el.href);
    });

    // 访问链接并提取订阅地址
    const subscriptionLinks = [];
    for (const link of links) {
      await page.goto(link, { waitUntil: 'networkidle2' });
      await new Promise(resolve => setTimeout(resolve, 2000));

      const subs = await page.evaluate(() => {
        const h3s = document.querySelectorAll('h3');
        let subLink = null;
        h3s.forEach(h3 => {
          if (h3.textContent.includes('Base64 订阅地址')) {
            const a = h3.nextElementSibling;
            if (a && a.tagName === 'A') {
              subLink = a.href;
            }
          }
        });
        return subLink;
      });

      if (subs) subscriptionLinks.push(subs);
    }

    // 保存结果
    fs.writeFileSync('links.txt', subscriptionLinks.join('\n'));
    console.log(`保存了 ${subscriptionLinks.length} 个订阅链接`);

    await browser.close();
  } catch (error) {
    console.error('爬虫出错:', error);
    process.exit(1);
  }
}

run();
