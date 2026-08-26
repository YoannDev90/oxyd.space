const svg=d3.select("#map");
const W=960,H=500;
const proj=d3.geoNaturalEarth1().scale(153).translate([W/2,H/2]);
const path=d3.geoPath(proj);

const defs=svg.append("defs");
const glow=defs.append("filter").attr("id","glow").attr("x","-50%").attr("y","-50%").attr("width","200%").attr("height","200%");
glow.append("feGaussianBlur").attr("stdDeviation","2.5").attr("result","blur");
glow.append("feMerge").selectAll("feMergeNode").data(["blur","SourceGraphic"]).join("feMergeNode").attr("in",d=>d);

const gMain=svg.append("g");

const zoom=d3.zoom()
  .scaleExtent([1,12])
  .on("zoom",e=>{
    gMain.attr("transform",e.transform);
    gMain.selectAll(".srv-dot").attr("r",3.2/e.transform.k);
    gMain.selectAll(".dot-label").attr("font-size",9/e.transform.k);
  });
svg.call(zoom);

gMain.append("path").datum({type:"Sphere"}).attr("class","sphere").attr("d",path);
gMain.append("path").datum(d3.geoGraticule().step([30,30])()).attr("class","graticule").attr("d",path);

let S=[];
let dotCircles;

function setDot(ip,status){
  const i=S.findIndex(s=>s.ip===ip);
  if(i<0)return;
  const c=d3.select(dotCircles.nodes()[i]);
  if(status==="success") c.attr("fill","#34d399").attr("opacity",1);
  else if(status==="pending") c.attr("fill","#2a3a50").attr("opacity",.5);
  else c.attr("fill","#f87171").attr("opacity",1);
}
function resetDots(){ dotCircles.attr("fill","#2a3a50").attr("opacity",.5); }

function drawDots(data){
  S=data;
  const dotsG=gMain.append("g");
  const dotData=dotsG.selectAll("g").data(S).join("g").attr("transform",d=>{
    const p=proj([d.lng,d.lat]);
    return "translate("+p[0]+","+p[1]+")";
  });
  dotData.append("circle")
    .attr("class","srv-dot").attr("r",3.2)
    .attr("fill","#2a3a50").attr("opacity",.5).attr("filter","url(#glow)");
  dotData.append("text")
    .attr("class","dot-label").attr("x",0).attr("y",-8).attr("text-anchor","middle")
    .text(d=>d.label);
  dotCircles=dotsG.selectAll(".srv-dot");
}

const domain=document.getElementById('domain');
const rtype=document.getElementById('rtype');
const go=document.getElementById('go');
const out=document.getElementById('resultsArea');

function buildGrid(items){
  return '<div class="results-header"><h2>Results</h2></div><div class="results-grid">'
    +items.map(j=>{
      return '<div class="srv-card"><span class="dot wait"></span>'
        +'<div class="info"><span class="name">'+j.flag+' '+j.label+'</span><span class="region">'+j.city+', '+j.country+' · '+j.ip+'</span></div>'
        +'<div class="result"><span class="ips">—</span><span class="ms"></span></div></div>';
    }).join('')+'</div>';
}

function renderResults(done,total){
  const ok=done.filter(d=>d.ok).length;
  const pct=Math.round(ok/total*100);
  const sorted=done.sort((a,b)=>(a.ms||9999)-(b.ms||9999));
  const cards=sorted.map(j=>{
    const cls=j.ms?(j.ms<100?'fast':j.ms>500?'slow':''):'';
    return '<div class="srv-card '+(j.ok?'ok':'err')+'"><span class="dot '+(j.ok?'ok':'err')+'"></span>'
      +'<div class="info"><span class="name">'+j.flag+' '+j.label+'</span><span class="region">'+j.city+', '+j.country+' · '+j.ip+'</span></div>'
      +'<div class="result"><span class="ips">'+j.ips+'</span>'
      +(j.ms?'<span class="ms '+cls+'">'+j.ms+'ms</span>':'<span class="ms">timeout</span>')+'</div></div>';
  }).join('');
  out.innerHTML=
    '<div class="results-header"><h2>Results</h2><span style="font-family:var(--mono);font-size:13px;color:var(--muted)">'+ok+'/'+total+'</span></div>'
    +'<div class="results-grid">'+cards+'</div>'
    +'<div class="summary-bar"><span class="count"><span class="ok">'+ok+'</span> ok · <span class="err">'+(total-ok)+'</span> failed</span>'
    +'<div class="progress-bar"><div class="progress-fill" style="width:'+pct+'%"></div></div>'
    +'<span class="elapsed">'+done.length+'/'+total+'</span></div>';
}

async function check(){
  const d=domain.value.trim().toLowerCase().replace(/^https?:\/\//,'').split('/')[0];
  if(!d)return;
  go.disabled=true;
  resetDots();
  out.innerHTML='<div class="results-header"><h2>Results</h2><span style="font-family:var(--mono);font-size:13px;color:var(--muted)">0/'+S.length+'</span></div><div class="results-grid"></div>';
  const t0=performance.now();
  const done=[];
  await Promise.allSettled(S.map(s=>
    fetch('https://dnsrobot.net/api/dns-query',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({domain:d,recordType:rtype.value,dnsServer:s.ip,timeout:5000})
    }).then(r=>r.json()).then(j=>{
      const success=j.status==='success';
      const ips=Array.isArray(j.resolvedIPs)?j.resolvedIPs.join(', '):(j.resolvedData||'—');
      done.push({ok:success,ip:s.ip,label:s.label,country:s.country,city:s.city,flag:s.flag,ips:ips,ms:j.responseTime||null});
      setDot(s.ip,success?"success":"error");
      renderResults(done,S.length);
    }).catch(()=>{
      done.push({ok:false,ip:s.ip,label:s.label,country:s.country,city:s.city,flag:s.flag,ips:'—',ms:null});
      setDot(s.ip,"error");
      renderResults(done,S.length);
    })
  ));
  const elapsed=Math.round(performance.now()-t0);
  renderResults(done,S.length);
  out.querySelector('.elapsed').textContent=elapsed+'ms total';
  go.disabled=false;
}

go.addEventListener('click',check);
domain.addEventListener('keydown',e=>{if(e.key==='Enter')check()});

Promise.all([
  fetch('assets/dns.json').then(r=>r.json()),
  d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
]).then(([servers,world])=>{
  gMain.append("g")
    .selectAll("path").data(topojson.feature(world,world.objects.countries).features).join("path")
    .attr("class","land").attr("d",path);
  gMain.append("path")
    .datum(topojson.mesh(world,world.objects.countries,(a,b)=>a!==b))
    .attr("class","border").attr("d",path);
  drawDots(servers);
});
