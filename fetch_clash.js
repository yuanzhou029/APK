const fs = require('fs');
const puppeteer = require('puppeteer');

(async () => {
  const url = process.env.TARGET_URL;
  if (!url) {
    console.error('请设置环境变量 TARGET_URL');
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });

  const content = await page.evaluate(() => document.body.innerText);

  fs.writeFileSync(process.env.OUTPUT_FILE || 'v2ray.txt', content, 'utf-8');

  console.log(`内容已保存到 ${process.env.OUTPUT_FILE || 'Clash1.txt'}`);

  await browser.close();
})();
