/* Disk-backed key/value store shaped like the panel's DB, so engine code runs
   here unchanged. Writes are debounced and atomic; the file survives restarts. */
const fs=require("fs"),path=require("path");
const FILE=path.join(__dirname,"state.json");
let mem={};
try{mem=JSON.parse(fs.readFileSync(FILE,"utf8"));}catch(e){mem={};}
let timer=null,dirty=false;
function flush(){
  if(!dirty)return;
  dirty=false;
  try{fs.writeFileSync(FILE+".tmp",JSON.stringify(mem));fs.renameSync(FILE+".tmp",FILE);}
  catch(e){console.error("state write failed:",e.message);}
}
const db={
  get:k=>mem[k],
  set:(k,v)=>{mem[k]=v;dirty=true;if(!timer)timer=setTimeout(()=>{timer=null;flush();},1500);},
  all:()=>mem,
  flushNow:flush
};
process.on("exit",flush);
for(const sig of ["SIGINT","SIGTERM"])process.on(sig,()=>{flush();process.exit(0);});
module.exports={db,FILE};
