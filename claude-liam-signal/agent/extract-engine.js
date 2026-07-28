/* Generates engine.js from index.html so the panel and this agent can never
   drift apart: one source of truth, extracted rather than copied by hand. */
const fs=require("fs"),path=require("path");
const html=fs.readFileSync(path.join(__dirname,"../../index.html"),"utf8");
const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const js=scripts.sort((a,b)=>b.length-a.length)[0];
const from=js.indexOf("function rsiSeries"), to=js.indexOf("function ibsDetectSwings");
if(from<0||to<0)throw new Error("engine markers not found in index.html");
let engine=js.slice(from,to);
// CASES lives with the Telegram code; pull it in so the agent shares the same memory logic
const cFrom=js.indexOf("const CASES=(()=>{");
if(cFrom>=0){
  const cTo=js.indexOf("})();",cFrom)+5;
  engine=js.slice(cFrom,cTo)+"\n"+engine;
}
// COMMODITY_KEEP is declared elsewhere in the panel; carry the same set
const kFrom=js.indexOf("COMMODITY_KEEP=new Set(");
if(kFrom>=0){
  const kTo=js.indexOf("]);",kFrom)+3;
  engine="const "+js.slice(kFrom,kTo).replace(/^const\s+/,"")+"\n"+engine;
}
const exported=["rsiSeries","smcATR","smcChannel","smcFVGs","smcLevels","smcOrderBlocks",
  "obVisits","smcTargets","rsiDivergence","smcSetup","confFeat","confP","confEV","confLearn",
  "confW","evMin","domState","domFit","domFa","domConflicts","CASES","COMMODITY_KEEP"];
const header=`/* GENERATED — do not edit. Rebuild with: node extract-engine.js
   Source: index.html, the same code the panel runs. */
const {db:DB}=require("./store");
`;
fs.writeFileSync(path.join(__dirname,"engine.js"),
  header+engine+`\nmodule.exports={${exported.join(",")}};\n`);
console.log("engine.js written:",engine.length,"bytes");
