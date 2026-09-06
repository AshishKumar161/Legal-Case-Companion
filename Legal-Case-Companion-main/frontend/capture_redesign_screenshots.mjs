import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = 'C:/Users/akuma/OneDrive/Desktop/lcc/screenshots';
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log('Launching browser to capture redesign verification screenshots...');
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  try {
    // 1. Landing Page
    console.log('1. Landing Page...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_redesigned_landing.png') });

    // 2. Find a Lawyer (Section 11)
    console.log('2. Find a Lawyer (Section 11)...');
    await page.goto('http://localhost:3000/lawyers', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_redesigned_lawyers.png') });

    // 3. Login as Demo Client
    console.log('3. Logging in as Client...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 25000 });
    await page.waitForSelector('#demo-client-btn', { timeout: 10000 });
    await page.click('#demo-client-btn');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1500));

    // 4. Client Dashboard (Section 6: What needs my attention?)
    console.log('4. Client Dashboard...');
    await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_redesigned_dashboard.png') });

    // 5. My Cases Listing
    console.log('5. My Cases Listing...');
    await page.goto('http://localhost:3000/cases', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_redesigned_cases_list.png') });

    // 6. Case Detail (Section 7: What should I do?)
    console.log('6. Case Detail Page...');
    const caseLink = await page.$('a[href^="/cases/"]');
    if (caseLink) {
      await caseLink.click();
      await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 25000 });
      await new Promise(r => setTimeout(r, 1500));
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_redesigned_case_detail.png') });

      // Click "What should I do?" button
      console.log('6b. Clicking [ What should I do? ]...');
      const buttons = await page.$$('button');
      for (const btn of buttons) {
        const text = await (await btn.getProperty('textContent')).jsonValue();
        if (text && text.includes('What should I do?')) {
          await btn.click();
          await new Promise(r => setTimeout(r, 600));
          await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05b_case_guidance_revealed.png') });
          break;
        }
      }
    }

    // 7. Documents (Section 9: Explain this document)
    console.log('7. Documents Page...');
    await page.goto('http://localhost:3000/documents', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_redesigned_documents.png') });

    // Click "Understand This" or "Explain this document"
    const docButtons = await page.$$('button');
    for (const btn of docButtons) {
      const text = await (await btn.getProperty('textContent')).jsonValue();
      if (text && (text.includes('Understand This') || text.includes('Explain this document'))) {
        await btn.click();
        await new Promise(r => setTimeout(r, 600));
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06b_explain_document_modal.png') });
        break;
      }
    }

    // 8. Hearings (Section 10: Action-oriented WHEN/WHERE/WHY/WHAT TO DO)
    console.log('8. Hearings Calendar Page...');
    await page.goto('http://localhost:3000/calendar', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_redesigned_hearings.png') });

    // 9. Mobile Responsive View (Section 16)
    console.log('9. Mobile Viewport (375x812)...');
    await page.setViewport({ width: 375, height: 812, isMobile: true });
    await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08_mobile_dashboard.png') });

    console.log('All verification screenshots captured successfully!');
  } catch (err) {
    console.error('Screenshot capture encountered an error:', err);
  } finally {
    await browser.close();
  }
}

run();
