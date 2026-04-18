import { chromium } from 'playwright';

const SIZES = [
  { name: 'full',   width: 1920, height: 1080 },
  { name: 'half',   width: 960,  height: 1080 },
  { name: 'mobile', width: 375,  height: 812 },
];

const TABS = ['Board', 'Parts List', 'Assembly', 'About'];

async function main() {
  const browser = await chromium.launch();
  const dir = '/tmp/obb-screenshots';

  for (const size of SIZES) {
    const context = await browser.newContext({
      viewport: { width: size.width, height: size.height },
    });
    const page = await context.newPage();
    await page.goto('http://localhost:1423/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);

    for (const tab of TABS) {
      try {
        await page.click(`button:has-text("${tab}")`, { force: true });
      } catch { continue; }
      await page.waitForTimeout(1500);

      const slug = tab.toLowerCase().replace(/\s+/g, '-');
      await page.screenshot({ path: `${dir}/${size.name}-${slug}.png` });
      console.log(`  ${size.name}-${slug}.png`);

      // Board tab: try selecting a component
      if (tab === 'Board') {
        try {
          const canvas = page.locator('canvas');
          if (await canvas.count() > 0) {
            const box = await canvas.boundingBox();
            if (box) {
              await page.mouse.click(box.x + box.width * 0.4, box.y + box.height * 0.45);
              await page.waitForTimeout(500);
              await page.screenshot({ path: `${dir}/${size.name}-board-selected.png` });
              console.log(`  ${size.name}-board-selected.png`);
            }
          }
        } catch (e) { console.log(`  skip board-selected: ${e.message.slice(0,60)}`); }
      }

      // Parts List: try selecting a row
      if (tab === 'Parts List') {
        try {
          const rows = page.locator('tbody tr');
          if (await rows.count() > 0) {
            await rows.first().click({ force: true, timeout: 5000 });
            await page.waitForTimeout(500);
            await page.screenshot({ path: `${dir}/${size.name}-parts-selected.png` });
            console.log(`  ${size.name}-parts-selected.png`);
          }
        } catch (e) { console.log(`  skip parts-selected: ${e.message.slice(0,60)}`); }
      }

      // Assembly: try clicking a step
      if (tab === 'Assembly') {
        try {
          // Use JavaScript click to bypass viewport/overlap issues
          await page.evaluate(() => {
            const cards = document.querySelectorAll('[style*="cursor: pointer"]');
            // Click the second card (first step with component refs)
            if (cards.length > 1) (cards[1]).click();
          });
          await page.waitForTimeout(1500);
          await page.screenshot({ path: `${dir}/${size.name}-assembly-step.png` });
          console.log(`  ${size.name}-assembly-step.png`);
        } catch (e) { console.log(`  skip assembly-step: ${e.message.slice(0,60)}`); }
      }
    }

    // About tab scrolled to middle
    try {
      await page.click(`button:has-text("About")`, { force: true });
      await page.waitForTimeout(500);
      await page.evaluate(() => {
        const main = document.querySelector('main');
        if (main) main.scrollTop = main.scrollHeight / 2;
      });
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${dir}/${size.name}-about-scrolled.png` });
      console.log(`  ${size.name}-about-scrolled.png`);
    } catch (e) { console.log(`  skip about-scrolled: ${e.message.slice(0,60)}`); }

    await context.close();
  }

  await browser.close();
  console.log(`\nDone — screenshots in ${dir}/`);
}

main().catch(e => { console.error(e); process.exit(1); });
