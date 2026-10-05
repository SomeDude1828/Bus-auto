const ROUTES = [
  { line: "27", dest: "Konzorcij", preferred: true },
  { line: "11", dest: "Drama", preferred: false },
  { line: "25", dest: "Bavarski dvor", preferred: false }
];
const WAKE_BEFORE = 20;
const HOME_TO_STOP = 8;
const BACKUP_BEFORE_WAKE = 15;

const $ = id => document.getElementById(id);
let schedule = null;

function tomorrowKey() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const y=d.getFullYear(), m=String(d.getMonth()+1).padStart(2,"0"), day=String(d.getDate()).padStart(2,"0");
  return `${y}-${m}-${day}`;
}
function dateLabel(key) {
  return new Intl.DateTimeFormat(undefined,{weekday:"short",day:"numeric",month:"short"}).format(new Date(key+"T12:00:00"));
}
function toMin(s) { const [h,m]=s.split(":").map(Number); return h*60+m; }
function fromMin(n) { n=((n%1440)+1440)%1440; return `${String(Math.floor(n/60)).padStart(2,"0")}:${String(n%60).padStart(2,"0")}`; }
function esc(s) { const d=document.createElement("div"); d.textContent=s; return d.innerHTML; }

async function load() {
  try {
    const r=await fetch(`data.json?${Date.now()}`, {cache:"no-store"});
    if(!r.ok) throw new Error(`data.json ${r.status}`);
    schedule=await r.json();
    $("status").textContent=`Timetable updated ${schedule.generated_at ? new Date(schedule.generated_at).toLocaleString() : ""}`;
  } catch(e) {
    $("status").textContent="No timetable data yet. GitHub Actions needs to run once — see the README.";
  }
  find();
}

function find() {
  const key=tomorrowKey();
  $("dateText").textContent=`Checking ${dateLabel(key)} · tomorrow`;
  const target=toMin($("arrival").value || "07:00");
  const day=schedule?.days?.[key];
  const results=[];
  for(const r of ROUTES) {
    const trips=(day?.[r.line]||[]).filter(x=>toMin(x.arr)<=target);
    // Latest arrival is the most useful: it minimizes waking/waiting early.
    trips.sort((a,b)=>toMin(b.arr)-toMin(a.arr) || toMin(b.dep)-toMin(a.dep));
    if(trips[0]) results.push({...r, ...trips[0]});
  }
  results.sort((a,b)=>toMin(a.dep)-toMin(b.dep));
  if(!results.length) {
    $("results").innerHTML=`<div class="card">No scheduled bus in the downloaded timetable arrives by <b>${esc($("arrival").value)}</b> tomorrow.</div>`;
    return;
  }
  $("results").innerHTML=results.map(r=>{
    const dep=toMin(r.dep), arr=toMin(r.arr), wake=dep-WAKE_BEFORE, backup=wake-BACKUP_BEFORE, leave=dep-HOME_TO_STOP;
    const buffer=target-arr;
    return `<article class="result ${r.preferred?"best":""}">
      <div class="resultTop"><div class="route">🚌 ${esc(r.line)} → ${esc(r.dest)}</div>${r.preferred?'<div class="tag">PREFERRED</div>':''}</div>
      <div class="dest">Arrives at ${esc(r.dest)} at <b>${esc(r.arr)}</b> · ${buffer} min before target</div>
      <div class="grid">
        <div class="stat"><small>Bus at Polje</small><b>${esc(r.dep)}</b></div>
        <div class="stat"><small>Wake up</small><b>${fromMin(wake)}</b></div>
        <div class="stat"><small>Leave home</small><b>${fromMin(leave)}</b></div>
        <div class="stat"><small>Backup alarm</small><b>${fromMin(backup)}</b></div>
      </div>
    </article>`;
  }).join("");
}

$("findBtn").addEventListener("click",find);
$("arrival").addEventListener("change",find);
$("themeBtn").addEventListener("click",()=>{
  document.documentElement.classList.toggle("light");
  localStorage.setItem("theme",document.documentElement.classList.contains("light")?"light":"dark");
});
if(localStorage.getItem("theme")==="light") document.documentElement.classList.add("light");
load();
