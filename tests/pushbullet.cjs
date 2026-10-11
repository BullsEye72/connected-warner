const {chromium}=require('C:/Users/bulls/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:820,height:1000}});
  const errors=[],requests=[],sentAt=[];let failure=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://api.pushbullet.com/**',async route=>{
   const req=route.request();const path=new URL(req.url()).pathname;
   assert.equal(req.headers()['access-token'],'fake-test-token');
   if(path.endsWith('/users/me'))return route.fulfill({json:{iden:'user',name:'Compte de test'}});
   if(path.endsWith('/devices'))return route.fulfill({json:{devices:[{active:true,iden:'phone',nickname:'Téléphone de test',pushable:true},{active:false,iden:'removed',nickname:'Ancien appareil'}]}});
   if(path==='/v2/pushes'&&req.method()==='GET')return route.fulfill({json:{pushes:[]}});
   assert.equal(path,'/v2/pushes');assert.equal(req.method(),'POST');
   const body=req.postDataJSON();requests.push(body);sentAt.push(await page.evaluate(()=>Date.now()));
   assert.equal(body.type,'note');assert.match(body.title,/^\[TEST AIDE\]/);assert.match(body.body,/aucune intervention nécessaire/);
   return route.fulfill(failure?{status:failure,json:{error:{message:'ignored'}}}:{json:{iden:'push-'+requests.length,created:1000}});
  });
  await page.clock.install();
  await page.goto('file:///E:/RJA/ps2/pushbullet-boutons.html');
  const lit=page.locator('[data-device="lit"]'),sdb=page.locator('[data-device="sdb"]');
  assert.equal(await lit.locator('.press').isDisabled(),true);
  assert.equal(await page.locator('#retries').inputValue(),'120');
  await page.locator('#retries').selectOption('0');
  await page.locator('#token').fill('fake-test-token');await page.locator('#connect').click();
  await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('Compte vérifié'));
  assert.equal(requests.length,0);assert.equal(await page.locator('#target option').count(),3);
  await page.screenshot({path:'E:/RJA/ps2/tests/pushbullet-preview.png',fullPage:true});
  await page.locator('#target').selectOption('phone');
  await lit.locator('.press').click();
  await page.waitForFunction(()=>document.querySelector('[data-device="lit"] .status').textContent==='Accepté par Pushbullet');
  assert.equal(requests.length,1);assert.equal(requests[0].device_iden,'phone');
  await lit.locator('.press').click();await page.clock.runFor(32000);assert.equal(requests.length,1);
  await lit.locator('.power').uncheck();assert.equal(await lit.locator('.press').isDisabled(),true);
  await page.locator('#retries').selectOption('120');await sdb.locator('.press').click();
  await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .status').textContent==='Accepté par Pushbullet');
  await page.clock.runFor(119000);assert.equal(requests.length,2);
  await page.clock.runFor(2000);await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .detail').textContent.startsWith('2 envoi'));
  for(let k=0;k<3;k++){await page.clock.runFor(121000);await page.waitForFunction(n=>document.querySelector('[data-device="sdb"] .detail').textContent.startsWith(n+' envoi'),k+3);}
  assert.equal(requests.length,6);
  for(let k=2;k<6;k++)assert.ok(sentAt[k]-sentAt[k-1]>=120000,'Relance trop rapprochée');
  assert.match(await sdb.locator('.status').innerText(),/relances terminées/);
  await page.clock.runFor(241000);assert.equal(requests.length,6);
  await page.locator('#messages .notice').first().getByRole('button',{name:'Terminer l’essai sur ce PC'}).click();
  assert.match(await sdb.locator('.status').innerText(),/terminé sur ce PC/);
  await page.locator('#retries').selectOption('0');await page.locator('#target').selectOption('email');await page.locator('#email').fill('proche@example.invalid');
  failure=429;await sdb.locator('.press').click();await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .detail').textContent.includes('Limite Pushbullet'));
  assert.equal(requests[6].email,'proche@example.invalid');assert.equal(requests[6].device_iden,undefined);
  await page.clock.runFor(61000);assert.equal(requests.length,7);
  failure=0;await page.getByRole('button',{name:'Réessayer l’envoi'}).click();await page.waitForFunction(()=>document.querySelector('[data-device="sdb"] .status').textContent==='Accepté par Pushbullet');
  assert.equal(requests.length,8);
  await page.locator('#disconnect').click();assert.equal(await page.locator('#token').inputValue(),'');assert.equal(await sdb.locator('.press').isDisabled(),true);
  assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
  await page.locator('#token').fill('fake-test-token');failure=401;
  // Authentication error on the account check, with no push request.
  await page.route('https://api.pushbullet.com/v2/users/me',route=>route.fulfill({status:401,json:{error:{}}}));
  await page.locator('#connect').click();await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('Jeton invalide'));
  assert.equal(await lit.locator('.press').isDisabled(),true);assert.equal(requests.length,8);
  await page.setViewportSize({width:360,height:1000});await page.clock.runFor(500);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);
  console.log('PASS : contrat API, destinataires, absence de doublons, boîtiers indépendants, plafond des relances, erreurs 401/429, reprise manuelle, effacement du jeton, absence de stockage et affichage mobile. Aucun envoi réel.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
