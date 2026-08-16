import fs from 'fs';
const h = fs.readFileSync('index.html','utf8');
const m = h.match(/const PANEL_NS=[\s\S]*?\}\)\(\);\nconst DB=\(\(\)=>[\s\S]*?\n\}\)\(\);/);
if(!m){ console.log('✗ بلوک ذخیره‌سازی پیدا نشد'); process.exit(1); }
let ok=0, fail=[];
const check=(n,c)=>{ if(c){ok++;console.log('  ✓ '+n);} else {fail.push(n);console.log('  ✗ '+n);} };
function panel(search, store){
  const location={search};
  const localStorage={_s:store,
    setItem(k,v){this._s[k]=String(v);}, getItem(k){return k in this._s?this._s[k]:null;},
    removeItem(k){delete this._s[k];}};
  return new Function('location','localStorage','URLSearchParams', m[0]+'; return DB;')
    (location, localStorage, URLSearchParams);
}
console.log('── فضای جدا برای هر پنل ──');
const store={ feedback: JSON.stringify(['قدیمی']), hsa_state_v4: JSON.stringify({v:5}) };
const before = JSON.stringify(store);
const chat=panel('?panel=chat',store), pin=panel('?panel=pin',store), plain=panel('',store);

check('پنل نام‌دار فضای خودش را می‌گیرد', chat.ns==='p:chat:' && pin.ns==='p:pin:');
check('پنل بدون پارامتر فضای مشترک می‌ماند (رفتار قبلی)', plain.ns==='');
check('هر دو پنل دادهٔ موجود را می‌بینند',
  JSON.stringify(chat.get('feedback'))==='["قدیمی"]' &&
  JSON.stringify(pin.get('feedback'))==='["قدیمی"]');

chat.set('feedback',['چت']); pin.set('feedback',['پین']);
check('نوشتن هر پنل فقط مال خودش است',
  JSON.stringify(chat.get('feedback'))==='["چت"]' &&
  JSON.stringify(pin.get('feedback'))==='["پین"]');
check('دادهٔ مشترکِ قبلی دست‌نخورده ماند', store['feedback']==='["قدیمی"]');
check('پنل بدون پارامتر هنوز همان قدیمی را می‌بیند',
  JSON.stringify(plain.get('feedback'))==='["قدیمی"]');
check('کلید نام‌دار جدا ساخته شد',
  'p:chat:feedback' in store && 'p:pin:feedback' in store);

// کلیدی که هیچ‌کدام ننوشته‌اند، هنوز از میراث می‌آید
check('کلید نانوشته از فضای مشترک خوانده می‌شود',
  JSON.stringify(chat.get('hsa_state_v4'))==='{"v":5}');
chat.set('hsa_state_v4',{v:6});
check('و بعد از نوشتن، نسخهٔ خودش را می‌بیند',
  JSON.stringify(chat.get('hsa_state_v4'))==='{"v":6}' &&
  JSON.stringify(pin.get('hsa_state_v4'))==='{"v":5}');
check('هیچ کلید قدیمی پاک نشد',
  Object.keys(JSON.parse(before)).every(k=>k in store));

// نام ناسالم نباید فضای عجیب بسازد
const weird=panel('?panel=../../evil',store);
check('نام ناسالم پاک‌سازی می‌شود', /^p:[a-zA-Z0-9_-]+:$/.test(weird.ns));
const empty=panel('?panel=',store);
check('پارامتر خالی = فضای مشترک', empty.ns==='');

console.log();
if(fail.length){ console.log('✗ '+fail.length+' شکست: '+fail.join(', ')); process.exit(1); }
console.log('✓ همهٔ '+ok+' آزمون فضای پنل گذشت');
