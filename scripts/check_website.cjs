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
      for (const file of ['index.html','calculator.html','report.html','terminal-bench.html','deepswe.html']) {
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(String(error)));
        page.on('response', response => { if(response.status()>=400) errors.push(response.url()+': '+response.status()); });
        await page.goto(base+'/'+file, {waitUntil:'networkidle'});
        assert.equal(await page.locator('h1').count(),1);
        const fonts = await page.evaluate(async () => {
          const loaded = [];
          for(const [weight, family] of [[400,'IBM Plex Sans'],[500,'IBM Plex Sans'],[600,'IBM Plex Sans'],[700,'IBM Plex Sans'],[400,'IBM Plex Mono']]){
            const faces = await document.fonts.load(weight+' 16px "'+family+'"','Cost to Done 0123456789');
            loaded.push(faces.length>0 && faces.every(face=>face.status==='loaded'));
          }
          await document.fonts.ready;
          return loaded;
        });
        assert.deepEqual(fonts,[true,true,true,true,true],file+' missing self-hosted Plex fonts');
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
        assert.ok(layout.font.startsWith('"IBM Plex Sans"'),file+' unexpected proportional family: '+layout.font);
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
        } else if(file==='terminal-bench.html'){
          assert.equal(await page.locator('#external-results tbody tr').count(),32);
          assert.ok((await page.locator('#external-results').innerText()).includes('$1,011.52'));
          assert.ok((await page.locator('#external-results').innerText()).includes('Undefined'));
          assert.ok((await page.locator('.notice').innerText()).includes('Third-party reported aggregate data'));
          await page.locator('#benchmark-filters').waitFor({state:'visible'});
          const visible = page.locator('#external-results tbody tr:visible');
          assert.equal(await visible.count(),32);
          await page.locator('#benchmark-query').fill('gpt-6.2');
          assert.equal(await visible.count(),2);
          await page.locator('#benchmark-cost').fill('2');
          assert.equal(await visible.count(),1);
          assert.ok((await visible.first().innerText()).includes('openai/gpt-6.2-sol'));
          await page.locator('#benchmark-success').fill('100');
          assert.equal(await visible.count(),0);
          await page.getByRole('button',{name:'Reset filters'}).click();
          assert.equal(await visible.count(),32);
          await page.locator('#benchmark-agent').selectOption('codex');
          assert.ok(await visible.count()>0 && await visible.count()<32);
          await page.getByRole('button',{name:'Copy filtered link'}).click();
          assert.equal(new URL(page.url()).searchParams.get('agent'),'codex');
          const count = await visible.count();
          await page.reload({waitUntil:'networkidle'});
          await page.locator('#benchmark-filters').waitFor({state:'visible'});
          assert.equal(await visible.count(),count);
          await page.getByRole('button',{name:'Reset filters'}).click();
          assert.equal(await visible.count(),32);
        } else if(file==='deepswe.html'){
          const response = await page.request.get(base+'/data/deepswe-recovery.json');
          assert.ok(response.ok());
          const evidence = await response.json();
          assert.equal(evidence.assignment_records,339);
          assert.equal(evidence.comparative_cost_ratio_available,false);
          const rendered = page.locator('#deepswe-outcomes tbody tr');
          assert.equal(await rendered.count(),evidence.rows.length);
          const money = value => value===null ? 'Unavailable' :
            new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(value));
          const outcomes = counts => [counts.pass,counts.fail,counts.ungraded].join(' / ');
          for(const [i,row] of evidence.rows.entries()){
            const ratio = row.reported_cost_per_final_pass;
            const cells = [row.agent,String(row.assigned_slots),outcomes(row.original_outcomes),
              outcomes(row.final_outcomes),money(row.recorded_model_spend_usd),
              ratio===null ? 'Unavailable' : money(Number(ratio.numerator_usd)/ratio.denominator)];
            assert.deepEqual(await rendered.nth(i).locator('th,td').allTextContents(),cells);
          }
          assert.ok((await page.locator('.notice').innerText()).includes('No comparative cost ranking'));
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
