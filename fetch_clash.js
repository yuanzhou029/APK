const fs = require('fs');
const puppeteer = require('puppeteer');

(async () => {
  const urlEnv = process.env.TARGET_URLS || '';
  const urlList = urlEnv.split(',').map(u => u.trim()).filter(Boolean);

  if (urlList.length === 0) {
    console.error('请设置环境变量 TARGET_URLS，多条 URL 用逗号分隔');
    process.exit(1);
  }

  const outputFile = process.env.OUTPUT_FILE || 'v2ray.txt';

  // 清空文件，避免重复追加
  fs.writeFileSync(outputFile, '', 'utf-8');

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  for (const url of urlList) {
    try {
      console.log(`正在访问：${url}`);
      await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });

      const content = await page.evaluate(() => document.body.textContent);

      fs.appendFileSync(outputFile, content + '\n\n', 'utf-8');

      console.log(`成功追加内容，URL：${url}`);
    } catch (e) {
      console.error(`访问失败，跳过 URL：${url}\n错误：${e.message}`);
    }
  }

  await browser.close();

  console.log(`所有完成，内容已保存到 ${outputFile}`);
})();
