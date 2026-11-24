/* Record the real release-generated report and public benchmark page.
 * Terminal scene contains actual command output, captured before recording.
 * No model calls, modified report HTML, or synthetic performance claims.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const out = process.env.CTD_DEMO_OUTPUT;
const base = process.env.CTD_DEMO_URL || 'http://127.0.0.1:8765';
if (!out) throw new Error('CTD_DEMO_OUTPUT is required');

async function main() {
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({headless:true});
  let context;
  try {
    context = await browser.newContext({
      viewport:{width:1280,height:800},
      deviceScaleFactor:1,
      recordVideo:{dir:path.join(out,'recording'),size:{width:1280,height:800}},
    });
    const unexpected=[];
    await context.route('**/*',route=>{
      if(new URL(route.request().url()).origin!==new URL(base).origin){
        unexpected.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',error=>errors.push(String(error)));
    page.on('response',response=>{if(response.status()>=400)errors.push(response.url()+': '+response.status());});
    const video=page.video();
    // Start with the actual product and its local use case.
    await page.goto(base+'/index.html',{waitUntil:'networkidle'});
    assert.ok(await page.getByRole('heading',{level:1}).isVisible());
    await page.waitForTimeout(4500);
    // Captured command transcript, clearly marked; not a timed installation.
    await page.goto(base+'/release-transcript.html',{waitUntil:'networkidle'});
    assert.ok((await page.locator('pre').innerText()).includes('cost-to-done demo --output demo.html'));
    assert.ok((await page.locator('pre').innerText()).includes('Synthetic demonstration'));
    await page.waitForTimeout(6500);
    // Real report produced by the immutable alpha wheel, not a screenshot mockup.
    await page.goto(base+'/demo.html',{waitUntil:'networkidle'});
    assert.ok((await page.locator('.notice').innerText()).includes('SYNTHETIC DATA'));
    assert.equal(await page.locator('tbody tr').count(),5);
    await page.locator('.section-head').scrollIntoViewIfNeeded();
    await page.waitForTimeout(6500);
    await page.locator('.method').scrollIntoViewIfNeeded();
    await page.waitForTimeout(3500);
    // Use the published external analysis as a separate, attributed example.
    await page.goto(base+'/terminal-bench.html',{waitUntil:'networkidle'});
    assert.ok((await page.locator('.notice').innerText()).includes('Third-party reported aggregate data'));
    await page.waitForTimeout(4500);
    await page.getByRole('heading',{name:'Three configurations, one metric'}).scrollIntoViewIfNeeded();
    await page.waitForTimeout(6500);
    await page.goto(base+'/index.html#use',{waitUntil:'networkidle'});
    await page.waitForTimeout(3500);
    assert.deepEqual(errors,[]);
    assert.deepEqual(unexpected,[]);
    await page.close();
    await context.close();
    context=null;
    await video.saveAs(path.join(out,'cost-to-done-v0.1.0-demo.webm'));
    console.log('Recorded actual release report, command transcript and attributed external analysis.');
  } finally {
    if(context)await context.close();
    await browser.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
