const {chromium}=require('C:/Users/bulls/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:820,height:1000}});
  const errors=[],sent=[];let replies=[],pollFailure=0,paginate=false,reads=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://api.pushbullet.com/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   assert.equal(req.headers()['access-token'],'fake-test-token');
   if(url.pathname.endsWith('/users/me'))return route.fulfill({json:{iden:'user',name:'Compte test',email:'compte@example.invalid'}});
   if(url.pathname.endsWith('/devices'))return route.fulfill({json:{devices:[{active:true,iden:'phone',nickname:'Téléphone test'}]}});
   assert.equal(url.pathname,'/v2/pushes');
   if(req.method()==='POST'){sent.push(req.postDataJSON());return route.fulfill({json:{iden:'notification-'+sent.length,created:1000}});}
   assert.equal(req.method(),'GET');reads++;
   assert.equal(url.searchParams.get('modified_after'),'999');assert.equal(url.searchParams.get('active'),'true');
   if(pollFailure)return route.fulfill({status:pollFailure,json:{error:{}}});
   if(paginate&&!url.searchParams.has('cursor'))return route.fulfill({json:{pushes:[],cursor:'suite'}});
   return route.fulfill({json:{pushes:replies}});
  });
  await page.clock.install();await page.goto('file:///E:/RJA/ps2/pushbullet-boutons.html');
  await page.locator('#token').fill('fake-test-token');await page.locator('#connect').click();
  await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('Compte vérifié'));
  const lit=page.locator('[data-device="lit"]'),sdb=page.locator('[data-device="sdb"]');
  async function press(box){await box.locator('.press').click();await page.waitForFunction(id=>document.querySelector(`[data-device="${id}"] .status`).textContent==='Accepté par Pushbullet',await box.getAttribute('data-device'));return sent.at(-1).body.match(/\nOK ([A-F0-9]{8})\n/)[1];}
  function reply(code,extra={}){return{iden:'reply-'+code,type:'note',active:true,body:'OK '+code,created:1002,modified:1002,direction:'self',sender_iden:'user',receiver_iden:'user',sender_name:'Depuis le téléphone',...extra};}
  async function tick(ms=6000){await page.clock.runFor(ms);await page.waitForTimeout(60);}
  const first=await press(lit);
  replies=[reply('FFFFFFFF'),reply(first,{sender_iden:'inconnu'}),reply(first,{receiver_iden:'autre'}),reply(first,{created:998}),reply(first,{active:false}),reply(first,{body:'Demande lue',dismissed:true})];
  await tick();assert.notEqual(await lit.locator('.status').innerText(),'Prise en charge confirmée');assert.ok(reads>0,JSON.stringify({errors,detail:await lit.locator('.detail').innerText(),ack:await page.locator('#ack-status').innerText()}));
  // Only the matching request becomes green. A valid reply can be on page two.
  const second=await press(sdb);assert.notEqual(first,second);paginate=true;replies=[reply(second)];
  await tick();await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .status').textContent==='Prise en charge confirmée');
  assert.notEqual(await lit.locator('.status').innerText(),'Prise en charge confirmée');
  paginate=false;replies=[reply(first)];await tick();await page.waitForFunction(()=>document.querySelector('[data-device="lit"] .status').textContent==='Prise en charge confirmée');
  const readsAfter=reads;await tick(15000);assert.equal(reads,readsAfter);
  // Local cancellation remains blue and cannot be mistaken for remote confirmation.
  replies=[];await press(lit);await page.locator('#messages .notice').first().getByRole('button',{name:'Terminer l’essai sur ce PC'}).click();
  assert.match(await lit.locator('.detail').innerText(),/sans confirmation/);assert.equal(await lit.locator('.lamp').evaluate(e=>e.style.getPropertyValue('--led')),'var(--blue)');
  // A distinct recipient must send an incoming response from the chosen account.
  await page.locator('#target').selectOption('email');await page.locator('#email').fill('proche@example.invalid');
  await page.locator('#retries').selectOption('120');const third=await press(lit);
  replies=[reply(third),reply(third,{direction:'incoming',sender_iden:'autre',sender_email:'autre@example.invalid'})];
  await tick();assert.notEqual(await lit.locator('.status').innerText(),'Prise en charge confirmée');
  pollFailure=429;await tick();await page.waitForFunction(()=>document.querySelector('#ack-status').textContent.includes('indisponible'));
  assert.notEqual(await lit.locator('.status').innerText(),'Prise en charge confirmée');
  pollFailure=0;replies=[reply(third,{direction:'incoming',sender_iden:'proche',sender_email:'proche@example.invalid',sender_name:'Le proche'})];
  await tick(31000);await page.waitForFunction(()=>document.querySelector('[data-device="lit"] .status').textContent==='Prise en charge confirmée');
  assert.match(await lit.locator('.detail').innerText(),/Le proche/);const sentAfterAck=sent.length;await tick(241000);assert.equal(sent.length,sentAfterAck);
  // Replies sent while the simulated box is unplugged are recovered on replugging.
  await page.locator('#target').selectOption('phone');await page.locator('#retries').selectOption('0');replies=[];const fourth=await press(sdb);
  await sdb.locator('.power').uncheck();replies=[reply(fourth)];await tick();assert.match(await sdb.locator('.status').innerText(),/Hors tension/);
  await sdb.locator('.power').check();await tick();await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .status').textContent==='Prise en charge confirmée');
  // A plain OK confirms all pending boxes, with the sender still checked.
  await page.locator('#retries').selectOption('120');replies=[];
  const globalLit=await press(lit);await press(sdb);
  replies=[reply(globalLit,{body:'OK',sender_iden:'inconnu'}),reply(globalLit,{body:'OK',created:999}),reply(globalLit,{body:'okay'}),reply(globalLit,{body:'OK',receiver_iden:'autre'})];
  await tick();assert.notEqual(await lit.locator('.status').innerText(),'Prise en charge confirmée');assert.notEqual(await sdb.locator('.status').innerText(),'Prise en charge confirmée');
  const globalReply=reply(globalLit,{body:'  oK\n'});replies=[globalReply];
  await tick();await page.waitForFunction(()=>[...document.querySelectorAll('.status')].every(el=>el.textContent==='Prise en charge confirmée'));
  const sentAfterGlobal=sent.length;await tick(241000);assert.equal(sent.length,sentAfterGlobal);
  // The same plain reply cannot confirm a future request, even if a mock
  // timestamp is identical. All three common case variants are accepted.
  for(const text of ['OK','ok','Ok']){
    replies=[];const code=await press(lit);replies=[globalReply];await tick();
    assert.notEqual(await lit.locator('.status').innerText(),'Prise en charge confirmée');
    replies=[reply(code,{body:text})];await tick();await page.waitForFunction(()=>document.querySelector('[data-device="lit"] .status').textContent==='Prise en charge confirmée');
  }
  // A relative authorized for one current request can confirm the whole
  // household, including another request addressed to a different relative.
  replies=[];await page.locator('#target').selectOption('email');await page.locator('#email').fill('proche-a@example.invalid');const grouped=await press(lit);
  await page.locator('#email').fill('proche-b@example.invalid');await press(sdb);
  await lit.locator('.power').uncheck();
  replies=[reply(grouped,{body:'ok',direction:'incoming',sender_iden:'proche-a',sender_email:'proche-a@example.invalid'})];
  await tick();await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .status').textContent==='Prise en charge confirmée');
  assert.match(await lit.locator('.status').innerText(),/Hors tension/);
  await lit.locator('.power').check();assert.equal(await lit.locator('.status').innerText(),'Prise en charge confirmée');
  await page.screenshot({path:'E:/RJA/ps2/tests/pushbullet-confirmation-preview.png',fullPage:true});
  await page.locator('#disconnect').click();const lastReads=reads;await tick(15000);assert.equal(reads,lastReads);assert.deepEqual(errors,[]);
  console.log('PASS : OK/ok/Ok global, confirmation simultanée, proches différents, rejet des expéditeurs inconnus et anciennes réponses, absence de réutilisation, codes individuels, pagination, panne/reprise, arrêt des relances et coupure/rebranchement. Aucun envoi réel.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
