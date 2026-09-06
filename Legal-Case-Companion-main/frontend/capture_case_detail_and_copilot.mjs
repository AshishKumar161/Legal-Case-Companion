import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = 'C:/Users/akuma/OneDrive/Desktop/lcc/screenshots';

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  try {
    // Recapture polished /lawyers page
    console.log('Recapturing /lawyers page...');
    await page.goto('http://localhost:3000/lawyers', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_redesigned_lawyers.png') });

    // 1. Login as Vikram Sharma
    console.log('Logging in as Vikram Sharma...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle2' });
    await page.waitForSelector('#demo-client-btn');
    await page.click('#demo-client-btn');
    await page.waitForNavigation({ waitUntil: 'networkidle2' });

    // 2. Go to /cases and find View My Case link
    console.log('Navigating to /cases...');
    await page.goto('http://localhost:3000/cases', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1200));

    const links = await page.$$('a');
    let caseUrl = '';
    for (const l of links) {
      const text = await (await l.getProperty('textContent')).jsonValue();
      if (text && text.includes('View My Case')) {
        caseUrl = await (await l.getProperty('href')).jsonValue();
        break;
      }
    }

    console.log('Found target case URL:', caseUrl);
    if (caseUrl) {
      console.log('Navigating to case detail:', caseUrl);
      await page.goto(caseUrl, { waitUntil: 'networkidle2' });
    }

    if (caseUrl) {
      await new Promise(r => setTimeout(r, 1500));
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_case_detail_active.png') });

      // Click "What should I do?"
      const buttons = await page.$$('button');
      for (const btn of buttons) {
        const text = await (await btn.getProperty('textContent')).jsonValue();
        if (text && text.includes('What should I do?')) {
          await btn.click();
          await new Promise(r => setTimeout(r, 800));
          await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05b_case_guidance_box.png') });
          break;
        }
      }

      // Switch to Assistant / Insights tab
      for (const btn of buttons) {
        const text = await (await btn.getProperty('textContent')).jsonValue();
        if (text && (text.includes('Legal Assistant') || text.includes('Insights') || text.includes('Ask LCC'))) {
          await btn.click();
          await new Promise(r => setTimeout(r, 800));
          await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05c_case_assistant_tab.png') });
          break;
        }
      }
    }

    console.log('Case detail and assistant screenshots captured successfully!');
  } catch (err) {
    console.error('Error:', err);
  } finally {
    await browser.close();
  }
}

run();
