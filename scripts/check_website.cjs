/* Browser checks for the static public website, not generated local reports. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const base = process.env.CTD_SITE_URL || 'http://127.0.0.1:8765';
const out = process.env.CTD_SCREENSHOTS || 'website-screenshots';

async function main() {
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({headless:true});
  try {
    for (const [label, viewport] of [
      ['desktop', {width:1440,height:1000}],
      ['tablet', {width:768,height:1024}],
      ['mobile', {width:390,height:844}],
      ['narrow', {width:320,height:800}],
    ]) {
      const context = await browser.newContext({viewport});
      // No external resources may be required to render the public pages.
      const unexpected = [];
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin !== new URL(base).origin) {
          unexpected.push(route.request().url()); return route.abort();
        }
        return route.continue();
      });
      for (const file of ['index.html','calculator.html','report.html']) {
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(String(error)));
        page.on('response', response => { if(response.status()>=400) errors.push(response.url()+': '+response.status()); });
        await page.goto(base+'/'+file, {waitUntil:'networkidle'});
        assert.equal(await page.locator('h1').count(),1);
        const layout = await page.evaluate(() => ({
          width:document.documentElement.scrollWidth,
          viewport:document.documentElement.clientWidth,
          italics:[...document.querySelectorAll('body *')].filter(el => getComputedStyle(el).fontStyle !== 'normal').map(el=>el.tagName),
          font:getComputedStyle(document.querySelector('h1')).fontFamily,
          bodyFont:getComputedStyle(document.body).fontFamily,
          background:getComputedStyle(document.documentElement).backgroundColor
        }));
        assert.ok(layout.width<=layout.viewport+1, file+' '+label+' horizontal overflow: '+JSON.stringify(layout));
        assert.deepEqual(layout.italics, [], file+' contains non-upright type');
        assert.equal(layout.font, layout.bodyFont, file+' inconsistent heading font');
        assert.equal(layout.background,'rgb(255, 255, 255)');
        assert.deepEqual(errors, []);
        if(file==='index.html'){
          for(const id of ['use','pilot','replay','method','repository']) assert.equal(await page.locator('#'+id).count(),1);
          assert.equal(await page.locator('#pilot table tbody tr').count(),4);
          assert.ok((await page.locator('#pilot').innerText()).includes('$0.003234'));
          assert.ok((await page.locator('.evidence-panel').innerText()).includes('3.88×'));
          await page.getByRole('link',{name:'Get started',exact:true}).click();
          assert.ok(page.url().endsWith('#use'));
          await page.evaluate(()=>window.scrollTo(0,0));
        } else if(file==='calculator.html'){
          assert.equal(await page.locator('.panel').count(),3);
          const first = page.locator('#f-0-cost');
          await first.fill('0');
          assert.ok((await page.locator('.panel').first().innerText()).includes('$0.0000'));
          await page.locator('#max').selectOption('1');
          await page.locator('#reset').click();
          assert.equal(await first.inputValue(),'0.05');
          assert.equal(await page.locator('#max').inputValue(),'3');
          assert.equal(await page.locator('.winner').count(),1);
        } else {
          assert.equal(await page.locator('tbody tr').count(),5);
          assert.ok((await page.locator('.notice').innerText()).includes('Synthetic data only'));
        }
        await page.screenshot({path:path.join(out,label+'-'+file.replace('.html','.png')),fullPage:true});
        console.log('PASS', label, file);
        await page.close();
      }
      assert.deepEqual(unexpected, []);
      await context.close();
    }
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
