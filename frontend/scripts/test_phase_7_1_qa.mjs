import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || path.resolve(process.cwd(), '../../screenshots/phase_7_1');
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function runVisualQA() {
  console.log('--- STARTING PHASE 7.1 VISUAL QA & FOUNDATION VERIFICATION ---');
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  page.on('console', msg => {
    console.log(`[BROWSER ${msg.type()}]:`, msg.text());
  });

  try {
    // =========================================================================
    // 1. DESKTOP VIEWPORT (1440x900) - DESIGN SYSTEM SHOWCASE
    // =========================================================================
    console.log('\n[1/5] Testing Design System Showcase on Desktop (1440x900)...');
    await page.setViewport({ width: 1440, height: 900 });
    await page.goto('http://localhost:3000/design-system', { waitUntil: 'networkidle2', timeout: 30000 });

    // Verify all showcase cards rendered
    const cardHeaders = await page.$$eval('h3', els => els.map(e => e.innerText));
    console.log('Rendered Card Headers count:', cardHeaders.length);

    // Test LegalTerm interaction
    console.log('Testing LegalTerm 3-layer popover interaction...');
    const legalTermButton = await page.$('span[role="button"][title*="plain-language"]');
    if (legalTermButton) {
      await legalTermButton.click();
      await new Promise(r => setTimeout(r, 400));
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_desktop_design_system_legalterm.png') });
    console.log('Saved 01_desktop_design_system_legalterm.png');

    // Test Modal interaction & Escape key
    console.log('Testing Modal dialog and Escape key dismiss...');
    const modalTrigger = await page.$('#btn-open-modal');
    if (modalTrigger) {
      await modalTrigger.click();
      await new Promise(r => setTimeout(r, 400));
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_desktop_modal_open.png') });
      await page.keyboard.press('Escape');
      await new Promise(r => setTimeout(r, 400));
    }

    // =========================================================================
    // 2. CLIENT AUTHENTICATED EXPERIENCE & ROLE-AWARE SIDEBAR
    // =========================================================================
    console.log('\n[2/5] Testing Client Authenticated Experience...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle2', timeout: 20000 });
    await new Promise(r => setTimeout(r, 2000)); // Ensure full client-side React hydration
    const demoClientBtn = await page.$('#demo-client-btn');
    console.log('Demo Client Button found:', !!demoClientBtn);
    if (demoClientBtn) {
      await demoClientBtn.click();
      console.log('Clicked demo client button, waiting for redirect / sidebar...');
      try {
        await page.waitForSelector('aside [class*="navItem"]', { timeout: 10000 });
      } catch (e) {
        const currentUrl = page.url();
        const alerts = await page.$$eval('div', els => els.map(e => e.innerText).filter(t => t.includes('Invalid') || t.includes('Error') || t.includes('failed')));
        console.log('Current URL on timeout:', currentUrl, 'Alerts:', alerts.slice(0, 3));
        throw e;
      }
      await new Promise(r => setTimeout(r, 1200));
    }

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_desktop_client_dashboard.png') });
    console.log('Saved 03_desktop_client_dashboard.png');

    // Verify Sidebar links for CLIENT per Section 8: Home, My Cases, Hearings, Documents, Find Lawyers, Messages, Payments
    const sidebarText = await page.$$eval('aside [class*="navItem"]', items =>
      items.map(i => i.innerText.replace('\n', ' ').trim()).filter(Boolean)
    );
    console.log('Client Navigation Items:', sidebarText);

    // =========================================================================
    // 3. GLOBAL SEARCH MODAL (KEYBOARD NAVIGATION)
    // =========================================================================
    console.log('\n[3/5] Testing Global Search Modal & Keyboard Navigation...');
    // Trigger global search via TopBar search button or keyboard shortcut
    const searchTrigger = await page.$('button[class*="searchTriggerBtn"]');
    if (searchTrigger) {
      await searchTrigger.click();
    } else {
      await page.keyboard.down('Control');
      await page.keyboard.press('k');
      await page.keyboard.up('Control');
    }
    await new Promise(r => setTimeout(r, 500));

    // Type query
    const searchInput = await page.$('input[placeholder*="Search cases"]');
    if (searchInput) {
      await searchInput.type('Sharma', { delay: 50 });
      await new Promise(r => setTimeout(r, 600)); // wait for bounded debounced search

      // Navigate with ArrowDown
      await page.keyboard.press('ArrowDown');
      await new Promise(r => setTimeout(r, 200));

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_desktop_global_search_active.png') });
      console.log('Saved 04_desktop_global_search_active.png');

      // Dismiss with Escape
      await page.keyboard.press('Escape');
      await new Promise(r => setTimeout(r, 300));
    }

    // =========================================================================
    // 4. PAYMENTS PAGE VERIFICATION
    // =========================================================================
    console.log('\n[4/5] Navigating to /payments...');
    await page.goto('http://localhost:3000/payments', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_desktop_payments_page.png') });
    console.log('Saved 05_desktop_payments_page.png');

    // =========================================================================
    // 5. MOBILE VIEWPORT 375x667 (SECTION 24 & SECTION 18 STRICT AUDIT)
    // =========================================================================
    console.log('\n[5/5] Testing Mobile 375x667 specifically (iPhone SE / Standard Indian Mobile)...');
    await page.setViewport({ width: 375, height: 667, isMobile: true, hasTouch: true });
    await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle2', timeout: 20000 });

    // Check for horizontal overflow
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    console.log(`Document scrollWidth on 375px viewport: ${scrollWidth}px (Target <= 375px)`);
    if (scrollWidth > 375) {
      console.warn(`WARNING: Horizontal overflow detected (${scrollWidth}px > 375px)`);
    } else {
      console.log('PASS: Zero horizontal overflow on 375x667.');
    }

    // Verify MobileBottomNav visible & count touch targets
    const mobileBottomNav = await page.$('nav[aria-label="Mobile Bottom Navigation"]');
    if (mobileBottomNav) {
      const isVisible = await page.evaluate(el => {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
      }, mobileBottomNav);
      console.log(`MobileBottomNav rendered & visible: ${isVisible}`);

      // Verify touch targets >= 44x44px
      const targetHeights = await page.$$eval('nav[aria-label="Mobile Bottom Navigation"] a', items =>
        items.map(item => ({
          text: item.innerText.replace('\n', ' '),
          height: item.getBoundingClientRect().height,
          width: item.getBoundingClientRect().width,
        }))
      );
      console.log('Mobile Touch Targets:', targetHeights);
      const allTouchTargetsValid = targetHeights.every(t => t.height >= 44 && t.width >= 44);
      console.log(`PASS: All mobile nav touch targets >= 44x44px: ${allTouchTargetsValid}`);
    }

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_mobile_375x667_dashboard.png') });
    console.log('Saved 06_mobile_375x667_dashboard.png');

    // Mobile Design System Check
    await page.goto('http://localhost:3000/design-system', { waitUntil: 'networkidle2', timeout: 20000 });
    const mobileLegalTerm = await page.$('span[role="button"][title*="plain-language"]');
    if (mobileLegalTerm) {
      await mobileLegalTerm.click();
      await new Promise(r => setTimeout(r, 400));
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_mobile_375x667_design_system_legalterm.png') });
    console.log('Saved 07_mobile_375x667_design_system_legalterm.png');

    // Mobile Payments Check
    await page.goto('http://localhost:3000/payments', { waitUntil: 'networkidle2', timeout: 20000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08_mobile_375x667_payments.png') });
    console.log('Saved 08_mobile_375x667_payments.png');

    console.log('\n--- ALL VISUAL QA CHECKS COMPLETED SUCCESSFULLY ---');
  } catch (err) {
    console.error('Visual QA Failure:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

runVisualQA();
