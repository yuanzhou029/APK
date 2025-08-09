const fs = require('fs');
const puppeteerExtra = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');

puppeteerExtra.use(StealthPlugin());

(async () => {
  const urlEnv = process.env.TARGET_URLS || '';
  const urls = urlEnv.split(/[\n,]+/).map(u => u.trim()).filter(Boolean);

  if (urls.length === 0) {
    console.error('请设置环境变量 TARGET_URLS，多个 URL 用换行或逗号分隔');
    process.exit(1);
  }

  const outputFile = process.env.OUTPUT_FILE || 'dy.txt';

  fs.writeFileSync(outputFile, '', 'utf-8');
  console.log(`清空文件：${outputFile}`);

  const browser = await puppeteerExtra.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();

  for (const url of urls) {
    try {
      console.log(`开始访问：${url}`);
      await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });

      const content = await page.evaluate(() => document.body.innerText);

      fs.appendFileSync(outputFile, content + '\n\n', 'utf-8');

      console.log(`成功追加内容，URL：${url}`);
    } catch (err) {
      console.error(`访问失败，跳过 URL：${url}，错误：${err.message}`);
    }
  }

  await browser.close();
  console.log(`全部完成，内容已保存到 ${outputFile}`);
})();
