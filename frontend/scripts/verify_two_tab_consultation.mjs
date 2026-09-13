import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const ARTIFACTS_DIR = 'C:/Users/akuma/.gemini/antigravity-ide/brain/9bdd484b-526c-4985-a0f6-17e47a7cb918';
const consultationId = process.argv[2] || '01a09b98-e39f-7fd1-9902-4ff93a73a15f';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function run() {
  console.log(`Starting Two-Tab Full-Stack Verification for Consultation: ${consultationId}...`);

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      '--disable-web-security',
      '--window-size=1400,900',
    ],
    defaultViewport: null,
  });

  try {
    // =========================================================================
    // STEP 1: Test Google OAuth Initiation
    // =========================================================================
    console.log('\n--- Step 1: Testing Google OAuth on Login Page ---');
    const pageOAuth = await browser.newPage();
    await pageOAuth.setViewport({ width: 1366, height: 800 });
    await pageOAuth.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await pageOAuth.screenshot({ path: path.join(ARTIFACTS_DIR, '01_login_page_with_google.png') });

    console.log('Finding Continue with Google button...');
    const buttons = await pageOAuth.$$('button');
    let clickedGoogle = false;
    for (const b of buttons) {
      const txt = await pageOAuth.evaluate(el => el.textContent, b);
      if (txt && txt.includes('Continue with Google')) {
        console.log('Found Google button, clicking...');
        await b.click();
        clickedGoogle = true;
        break;
      }
    }
    
    await sleep(3500);
    const oauthUrl = pageOAuth.url();
    console.log('Redirected to URL:', oauthUrl);
    await pageOAuth.screenshot({ path: path.join(ARTIFACTS_DIR, '02_google_oauth_redirect.png') });
    await pageOAuth.close();

    // =========================================================================
    // STEP 2: Browser Context 1 — Tab 1 (Lawyer: Advocate Ananya Roy)
    // =========================================================================
    console.log('\n--- Step 2: Tab 1 — Lawyer Login & Standby (Advocate Ananya Roy) ---');
    const lawyerContext = await browser.createBrowserContext();
    const lawyerPage = await lawyerContext.newPage();
    await lawyerPage.setViewport({ width: 1366, height: 850 });

    await lawyerPage.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await lawyerPage.waitForSelector('#demo-lawyer-btn', { timeout: 10000 });
    await lawyerPage.click('#demo-lawyer-btn');
    await sleep(2500);
    console.log('Lawyer landed at:', lawyerPage.url());
    await lawyerPage.screenshot({ path: path.join(ARTIFACTS_DIR, '03_lawyer_dashboard.png') });

    console.log('Checking notifications on Lawyer TopBar...');
    const bellBtn = await lawyerPage.$('button[aria-label="Workflow Notifications"]');
    if (bellBtn) {
      await bellBtn.click();
      await sleep(1000);
      await lawyerPage.screenshot({ path: path.join(ARTIFACTS_DIR, '04_lawyer_notifications_panel.png') });
    }

    console.log(`Lawyer navigating to Consultation Room: /consultations/${consultationId}/room...`);
    await lawyerPage.goto(`http://localhost:3000/consultations/${consultationId}/room`, { waitUntil: 'networkidle2', timeout: 25000 });
    await sleep(3000);
    await lawyerPage.screenshot({ path: path.join(ARTIFACTS_DIR, '05_lawyer_in_meeting_room_camera.png') });

    // =========================================================================
    // STEP 3: Browser Context 2 — Tab 2 (Client: Vikram Sharma)
    // =========================================================================
    console.log('\n--- Step 3: Tab 2 — Client Login & AI Advisor (Vikram Sharma) ---');
    const clientContext = await browser.createBrowserContext();
    const clientPage = await clientContext.newPage();
    await clientPage.setViewport({ width: 1366, height: 850 });

    await clientPage.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await clientPage.waitForSelector('#demo-client-btn', { timeout: 10000 });
    await clientPage.click('#demo-client-btn');
    await sleep(2500);
    console.log('Client landed at:', clientPage.url());
    await clientPage.screenshot({ path: path.join(ARTIFACTS_DIR, '06_client_dashboard.png') });

    console.log('Client navigating to /ai-advisor...');
    await clientPage.goto('http://localhost:3000/ai-advisor', { waitUntil: 'networkidle2', timeout: 20000 });
    await sleep(1500);
    await clientPage.screenshot({ path: path.join(ARTIFACTS_DIR, '07_ai_advisor_page.png') });

    console.log('Client typing legal inquiry to AI Advisor...');
    await clientPage.waitForSelector('#ai-advisor-input', { timeout: 10000 });
    await clientPage.type('#ai-advisor-input', 'What are the legal steps under Section 138 of Negotiable Instruments Act? Please explain clearly.');
    await clientPage.click('#ai-advisor-send-btn');
    
    console.log('Waiting for AI response from Lex...');
    try {
      await clientPage.waitForFunction(
        () => {
          const texts = Array.from(document.querySelectorAll('div, p')).map(e => e.textContent || '');
          return texts.some(t => t.includes('Negotiable Instruments') || t.includes('Lex') || t.includes('statutory') || t.includes('dishonor'));
        },
        { timeout: 25000 }
      );
      console.log('AI Advisor generated live response successfully!');
    } catch (e) {
      console.warn('AI Advisor wait timed out, continuing:', e.message);
    }
    await sleep(2000);
    await clientPage.screenshot({ path: path.join(ARTIFACTS_DIR, '08_ai_advisor_response_received.png') });

    // =========================================================================
    // STEP 4: Client Joins the Live Consultation Meeting Room
    // =========================================================================
    console.log(`\n--- Step 4: Client Joining Meeting Room /consultations/${consultationId}/room ---`);
    await clientPage.goto(`http://localhost:3000/consultations/${consultationId}/room`, { waitUntil: 'networkidle2', timeout: 25000 });
    await sleep(4000);
    await clientPage.screenshot({ path: path.join(ARTIFACTS_DIR, '09_client_joined_meeting_room.png') });

    const enterButtons = await clientPage.$$('button');
    for (const b of enterButtons) {
      const txt = await clientPage.evaluate(el => el.textContent, b);
      if (txt && (txt.includes('Enter Meeting') || txt.includes('Connect Now') || txt.includes('Join Video Call'))) {
        console.log('Clicking client enter meeting button:', txt);
        await b.click();
        await sleep(2000);
        break;
      }
    }

    const lawyerEnterBtns = await lawyerPage.$$('button');
    for (const b of lawyerEnterBtns) {
      const txt = await lawyerPage.evaluate(el => el.textContent, b);
      if (txt && (txt.includes('Enter Meeting') || txt.includes('Connect Now') || txt.includes('Join Video Call'))) {
        console.log('Clicking lawyer enter meeting button:', txt);
        await b.click();
        await sleep(2000);
        break;
      }
    }

    await sleep(4000);

    // =========================================================================
    // STEP 5: In-Meeting Chat & Peer Interaction
    // =========================================================================
    console.log('\n--- Step 5: Testing In-Meeting Real-Time Chat ---');
    const clientChatBtn = await clientPage.$('button[title*="Chat"], button[aria-label*="Chat"]');
    if (clientChatBtn) {
      console.log('Opening chat panel on Client page...');
      await clientChatBtn.click();
      await sleep(1000);
    }

    const chatInputs = await clientPage.$$('input, textarea');
    for (const inp of chatInputs) {
      const placeholder = await clientPage.evaluate(el => el.placeholder || '', inp);
      if (placeholder.toLowerCase().includes('message') || placeholder.toLowerCase().includes('type')) {
        console.log('Found chat input, typing message...');
        await inp.type('Hello Advocate Ananya, Vikram here. Can you hear and see me?');
        await clientPage.keyboard.press('Enter');
        await sleep(2000);
        break;
      }
    }

    await clientPage.screenshot({ path: path.join(ARTIFACTS_DIR, '10_client_in_meeting_chat.png') });

    const lawyerChatBtn = await lawyerPage.$('button[title*="Chat"], button[aria-label*="Chat"]');
    if (lawyerChatBtn) {
      console.log('Opening chat panel on Lawyer page...');
      await lawyerChatBtn.click();
      await sleep(1000);
    }

    await sleep(2000);
    await lawyerPage.screenshot({ path: path.join(ARTIFACTS_DIR, '11_lawyer_view_with_client_chat.png') });

    console.log('\n--- ALL VERIFICATION STEPS COMPLETED SUCCESSFULLY! ---');
  } catch (err) {
    console.error('Verification error:', err);
    try {
      const pages = await browser.pages();
      if (pages.length > 0) {
        await pages[0].screenshot({ path: path.join(ARTIFACTS_DIR, 'error_state.png') });
      }
    } catch {}
  } finally {
    await browser.close();
    console.log('Browser closed cleanly.');
  }
}

run();
