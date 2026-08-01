/* Delivery that does not lose messages: a failed send is queued on disk and
   retried, so a signal issued during an outage still arrives. */
const {db}=require("./store");
const QK="tg_queue";
function cfg(){return Object.assign({token:process.env.TG_TOKEN||"",chat:process.env.TG_CHAT||""},db.get("tg")||{});}
function on(){const c=cfg();return !!(c.token&&c.chat);}
async function raw(text){
  const c=cfg();if(!c.token||!c.chat)return false;
  try{
    const r=await fetch(`https://api.telegram.org/bot${c.token}/sendMessage`,
      {method:"POST",headers:{"Content-Type":"application/json"},
       body:JSON.stringify({chat_id:c.chat,text,parse_mode:"HTML",disable_web_page_preview:true})});
    return r.ok;
  }catch(e){return false;}
}
async function send(text){
  if(!on())return false;
  const ok=await raw(text);
  if(!ok){const q=db.get(QK)||[];q.push({t:Date.now(),text});db.set(QK,q.slice(-60));}
  return ok;
}
async function flush(){
  const q=db.get(QK)||[];if(!q.length||!on())return 0;
  const keep=[];let sent=0;
  for(const m of q){if(await raw(m.text))sent++;else keep.push(m);}
  db.set(QK,keep);return sent;
}
setInterval(flush,60000).unref?.();
module.exports={send,flush,on,cfg,pending:()=>(db.get(QK)||[]).length};
