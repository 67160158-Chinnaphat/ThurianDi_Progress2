const $ = (id) => document.getElementById(id);

const pageMeta = {
  diagnosis: { title: "หมอนทอง AI ผู้ช่วยอุปกรณ์สวน", sub: "ถ่ายรูปหรือพิมพ์อาการของเครื่องมือ/อุปกรณ์ทำสวนที่มีปัญหา แล้วให้หมอนทองช่วยวิเคราะห์และแนะนำวิธีแก้เบื้องต้น" },
  community: { title: "ชุมชนและรีวิว", sub: "อ่านรีวิวและประสบการณ์จากชาวสวนทุเรียนท่านอื่น" },
  parts: { title: "เทียบอะไหล่เกษตร", sub: "ค้นหาและเทียบอะไหล่เครื่องสูบน้ำ-อุปกรณ์ข้ามยี่ห้อ" },
  dashboard: { title: "แดชบอร์ดสวนของฉัน", sub: "ภาพรวมสถิติโรค ค่าใช้จ่าย และประวัติของสวน" },
  share: { title: "แบ่งปันข้อมูล", sub: "โพสต์อัปเดตผลการรักษา รีวิว หรือช่วยตอบคำถามเพื่อนชาวสวน" },
};

/* ===================== NAVIGATION ===================== */
document.querySelectorAll(".nav-item").forEach((btn) => btn.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  const view = btn.dataset.view;
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $(`view-${view}`).classList.add("active");
  $("pageTitle").textContent = pageMeta[view].title;
  $("pageSubtitle").textContent = pageMeta[view].sub;
  $("notifPanel").classList.remove("open");
  // Charts are built while the dashboard panel is hidden (display:none),
  // so Chart.js measures a 0x0 canvas and never draws the data. Force a
  // resize once the panel is actually visible so it re-measures correctly.
  if (view === "dashboard") {
    requestAnimationFrame(() => {
      [chartDiseaseInstance, chartPieInstance].forEach(c => c && c.resize());
    });
  }
}));

$("notifBtn").addEventListener("click", (e) => { e.stopPropagation(); $("notifPanel").classList.toggle("open"); });
document.addEventListener("click", () => $("notifPanel").classList.remove("open"));

/* ===================== SESSION ===================== */
function updateAuthUI(user) {
  $("authBtn").textContent = `ออกจากระบบ · ${user.username}`;
  $("authBtn").classList.remove("btn-ghost"); $("authBtn").classList.add("btn-outline");
  const nameEl = document.querySelector(".user-name"); if (nameEl) nameEl.textContent = user.username;
  const subEl = document.querySelector(".user-sub"); if (subEl) subEl.textContent = user.email;
  const sessionEl = $("userSession");
  if (sessionEl) sessionEl.innerHTML = `<span class="session-dot"></span> เชื่อมต่อฐานข้อมูลแล้ว · ${user.email}`;
}
$("authBtn").addEventListener("click", logout);

/* ===================== หมอนทอง AI (ผู้ช่วยอุปกรณ์สวน) ===================== */
const chatWindow = $("chatWindow");
function addUserMsg(text, imageName = "") {
  const div = document.createElement("div"); div.className = "msg user";
  div.innerHTML = `<div class="hex msg-avatar">👨‍🌾</div><div class="bubble">${imageName ? `<div class="upload-chip">📷 ${escapeHtml(imageName)}</div>` : ""}${escapeHtml(text)}</div>`;
  chatWindow.appendChild(div); chatWindow.scrollTop = chatWindow.scrollHeight;
}
function addBotThinking() {
  $("thinkingMsg")?.remove();
  const div = document.createElement("div"); div.className = "msg bot"; div.id = "thinkingMsg";
  div.innerHTML = `<div class="hex msg-avatar">🤖</div><div class="bubble thinking"><span></span><span></span><span></span> กำลังวิเคราะห์...</div>`;
  chatWindow.appendChild(div); chatWindow.scrollTop = chatWindow.scrollHeight;
}
function addBotDiagnosis(result) {
  $("thinkingMsg")?.remove();
  const div = document.createElement("div"); div.className = "msg bot";
  div.innerHTML = `<div class="hex msg-avatar">🤖</div><div class="bubble">จากข้อมูลที่ส่งมา หมอนทองพบปัญหาที่เป็นไปได้ดังนี้ครับ<div class="diag-card"><div class="diag-card-title">🔧 ${escapeHtml(result.problem)} <span class="diag-scientific">(${escapeHtml(result.likely_cause)})</span></div><div class="diag-conf">ความมั่นใจของระบบ: ${result.confidence}%</div><ul>${result.recommendations.map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul><button class="btn btn-ghost" type="button" onclick="alert('ฟังก์ชันส่งต่อช่างซ่อมพร้อมเชื่อมต่อได้เมื่อมีบัญชีช่างในระบบ')">ส่งต่อช่างซ่อมอุปกรณ์การเกษตร</button></div><div class="diag-note">${escapeHtml(result.disclaimer || "")}</div></div>`;
  chatWindow.appendChild(div); chatWindow.scrollTop = chatWindow.scrollHeight;
}
async function diagnoseFile(file) {
  if (!file) return;
  addUserMsg("ส่งรูปเพื่อวิเคราะห์ปัญหาอุปกรณ์", file.name); addBotThinking();
  try {
    const fd = new FormData(); fd.append("image", file);
    const result = await api("/diagnose", { method: "POST", body: fd });
    addBotDiagnosis(result);
  } catch (err) { $("thinkingMsg")?.remove(); addUserMsg(`เกิดข้อผิดพลาด: ${err.message}`); }
}
$("sendChatBtn").addEventListener("click", async () => {
  const text = $("chatText").value.trim(); if (!text) return;
  addUserMsg(text); $("chatText").value = ""; addBotThinking();
  setTimeout(() => addBotDiagnosis({ problem: "ปั๊มน้ำสตาร์ทไม่ติด", likely_cause: "แบตเตอรี่/สายไฟหลวมหรือเสื่อมสภาพ", confidence: 82, recommendations: ["ตรวจสอบขั้วแบตเตอรี่และสายไฟให้แน่นและไม่มีสนิม", "ลองสตาร์ทด้วยแบตเตอรี่สำรองเพื่อแยกปัญหา", "ตรวจสอบฟิวส์และรีเลย์สตาร์ทเตอร์"], disclaimer: "ผลจากข้อความเป็นการสาธิตการทำงานของระบบเท่านั้น" }), 700);
});
$("chatText").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); $("sendChatBtn").click(); } });
$("uploadPhotoBtn").addEventListener("click", () => $("photoInput").click());
$("photoInput").addEventListener("change", e => diagnoseFile(e.target.files[0]));

/* ===================== COMMUNITY ===================== */
const demoPosts = [
  { author:"สมหญิง สวนดี", region:"south", regionLabel:"ภาคใต้", category:"disease", rating:5, time:"2 ชม.ที่แล้ว", title:"ใบไหม้ช่วงฝนตก", text:"ปีนี้เจอใบไหม้เยอะมากช่วงฝนตกต่อเนื่อง ลองพ่นสารตามคำแนะนำ 2 รอบ อาการเริ่มดีขึ้นแล้วครับ", image:true },
  { author:"ประเสริฐ ทุเรียนทอง", region:"east", regionLabel:"ภาคตะวันออก", category:"fertilizer", rating:4, time:"5 ชม.ที่แล้ว", title:"รีวิวปุ๋ย 8-24-24", text:"รีวิวปุ๋ยสูตร 8-24-24 ที่บอทแนะนำ ใช้แล้วดอกติดดีขึ้นเยอะ แต่ราคาสูงกว่าปุ๋ยทั่วไปนิดหน่อย" },
  { author:"มานพ ใจเกษตร", region:"south", regionLabel:"ภาคใต้", category:"general", rating:0, time:"1 วันที่แล้ว", title:"ถามสูตรปุ๋ย", text:"มือใหม่ปลูกทุเรียนปีแรก อยากถามว่าช่วงนี้ควรใส่ปุ๋ยสูตรไหนดีครับ พื้นที่ดินร่วนปนทราย" },
  { author:"วิภา สวนเขาใหญ่", region:"east", regionLabel:"ภาคตะวันออก", category:"disease", rating:5, time:"1 วันที่แล้ว", title:"ก่อน-หลังรักษารากเน่า", text:"แชร์ภาพก่อน-หลังรักษาโรครากเน่าโคนเน่า ใช้เวลาประมาณ 3 สัปดาห์ต้นฟื้นตัวชัดเจน", image:true },
  { author:"อรุณ ทองสวน", region:"north", regionLabel:"ภาคเหนือ", category:"fertilizer", rating:3, time:"2 วันที่แล้ว", title:"ลองปุ๋ยอินทรีย์", text:"ลองปุ๋ยอินทรีย์ยี่ห้อที่ชุมชนแนะนำ ผลลัพธ์กลางๆ ต้นโตช้ากว่าที่คาด อาจเพราะอากาศเย็นกว่าภาคอื่น" },
];
function renderStars(n) { return n ? `<span class="stars">${"★".repeat(n)}${"☆".repeat(5-n)}</span>` : ""; }
function categoryLabel(c) { return ({disease:"โรคพืช", fertilizer:"ปุ๋ย/ยา", general:"ถาม-ตอบทั่วไป", update:"อัปเดตผลการรักษา", review:"รีวิวปุ๋ย/อะไหล่", qa:"ถามคำถาม"}[c] || c); }
function buildPostCard(p) {
  const div = document.createElement("article"); div.className = "post-card";
  const when = p.time || formatTime(p.created_at);
  div.innerHTML = `<div class="post-head"><div class="post-author"><div class="hex post-author-avatar">👤</div><div><div class="post-author-name">${escapeHtml(p.author || p.username)}</div><div class="post-meta">${escapeHtml(categoryLabel(p.category))} · ${escapeHtml(when)}</div></div></div>${renderStars(p.rating)}</div><div class="post-title">${escapeHtml(p.title || "โพสต์จากชุมชน")}</div><div class="post-body">${escapeHtml(p.text || p.content)}</div>${p.image ? '<div class="post-imgs"><div class="img-placeholder">ภาพก่อน</div><div class="img-placeholder">ภาพหลัง</div></div>' : ''}<div class="post-footer"><span class="region-tag">${escapeHtml(p.regionLabel || "ชุมชนทุเรียน")}</span>${p.comment_count !== undefined ? `<span class="comment-count">💬 ${p.comment_count}</span>` : ""}</div>`;
  return div;
}
async function loadCommunityFeed() {
  const feed = $("communityFeed"); feed.innerHTML = `<div class="panel loading-card">กำลังโหลดข้อมูลชุมชน...</div>`;
  const search = $("communitySearch").value.trim(); const cat = document.querySelector("#categoryPills .pill.active")?.dataset.cat || "all";
  try {
    const posts = await api(`/posts?q=${encodeURIComponent(search)}&category=${encodeURIComponent(cat)}&limit=50`);
    if (!posts.length) throw new Error("empty");
    feed.innerHTML = ""; posts.forEach(p => feed.appendChild(buildPostCard(p)));
  } catch {
    const region = $("communityRegion").value;
    const filtered = demoPosts.filter(p => (!search || `${p.author} ${p.text} ${p.title}`.toLowerCase().includes(search.toLowerCase())) && (!region || region === "all" || p.region === region) && (cat === "all" || p.category === cat));
    feed.innerHTML = "";
    if (!filtered.length) feed.innerHTML = `<div class="panel empty-state">ไม่พบข้อมูลที่ตรงกับเงื่อนไข</div>`;
    else filtered.forEach(p => feed.appendChild(buildPostCard(p)));
  }
}
$("communitySearch").addEventListener("input", debounce(loadCommunityFeed, 250));
$("communityRegion").addEventListener("change", loadCommunityFeed);
document.querySelectorAll("#categoryPills .pill").forEach(pill => pill.addEventListener("click", () => { document.querySelectorAll("#categoryPills .pill").forEach(p => p.classList.remove("active")); pill.classList.add("active"); loadCommunityFeed(); }));

/* ===================== PARTS ===================== */
const partsData = [
  { model:"Honda WB20XH", part:"ซีลกันน้ำปั๊ม", alt:"SIMEC SP-20 / Kubota KWP-20", price:"180–320 บาท" },
  { model:"Honda WB30XH", part:"ใบพัดปั๊ม (Impeller)", alt:"SIMEC SP-30 / Mitsubishi MPD-30", price:"450–650 บาท" },
  { model:"Kubota KWP-20", part:"แหวนรองกันสั่น", alt:"Honda WB20XH / SIMEC SP-20", price:"60–120 บาท" },
  { model:"Mitsubishi MPD-30", part:"ท่อดูดสายยาง 3 นิ้ว", alt:"ใช้ร่วมกันได้ทุกยี่ห้อ", price:"250–400 บาท" },
  { model:"SIMEC SP-20", part:"สปริงวาล์วเช็ค", alt:"Honda WB20XH / Kubota KWP-20", price:"40–90 บาท" },
];
function renderPartsTable() {
  const q = $("partsSearch").value.toLowerCase(); const tbody = document.querySelector("#partsTable tbody"); tbody.innerHTML = "";
  const filtered = partsData.filter(r => `${r.model} ${r.part} ${r.alt}`.toLowerCase().includes(q));
  if (!filtered.length) { tbody.innerHTML = `<tr><td colspan="4" class="empty-cell">ไม่พบรายการ</td></tr>`; return; }
  filtered.forEach(r => { const tr = document.createElement("tr"); tr.innerHTML = `<td>${escapeHtml(r.model)}</td><td>${escapeHtml(r.part)}</td><td>${escapeHtml(r.alt)}</td><td>${escapeHtml(r.price)}</td>`; tbody.appendChild(tr); });
}
$("partsSearch").addEventListener("input", renderPartsTable);
$("partsCameraBtn").addEventListener("click", () => { $("partsSearch").value = "Honda WB20XH"; renderPartsTable(); });
renderPartsTable();
const shops = [{name:"ร้านเกษตรพัฒนา",addr:"ถ.สายเกษตร ต.บ้านโป่ง (2.4 กม. จากสวน)",phone:"089-123-4567"},{name:"ยงยุทธการเกษตร",addr:"หน้าตลาดสด อ.เมือง (5.1 กม. จากสวน)",phone:"081-987-6543"},{name:"ร้านอะไหล่ปั๊มน้ำไทยเจริญ",addr:"ถ.เพชรเกษม กม.14 (8.7 กม. จากสวน)",phone:"086-555-2211"}];
shops.forEach(s => { const d=document.createElement("div"); d.className="shop-item"; d.innerHTML=`<div class="shop-info"><div class="hex pin">📍</div><div><div class="shop-name">${s.name}</div><div class="shop-addr">${s.addr}</div></div></div><a class="btn btn-ghost" href="tel:${s.phone}">📞 ${s.phone}</a>`; $("shopList").appendChild(d); });

/* ===================== DASHBOARD ===================== */
const chartCommon = { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ labels:{ font:{family:"Kanit"} } } } };
let chartDiseaseInstance, chartPieInstance;
if (window.Chart) {
  chartDiseaseInstance = new Chart($("chartDisease"), { type:"bar", data:{labels:["ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค."],datasets:[{label:"จำนวนครั้งที่พบโรค",data:[2,3,1,4,5,3],backgroundColor:"#E8A83C",borderRadius:7}]}, options:{...chartCommon, plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true,ticks:{stepSize:1}}}} });
  chartPieInstance = new Chart($("chartPie"), { type:"doughnut", data:{labels:["ใบไหม้","รากเน่าโคนเน่า","ราดำ","ปกติดี"],datasets:[{data:[42,23,15,20],backgroundColor:["#C4562E","#1F4D36","#7FA687","#E8A83C"],borderWidth:0}]}, options:{...chartCommon, plugins:{legend:{position:"bottom",labels:{font:{family:"Kanit"}}}}} });
} else {
  document.querySelectorAll("canvas").forEach(c => { c.insertAdjacentHTML("afterend", '<p class="chart-fallback">กราฟจะโหลดเมื่อเชื่อมต่อ Chart.js ได้</p>'); });
}
const historyData=[{date:"17 ก.ค. 2569",item:"ใบไหม้ (Phytophthora)",action:"พ่นสารป้องกันเชื้อรา",cost:"฿850"},{date:"10 ก.ค. 2569",item:"ตรวจสุขภาพต้นทั่วไป",action:"ไม่พบความผิดปกติ",cost:"฿0"},{date:"2 ก.ค. 2569",item:"รากเน่าโคนเน่า",action:"ตัดแต่งรากเน่า + ใส่ปูนขาว",cost:"฿1,200"},{date:"24 มิ.ย. 2569",item:"ซื้อปุ๋ยสูตร 8-24-24",action:"ใส่ปุ๋ยรอบดอกบาน",cost:"฿2,200"}];
historyData.forEach(h=>{const tr=document.createElement("tr");tr.innerHTML=`<td>${h.date}</td><td>${h.item}</td><td>${h.action}</td><td>${h.cost}</td>`;$("historyTableBody").appendChild(tr);});

/* ===================== SHARE ===================== */
async function submitPost() {
  const content = $("postContent").value.trim(); if (!content) return;
  const category = $("postCategory").value;
  try {
    await api("/posts", {method:"POST",body:JSON.stringify({title: content.length>60 ? content.slice(0,60)+"…" : content,content,category})});
    $("postContent").value=""; await loadCommunityFeed();
    document.querySelector('[data-view="community"]').click();
  } catch (err) { alert(err.message); }
}
$("postSubmitBtn").addEventListener("click", submitPost);
$("postImageBtn").addEventListener("click", () => alert("แนบรูปสำหรับโพสต์จะเพิ่มต่อในโมดูลอัปโหลดไฟล์ได้ ระบบ Backend สำหรับโพสต์พร้อมรองรับ image_url แล้ว"));

function formatTime(date) { try { return new Date(date).toLocaleString("th-TH", {dateStyle:"short",timeStyle:"short"}); } catch { return "ล่าสุด"; } }
function escapeHtml(str) { return String(str ?? "").replace(/[&<>\"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[ch])); }
function debounce(fn, wait) { let t; return (...args)=>{clearTimeout(t);t=setTimeout(()=>fn(...args),wait);}; }

requireAuth(["user"]).then((me) => { updateAuthUI(me); loadCommunityFeed(); });
