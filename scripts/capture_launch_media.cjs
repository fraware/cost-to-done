/* Capture unmodified public product pages at Product Hunt gallery dimensions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

async function main() {
  const out = process.env.CTD_MEDIA_OUTPUT;
  const base = 'http://127.0.0.1:8765';
  assert.ok(out);
  fs.mkdirSync(out, { recursive:true });
  const browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1270,height:760}, deviceScaleFactor:1});
    const requests = [];
    await context.route('**/*',route=>{
      if(new URL(route.request().url()).origin !== base){
        requests.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror',e=>errors.push(String(e)));
    page.on('response',r=>{if(r.status()>=400)errors.push(r.url()+': '+r.status());});
    const images = [
      ['index.html','01-home.png', null, 'What does completed AI work'],
      ['terminal-bench.html','02-evidence.png', null, 'Third-party reported aggregate data'],
      ['calculator.html','03-calculator.png',null,'Hypothetical assumptions only'],
      ['report.html','04-report.png',null,'Synthetic data only']
    ];
    for(const [file,name,selector,expected] of images){
      await page.goto(base+'/'+file,{waitUntil:'networkidle'});
      assert.ok((await page.locator('body').innerText()).includes(expected),file);
      if(selector)await page.locator(selector).scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(out,name),animations:'disabled'});
      console.log('Captured actual interface:',name);
    }
    await page.setViewportSize({width:240,height:240});
    await page.goto(base+'/launch-media/wordmark.svg',{waitUntil:'networkidle'});
    await page.locator('svg').screenshot({path:path.join(out,'logo.png')});
    assert.deepEqual(errors,[]);
    assert.deepEqual(requests,[]);
    await context.close();
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
