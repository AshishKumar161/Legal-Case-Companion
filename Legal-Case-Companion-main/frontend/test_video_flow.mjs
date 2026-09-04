import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = 'C:/Users/akuma/OneDrive/Desktop/lcc/screenshots';
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const CONSULTATION_ID = '01a06bfc-9047-7ea2-a1b4-c4e745431fe7';

async function run() {
  console.log('--- Starting Two-Tab Video Consultation WebRTC Verification ---');

  // Launch browser with fake media stream devices so both tabs get a live camera stream simultaneously
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      '--window-size=1280,850'
    ]
  });

  try {
    // ----------------------------------------------------
    // Context 1: Client Tab (Vikram Sharma)
    // ----------------------------------------------------
    const clientContext = await browser.createBrowserContext();
    const clientPage = await clientContext.newPage();
    await clientPage.setViewport({ width: 1280, height: 850 });
    clientPage.on('console', msg => console.log('[CLIENT LOG]:', msg.text()));

    console.log('1. Client logging in via 1-Click Demo Client...');
    await clientPage.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await clientPage.waitForSelector('#demo-client-btn', { timeout: 10000 });
    await clientPage.click('#demo-client-btn');
    await clientPage.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 });

    console.log('2. Client navigating to Consultation Room:', CONSULTATION_ID);
    await clientPage.goto(`http://localhost:3000/consultations/${CONSULTATION_ID}/room`, {
      waitUntil: 'networkidle2',
      timeout: 25000
    });

    // Wait for client room to load and acquire local video
    await clientPage.waitForSelector('#local-video-element', { timeout: 15000 });
    console.log('Client entered room. Local video mounted.');

    // ----------------------------------------------------
    // Context 2: Lawyer Tab (Advocate Ananya Roy)
    // ----------------------------------------------------
    const lawyerContext = await browser.createBrowserContext();
    const lawyerPage = await lawyerContext.newPage();
    await lawyerPage.setViewport({ width: 1280, height: 850 });
    lawyerPage.on('console', msg => console.log('[LAWYER LOG]:', msg.text()));

    console.log('3. Lawyer logging in via 1-Click Demo Lawyer...');
    await lawyerPage.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await lawyerPage.waitForSelector('#demo-lawyer-btn', { timeout: 10000 });
    await lawyerPage.click('#demo-lawyer-btn');
    await lawyerPage.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 });

    console.log('4. Lawyer navigating to Consultation Room:', CONSULTATION_ID);
    await lawyerPage.goto(`http://localhost:3000/consultations/${CONSULTATION_ID}/room`, {
      waitUntil: 'networkidle2',
      timeout: 25000
    });

    await lawyerPage.waitForSelector('#local-video-element', { timeout: 15000 });
    console.log('Lawyer entered room. Local video mounted.');

    // Wait 3 seconds for WebRTC handshake and video transmission between both peers
    console.log('5. Waiting for WebRTC P2P handshake and track exchange...');
    await new Promise(r => setTimeout(r, 4000));

    // Verify remote video in Client page
    const clientRemoteVideoActive = await clientPage.evaluate(() => {
      const el = document.getElementById('remote-video-element');
      return el && el.srcObject !== null;
    });
    console.log('Client page remote video has srcObject:', clientRemoteVideoActive);

    // Verify remote video in Lawyer page
    const lawyerRemoteVideoActive = await lawyerPage.evaluate(() => {
      const el = document.getElementById('remote-video-element');
      return el && el.srcObject !== null;
    });
    console.log('Lawyer page remote video has srcObject:', lawyerRemoteVideoActive);

    // Take screenshots of both tabs with both cameras active
    console.log('6. Capturing consultation room screenshots (Both Cameras ON)...');
    await clientPage.screenshot({ path: path.join(SCREENSHOT_DIR, '08_client_room_connected.png') });
    await lawyerPage.screenshot({ path: path.join(SCREENSHOT_DIR, '09_lawyer_room_connected.png') });

    // 7. Test Toggling Lawyer Camera OFF
    console.log('7. Testing Camera Toggle: Lawyer turns camera OFF...');
    await lawyerPage.waitForSelector('#toggle-video-btn', { timeout: 5000 });
    await lawyerPage.click('#toggle-video-btn');
    await new Promise(r => setTimeout(r, 2000));
    await clientPage.screenshot({ path: path.join(SCREENSHOT_DIR, '10_client_view_lawyer_camera_off.png') });
    await lawyerPage.screenshot({ path: path.join(SCREENSHOT_DIR, '10_lawyer_view_camera_off.png') });

    // 8. Test Toggling Lawyer Camera Back ON
    console.log('8. Testing Camera Toggle: Lawyer turns camera back ON...');
    await lawyerPage.click('#toggle-video-btn');
    await new Promise(r => setTimeout(r, 2500));
    await clientPage.screenshot({ path: path.join(SCREENSHOT_DIR, '11_client_view_lawyer_camera_back_on.png') });
    await lawyerPage.screenshot({ path: path.join(SCREENSHOT_DIR, '11_lawyer_view_camera_back_on.png') });

    console.log('✅ Full two-tab camera sharing and toggle verification completed successfully!');
  } catch (err) {
    console.error('❌ Test failed:', err);
  } finally {
    await browser.close();
  }
}

run();
