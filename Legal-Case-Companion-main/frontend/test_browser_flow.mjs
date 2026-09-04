import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = 'C:/Users/akuma/OneDrive/Desktop/lcc/screenshots';
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log('Launching Chrome browser for comprehensive verification...');
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,850']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 850 });

  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', err => console.error('BROWSER ERROR:', err.message));

  try {
    // 1. Visit Landing Page
    console.log('1. Navigating to landing page http://localhost:3000...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_landing_page_updated.png') });

    // Test anchor navigation to #features
    console.log('1b. Navigating to #features anchor...');
    await page.goto('http://localhost:3000/#features', { waitUntil: 'networkidle2', timeout: 20000 });
    await new Promise(r => setTimeout(r, 800));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_features_anchor_scrolled.png') });

    // 2. Test Public Lawyer Discovery (unauthenticated)
    console.log('2. Navigating to /lawyers without authentication...');
    await page.goto('http://localhost:3000/lawyers', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.waitForFunction(() => document.body.innerText.includes('Ananya Roy') || document.body.innerText.includes('Retain Verified'), { timeout: 15000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_lawyers_public_view.png') });

    // 3. Test Unauthenticated Modal Interaction
    console.log('3. Triggering unauthenticated booking prompt...');
    const bookButtons = await page.$$('button');
    for (const btn of bookButtons) {
      const text = await (await btn.getProperty('textContent')).jsonValue();
      if (text.includes('Book Consultation') || text.includes('Book Session') || text.includes('Instant Video Call')) {
        await btn.click();
        break;
      }
    }
    await page.waitForFunction(() => document.body.innerText.includes('Sign In to Consult Counsel'), { timeout: 8000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_unauth_booking_modal.png') });

    // 4. Visit Login Page to verify 1-Click Demo Personas
    console.log('4. Navigating to /login...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.waitForSelector('#demo-client-btn', { timeout: 15000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_login_page_demo_buttons.png') });

    // 5. Test 1-Click Client Login (Vikram Sharma)
    console.log('5. Clicking 1-Click Demo Client (Vikram Sharma)...');
    await page.click('#demo-client-btn');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 });
    console.log('Client redirected to:', page.url());
    await page.waitForFunction(() => document.body.innerText.includes('Cases') || document.body.innerText.includes('Active Matters'), { timeout: 15000 });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_dashboard_client_view.png') });

    // 6. Test 1-Click Advocate Login (Adv. Ananya Roy)
    console.log('6. Navigating to /login for Advocate test...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.waitForSelector('#demo-lawyer-btn', { timeout: 15000 });
    await page.click('#demo-lawyer-btn');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 });
    console.log('Lawyer redirected to:', page.url());
    await page.waitForFunction(() => document.body.innerText.includes('Advocate Chambers') || document.body.innerText.includes('Bar Profile'), { timeout: 15000 });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_lawyer_dashboard_view.png') });

    // 7. Test 1-Click Admin Login (Platform Administrator)
    console.log('7. Navigating to /login for Admin test...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.waitForSelector('#demo-admin-btn', { timeout: 15000 });
    await page.click('#demo-admin-btn');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 });
    console.log('Admin redirected to:', page.url());
    await page.waitForFunction(() => document.body.innerText.includes('Refresh Data') || document.body.innerText.includes('Verifications'), { timeout: 15000 });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_admin_dashboard_view.png') });

    console.log('All browser verification steps completed successfully!');
  } catch (err) {
    console.error('Browser verification failed:', err);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'error_state.png') });
  } finally {
    await browser.close();
  }
}

run();
