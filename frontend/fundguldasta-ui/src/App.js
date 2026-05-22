import React, { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import "./i18n";

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => { navigator.serviceWorker.register("/sw.js").catch(() => {}); });
}

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const USE_LIVE_DATA = true;

async function apiCall(method, path, body = null) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) options.body = JSON.stringify(body);
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

async function authRegister(email, password, displayName) {
  return apiCall("POST", "/api/auth/register", { email, password, display_name: displayName });
}
async function authLogin(email, password) {
  return apiCall("POST", "/api/auth/login", { email, password });
}
async function authMe(token) {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { "Authorization": `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Session expired");
  return res.json();
}

async function apiSaveBouquet(token, payload) {
  const res = await fetch(`${API_BASE}/api/user/saved-bouquets`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Save failed"); }
  return res.json();
}
async function apiFundSearch(q) {
  const res = await fetch(`${API_BASE}/api/funds/search?q=${encodeURIComponent(q)}&limit=8`);
  if (!res.ok) return [];
  return res.json();
}
async function apiAnalysePortfolio(funds, horizonYears = 7) {
  const res = await fetch(`${API_BASE}/api/portfolio/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ funds, horizon_years: horizonYears }),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Analysis failed"); }
  return res.json();
}

async function apiListSaved(token) {
  const res = await fetch(`${API_BASE}/api/user/saved-bouquets`, {
    headers: { "Authorization": `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Could not load saved bouquets");
  return res.json();
}
async function apiDeleteSaved(token, id) {
  await fetch(`${API_BASE}/api/user/saved-bouquets/${id}`, {
    method: "DELETE",
    headers: { "Authorization": `Bearer ${token}` },
  });
}

async function curateBouquets(params) {
  if (USE_LIVE_DATA) {
    return apiCall("POST", "/api/bouquets/curate", params);
  }
  return null;
}

async function getFreshness() {
  if (USE_LIVE_DATA) {
    return apiCall("GET", "/api/bouquets/steady/freshness");
  }
  return null;
}

const G = {
  bg: "#090C11", sur: "#10151F", elv: "#161D2C",
  bord: "rgba(255,255,255,0.07)", bordG: "rgba(212,175,55,0.22)",
  gold: "#D4AF37", goldD: "#7A6010",
  white: "#FFFFFF", slate: "#8892A4", mist: "#505870", fog: "#C0C8D8",
  em: "#22A86A", emBg: "rgba(34,168,106,0.1)",
  am: "#E8A000", amBg: "rgba(232,160,0,0.1)",
  ro: "#D84848", roBg: "rgba(216,72,72,0.1)",
  az: "#4282D0", azBg: "rgba(66,130,208,0.1)",
};

const SCENARIOS = [
  {
    id: "crash", borderColor: "#D84848",
    title: "Scenario 1 of 3 — The Crash Test", date: "March 2020",
    situation: "COVID lockdowns announced. Markets fall <strong>38% in 6 weeks.</strong> Your ₹10 Lakh portfolio shows ₹6.2 Lakhs. Your SIP of ₹15,000 is due next week.",
    question: "What do you actually do?",
    options: [
      { id: "a", text: "Increase SIP — this is exactly the buying opportunity I have been waiting for", score: 4 },
      { id: "b", text: "Pay SIP as usual and add lump sum if possible", score: 3 },
      { id: "c", text: "Pay SIP as usual — trust the long term", score: 3 },
      { id: "d", text: "Pay this month's SIP but feel very uncertain about continuing", score: 2 },
      { id: "e", text: "Pause SIP temporarily until situation becomes clearer", score: 1 },
      { id: "f", text: "Redeem everything — capital preservation first", score: 0 },
    ],
  },
  {
    id: "drought", borderColor: "#E8A000",
    title: "Scenario 2 of 3 — The Long Drought", date: "4 years into a 7-year investment",
    situation: "Year 1: +18%. Year 2: −12%. Year 3: −8%. Year 4: +2%. <strong>After 4 years your ₹10 Lakhs is worth ₹9.6 Lakhs.</strong> Three years remain.",
    question: "What do you do?",
    options: [
      { id: "a", text: "Stay fully invested — 3 years remain, this is when patience gets rewarded", score: 4 },
      { id: "b", text: "Stay invested but stop adding new money until recovery starts", score: 2 },
      { id: "c", text: "Partially redeem — recover at least my original capital", score: 1 },
      { id: "d", text: "Exit fully — this clearly is not working", score: 0 },
    ],
  },
  {
    id: "fomo", borderColor: "#4282D0",
    title: "Scenario 3 of 3 — The FOMO Test", date: "3 years into investment",
    situation: "Your bouquet delivered <strong>11% CAGR over 3 years.</strong> A colleague's technology fund delivered 34% in the same period.",
    question: "What do you do?",
    options: [
      { id: "a", text: "Nothing — my bouquet tracks my 7-year goal. One 3-year comparison is meaningless.", score: 4 },
      { id: "b", text: "Research the technology fund but make no portfolio changes", score: 3 },
      { id: "c", text: "Shift 20–30% into the technology fund", score: 1 },
      { id: "d", text: "Exit most of bouquet and move into recent top performers", score: 0 },
    ],
  },
];

function getBehavProfile(total) {
  if (total >= 10) return { type: "Steadfast Investor", color: G.em, archId: "aggressive", text: "Your responses suggest you can remain invested through significant volatility. This is the single most important factor in capturing long-term returns." };
  if (total >= 7) return { type: "Rational but Tested", color: G.az, archId: "balanced", text: "You show sound instincts but volatility tests your conviction. Bouquets with shorter recovery periods may help you stay invested." };
  if (total >= 4) return { type: "Anxiety-Prone Investor", color: G.am, archId: "steady", text: "Your responses suggest volatility may lead to early exit. A lower volatility bouquet you stay invested in will outperform a higher return one you exit early." };
  return { type: "Reactive Investor", color: G.ro, archId: "steady", text: "Your responses suggest a pattern of exiting during downturns. A lower-return, lower-volatility bouquet is strongly recommended." };
}

const css = `
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Outfit:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Outfit',sans-serif;background:${G.bg};color:${G.fog};min-height:100vh;overflow-x:hidden}
.hero{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 24px;position:relative}
.mesh{position:absolute;inset:0;background:radial-gradient(ellipse 80% 60% at 20% 50%,rgba(212,175,55,0.06) 0%,transparent 60%),radial-gradient(ellipse 60% 80% at 80% 30%,rgba(66,130,208,0.04) 0%,transparent 60%);pointer-events:none}
.brand{display:flex;align-items:center;gap:20px;margin-bottom:52px;animation:up .9s ease .1s both}
.bmark{width:108px;height:108px;background:#060910;border-radius:18px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 44px rgba(212,175,55,0.35),0 0 0 1px rgba(212,175,55,0.25);flex-shrink:0;overflow:hidden;padding:0}
.bname{font-family:'Cormorant Garamond',serif;font-size:52px;font-weight:700;color:${G.gold};line-height:1.05}
.btag{font-size:18px;color:${G.gold};margin-top:6px;letter-spacing:.04em;font-style:italic;font-family:'Cormorant Garamond',serif;line-height:1.3}
.h1{font-family:'Cormorant Garamond',serif;font-size:clamp(48px,8vw,84px);font-weight:700;line-height:1.06;text-align:center;color:${G.white};max-width:900px;margin-bottom:14px;animation:up .9s ease .3s both}
.h1 em{color:${G.gold};font-style:normal}
.tagline{font-family:'Cormorant Garamond',serif;font-size:clamp(20px,2.8vw,28px);color:${G.gold};margin-bottom:10px;letter-spacing:.04em;font-style:italic;animation:up .9s ease .38s both}.gold-rule{width:52px;height:1px;background:${G.gold};margin:10px auto 20px;opacity:0.6}.sec-tag{font-family:'Outfit',sans-serif;font-size:13px;color:${G.slate};letter-spacing:.12em;text-transform:uppercase;text-align:center;margin-bottom:28px;animation:up .9s ease .36s both}
.sub{font-size:15px;color:${G.slate};text-align:center;max-width:480px;line-height:1.8;margin-bottom:50px;font-weight:300;animation:up .9s ease .44s both}
.icard{background:${G.sur};border:1px solid ${G.bordG};border-radius:20px;padding:36px;width:100%;max-width:600px;box-shadow:0 40px 80px rgba(0,0,0,0.5);animation:up .9s ease .54s both;position:relative}
.icard::before{content:'';position:absolute;inset:-1px;border-radius:20px;background:linear-gradient(135deg,rgba(212,175,55,0.14),transparent 60%);pointer-events:none}
.tabs{display:flex;gap:4px;background:${G.elv};border-radius:10px;padding:4px;margin-bottom:28px}
.tab{flex:1;padding:8px 10px;border:none;background:transparent;color:${G.mist};font-family:'Outfit',sans-serif;font-size:12px;font-weight:500;border-radius:7px;cursor:pointer;transition:all .2s;white-space:nowrap}
.tab.on{background:${G.bg};color:${G.gold};border:1px solid rgba(212,175,55,0.2)}
.lbl{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:${G.mist};margin-bottom:10px;display:block;font-weight:500}
.row{display:flex;gap:10px}
.iw{flex:1;position:relative}
.inp{width:100%;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px 46px 14px 16px;font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:500;color:${G.white};outline:none;transition:border-color .2s;-moz-appearance:textfield}
.inp::-webkit-inner-spin-button,.inp::-webkit-outer-spin-button{-webkit-appearance:none}
.inp:focus{border-color:rgba(212,175,55,0.4)}
.inp-sm{font-size:16px;padding:12px 46px 12px 16px}
.sfx{position:absolute;right:14px;top:50%;transform:translateY(-50%);font-size:12px;color:${G.gold};font-weight:600;pointer-events:none}
.warn-box{background:rgba(232,160,0,0.08);border:1px solid rgba(232,160,0,0.25);border-radius:10px;padding:14px 16px;font-size:13px;color:${G.am};line-height:1.7;margin-bottom:20px}.advisory{background:rgba(146,64,14,0.12);border:1px solid rgba(212,175,55,0.25);border-radius:12px;padding:20px 24px;margin-bottom:24px}.adv-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.adv-title{font-family:'Cormorant Garamond',serif;font-size:16px;font-weight:600;color:${G.gold};letter-spacing:.04em}.adv-close{background:none;border:none;color:${G.mist};font-size:18px;cursor:pointer;line-height:1;padding:2px 6px;border-radius:4px}.adv-close:hover{color:${G.fog}}.adv-sections{display:flex;flex-direction:column;gap:12px}.adv-row{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px 14px}.adv-row-label{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:${G.mist};margin-bottom:6px;font-weight:600}.adv-row-content{font-size:13px;color:${G.fog};line-height:1.7}.adv-badge{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:4px;padding:2px 8px;margin-right:8px;vertical-align:middle}.adv-badge.unsuitable{background:rgba(224,85,85,0.2);color:#E05555;border:1px solid rgba(224,85,85,0.3)}.adv-badge.caution{background:rgba(240,165,0,0.15);color:#F0A500;border:1px solid rgba(240,165,0,0.25)}.adv-badge.acceptable{background:rgba(212,175,55,0.12);color:${G.gold};border:1px solid rgba(212,175,55,0.2)}.adv-badge.good,.adv-badge.ideal{background:rgba(39,174,120,0.15);color:#27AE78;border:1px solid rgba(39,174,120,0.25)}.adv-badge.unrealistic{background:rgba(224,85,85,0.2);color:#E05555;border:1px solid rgba(224,85,85,0.3)}.adv-badge.aggressive{background:rgba(240,165,0,0.15);color:#F0A500;border:1px solid rgba(240,165,0,0.25)}.adv-badge.realistic,.adv-badge.below_realistic{background:rgba(39,174,120,0.12);color:#27AE78;border:1px solid rgba(39,174,120,0.22)}.adv-badge.below_fd{background:rgba(212,175,55,0.12);color:${G.gold};border:1px solid rgba(212,175,55,0.2)}.adv-prob{margin-top:6px;font-size:11px;color:${G.mist}}.adv-prob strong{color:${G.fog}}.ra-table{width:100%;border-collapse:collapse;margin-top:8px}.ra-table th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:${G.mist};padding:6px 10px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.07)}.ra-table th:not(:first-child){text-align:right}.ra-table td{font-size:12px;color:${G.fog};padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.03)}.ra-table td:not(:first-child){text-align:right;font-family:'JetBrains Mono',monospace}.ra-table tr:last-child td{border-bottom:none}.ra-target-row td{color:${G.gold}!important;font-weight:600}.adv-proceed{margin-top:14px;display:flex;justify-content:flex-end}.adv-proceed-btn{font-size:12px;color:${G.mist};background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:6px 16px;cursor:pointer;font-family:Outfit,sans-serif}.adv-proceed-btn:hover{color:${G.gold};border-color:rgba(212,175,55,0.3)}.adv-icon{font-size:20px;flex-shrink:0;margin-top:1px}.adv-body{flex:1}.adv-cat{font-size:11px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;margin-bottom:4px}.adv-cat.aggressive{color:#F0A500}.adv-cat.unrealistic{color:#E05555}.adv-msg{font-size:13px;color:${G.fog};line-height:1.7;margin-bottom:10px}.adv-dismiss{font-size:11px;color:${G.mist};background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:4px 12px;cursor:pointer;font-family:Outfit,sans-serif}.adv-dismiss:hover{color:${G.gold};border-color:rgba(212,175,55,0.3)}
.implied{padding:10px 14px;border-radius:8px;background:rgba(212,175,55,0.08);border:1px solid rgba(212,175,55,0.15);font-size:13px;color:${G.gold};margin-bottom:18px;line-height:1.6}
.btn-p{width:100%;padding:15px;background:linear-gradient(135deg,${G.gold},${G.goldD});border:none;border-radius:11px;font-family:'Outfit',sans-serif;font-size:15px;font-weight:600;color:${G.bg};cursor:pointer;transition:all .2s;margin-bottom:2px}
.btn-p:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 10px 40px rgba(212,175,55,0.35)}
.btn-p:disabled{opacity:.4;cursor:not-allowed}
.note{font-size:11px;color:${G.mist};text-align:center;margin-top:14px;line-height:1.7}
.loading{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px}
.lt{font-family:'Cormorant Garamond',serif;font-size:32px;color:${G.white}}
.dots{display:flex;gap:8px}
.dot{width:8px;height:8px;background:${G.gold};border-radius:50%;animation:pulse 1.3s ease-in-out infinite}
.dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}
.lstep{font-size:13px;color:${G.mist};animation:up .5s ease both}
.rbar{background:rgba(9,12,17,0.96);backdrop-filter:blur(16px);border-bottom:1px solid ${G.bord};padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}.sec-nav{display:none;position:sticky;top:57px;z-index:90;background:rgba(9,12,17,0.97);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.05);padding:0 16px;overflow-x:auto;white-space:nowrap;scrollbar-width:none}.sec-nav::-webkit-scrollbar{display:none}.sec-nav-btn{display:inline-block;padding:8px 14px;font-size:11px;color:rgba(255,255,255,0.35);font-family:Outfit,sans-serif;cursor:pointer;border:none;background:none;border-bottom:2px solid transparent;transition:all .18s;letter-spacing:.03em;white-space:nowrap}.sec-nav-btn:hover{color:${G.gold}}.sec-nav-btn.active{color:${G.gold};border-bottom-color:${G.gold}}@media(max-width:768px){.sec-nav{display:block}}
.rbar-l{display:flex;align-items:center;gap:14px}
.rbn{font-family:'Cormorant Garamond',serif;font-size:20px;color:${G.gold};font-weight:600}
.pill{background:rgba(212,175,55,0.1);border:1px solid rgba(212,175,55,0.2);border-radius:20px;padding:5px 14px;font-size:12px;color:${G.gold};font-weight:500}
.bbtn{background:none;border:1px solid ${G.bord};color:${G.slate};padding:6px 14px;border-radius:8px;font-size:12px;cursor:pointer;font-family:'Outfit',sans-serif;transition:all .2s}
.bbtn:hover{color:${G.fog};border-color:rgba(255,255,255,0.15)}
.rbody{max-width:1160px;margin:0 auto;padding:32px 24px 60px}
.philo{background:${G.sur};border:1px solid ${G.bord};border-left:3px solid ${G.gold};border-radius:14px;padding:20px 26px;margin-bottom:24px;text-align:center}
.pt{font-family:'Cormorant Garamond',serif;font-size:13px;color:${G.gold};letter-spacing:.1em;text-transform:uppercase;margin-bottom:9px}
.pb{font-size:13px;color:${G.mist};line-height:1.9;max-width:720px;margin:0 auto}
.pb strong{color:${G.fog};font-weight:500}
.card{background:${G.sur};border:1px solid ${G.bord};border-radius:16px;overflow:hidden;margin-bottom:20px}
.ch{padding:17px 22px;border-bottom:1px solid ${G.bord};display:flex;align-items:center;justify-content:space-between}
.ct{font-family:'Cormorant Garamond',serif;font-size:19px;color:${G.white};font-weight:600}
.badge{font-size:11px;padding:4px 12px;border-radius:20px;font-weight:600}
.bg-g{background:${G.emBg};color:${G.em}}.bg-a{background:${G.amBg};color:${G.am}}.bg-r{background:${G.roBg};color:${G.ro}}.bg-z{background:${G.azBg};color:${G.az}}.bg-gold{background:rgba(212,175,55,0.1);color:${G.gold}}
.cb{padding:20px 22px}
.sc{background:${G.elv};border-radius:12px;padding:20px;border-left:3px solid}
.opts{display:flex;flex-direction:column;gap:8px;margin-top:14px}
.opt{padding:11px 16px;border:1px solid ${G.bord};border-radius:8px;background:transparent;color:${G.slate};font-family:'Outfit',sans-serif;font-size:13px;text-align:left;cursor:pointer;transition:all .2s;line-height:1.5}
.opt:hover{border-color:rgba(212,175,55,0.3);color:${G.fog};background:rgba(212,175,55,0.04)}
.opt.sel{border-color:${G.gold};color:${G.gold};background:rgba(212,175,55,0.08)}
.pbox{background:${G.elv};border-radius:12px;padding:20px 22px;margin-top:18px;border:1px solid}
.spec{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:26px}
@media(max-width:768px){.spec{grid-template-columns:repeat(2,1fr)}}
.arch{background:${G.sur};border:2px solid ${G.bord};border-radius:14px;padding:18px 14px;cursor:pointer;transition:all .25s;text-align:center}
.arch:hover{transform:translateY(-2px)}
.arch.sel{border-color:var(--ac);background:rgba(var(--ar),.07)}
.exec{background:linear-gradient(135deg,rgba(212,175,55,0.09),rgba(212,175,55,0.04));border:1px solid rgba(212,175,55,0.2);border-radius:16px;padding:24px 28px;display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:22px}
@media(max-width:700px){.exec{flex-direction:column}}
.exb{display:flex;gap:10px;flex-shrink:0}
.bg2{padding:11px 22px;background:linear-gradient(135deg,${G.gold},${G.goldD});border:none;border-radius:9px;font-family:'Outfit',sans-serif;font-size:13px;font-weight:600;color:${G.bg};cursor:pointer;transition:all .2s}
.bg2:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(212,175,55,0.3)}
.bo{padding:11px 22px;background:transparent;border:1px solid rgba(212,175,55,0.3);border-radius:9px;font-family:'Outfit',sans-serif;font-size:13px;color:${G.gold};cursor:pointer}
.fg{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
@media(max-width:1100px){.fg{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.fg{grid-template-columns:repeat(2,1fr)}}
.fc{background:${G.elv};border-radius:12px;padding:16px;border:1px solid ${G.bord}}
.fw{font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:500;color:${G.gold};margin-bottom:8px}
.fn{font-size:11px;font-weight:600;color:${G.white};line-height:1.4;margin-bottom:4px}
.fcat{font-size:10px;color:${G.mist};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
.fm{font-size:11px;color:${G.slate};line-height:1.9}.fm span{color:${G.fog};font-weight:500}
.tier{display:inline-flex;align-items:center;gap:4px;font-size:10px;padding:3px 8px;border-radius:4px;margin-top:8px;font-weight:600}
.t1{background:${G.emBg};color:${G.em}}.t2{background:${G.azBg};color:${G.az}}.t3{background:${G.amBg};color:${G.am}}
.mt{width:100%;border-collapse:collapse}
.mt th{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:${G.mist};padding:10px 14px;text-align:right;border-bottom:1px solid ${G.bord};font-weight:600}
.mt th:first-child{text-align:left}
.mt td{padding:12px 14px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:13px;color:${G.fog};border-bottom:1px solid rgba(255,255,255,0.03)}
.mt td:first-child{text-align:left;font-family:'Outfit',sans-serif;font-size:12px;color:${G.mist};font-weight:500}
.mt tr:last-child td{border-bottom:none}
.gc{color:${G.gold};font-weight:500}.ec{color:${G.em}}.zc{color:${G.az}}.dc{color:${G.mist};font-size:12px}.rc{color:${G.ro}}
.cg{display:grid;grid-template-columns:150px 1fr;gap:28px;align-items:start}
@media(max-width:600px){.cg{grid-template-columns:1fr}}
.dial{width:120px;height:120px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;border:3px solid}
.ds{font-family:'JetBrains Mono',monospace;font-size:34px;font-weight:500;line-height:1}
.dof{font-size:10px;letter-spacing:.1em;text-transform:uppercase;margin-top:3px}
.cf{margin-bottom:14px}.cfh{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.cfn{font-size:12px;color:${G.slate}}.cfv{font-size:11px;color:${G.fog};font-style:italic}
.bar{height:4px;background:${G.elv};border-radius:2px;overflow:hidden}
.bf{height:100%;border-radius:2px}
.sg{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:700px){.sg{grid-template-columns:1fr}}
.sk{background:${G.elv};border-radius:12px;padding:17px;border-top:3px solid ${G.ro}}
.dl{list-style:none;display:flex;flex-direction:column;gap:10px}
.di{display:flex;gap:12px;align-items:flex-start;padding:13px 15px;background:rgba(216,72,72,0.05);border-radius:10px;border-left:3px solid ${G.ro}}.di-pro{display:flex;gap:12px;align-items:flex-start;padding:13px 15px;background:rgba(39,174,120,0.05);border-radius:10px;border-left:3px solid #27AE78}
.mg{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(max-width:700px){.mg{grid-template-columns:1fr}}
.mi{display:flex;gap:10px;align-items:flex-start;background:${G.elv};border-radius:8px;padding:11px 13px}
.cog{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:700px){.cog{grid-template-columns:repeat(2,1fr)}}
.coc{background:${G.elv};border-radius:12px;padding:18px 14px;text-align:center}
.coc.pri{background:rgba(212,175,55,0.08);border:1px solid rgba(212,175,55,0.2)}
.frg{display:flex;flex-direction:column;gap:8px}
.frr{display:flex;align-items:center;justify-content:space-between;background:${G.elv};border-radius:8px;padding:10px 14px}
.fdot{width:8px;height:8px;border-radius:50%}.fdw{background:#F0A500}
.fdg{background:${G.em}}.fda{background:${G.am}}
.slbl{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:${G.gold};margin-bottom:14px}
.itax{margin-top:14px;padding:13px 15px;background:rgba(232,160,0,0.07);border:1px solid rgba(232,160,0,0.2);border-radius:10px;font-size:12px;color:${G.am};line-height:1.7}
.customize-toggle{display:flex;align-items:center;gap:8px;background:transparent;border:1px solid rgba(212,175,55,0.25);border-radius:8px;padding:8px 16px;color:${G.mist};font-family:'Outfit',sans-serif;font-size:12px;cursor:pointer;transition:all .2s;margin-top:16px}.customize-toggle:hover{border-color:rgba(212,175,55,0.5);color:${G.gold}}.customize-panel{margin-top:16px;border:1px solid rgba(212,175,55,0.15);border-radius:12px;padding:20px;background:rgba(212,175,55,0.03)}.cx-search{width:100%;background:${G.elv};border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:10px 14px;color:${G.white};font-family:'Outfit',sans-serif;font-size:13px;outline:none;box-sizing:border-box}.cx-search:focus{border-color:rgba(212,175,55,0.35)}.cx-results{margin-top:4px;background:${G.sur};border:1px solid ${G.bord};border-radius:8px;overflow:hidden}.cx-result{padding:12px 14px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,0.04);transition:background .15s}.cx-result:last-child{border-bottom:none}.cx-result:hover{background:rgba(212,175,55,0.06)}.cx-result-name{font-size:13px;color:${G.white};margin-bottom:2px}.cx-result-meta{font-size:11px;color:${G.mist}}.cx-compare{margin-top:16px}.cx-table{width:100%;border-collapse:collapse;margin-top:10px}.cx-table th{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:${G.mist};padding:8px 10px;text-align:left;border-bottom:1px solid ${G.bord}}.cx-table th:not(:first-child){text-align:right}.cx-table td{padding:9px 10px;font-size:12px;color:${G.fog};border-bottom:1px solid rgba(255,255,255,0.03)}.cx-table td:not(:first-child){text-align:right;font-family:'JetBrains Mono',monospace}.cx-table tr:last-child td{border-bottom:none}.cx-better{color:#27AE78}.cx-worse{color:#E05555}.cx-impact{margin-top:12px;padding:12px 14px;background:rgba(255,255,255,0.03);border-radius:8px;font-size:12px;color:${G.mist};line-height:1.7}.cx-actions{display:flex;gap:10px;margin-top:14px}.cx-accept{flex:1;padding:10px;background:rgba(39,174,120,0.15);border:1px solid rgba(39,174,120,0.3);border-radius:8px;color:#27AE78;font-family:'Outfit',sans-serif;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}.cx-accept:hover{background:rgba(39,174,120,0.25)}.cx-reject{flex:1;padding:10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:${G.mist};font-family:'Outfit',sans-serif;font-size:13px;cursor:pointer;transition:all .2s}.cx-reject:hover{background:rgba(255,255,255,0.07)}.cx-applied{display:inline-flex;align-items:center;gap:5px;font-size:10px;background:rgba(39,174,120,0.12);border:1px solid rgba(39,174,120,0.25);border-radius:6px;padding:3px 8px;color:#27AE78;margin-left:8px}.cx-fund-target{border:1.5px solid rgba(212,175,55,0.6) !important;background:rgba(212,175,55,0.06) !important;position:relative}.cx-fund-replaced{border:1.5px solid rgba(39,174,120,0.4) !important;background:rgba(39,174,120,0.05) !important;position:relative}.cx-target-label{position:absolute;top:6px;right:8px;font-size:9px;color:${G.gold};letter-spacing:.05em;text-transform:uppercase;font-weight:600}.cx-replaced-label{position:absolute;top:6px;right:8px;font-size:9px;color:#27AE78;letter-spacing:.05em;font-weight:600}.cx-search:disabled{opacity:.45;cursor:not-allowed}.match-best{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;background:rgba(39,174,120,0.15);border:1px solid rgba(39,174,120,0.3);border-radius:4px;padding:2px 7px;color:#27AE78;margin-top:7px;display:inline-block}.match-label{font-size:9px;color:rgba(255,255,255,0.3);margin-top:6px;letter-spacing:.04em}.gen-more-cta{margin:32px 0 0;padding:28px 24px;border:1px dashed rgba(212,175,55,0.25);border-radius:16px;text-align:center;background:rgba(212,175,55,0.02)}.gen-more-title{font-family:Cormorant Garamond,serif;font-size:20px;color:${G.white};margin-bottom:8px;font-weight:600}.gen-more-sub{font-size:13px;color:${G.mist};line-height:1.7;margin-bottom:20px;max-width:480px;margin-left:auto;margin-right:auto}.gen-more-btn{background:transparent;border:1px solid rgba(212,175,55,0.4);border-radius:10px;padding:12px 32px;color:${G.gold};font-family:Outfit,sans-serif;font-size:14px;font-weight:600;cursor:pointer;letter-spacing:.04em;transition:all .2s}.gen-more-btn:hover{background:rgba(212,175,55,0.08);border-color:rgba(212,175,55,0.7)}.gen-more-btn:disabled{opacity:.4;cursor:not-allowed}.alt-round-header{display:flex;align-items:center;gap:14px;margin:40px 0 20px}.alt-round-divider{flex:1;height:1px;background:linear-gradient(90deg,rgba(212,175,55,0.2),transparent)}.alt-round-label{font-family:Cormorant Garamond,serif;font-size:16px;color:${G.white};white-space:nowrap;letter-spacing:.04em}.alt-round-note{font-size:11px;color:${G.mist};margin-top:4px;text-align:center}.gen-loading{display:flex;flex-direction:column;align-items:center;gap:16px;padding:40px;color:${G.mist};font-size:13px}.gen-spinner{width:36px;height:36px;border:2px solid rgba(212,175,55,0.15);border-top-color:rgba(212,175,55,0.7);border-radius:50%;animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.gen-exhausted{margin:24px 0;padding:16px 20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;text-align:center;font-size:12px;color:}.byob-entry{display:inline-flex;align-items:center;gap:8px;background:transparent;border:1px solid rgba(212,175,55,0.3);border-radius:10px;padding:10px 22px;color:${G.gold};font-family:'Outfit',sans-serif;font-size:13px;cursor:pointer;transition:all .2s;margin-top:12px}.byob-entry:hover{background:rgba(212,175,55,0.07);border-color:rgba(212,175,55,0.6)}.byob-screen{min-height:100vh;background:${G.bg};padding:48px 24px 88px}.byob-inner{max-width:780px;margin:0 auto}.byob-back{background:none;border:none;color:${G.mist};font-size:13px;cursor:pointer;font-family:Outfit,sans-serif;display:flex;align-items:center;gap:6px;padding:0;margin-bottom:32px}.byob-back:hover{color:${G.gold}}.byob-title{font-family:'Cormorant Garamond',serif;font-size:36px;color:${G.white};margin-bottom:6px;font-weight:600}.byob-sub{font-size:13px;color:${G.mist};margin-bottom:36px;line-height:1.7}.byob-search{position:relative}.byob-input{width:100%;background:${G.elv};border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:13px 16px;color:${G.white};font-family:'Outfit',sans-serif;font-size:14px;outline:none;box-sizing:border-box}.byob-input:focus{border-color:rgba(212,175,55,0.4)}.byob-dropdown{position:absolute;top:calc(100% + 4px);left:0;right:0;background:${G.sur};border:1px solid ${G.bord};border-radius:10px;overflow:hidden;z-index:50;box-shadow:0 8px 32px rgba(0,0,0,0.4)}.byob-opt{padding:13px 16px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,0.04);transition:background .12s}.byob-opt:last-child{border-bottom:none}.byob-opt:hover{background:rgba(212,175,55,0.07)}.byob-opt-name{font-size:13px;color:${G.white};margin-bottom:2px}.byob-opt-meta{font-size:11px;color:${G.mist}}.byob-fund-list{margin-top:20px}.byob-fund-row{display:flex;align-items:center;gap:12px;padding:14px 16px;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:10px;margin-bottom:8px}.byob-fund-info{flex:1;min-width:0}.byob-fund-name{font-size:13px;color:${G.white};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.byob-fund-meta{font-size:11px;color:${G.mist};margin-top:2px}.byob-weight-input{width:64px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:6px 10px;color:${G.white};font-family:'JetBrains Mono',monospace;font-size:13px;text-align:right;outline:none}.byob-weight-input:focus{border-color:rgba(212,175,55,0.4)}.byob-pct{font-size:12px;color:${G.mist}}.byob-remove{background:none;border:none;color:${G.mist};font-size:16px;cursor:pointer;padding:4px;line-height:1;border-radius:4px}.byob-remove:hover{color:#E05555}.byob-total{text-align:right;font-size:12px;margin-top:8px;font-family:'JetBrains Mono',monospace}.byob-total.ok{color:#27AE78}.byob-total.warn{color:#E05555}.byob-controls{display:flex;align-items:center;gap:16px;margin-top:28px;flex-wrap:wrap}.byob-horizon-wrap{display:flex;align-items:center;gap:10px}.byob-horizon-label{font-size:12px;color:${G.mist}}.byob-horizon-input{width:56px;background:${G.elv};border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 10px;color:${G.white};font-family:'JetBrains Mono',monospace;font-size:14px;text-align:center;outline:none}.byob-horizon-input:focus{border-color:rgba(212,175,55,0.4)}.byob-analyse-btn{flex:1;min-width:200px;padding:13px 24px;background:rgba(212,175,55,0.12);border:1px solid rgba(212,175,55,0.4);border-radius:10px;color:${G.gold};font-family:'Outfit',sans-serif;font-size:14px;font-weight:600;cursor:pointer;letter-spacing:.04em;transition:all .2s}.byob-analyse-btn:hover{background:rgba(212,175,55,0.2);border-color:rgba(212,175,55,0.7)}.byob-analyse-btn:disabled{opacity:.4;cursor:not-allowed}.byob-results{margin-top:40px}.byob-result-header{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:28px}.byob-metric-card{flex:1;min-width:160px;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:20px 22px}.byob-metric-label{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:${G.mist};margin-bottom:8px}.byob-metric-value{font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:500;color:${G.gold}}.byob-metric-sub{font-size:11px;color:${G.mist};margin-top:4px}.byob-table{width:100%;border-collapse:collapse;margin-top:6px}.byob-table th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:${G.mist};padding:8px 12px;text-align:left;border-bottom:1px solid ${G.bord}}.byob-table th:not(:first-child){text-align:right}.byob-table td{font-size:12px;color:${G.fog};padding:11px 12px;border-bottom:1px solid rgba(255,255,255,0.03)}.byob-table td:not(:first-child){text-align:right;font-family:'JetBrains Mono',monospace}.byob-table tr:last-child td{border-bottom:none}.byob-score-bar{display:inline-block;width:36px;height:4px;border-radius:2px;margin-left:8px;vertical-align:middle}.byob-section{margin-top:24px;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:20px 22px}.byob-section-title{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:${G.mist};margin-bottom:14px;font-weight:600}.byob-warn-item{font-size:12px;color:${G.fog};line-height:1.7;margin-bottom:8px;padding-left:14px;position:relative}.byob-warn-item::before{content:'';position:absolute;left:0;top:7px;width:5px;height:5px;border-radius:50%;background:#F0A500}.byob-warn-item.danger::before{background:#E05555}.byob-suggestion{background:rgba(39,174,120,0.06);border:1px solid rgba(39,174,120,0.15);border-radius:10px;padding:14px 16px;margin-bottom:10px}.byob-sug-header{font-size:12px;color:${G.fog};margin-bottom:6px}.byob-sug-funds{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.byob-sug-from{font-size:13px;color:${G.mist};text-decoration:line-through}.byob-sug-arrow{color:${G.gold};font-size:16px}.byob-sug-to{font-size:13px;color:#27AE78;font-weight:500}.byob-sug-delta{font-size:11px;color:#27AE78;background:rgba(39,174,120,0.12);border-radius:4px;padding:2px 7px;margin-left:6px}.byob-sug-rationale{font-size:11px;color:${G.mist};margin-top:6px;line-height:1.6}.nav-refresh-btn{margin-left:auto;background:transparent;border:1px solid rgba(212,175,55,0.3);border-radius:8px;padding:5px 14px;color:${G.mist};font-family:'Outfit',sans-serif;font-size:12px;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:6px}.nav-refresh-btn:hover{border-color:rgba(212,175,55,0.6);color:${G.gold}}.nav-refresh-btn:disabled{opacity:.5;cursor:not-allowed}.nav-refresh-btn.spinning{color:${G.gold};border-color:rgba(212,175,55,0.5)}@keyframes spin-icon{to{transform:rotate(360deg)}}.spinning span{display:inline-block;animation:spin-icon 1s linear infinite}.pros-cons-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:600px){.pros-cons-grid{grid-template-columns:1fr}}.pros-col,.cons-col{}.pros-col-header{font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:#27AE78;margin-bottom:12px;display:flex;align-items:center;gap:6px}.cons-col-header{font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:#E05555;margin-bottom:12px;display:flex;align-items:center;gap:6px}.pros-col-icon{font-size:14px;color:#27AE78}.cons-col-icon{font-size:14px;color:#E05555}.byob-suggestion{cursor:pointer;user-select:none}.byob-sug-selected{background:rgba(39,174,120,0.1);border-color:rgba(39,174,120,0.35)}.byob-sug-check{width:20px;height:20px;min-width:20px;border:1.5px solid rgba(39,174,120,0.35);border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:11px;color:#27AE78;background:rgba(39,174,120,0.06);margin-top:2px;transition:all .15s}.byob-sug-check.checked{background:rgba(39,174,120,0.2);border-color:#27AE78}.byob-sug-replace-btn{margin-top:16px;width:100%;padding:13px 24px;background:rgba(39,174,120,0.14);border:1px solid rgba(39,174,120,0.4);border-radius:10px;color:#27AE78;font-family:'Outfit',sans-serif;font-size:14px;font-weight:600;cursor:pointer;letter-spacing:.03em;transition:all .2s}.byob-sug-replace-btn:hover{background:rgba(39,174,120,0.24);border-color:rgba(39,174,120,0.65)}.byob-sug-replace-btn:disabled{opacity:.4;cursor:not-allowed}@keyframes up{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}.ai-toggle-btn{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,rgba(212,175,55,0.12),rgba(139,92,246,0.1));border:1px solid rgba(212,175,55,0.35);border-radius:9px;padding:7px 16px;color:${G.gold};font-family:"Outfit",sans-serif;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;letter-spacing:.04em}.ai-toggle-btn:hover{background:linear-gradient(135deg,rgba(212,175,55,0.2),rgba(139,92,246,0.15));border-color:rgba(212,175,55,0.6)}.ai-toggle-btn.active{background:linear-gradient(135deg,rgba(212,175,55,0.18),rgba(139,92,246,0.18));border-color:rgba(212,175,55,0.7)}.ai-panel{margin-top:16px;background:linear-gradient(135deg,rgba(17,14,26,0.98),rgba(20,16,32,0.98));border:1px solid rgba(212,175,55,0.2);border-radius:16px;padding:22px 24px;box-shadow:0 8px 32px rgba(0,0,0,0.4),inset 0 1px 0 rgba(212,175,55,0.08)}.ai-panel-header{display:flex;align-items:center;gap:10px;margin-bottom:18px}.ai-panel-icon{font-size:20px;flex-shrink:0}.ai-panel-title{font-family:"Cormorant Garamond",serif;font-size:16px;color:${G.gold};font-weight:600;letter-spacing:.04em}.ai-panel-sub{font-size:11px;color:${G.mist};margin-top:2px}.ai-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}.ai-chip{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);border-radius:20px;padding:5px 13px;font-size:11.5px;color:${G.fog};cursor:pointer;transition:all .15s;font-family:"Outfit",sans-serif}.ai-chip:hover{background:rgba(212,175,55,0.08);border-color:rgba(212,175,55,0.3);color:${G.gold}}.ai-input-row{display:flex;gap:10px}.ai-input{flex:1;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:9px;padding:10px 14px;color:${G.white};font-family:"Outfit",sans-serif;font-size:13px;outline:none}.ai-input:focus{border-color:rgba(212,175,55,0.4)}.ai-send-btn{padding:10px 20px;background:rgba(212,175,55,0.15);border:1px solid rgba(212,175,55,0.4);border-radius:9px;color:${G.gold};font-family:"Outfit",sans-serif;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;white-space:nowrap}.ai-send-btn:hover{background:rgba(212,175,55,0.25)}.ai-send-btn:disabled{opacity:.4;cursor:not-allowed}.ai-response{margin-top:16px;font-size:13px;color:${G.fog};line-height:1.85;white-space:pre-wrap}.ai-response strong{color:${G.fog};font-weight:600}.ai-disclaimer{margin-top:12px;font-size:11px;color:${G.mist};opacity:.7;font-style:italic}.ai-thinking{display:flex;align-items:center;gap:8px;color:${G.mist};font-size:12px;margin-top:14px}.ai-thinking-dots span{display:inline-block;width:5px;height:5px;border-radius:50%;background:${G.gold};animation:ai-pulse 1.2s ease-in-out infinite;margin:0 2px}.ai-thinking-dots span:nth-child(2){animation-delay:.2s}.ai-thinking-dots span:nth-child(3){animation-delay:.4s}@keyframes ai-pulse{0%,80%,100%{opacity:.2;transform:scale(.8)}40%{opacity:1;transform:scale(1)}}
.about-screen{min-height:100vh;background:${G.bg};padding:72px 24px 96px}.about-inner{max-width:760px;margin:0 auto}.about-back{background:none;border:none;color:${G.mist};font-size:13px;cursor:pointer;font-family:Outfit,sans-serif;display:flex;align-items:center;gap:6px;padding:0;margin-bottom:48px}.about-back:hover{color:${G.gold}}.about-hero{display:flex;align-items:flex-start;gap:32px;margin-bottom:56px}.about-mark{width:80px;height:80px;background:linear-gradient(145deg,${G.gold},${G.goldD});border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:32px;flex-shrink:0;box-shadow:0 0 32px rgba(212,175,55,0.35)}.about-headline{font-family:"Cormorant Garamond",serif;font-size:clamp(28px,5vw,46px);color:${G.white};font-weight:600;line-height:1.15;margin-bottom:12px}.about-tagline{font-size:15px;color:${G.gold};font-style:italic;font-family:"Cormorant Garamond",serif;margin-bottom:0}.about-section{margin-bottom:48px}.about-section-title{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:${G.gold};font-weight:700;margin-bottom:20px}.about-card{background:${G.sur};border:1px solid ${G.bord};border-radius:16px;padding:28px 32px;margin-bottom:16px}.about-card-title{font-family:"Cormorant Garamond",serif;font-size:20px;color:${G.white};font-weight:600;margin-bottom:10px}.about-card-body{font-size:14px;color:${G.fog};line-height:1.85}.about-card-body strong{color:${G.white}}.about-builder{background:linear-gradient(135deg,rgba(212,175,55,0.07),rgba(212,175,55,0.02));border:1px solid rgba(212,175,55,0.2);border-radius:20px;padding:32px}.about-builder-name{font-family:"Cormorant Garamond",serif;font-size:32px;color:${G.gold};font-weight:700;margin-bottom:4px}.about-builder-role{font-size:13px;color:${G.mist};margin-bottom:20px;letter-spacing:.04em}.about-builder-body{font-size:14px;color:${G.fog};line-height:1.85}.about-builder-body strong{color:${G.white}}.about-principle{display:flex;gap:16px;padding:18px 20px;border-radius:12px;background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.05);margin-bottom:10px}.about-principle-num{font-family:"JetBrains Mono",monospace;font-size:11px;color:${G.gold};font-weight:700;flex-shrink:0;margin-top:2px}.about-principle-text{font-size:13px;color:${G.fog};line-height:1.75}.about-principle-text strong{color:${G.white}}.about-lang-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.about-lang-chip{padding:5px 14px;border:1px solid rgba(212,175,55,0.25);border-radius:20px;font-size:12px;color:${G.mist};font-family:Outfit,sans-serif}.health-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;cursor:pointer;transition:all .3s}.health-dot.healthy{background:#27AE78;box-shadow:0 0 6px rgba(39,174,120,0.7)}.health-dot.degraded{background:#E8A000;box-shadow:0 0 6px rgba(232,160,0,0.7)}.health-dot.critical{background:#D84848;box-shadow:0 0 6px rgba(216,72,72,0.7);animation:health-pulse 1.2s ease-in-out infinite}.health-dot.starting{background:rgba(255,255,255,0.2)}@keyframes health-pulse{0%,100%{opacity:.4;transform:scale(.85)}50%{opacity:1;transform:scale(1.15)}}.health-panel{position:absolute;top:calc(100% + 10px);right:0;background:rgba(16,21,31,0.98);border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:18px 20px;min-width:320px;box-shadow:0 12px 40px rgba(0,0,0,0.5);z-index:300;backdrop-filter:blur(16px)}.health-panel-title{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,0.4);margin-bottom:14px;font-weight:600}.health-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.04)}.health-row:last-child{border-bottom:none}.health-row-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}.health-row-name{font-size:12px;color:rgba(255,255,255,0.55);flex:0 0 80px}.health-row-detail{font-size:11px;color:rgba(255,255,255,0.3);flex:1;line-height:1.4}.health-run-btn{margin-top:12px;width:100%;padding:7px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:7px;color:rgba(255,255,255,0.35);font-family:Outfit,sans-serif;font-size:11px;cursor:pointer;transition:all .2s}.health-run-btn:hover{border-color:rgba(212,175,55,0.3);color:${G.gold}}.health-wrap{position:relative;display:flex;align-items:center;gap:6px}@keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}
@media(max-width:768px){.fg{grid-template-columns:1fr 1fr}.cog{flex-direction:column}.coc{min-width:auto;width:100%}.card{border-radius:12px;margin-bottom:16px}.ai-chips{gap:6px}.ai-chip{font-size:10.5px;padding:4px 10px}.byob-result-header{flex-direction:column}.byob-metric-card{min-width:auto}.gen-more-title{font-size:18px}}
@media(max-width:480px){.fg{grid-template-columns:1fr}.ai-send-btn{width:100%}.byob-controls{flex-direction:column}.byob-analyse-btn{min-width:auto;width:100%}.cog{gap:10px}.cx-actions{flex-direction:column}.ch{flex-wrap:wrap;gap:6px}.badge{font-size:9px}}
.hero-bg-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.07;pointer-events:none;z-index:0}
.hero-deco{position:absolute;right:0;top:50%;transform:translateY(-50%);width:300px;pointer-events:none;-webkit-mask-image:radial-gradient(ellipse 80% 100% at 80% 50%,black 30%,transparent 80%);mask-image:radial-gradient(ellipse 80% 100% at 80% 50%,black 30%,transparent 80%);animation:deco-in 1.4s ease 0.8s both;opacity:0.9}
@keyframes deco-in{from{opacity:0;transform:translateY(-50%) translateX(40px)}to{opacity:0.9;transform:translateY(-50%) translateX(0)}}
@media(max-width:1200px){.hero-deco{display:none}}
.hero-deco-left{position:absolute;left:0;top:50%;transform:translateY(-50%) scaleX(-1);width:300px;pointer-events:none;-webkit-mask-image:radial-gradient(ellipse 80% 100% at 20% 50%,black 30%,transparent 80%);mask-image:radial-gradient(ellipse 80% 100% at 20% 50%,black 30%,transparent 80%);animation:deco-in 1.4s ease 0.8s both;opacity:0.9}
@media(max-width:1200px){.hero-deco-left{display:none}}
.inp::placeholder{color:rgba(80,88,112,0.38);font-family:'Outfit',sans-serif}
.input-hint{font-size:13px;margin-top:8px;line-height:1.6;background:rgba(212,175,55,0.07);border:1px solid rgba(212,175,55,0.18);border-radius:8px;padding:9px 13px}
.pros-col-header{font-size:11px!important;letter-spacing:.08em!important;padding:9px 14px;background:rgba(39,174,120,0.07);border:1px solid rgba(39,174,120,0.18);border-radius:8px;margin-bottom:14px!important}
.cons-col-header{font-size:11px!important;letter-spacing:.08em!important;padding:9px 14px;background:rgba(216,72,72,0.07);border:1px solid rgba(216,72,72,0.18);border-radius:8px;margin-bottom:14px!important}
.site-footer{background:#10151F;border-top:1px solid rgba(255,255,255,0.06);padding:40px 24px 90px}
.site-footer-inner{max-width:1160px;margin:0 auto;display:flex;align-items:flex-start;justify-content:space-between;gap:32px;flex-wrap:wrap}
.footer-brand-name{font-family:'Cormorant Garamond',serif;font-size:22px;color:#D4AF37;font-weight:600;margin-bottom:4px}
.footer-brand-tag{font-size:12px;color:#505870;font-style:italic;font-family:'Cormorant Garamond',serif}
.footer-links{display:flex;gap:20px;flex-wrap:wrap;align-items:center;margin-top:8px}
.footer-link{font-size:12px;color:#505870;background:none;border:none;cursor:pointer;font-family:'Outfit',sans-serif;padding:0;transition:color .2s}
.footer-link:hover{color:#D4AF37}
.footer-legal{font-size:10px;color:rgba(255,255,255,0.18);width:100%;margin-top:24px;line-height:1.8;border-top:1px solid rgba(255,255,255,0.05);padding-top:18px}
`;

export default function App() {
  const { t, i18n } = useTranslation();
  const [screen, setScreen] = useState("hero");
  const [mode, setMode] = useState("return");
  const [cagr, setCAGR] = useState("");
  const [yrs, setYrs] = useState("");
  const [corpus, setCorpus] = useState("");
  const [ls, setLs] = useState("");
  const [sip, setSip] = useState("");
  const [inputWarn, setInputWarn] = useState("");
  const [curationResult, setCurationResult] = useState(null);
  const [selectedArch, setSelectedArch] = useState(null);
  const [bStep, setBStep] = useState(0);
  const [bAns, setBAns] = useState({});
  const [bDone, setBDone] = useState(false);
  const [bProf, setBProf] = useState(null);
  const [showBehav, setShowBehav] = useState(true);
  const [freshness, setFreshness] = useState(null);
  const [navRefreshing, setNavRefreshing] = useState(false);
  const [navRefreshMsg, setNavRefreshMsg] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [cagrAdvisory, setCagrAdvisory] = useState(null);
  const [sysHealth, setSysHealth] = useState(null);
  const [healthOpen, setHealthOpen] = useState(false);
  const [approxHorizon, setApproxHorizon] = useState(null);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [customizeTargetFund, setCustomizeTargetFund] = useState(null);
  const [rebalOpen, setRebalOpen] = useState(true);
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [aiToolOpen, setAiToolOpen] = useState(null);
  const [rebalValues, setRebalValues] = useState({});
  const [ltcgInputs, setLtcgInputs] = useState({ purchase: '', current: '', months: '', fundType: 'equity' });
  const [ltcgResult, setLtcgResult] = useState(null);
  const [sipInputs, setSipInputs] = useState({ targetCorpus: '', horizon: '', cagr: '' });
  const [customizeSearch, setCustomizeSearch] = useState('');
  const [customizeResults, setCustomizeResults] = useState([]);
  const [customizeComparing, setCustomizeComparing] = useState(null);
  const [customizeApplied, setCustomizeApplied] = useState(null);
  const [customizeLoading, setCustomizeLoading] = useState(false);
  const [altRounds, setAltRounds] = useState([]);
  const [altLoading, setAltLoading] = useState(false);
  const [altError, setAltError] = useState(null);
  const [altPoolExhausted, setAltPoolExhausted] = useState(false);
  // Custom builder
  const [cbFunds, setCbFunds] = useState([]);
  const [cbSearch, setCbSearch] = useState('');
  const [cbResults, setCbResults] = useState([]);
  const [cbHorizon, setCbHorizon] = useState('7');
  const [cbLoading, setCbLoading] = useState(false);
  const [cbAnalysis, setCbAnalysis] = useState(null);
  const [cbError, setCbError] = useState(null);
  const cbResultsRef = useRef(null);
  const [cbSelectedSwaps, setCbSelectedSwaps] = useState(new Set());
  const [pwaPrompt, setPwaPrompt] = useState(null);
  const [user, setUser] = useState(null);
  const [authModal, setAuthModal] = useState(false);
  const [authTab, setAuthTab] = useState("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authName, setAuthName] = useState("");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [savedList, setSavedList] = useState([]);
  const [savedPanel, setSavedPanel] = useState(false);
  const [savedMsg, setSavedMsg] = useState({});
  const [pfFunds, setPfFunds] = useState([]);
  const [pfSearch, setPfSearch] = useState('');
  const [pfResults, setPfResults] = useState([]);
  const [pfSearching, setPfSearching] = useState(false);
  const [pfAnalysis, setPfAnalysis] = useState(null);
  const [pfAnalysing, setPfAnalysing] = useState(false);
  const [pfError, setPfError] = useState(null);

  const impliedCAGR = (() => {
    if (mode === "return") return parseFloat(cagr) || null;
    if (mode === "corpus" && corpus && ls && yrs)
      return Math.round((Math.pow(parseFloat(corpus) / parseFloat(ls), 1 / parseFloat(yrs)) - 1) * 1000) / 10;
    return null;
  })();

  const isValid = (() => {
    if (mode === "return") return !!cagr && !!yrs;
    if (mode === "corpus") return !!corpus && !!ls && !!yrs;
    return !!sip && !!yrs;
  })();

  const goalPill = (() => {
    if (mode === "return") return `${cagr}% CAGR · ${yrs} Years`;
    if (mode === "corpus") return `₹${corpus}L corpus in ${yrs} yrs · ~${impliedCAGR}% CAGR`;
    return `₹${sip}/mo SIP · ${yrs} Years`;
  })();

  const handleFind = async () => {
    if (impliedCAGR && impliedCAGR > 20) {
      setInputWarn(`Your goal implies ~${impliedCAGR}% CAGR. No diversified bouquet has delivered this consistently. You may still proceed.`);
      return;
    }
    setInputWarn("");
    setScreen("loading");
    setApiError(null);
    try {
      const result = await curateBouquets({
        mode,
        targetCAGR: parseFloat(cagr) || impliedCAGR,
        targetCorpus: parseFloat(corpus) * 100000 || null,
        lumpsum: parseFloat(ls) * 100000 || null,
        sipAmount: parseFloat(sip) || null,
        horizonYears: parseFloat(yrs) || 7,
      });
      setCurationResult(result);
      if (result.archetypes?.length > 0) {
        setCagrAdvisory(result.archetypes[0].realisticAssessment || null);
      setApproxHorizon(result.horizonApproximate ? { used: result.horizonUsed, requested: result.horizonRequested } : null);
      }
      const fdata = await getFreshness().catch(() => null);
      setFreshness(fdata);
      setScreen("results");
    } catch (err) {
      setApiError("Could not connect to API. Please ensure the backend is running on port 8000.");
      setScreen("hero");
    }
  };

  const handleCbSearch = async (q) => {
    setCbSearch(q);
    if (q.length < 2) { setCbResults([]); return; }
    try {
      const res = await apiCall('GET', `/api/funds/search?q=${encodeURIComponent(q)}&limit=10`);
      setCbResults(Array.isArray(res) ? res.filter(f => !cbFunds.some(cf => cf.scheme_code === f.scheme_code)) : []);
    } catch { setCbResults([]); }
  };

  const handleCbAddFund = (fund) => {
    if (cbFunds.length >= 12) return;
    if (cbFunds.some(f => f.scheme_code === fund.scheme_code)) return;
    const defaultWeight = Math.round(100 / (cbFunds.length + 1));
    const newFunds = [
      ...cbFunds.map(f => ({ ...f, weight: defaultWeight })),
      { scheme_code: fund.scheme_code, name: fund.name, amc: fund.amc,
        category: fund.category, tier_label: fund.tier_label, weight: defaultWeight }
    ];
    // Adjust last fund to make total exactly 100
    const total = newFunds.reduce((s, f) => s + f.weight, 0);
    if (total !== 100 && newFunds.length > 0) newFunds[0].weight += (100 - total);
    setCbFunds(newFunds);
    setCbSearch(''); setCbResults([]);
    setCbAnalysis(null);
  };

  const handleCbRemoveFund = (code) => {
    const remaining = cbFunds.filter(f => f.scheme_code !== code);
    if (remaining.length === 0) { setCbFunds([]); return; }
    const equalW = Math.round(100 / remaining.length);
    const reweighted = remaining.map((f, i) => ({ ...f, weight: equalW }));
    const total = reweighted.reduce((s, f) => s + f.weight, 0);
    if (total !== 100) reweighted[0].weight += (100 - total);
    setCbFunds(reweighted);
    setCbAnalysis(null);
  };

  const handleCbWeightChange = (code, val) => {
    setCbFunds(prev => prev.map(f => f.scheme_code === code ? { ...f, weight: parseFloat(val) || 0 } : f));
    setCbAnalysis(null);
  };

  const runAnalysis = async (fundsToAnalyse) => {
    const total = fundsToAnalyse.reduce((s, f) => s + Number(f.weight), 0);
    if (Math.abs(total - 100) > 2) { setCbError(`Weights sum to ${total.toFixed(1)}% — please adjust to 100%.`); return; }
    setCbLoading(true); setCbError(null); setCbAnalysis(null); setCbSelectedSwaps(new Set());
    try {
      const result = await apiCall('POST', '/api/bouquets/analyse-custom', {
        funds: fundsToAnalyse.map(f => ({ scheme_code: f.scheme_code, weight: Number(f.weight) })),
        horizonYears: parseFloat(cbHorizon) || 7,
      });
      setCbAnalysis(result);
      setTimeout(() => cbResultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
    } catch (e) {
      setCbError('Analysis failed — please check that the server is running and try again.');
    } finally {
      setCbLoading(false);
    }
  };

  const handleCbAnalyse = async () => {
    if (cbFunds.length < 1) return;
    await runAnalysis(cbFunds);
  };

  const handleCbApplySwaps = async () => {
    let newFunds = [...cbFunds];
    for (const i of cbSelectedSwaps) {
      const s = cbAnalysis.suggestions[i];
      if (!s) continue;
      newFunds = newFunds.map(f =>
        f.scheme_code === s.replace_fund.scheme_code
          ? { scheme_code: s.with_fund.scheme_code, name: s.with_fund.name, amc: s.with_fund.amc || '', category: s.with_fund.category, weight: f.weight }
          : f
      );
    }
    setCbFunds(newFunds);
    await runAnalysis(newFunds);
  };

  const handleNavRefresh = async () => {
    if (navRefreshing) return;
    setNavRefreshing(true);
    setNavRefreshMsg(null);
    try {
      const result = await apiCall('POST', '/api/pipeline/trigger-nav');
      if (result.status === 'cooldown') {
        setNavRefreshMsg({ type: 'warn', text: result.message });
      } else {
        setNavRefreshMsg({ type: 'ok', text: `Data refreshed — NAV through: ${result.nav_data_through}` });
        const fdata = await getFreshness().catch(() => null);
        if (fdata) setFreshness(fdata);
      }
    } catch (e) {
      setNavRefreshMsg({ type: 'error', text: 'Refresh failed — server may be busy. Try again shortly.' });
    } finally {
      setNavRefreshing(false);
    }
  };

  const handleGenerateMore = async () => {
    setAltLoading(true);
    setAltError(null);
    const currentRound = altRounds.length + 2;
    // Collect all fund codes shown so far (round 1 + all alt rounds)
    const usedCodes = [
      ...(curationResult?.archetypes?.flatMap(a => a.funds?.map(f => f.scheme_code) || []) || []),
      ...altRounds.flatMap(r => r.archetypes?.flatMap(a => a.funds?.map(f => f.scheme_code) || []) || []),
    ];
    try {
      const result = await apiCall('POST', '/api/bouquets/generate-more', {
        horizonYears: parseFloat(yrs) || 7,
        targetCAGR: parseFloat(cagr) || 16,
        excludedFunds: [...new Set(usedCodes)],
        roundNumber: currentRound,
      });
      setAltRounds(prev => [...prev, result]);
      if (result.poolExhausted) setAltPoolExhausted(true);
    } catch (e) {
      const msg = e?.message || 'Generation failed';
      if (msg.includes('exhausted') || msg.includes('409')) {
        setAltPoolExhausted(true);
      } else {
        setAltError('Could not generate alternative bouquets. Please try again.');
      }
    } finally {
      setAltLoading(false);
    }
  };

  const handleCustomizeSearch = async (q) => {
    setCustomizeSearch(q);
    if (q.length < 2) { setCustomizeResults([]); return; }
    try {
      const res = await apiCall('GET', `/api/funds/search?q=${encodeURIComponent(q)}&limit=8`);
      setCustomizeResults(Array.isArray(res) ? res : []);
    } catch { setCustomizeResults([]); }
  };

  const handleCustomizeSelect = async (fund) => {
    setCustomizeResults([]);
    setCustomizeSearch(fund.name);
    setCustomizeLoading(true);
    try {
      const horizonYears = parseInt(yrs) || 7;
      const targetCAGR = parseFloat(cagr) || 16;
      const result = await apiCall('POST', '/api/bouquets/customize', {
        archetype_id: selectedArch?.id,
        replacement_fund_code: fund.scheme_code,
        replaced_fund_code: customizeTargetFund?.scheme_code || null,
        horizon_years: horizonYears,
        target_cagr: targetCAGR,
      });
      setCustomizeComparing(result);
    } catch (e) {
      console.error('Customize error', e);
    } finally {
      setCustomizeLoading(false);
    }
  };

  const handleScenario = (scId, optId, score) => {
    const next = { ...bAns, [scId]: { optId, score } };
    setBAns(next);
    if (bStep < SCENARIOS.length - 1) {
      setBStep(s => s + 1);
    } else {
      const total = Object.values(next).reduce((s, v) => s + v.score, 0);
      const prof = getBehavProfile(total);
      setBProf(prof);
      setBDone(true);
      const suggested = curationResult?.archetypes?.find(a => a.id === prof.archId);
      if (suggested) setSelectedArch(suggested);
    }
  };

  // Health polling — every 5 minutes
  useEffect(() => {
    const poll = () => {
      fetch(`${API_BASE}/health`)
        .then(r => r.json())
        .then(d => setSysHealth(d))
        .catch(() => setSysHealth({ status: "critical" }));
    };
    poll();
    const id = setInterval(poll, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

    const reset = () => {
    setScreen("hero"); setSelectedArch(null); setBStep(0); setCagrAdvisory(null); setApproxHorizon(null); setCustomizeApplied(null); setCustomizeOpen(false); setAltRounds([]); setAltLoading(false); setAltError(null); setAltPoolExhausted(false); setCbFunds([]); setCbSearch(''); setCbResults([]); setCbAnalysis(null); setCbError(null);
    setBAns({}); setBDone(false); setBProf(null);
    setShowBehav(true); setCurationResult(null); setApiError(null);
  };

  useEffect(() => {
    setCustomizeOpen(false);
    setCustomizeSearch('');
    setCustomizeResults([]);
    setCustomizeComparing(null);
    setCustomizeApplied(null);
    setCustomizeTargetFund(null);
    setCustomizeLoading(false);
  }, [selectedArch]);
useEffect(() => {
    const handler = e => { e.preventDefault(); setPwaPrompt(e); };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("fg_token");
    if (!token) return;
    authMe(token).then(u => {
      setUser(u);
      apiListSaved(token).then(setSavedList).catch(() => {});
    }).catch(() => {
      localStorage.removeItem("fg_token");
    });
  }, []);

  const handleAskAI = async (question, contextType, contextData) => {
    const q = question || aiQuestion;
    if (!q.trim()) return;
    setAiLoading(true);
    setAiResponse("");
    setAiError(null);
    try {
      const res = await fetch(`${API_BASE}/api/ai/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          context_type: contextType || 'bouquet',
          context_data: contextData || {
            name: a?.label,
            funds: a?.funds,
            cagrRange: a?.cagrRange,
            confidence: a?.confidence,
            stressTest: a?.stressTest,
            overlap: a?.overlap,
            metrics: a?.metrics,
            devils: a?.devils,
            horizonYears: yrs || 7,
          },
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        setAiError(err.detail || 'AI service unavailable');
        setAiLoading(false);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') { setAiLoading(false); return; }
          try {
            const parsed = JSON.parse(payload);
            if (parsed.error) { setAiError(parsed.error); setAiLoading(false); return; }
            if (parsed.text) { full += parsed.text; setAiResponse(full); }
          } catch {}
        }
      }
    } catch (e) {
      setAiError('Connection error — is the API running?');
    }
    setAiLoading(false);
  };

  const computeLTCG = (purchase, current, months, fundType) => {
    const gain = current - purchase;
    if (gain <= 0) return { gain, taxType: 'No gain — no tax', tax: 0, netGain: gain };
    if (fundType === 'debt') return { gain, taxType: 'Income slab rate (debt/FOF)', tax: null, netGain: null };
    if (months <= 12) return { gain, taxType: 'STCG @ 20%', tax: gain * 0.20, netGain: gain * 0.80 };
    const taxable = Math.max(0, gain - 125000);
    return { gain, taxType: 'LTCG @ 10% (₹1.25L exempt)', tax: taxable * 0.10, netGain: gain - taxable * 0.10 };
  };

  const a = selectedArch;
  const archetypes = curationResult?.archetypes || [];

  const dotColor = { healthy: '#27AE78', degraded: '#E8A000', critical: '#D84848', starting: 'rgba(255,255,255,0.2)' }[sysHealth?.status] || 'rgba(255,255,255,0.2)';
  const dotClass = `health-dot ${sysHealth?.status || 'starting'}`;
  const compColors = { healthy: '#27AE78', degraded: '#E8A000', critical: '#D84848', unknown: 'rgba(255,255,255,0.2)' };

  const HealthIndicator = () => (
    <div className="health-wrap">
      <div
        className={dotClass}
        title={`Platform: ${sysHealth?.status || 'checking...'}`}
        onClick={() => setHealthOpen(v => !v)}
      />
      {healthOpen && sysHealth && (
        <div className="health-panel" onClick={e => e.stopPropagation()}>
          <div className="health-panel-title">
            Platform Health
            <span style={{ float: 'right', textTransform: 'none', letterSpacing: 0, color: dotColor, fontWeight: 700 }}>
              {(sysHealth.status || '').toUpperCase()}
            </span>
          </div>
          {sysHealth.components && Object.entries(sysHealth.components).map(([name, comp]) => (
            <div key={name} className="health-row">
              <div className="health-row-dot" style={{ background: compColors[comp.status] || compColors.unknown }} />
              <div className="health-row-name">{name.replace('_', ' ')}</div>
              <div className="health-row-detail">{comp.detail || comp.status}</div>
            </div>
          ))}
          {!sysHealth.components && (
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>Connecting to API...</div>
          )}
          {sysHealth.last_check && (
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', marginTop: 10 }}>
              Last checked: {new Date(sysHealth.last_check).toLocaleTimeString()}
            </div>
          )}
          <button className="health-run-btn" onClick={() => {
            fetch(`${API_BASE}/api/health/run-now`, { method: 'POST' })
              .then(() => setTimeout(() => fetch(`${API_BASE}/health`).then(r => r.json()).then(setSysHealth), 12000));
            setHealthOpen(false);
          }}>Run diagnostic now</button>
        </div>
      )}
    </div>
  );

  const handleSaveBouquet = async (at) => {
    const token = localStorage.getItem("fg_token");
    if (!token) { setAuthTab("login"); setAuthModal(true); return; }
    try {
      const res = await apiSaveBouquet(token, {
        archetype_id: at.id,
        horizon_years: at.horizonYears || 7,
        target_cagr: parseFloat(at.cagrRange) || 16,
        name: `${at.label} · ${at.cagrRange}`,
      });
      setSavedList(prev => [res, ...prev]);
      setSavedMsg(prev => ({ ...prev, [at.id]: true }));
      setTimeout(() => setSavedMsg(prev => ({ ...prev, [at.id]: false })), 2000);
    } catch (e) {
      alert(e.message);
    }
  };

  const handleDeleteSaved = async (id) => {
    const token = localStorage.getItem("fg_token");
    if (!token) return;
    await apiDeleteSaved(token, id);
    setSavedList(prev => prev.filter(b => b.id !== id));
  };

  const handleAuthSubmit = async () => {
    setAuthError("");
    setAuthLoading(true);
    try {
      let res;
      if (authTab === "login") {
        res = await authLogin(authEmail, authPassword);
      } else {
        res = await authRegister(authEmail, authPassword, authName);
      }
      localStorage.setItem("fg_token", res.token);
      setUser(res.user);
      setAuthModal(false);
      setAuthEmail(""); setAuthPassword(""); setAuthName("");
    } catch (e) {
      setAuthError(e.message || "Something went wrong");
    }
    setAuthLoading(false);
  };

  const handlePfAddFund = (fund) => {
    if (pfFunds.find(f => f.scheme_code === fund.scheme_code)) return;
    const remaining = Math.max(0, 100 - pfFunds.reduce((s, f) => s + f.allocation_pct, 0));
    setPfFunds(prev => [...prev, { ...fund, allocation_pct: remaining || 20 }]);
    setPfSearch(''); setPfResults([]);
  };
  const handlePfRemoveFund = (code) => setPfFunds(prev => prev.filter(f => f.scheme_code !== code));
  const handlePfAlloc = (code, val) => setPfFunds(prev => prev.map(f => f.scheme_code === code ? { ...f, allocation_pct: parseFloat(val) || 0 } : f));
  const handlePfAnalyse = async () => {
    if (pfFunds.length < 1) { setPfError("Add at least one fund"); return; }
    setPfAnalysing(true); setPfError(null); setPfAnalysis(null);
    try {
      const result = await apiAnalysePortfolio(pfFunds.map(f => ({ scheme_code: f.scheme_code, allocation_pct: f.allocation_pct })));
      setPfAnalysis(result);
    } catch(e) { setPfError(e.message); }
    finally { setPfAnalysing(false); }
  };

  const handleSignOut = () => {
    localStorage.removeItem("fg_token");
    setUser(null);
    setSavedList([]);
    setSavedPanel(false);
  };

  const AuthModal = () => (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.7)", zIndex:2000, display:"flex", alignItems:"center", justifyContent:"center" }}
      onClick={e => { if (e.target === e.currentTarget) setAuthModal(false); }}>
      <div style={{ background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:16, padding:32, width:360, maxWidth:"90vw", fontFamily:"Outfit,sans-serif" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:24 }}>
          <span style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:20, fontWeight:700 }}>
            {authTab === "login" ? "Sign In" : "Create Account"}
          </span>
          <button onClick={() => setAuthModal(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:18 }}>&#x2715;</button>
        </div>
        <div style={{ display:"flex", gap:0, marginBottom:24, background:G.bg, borderRadius:8, padding:3 }}>
          {["login","register"].map(tab => (
            <button key={tab} onClick={() => { setAuthTab(tab); setAuthError(""); }}
              style={{ flex:1, padding:"7px 0", border:"none", borderRadius:6, cursor:"pointer", fontSize:13, fontWeight:600, letterSpacing:".03em",
                background: authTab===tab ? G.gold : "none", color: authTab===tab ? G.bg : G.slate, transition:"all .2s" }}>
              {tab === "login" ? "Sign In" : "Register"}
            </button>
          ))}
        </div>
        {authTab === "register" && (
          <div style={{ marginBottom:14 }}>
            <div style={{ fontSize:11, color:G.slate, marginBottom:5 }}>Display Name (optional)</div>
            <input value={authName} onChange={e => setAuthName(e.target.value)}
              placeholder="e.g. Bikram"
              style={{ width:"100%", background:G.bg, border:`1px solid ${G.bord}`, borderRadius:8, padding:"9px 12px",
                color:G.white, fontSize:14, fontFamily:"Outfit,sans-serif", boxSizing:"border-box" }} />
          </div>
        )}
        <div style={{ marginBottom:14 }}>
          <div style={{ fontSize:11, color:G.slate, marginBottom:5 }}>Email</div>
          <input value={authEmail} onChange={e => setAuthEmail(e.target.value)} type="email"
            placeholder="you@example.com"
            onKeyDown={e => e.key==="Enter" && handleAuthSubmit()}
            style={{ width:"100%", background:G.bg, border:`1px solid ${G.bord}`, borderRadius:8, padding:"9px 12px",
              color:G.white, fontSize:14, fontFamily:"Outfit,sans-serif", boxSizing:"border-box" }} />
        </div>
        <div style={{ marginBottom:20 }}>
          <div style={{ fontSize:11, color:G.slate, marginBottom:5 }}>Password</div>
          <input value={authPassword} onChange={e => setAuthPassword(e.target.value)} type="password"
            placeholder={authTab==="register" ? "Min 8 characters" : ""}
            onKeyDown={e => e.key==="Enter" && handleAuthSubmit()}
            style={{ width:"100%", background:G.bg, border:`1px solid ${G.bord}`, borderRadius:8, padding:"9px 12px",
              color:G.white, fontSize:14, fontFamily:"Outfit,sans-serif", boxSizing:"border-box" }} />
        </div>
        {authError && <div style={{ color:G.ro, fontSize:12, marginBottom:14, background:G.roBg, padding:"8px 12px", borderRadius:6 }}>{authError}</div>}
        <button onClick={handleAuthSubmit} disabled={authLoading}
          style={{ width:"100%", padding:"11px 0", background:G.gold, border:"none", borderRadius:8,
            color:G.bg, fontSize:14, fontWeight:700, fontFamily:"Outfit,sans-serif", cursor:authLoading?"not-allowed":"pointer", opacity:authLoading?0.7:1 }}>
          {authLoading ? "Please wait…" : authTab==="login" ? "Sign In" : "Create Account"}
        </button>
        <div style={{ marginTop:14, textAlign:"center", fontSize:12, color:G.slate }}>
          {authTab==="login" ? "No account? " : "Already have one? "}
          <button onClick={() => { setAuthTab(authTab==="login"?"register":"login"); setAuthError(""); }}
            style={{ background:"none", border:"none", color:G.gold, cursor:"pointer", fontSize:12, fontWeight:600 }}>
            {authTab==="login" ? "Register" : "Sign In"}
          </button>
        </div>
      </div>
    </div>
  );

  const SavedPanel = () => (
    <div style={{ position:"fixed", inset:0, zIndex:1900, display:"flex", justifyContent:"flex-end" }}
      onClick={e => { if (e.target === e.currentTarget) setSavedPanel(false); }}>
      <div style={{ background:G.sur, borderLeft:`1px solid ${G.bordG}`, width:360, maxWidth:"90vw",
        height:"100%", overflowY:"auto", padding:24, fontFamily:"Outfit,sans-serif", display:"flex", flexDirection:"column", gap:16 }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <span style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:20, fontWeight:700 }}>Saved Bouquets</span>
          <button onClick={() => setSavedPanel(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:18 }}>&#x2715;</button>
        </div>
        {savedList.length === 0 && (
          <p style={{ color:G.slate, fontSize:13 }}>No saved bouquets yet. Click the bookmark icon on any archetype to save it.</p>
        )}
        {savedList.map(b => (
          <div key={b.id} style={{ background:G.elv, border:`1px solid ${G.bord}`, borderRadius:10, padding:"12px 16px", display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
            <div>
              <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:4 }}>{b.name}</div>
              <div style={{ color:G.slate, fontSize:11 }}>{b.horizon_years}yr · {b.target_cagr}% CAGR</div>
              <div style={{ color:G.mist, fontSize:10, marginTop:4 }}>{new Date(b.saved_at).toLocaleDateString("en-IN", {day:"numeric",month:"short",year:"numeric"})}</div>
            </div>
            <button onClick={() => handleDeleteSaved(b.id)}
              style={{ background:"none", border:"none", color:G.ro, cursor:"pointer", fontSize:16, padding:"0 4px", flexShrink:0 }}>&#x2715;</button>
          </div>
        ))}
      </div>
    </div>
  );

  const ARCHETYPE_LABELS = {
    "steady_compounder": "Steady Compounder",
    "balanced_growther": "Balanced Growther",
    "aggressive_achiever": "Aggressive Achiever",
    "high_conviction": "High Conviction",
  };

  if (screen === "portfolio") {
    const total = pfFunds.reduce((s, f) => s + (f.allocation_pct || 0), 0);
    const totalOk = total >= 95 && total <= 105;
    return (
      <>
        <style>{css}</style>
        <div style={{ minHeight:"100vh", background:G.bg, fontFamily:"Outfit,sans-serif", padding:24 }}>
          <div style={{ maxWidth:800, margin:"0 auto" }}>
            <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:28 }}>
              <button onClick={() => { setScreen("hero"); setPfAnalysis(null); setPfError(null); }} style={{ background:"none", border:`1px solid ${G.bord}`, borderRadius:8, padding:"5px 14px", color:G.slate, fontSize:12, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>← Back</button>
              <span style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:26, fontWeight:700 }}>My Portfolio Analyser</span>
            </div>

            {/* Fund Search */}
            <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:20 }}>
              <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:12 }}>Add Funds to Your Portfolio</div>
              <div style={{ position:"relative" }}>
                <input
                  value={pfSearch}
                  onChange={async e => {
                    const q = e.target.value;
                    setPfSearch(q);
                    if (q.length >= 2) {
                      setPfSearching(true);
                      const r = await apiFundSearch(q);
                      setPfResults(r); setPfSearching(false);
                    } else { setPfResults([]); }
                  }}
                  placeholder="Search by fund name or AMC..."
                  style={{ width:"100%", background:G.elv, border:`1px solid ${G.bord}`, borderRadius:8, padding:"10px 14px", color:G.white, fontSize:13, fontFamily:"Outfit,sans-serif", outline:"none", boxSizing:"border-box" }}
                />
                {pfSearching && <span style={{ position:"absolute", right:12, top:"50%", transform:"translateY(-50%)", color:G.slate, fontSize:12 }}>...</span>}
                {pfResults.length > 0 && (
                  <div style={{ position:"absolute", top:"100%", left:0, right:0, background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:8, zIndex:100, maxHeight:240, overflowY:"auto", marginTop:4 }}>
                    {pfResults.map(r => (
                      <div key={r.scheme_code} onClick={() => handlePfAddFund(r)} style={{ padding:"10px 14px", cursor:"pointer", borderBottom:`1px solid ${G.bord}` }}
                        onMouseEnter={e => e.currentTarget.style.background=G.elv}
                        onMouseLeave={e => e.currentTarget.style.background="transparent"}>
                        <div style={{ color:G.white, fontSize:13, fontWeight:600 }}>{r.name || r.scheme_name}</div>
                        <div style={{ color:G.slate, fontSize:11, marginTop:2 }}>{r.amc || r.amc_name} · {r.category || r.sebi_category}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Fund List */}
            {pfFunds.length > 0 && (
              <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:20 }}>
                <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:12 }}>Your Funds</div>
                {pfFunds.map(f => (
                  <div key={f.scheme_code} style={{ display:"flex", alignItems:"center", gap:12, marginBottom:10, padding:"10px 14px", background:G.elv, borderRadius:8 }}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ color:G.white, fontSize:12, fontWeight:600, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{f.name || f.scheme_name}</div>
                      <div style={{ color:G.slate, fontSize:11, marginTop:2 }}>{f.category || f.sebi_category}</div>
                    </div>
                    <div style={{ display:"flex", alignItems:"center", gap:6, flexShrink:0 }}>
                      <input type="number" min={1} max={100} value={f.allocation_pct}
                        onChange={e => handlePfAlloc(f.scheme_code, e.target.value)}
                        style={{ width:56, background:G.bg, border:`1px solid ${G.bordG}`, borderRadius:6, padding:"4px 8px", color:G.gold, fontSize:13, fontFamily:"Outfit,sans-serif", textAlign:"right" }} />
                      <span style={{ color:G.slate, fontSize:12 }}>%</span>
                    </div>
                    <button onClick={() => handlePfRemoveFund(f.scheme_code)} style={{ background:"none", border:"none", color:G.ro, cursor:"pointer", fontSize:16, padding:"0 4px", flexShrink:0 }}>&#x2715;</button>
                  </div>
                ))}
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginTop:12, paddingTop:12, borderTop:`1px solid ${G.bord}` }}>
                  <span style={{ color: totalOk ? G.green : "#FF6B6B", fontSize:13, fontWeight:600 }}>Total: {total.toFixed(1)}%{!totalOk && " (must be ~100%)"}</span>
                  <button onClick={handlePfAnalyse} disabled={pfAnalysing || !totalOk}
                    style={{ background: totalOk ? "linear-gradient(135deg,rgba(212,175,55,0.2),rgba(212,175,55,0.08))" : G.elv,
                      border:`1px solid ${totalOk ? G.bordG : G.bord}`, borderRadius:10, padding:"8px 24px",
                      color: totalOk ? G.gold : G.slate, fontSize:13, fontWeight:600, cursor: totalOk ? "pointer" : "not-allowed",
                      fontFamily:"Outfit,sans-serif" }}>
                    {pfAnalysing ? "Analysing..." : "Analyse Portfolio →"}
                  </button>
                </div>
              </div>
            )}

            {pfError && <div style={{ background:"rgba(255,107,107,0.1)", border:"1px solid rgba(255,107,107,0.3)", borderRadius:8, padding:"12px 16px", color:"#FF6B6B", fontSize:13, marginBottom:16 }}>{pfError}</div>}

            {/* Analysis Results */}
            {pfAnalysis && (
              <div>
                {/* Portfolio Metrics */}
                <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:16 }}>
                  <div style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:18, fontWeight:700, marginBottom:16 }}>Portfolio Metrics</div>
                  <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(140px,1fr))", gap:12 }}>
                    {[
                      ["Composite Score", pfAnalysis.portfolio_metrics.weighted_composite_score, G.gold],
                      ["Expense Ratio", `${(pfAnalysis.portfolio_metrics.weighted_expense_ratio * 100).toFixed(2)}%`, G.mist],
                      ["No. of Funds", pfAnalysis.portfolio_metrics.fund_count, G.white],
                    ].map(([label, val, col]) => (
                      <div key={label} style={{ background:G.elv, borderRadius:8, padding:"12px 14px" }}>
                        <div style={{ color:G.slate, fontSize:10, marginBottom:4 }}>{label}</div>
                        <div style={{ color:col, fontSize:18, fontWeight:700, fontFamily:"JetBrains Mono,monospace" }}>{val}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Category Distribution */}
                <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:16 }}>
                  <div style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:18, fontWeight:700, marginBottom:14 }}>Category Distribution</div>
                  {Object.entries(pfAnalysis.portfolio_metrics.category_distribution).map(([cat, pct]) => (
                    <div key={cat} style={{ marginBottom:10 }}>
                      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                        <span style={{ color:G.white, fontSize:12 }}>{cat}</span>
                        <span style={{ color:G.gold, fontSize:12, fontWeight:600 }}>{pct.toFixed(1)}%</span>
                      </div>
                      <div style={{ background:G.elv, borderRadius:4, height:6 }}>
                        <div style={{ background:`linear-gradient(90deg,${G.gold},rgba(212,175,55,0.4))`, width:`${pct}%`, height:"100%", borderRadius:4, transition:"width .5s" }} />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Archetype Similarity */}
                <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:16 }}>
                  <div style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:18, fontWeight:700, marginBottom:14 }}>Archetype Similarity</div>
                  <p style={{ color:G.slate, fontSize:12, marginBottom:16, marginTop:0 }}>How closely your portfolio resembles each FundGuldasta archetype bouquet.</p>
                  {pfAnalysis.archetype_matches.map((am, i) => (
                    <div key={am.archetype_id} style={{ display:"flex", alignItems:"center", gap:14, marginBottom:14, padding:"12px 16px", background:G.elv, borderRadius:10, border:`1px solid ${i === 0 ? G.bordG : G.bord}` }}>
                      <div style={{ flex:1 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
                          {i === 0 && <span style={{ background:"rgba(212,175,55,0.15)", border:`1px solid ${G.bordG}`, borderRadius:4, padding:"1px 7px", fontSize:10, color:G.gold, fontWeight:600 }}>Closest Match</span>}
                          <span style={{ color:G.white, fontSize:13, fontWeight:600 }}>{ARCHETYPE_LABELS[am.archetype_id] || am.archetype_id}</span>
                        </div>
                        <div style={{ color:G.slate, fontSize:11 }}>{am.common_funds} of {am.total_archetype_funds} funds in common · {am.weighted_overlap_pct.toFixed(0)}% allocation overlap</div>
                      </div>
                      <div style={{ textAlign:"right", flexShrink:0 }}>
                        <div style={{ color: i === 0 ? G.gold : G.slate, fontSize:22, fontWeight:700, fontFamily:"JetBrains Mono,monospace" }}>{am.similarity_score.toFixed(0)}<span style={{ fontSize:12 }}>/100</span></div>
                      </div>
                    </div>
                  ))}
                </div>

                {pfAnalysis.missing_data_codes?.length > 0 && (
                  <div style={{ color:G.slate, fontSize:11, marginTop:8 }}>Note: No computed data for scheme codes {pfAnalysis.missing_data_codes.join(", ")} — those funds were not scored.</div>
                )}
              </div>
            )}

            {pfFunds.length === 0 && !pfAnalysis && (
              <div style={{ textAlign:"center", padding:"60px 20px", color:G.slate, fontSize:13 }}>
                <div style={{ fontSize:32, marginBottom:12 }}>📊</div>
                <div>Search for funds above to build your portfolio.</div>
                <div style={{ marginTop:8, fontSize:12 }}>Then click "Analyse Portfolio" to see how it compares to our bouquets.</div>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

    if (screen === "hero") return (
    <>
      {authModal && <AuthModal />}
      <style>{css}</style>
      <div className="hero">
        <div className="mesh" />
        <img src="/hero-tree.png" className="hero-bg-img" alt="" />
        <img src="/hero-bouquet.png" className="hero-deco" alt="" />
        <img src="/hero-bouquet.png" className="hero-deco-left" alt="" />
        <div className="brand">
          <div className="bmark">
            <img src="/logo-bouquet-real.png" alt="FundGuldasta — five fund categories as a bouquet" style={{width:'108px',height:'108px',objectFit:'cover',display:'block'}}/>
          </div>
          <div>
            <div className="bname">FundGuldasta</div>
            <div className="btag">Fund selection ka ek rasta</div>
            <div style={{ fontSize: 13, color: "rgba(212,175,55,0.5)", fontFamily: "Outfit,sans-serif", marginTop: 4, letterSpacing: "0.06em", textTransform: "uppercase" }}>Direct Plans · Research &amp; Education</div>
          </div>
        </div>
        <div className="tagline">Mutual Fund Research. Unfiltered.</div>
        <div className="gold-rule" />
        <div className="sec-tag">Honest-by-Design Mutual Fund Research</div>
        <h1 className="h1">Curated fund bouquets.<br /><em>Honest by design.</em></h1>
        <p className="sub">Two inputs. Four bouquet archetypes. Ten layers of transparent research. No commission. No false assurance.</p>
        {pwaPrompt && (
          <button
            onClick={() => { pwaPrompt.prompt(); pwaPrompt.userChoice.then(() => setPwaPrompt(null)); }}
            style={{ display:'inline-flex', alignItems:'center', gap:8, background:'rgba(212,175,55,0.1)', border:'1px solid rgba(212,175,55,0.35)', borderRadius:10, padding:'9px 22px', color:'#D4AF37', fontFamily:'Outfit,sans-serif', fontSize:13, fontWeight:600, cursor:'pointer', letterSpacing:'.04em', marginBottom:16 }}
          >
            <img src="/logo-bouquet-real.png" alt="" style={{width:28,height:28,objectFit:'cover',borderRadius:6,flexShrink:0}} />
            Install App
          </button>
        )}
        {apiError && <div className="warn-box" style={{ maxWidth: 600, marginBottom: 20 }}>⚠️ {apiError}</div>}
        <div className="icard">
          <div className="tabs">
            {[["return", "Return target"], ["corpus", "Corpus target"], ["sip", "SIP capacity"]].map(([id, lbl]) => (
              <button key={id} className={`tab${mode === id ? " on" : ""}`} onClick={() => { setMode(id); setInputWarn(""); }}>{lbl}</button>
            ))}
          </div>
          {mode === "return" && (
            <div style={{ marginBottom: 24 }}>
              <label className="lbl">Target CAGR & investment horizon (any value — we'll show you what it means)</label>
              <div className="row">
                <div className="iw"><input className="inp" type="number" placeholder="16" min="1" max="50" value={cagr} onChange={e => setCAGR(e.target.value)} /><span className="sfx">% CAGR</span></div>
                <div className="iw"><input className="inp" type="number" placeholder="7" min="1" max="40" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx">Years</span></div>
              </div>
              {cagr && yrs && (() => {
                const c = parseFloat(cagr), y = parseFloat(yrs);
                if (!c || !y) return null;
                const fd = (10 * Math.pow(1.07, y)).toFixed(1);
                const target = (10 * Math.pow(1 + c/100, y)).toFixed(1);
                const isShort = y <= 2;
                const isHigh = c > 20;
                const hint = isShort
                  ? `${y}-year horizon: equity MFs carry high risk — markets can be down 40%+ at the 2-year mark.`
                  : isHigh
                  ? `${c}% over ${y} years: historically rare. At FD (7%): ₹${fd}L. At ${c}%: ₹${target}L.`
                  : `₹10L at ${c}% over ${y} years → ₹${target}L. FD (7%) → ₹${fd}L.`;
                const hintColor = isShort || isHigh ? "#F0A500" : G.mist;
                return <div className="input-hint" style={{ color: hintColor }}>{hint}</div>;
              })()}
            </div>
          )}
          {mode === "corpus" && (
            <>
              <div style={{ marginBottom: 14 }}>
                <label className="lbl">Target corpus & horizon</label>
                <div className="row">
                  <div className="iw"><input className="inp inp-sm" type="number" placeholder="50" value={corpus} onChange={e => setCorpus(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>₹ Lakhs</span></div>
                  <div className="iw"><input className="inp inp-sm" type="number" placeholder="7" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>Yrs</span></div>
                </div>
              </div>
              <div style={{ marginBottom: 14 }}>
                <label className="lbl">Starting lump sum (₹ Lakhs)</label>
                <div className="iw"><input className="inp inp-sm" type="number" placeholder="10" value={ls} onChange={e => setLs(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>₹ L</span></div>
              </div>
              {impliedCAGR && impliedCAGR > 0 && (
                <div className="implied">Implied CAGR: <strong style={{ color: G.gold }}>~{impliedCAGR}%</strong></div>
              )}
            </>
          )}
          {mode === "sip" && (
            <>
              <div style={{ marginBottom: 14 }}>
                <label className="lbl">Monthly SIP & horizon</label>
                <div className="row">
                  <div className="iw"><input className="inp inp-sm" type="number" placeholder="15000" value={sip} onChange={e => setSip(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>/mo</span></div>
                  <div className="iw"><input className="inp inp-sm" type="number" placeholder="10" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>Yrs</span></div>
                </div>
              </div>
              {sip && yrs && (
                <div className="implied" style={{ fontSize: 12 }}>
                  At 12% → ₹{(parseFloat(sip) * parseFloat(yrs) * 12 * 1.6 / 100000).toFixed(1)}L · At 16% → ₹{(parseFloat(sip) * parseFloat(yrs) * 12 * 2.0 / 100000).toFixed(1)}L · At 20% → ₹{(parseFloat(sip) * parseFloat(yrs) * 12 * 2.5 / 100000).toFixed(1)}L
                </div>
              )}
            </>
          )}
          {inputWarn && <div className="warn-box">⚠️ {inputWarn}</div>}
          <button className="btn-p" disabled={!isValid} onClick={handleFind}>Curate My Bouquets →</button>
          <button className="byob-entry" style={{ marginTop: 8 }} onClick={() => setScreen("custom_builder")}>✎ Build Your Own Bouquet</button>
          <button className="byob-entry" style={{ marginTop: 8, background:"rgba(212,175,55,0.08)" }} onClick={() => setScreen("portfolio")}>📊 Analyse My Portfolio</button>
          <p className="note">Research & education only · Not investment advice · Past performance does not guarantee future returns<br />All fund data sourced from AMFI · No commission earned on any recommendation · fundguldasta.com</p>
        </div>
      </div>
    </>
  );

  if (screen === "about") return (
    <>
      <style>{css}</style>
      <div className="about-screen">
        <div className="about-inner">
          <button className="about-back" onClick={() => setScreen("hero")}>← Back to FundGuldasta</button>

          <div className="about-hero">
            <div className="about-mark">FG</div>
            <div>
              <div className="about-headline">Mutual Fund Research.<br />Unfiltered.</div>
              <div className="about-tagline">India's Honest-by-Design Research Platform</div>
            </div>
          </div>

          <div className="about-section">
            <div className="about-section-title">The Builder</div>
            <div className="about-builder">
              <div className="about-builder-name">Bikram</div>
              <div className="about-builder-role">Builder & Researcher · 66 years of real-world experience</div>
              <div className="about-builder-body">
                <p>FundGuldasta was built by <strong>Bikram</strong> — with 66 years of lived experience navigating markets, economic cycles, policy shifts, and the quiet erosion of savings that happens when people are given complexity instead of clarity.</p>
                <p style={{ marginTop: 12 }}>The platform was not built to compete with fund houses, distributors, or fintechs. It was built because <strong>honest, accessible, commission-free mutual fund research</strong> remained out of reach for the ordinary Indian investor — buried in jargon, sold as advice, or locked behind institutional access.</p>
                <p style={{ marginTop: 12 }}>Every algorithm threshold, every data source, every word of explanatory copy has been calibrated against the question: <strong>"Would this genuinely help someone making their first SIP decision?"</strong></p>
              </div>
            </div>
          </div>

          <div className="about-section">
            <div className="about-section-title">Our Purpose</div>
            <div className="about-card">
              <div className="about-card-title">Non-Profit. Educational. Accessible.</div>
              <div className="about-card-body">
                <p>FundGuldasta is a <strong>non-profit research and education platform</strong>. It earns nothing from fund houses, distributors, or any financial entity. No trail commissions. No referral fees. No sponsored rankings.</p>
                <p style={{ marginTop: 12 }}>Our goal is simple: give every Indian — in their own language, at their own level of financial literacy — the same quality of mutual fund research that was previously available only to institutional investors or those who could afford professional advice.</p>
                <div className="about-lang-chips">
                  {["English","हिन्दी (Hindi)","Roman Hindi","More languages coming"].map(l => (
                    <span key={l} className="about-lang-chip">{l}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="about-section">
            <div className="about-section-title">Our Principles</div>
            {[
              ["01", "Direct plans only", "We never recommend regular plans. Distributor trail commissions — typically 0.9–1.1% per year — compound into significant lost wealth over a 7-year horizon. We show you exactly how much."],
              ["02", "No false assurance", "Where historical data is complete, we show history. Where it is partial, we say so. Uncertainty is never hidden in footnotes."],
              ["03", "Algorithm, not opinion", "Every bouquet is constructed by a 5-layer quantitative engine: eligibility filter, fund scorer, bouquet builder, confidence scorer, and pre-computation. No human bias in fund selection."],
              ["04", "User agency above all", "Research advisories never block you. CAGR warnings, horizon cautions, and risk assessments are always dismissible. You have full agency over your decisions."],
              ["05", "Honest about limits", "Manager stability scores use available data. Stock-level overlap is not yet computed. We tell you this directly, on every screen where it matters."],
            ].map(([num, title, body]) => (
              <div key={num} className="about-principle">
                <div className="about-principle-num">{num}</div>
                <div className="about-principle-text"><strong>{title}</strong> — {body}</div>
              </div>
            ))}
          </div>

          <div className="about-section">
            <div className="about-section-title">What FundGuldasta Is Not</div>
            <div className="about-card">
              <div className="about-card-body">
                <p>FundGuldasta is <strong>not a SEBI-registered investment advisor</strong>. It does not provide personalised investment advice. It does not execute transactions. It does not hold your money.</p>
                <p style={{ marginTop: 12 }}>It is a research and education tool. The final investment decision — the fund, the amount, the platform — is always yours. We exist to make sure that decision is better informed than it would have been without us.</p>
                <p style={{ marginTop: 12, fontSize: 12, color: "rgba(255,255,255,0.3)", fontStyle: "italic" }}>Mutual fund investments are subject to market risks. Past performance is not indicative of future returns. Please read all scheme documents carefully before investing. Verify current NAV, TER, and fund data on amfiindia.com.</p>
              </div>
            </div>
          </div>

          <div style={{ textAlign: "center", marginTop: 48, paddingBottom: 24 }}>
            <button onClick={() => setScreen("hero")} style={{ background: "linear-gradient(135deg,rgba(212,175,55,0.15),rgba(212,175,55,0.05))", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, padding: "14px 40px", color: G.gold, fontFamily: "Outfit,sans-serif", fontSize: 14, fontWeight: 600, cursor: "pointer", letterSpacing: ".04em" }}>
              Start Researching →
            </button>
          </div>
        </div>
      </div>
      {/* Site Footer */}
      {screen === "results" && (
        <div className="site-footer">
          <div className="site-footer-inner">
            <div>
              <div className="footer-brand-name">FundGuldasta</div>
              <div className="footer-brand-tag">Mutual Fund Research. Unfiltered.</div>
              <div className="footer-links">
                <button className="footer-link" onClick={() => setScreen("about")}>About</button>
                <button className="footer-link" onClick={() => setScreen("custom_builder")}>Build Your Own</button>
                <button className="footer-link" onClick={reset}>New Search</button>
              </div>
            </div>
            <div className="footer-legal">
              FundGuldasta is a research &amp; education platform — not a SEBI-registered investment advisor or distributor. All data sourced from AMFI. Past performance is not indicative of future results. No commission earned on any recommendation. Direct plans only.<br />
              &copy; 2025 FundGuldasta &nbsp;&middot;&nbsp; fundguldasta.com &nbsp;&middot;&nbsp; Research &amp; Education Only &nbsp;&middot;&nbsp; Not Investment Advice
            </div>
          </div>
        </div>
      )}
      {/* SEBI Disclaimer — sticky footer */}
      <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 200, background: "rgba(9,12,17,0.97)", backdropFilter: "blur(12px)", borderTop: "1px solid rgba(255,255,255,0.06)", padding: "8px 24px", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.28)", textAlign: "center", maxWidth: 900, lineHeight: 1.6 }}>
          <strong style={{ color: "rgba(255,255,255,0.4)" }}>Disclaimer:</strong> FundGuldasta is a research &amp; education platform — not a SEBI-registered investment advisor or distributor. Information is for educational purposes only. Mutual fund investments are subject to market risks. Verify current data on amfiindia.com.
        </span>
      </div>
    </>
  );

  if (screen === "custom_builder") return (
    <>
      <style>{css}</style>
      <div className="byob-screen">
        <div className="byob-inner">
          <button className="byob-back" onClick={() => setScreen("hero")}>← Back to search</button>
          <div className="byob-title">Build Your Own Bouquet</div>
          <div className="byob-sub">Search and add funds you are considering. Assign weights, set your horizon, and our engine will score your bouquet — and suggest where it can be stronger.</div>

          {/* Fund search */}
          <div style={{ marginBottom: 20 }}>
            <div className="byob-search">
              <input
                className="byob-input"
                type="text"
                placeholder="Search fund by name or AMC (e.g. Axis Midcap, HDFC, Parag Parikh...)"
                value={cbSearch}
                onChange={e => handleCbSearch(e.target.value)}
              />
              {cbResults.length > 0 && (
                <div className="byob-dropdown">
                  {cbResults.map(f => (
                    <div key={f.scheme_code} className="byob-opt" onClick={() => handleCbAddFund(f)}>
                      <div className="byob-opt-name">{f.name}</div>
                      <div className="byob-opt-meta">{f.amc} · {f.category} · {f.tier_label}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Fund list */}
          {cbFunds.length > 0 && (
            <div className="byob-fund-list">
              <div style={{ fontSize: 11, letterSpacing: ".1em", textTransform: "uppercase", color: G.mist, marginBottom: 10 }}>Your Bouquet ({cbFunds.length} fund{cbFunds.length !== 1 ? "s" : ""})</div>
              {cbFunds.map(f => (
                <div key={f.scheme_code} className="byob-fund-row">
                  <div className="byob-fund-info">
                    <div className="byob-fund-name">{f.name}</div>
                    <div className="byob-fund-meta">{f.amc} · {f.category}</div>
                  </div>
                  <input
                    className="byob-weight-input"
                    type="number"
                    min="1" max="100"
                    value={f.weight}
                    onChange={e => handleCbWeightChange(f.scheme_code, e.target.value)}
                  />
                  <span className="byob-pct">%</span>
                  <button className="byob-remove" onClick={() => handleCbRemoveFund(f.scheme_code)}>✕</button>
                </div>
              ))}
              {(() => {
                const total = cbFunds.reduce((s, f) => s + (parseFloat(f.weight) || 0), 0);
                return <div className={`byob-total ${Math.abs(total - 100) <= 0.5 ? "ok" : "warn"}`}>Total: {total.toFixed(1)}%{Math.abs(total - 100) > 0.5 ? " — must equal 100%" : " ✓"}</div>;
              })()}
            </div>
          )}

          {/* Controls */}
          <div className="byob-controls">
            <div className="byob-horizon-wrap">
              <span className="byob-horizon-label">Investment horizon</span>
              <input className="byob-horizon-input" type="number" min="1" max="25" value={cbHorizon} onChange={e => setCbHorizon(e.target.value)} />
              <span className="byob-horizon-label">years</span>
            </div>
            <button
              className="byob-analyse-btn"
              disabled={cbFunds.length < 1 || cbLoading}
              onClick={handleCbAnalyse}
            >
              {cbLoading ? "Analysing..." : "Analyse My Bouquet"}
            </button>
          </div>
          {cbError && <div style={{ color: "#E05555", fontSize: 12, marginTop: 10 }}>{cbError}</div>}
          {cbLoading && <div style={{ color: G.mist, fontSize: 12, marginTop: 16 }}>Scoring funds and computing correlations — usually under 60 seconds...</div>}

          {/* Analysis Results */}
          {cbAnalysis && (
            <div className="byob-results" ref={cbResultsRef}>
              <div style={{ width: 40, height: 1, background: "rgba(212,175,55,0.3)", margin: "0 0 28px" }} />

              {/* Pros & cons */}
              {(cbAnalysis.pros?.length > 0 || true) && (
                <div className="byob-section" style={{ marginBottom: 24 }}>
                  <div className="pros-cons-grid">
                    <div className="pros-col">
                      <div className="pros-col-header"><span className="pros-col-icon">↑</span> What Works</div>
                      <ul className="dl" style={{ margin: 0 }}>
                        {(cbAnalysis.pros || []).map((p, i) => (
                          <li key={i} className="di">
                            <span style={{ color: G.em, flexShrink: 0, fontSize: 14, marginTop: 1 }}>✓</span>
                            <span style={{ fontSize: 12, color: G.fog, lineHeight: 1.6 }}>{p}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="cons-col">
                      <div className="cons-col-header"><span className="cons-col-icon">↓</span> Risks & Gaps</div>
                      <ul className="dl" style={{ margin: 0 }}>
                        {(() => {
                          const allW = [
                            ...(cbAnalysis.warnings?.correlation || []).map(w => typeof w === 'string' ? w : w.message),
                            ...(cbAnalysis.warnings?.concentration || []).map(w => typeof w === 'string' ? w : w.message),
                            ...(cbAnalysis.warnings?.amc || []).map(w => typeof w === 'string' ? w : w.message),
                          ].slice(0, 5);
                          return allW.length > 0 ? allW.map((w, i) => (
                            <li key={i} className="di">
                              <span style={{ color: G.ro, flexShrink: 0, fontSize: 14, marginTop: 1 }}>→</span>
                              <span style={{ fontSize: 12, color: G.fog, lineHeight: 1.6 }}>{w}</span>
                            </li>
                          )) : (
                            <li className="di">
                              <span style={{ color: G.em, flexShrink: 0, fontSize: 14, marginTop: 1 }}>✓</span>
                              <span style={{ fontSize: 12, color: G.fog, lineHeight: 1.6 }}>No major risk flags detected in your selection</span>
                            </li>
                          );
                        })()}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Key metrics row */}
              <div className="byob-result-header">
                <div className="byob-metric-card">
                  <div className="byob-metric-label">Projected CAGR</div>
                  <div className="byob-metric-value">{cbAnalysis.projected_cagr != null ? cbAnalysis.projected_cagr + "%" : "—"}</div>
                  <div className="byob-metric-sub">Weighted median rolling return over {cbHorizon}yr</div>
                </div>
                <div className="byob-metric-card">
                  <div className="byob-metric-label">Composite Score</div>
                  <div className="byob-metric-value" style={{ color: cbAnalysis.quality_color }}>{cbAnalysis.weighted_composite_score ?? "—"}</div>
                  <div className="byob-metric-sub">{cbAnalysis.quality_label} · /100 scale</div>
                </div>
                <div className="byob-metric-card">
                  <div className="byob-metric-label">Avg Correlation</div>
                  <div className="byob-metric-value" style={{ color: cbAnalysis.avg_correlation > 0.9 ? "#E05555" : cbAnalysis.avg_correlation > 0.8 ? "#F0A500" : "#27AE78" }}>
                    {cbAnalysis.avg_correlation != null ? cbAnalysis.avg_correlation.toFixed(2) : "—"}
                  </div>
                  <div className="byob-metric-sub">{cbAnalysis.avg_correlation > 0.9 ? "High — low true diversification" : cbAnalysis.avg_correlation > 0.8 ? "Moderate" : "Good diversification"}</div>
                </div>
              </div>

              {/* CAGR realism advisory */}
              {cbAnalysis.realism_advisory && cbAnalysis.realism_advisory.category !== "realistic" && (
                <div className="warn-box" style={{ marginBottom: 20 }}>
                  <strong>CAGR Advisory — {cbAnalysis.realism_advisory.category.replace("_", " ")}:</strong> {cbAnalysis.realism_advisory.message}
                </div>
              )}

              {/* Fund-level analysis table */}
              <div className="byob-section">
                <div className="byob-section-title">Fund-Level Analysis</div>
                <table className="byob-table">
                  <thead>
                    <tr><th>Fund</th><th>Weight</th><th>Score</th><th>Rolling CAGR</th><th>Tier</th><th>Category</th></tr>
                  </thead>
                  <tbody>
                    {cbAnalysis.funds.map(f => (
                      <tr key={f.scheme_code}>
                        <td style={{ maxWidth: 200, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name}</td>
                        <td>{f.weight}%</td>
                        <td>
                          {f.composite_score != null ? (
                            <span style={{ color: f.composite_score >= 65 ? "#27AE78" : f.composite_score >= 50 ? "#F0A500" : "#E05555" }}>
                              {f.composite_score.toFixed(1)}
                            </span>
                          ) : "—"}
                        </td>
                        <td>{f.rolling_cagr != null ? f.rolling_cagr + "%" : "—"}</td>
                        <td><span style={{ color: f.tier === 1 ? "#27AE78" : f.tier === 2 ? "#F0A500" : "#E05555" }}>T{f.tier}</span></td>
                        <td style={{ color: G.mist, fontSize: 11 }}>{f.category || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Improvement suggestions */}
              {cbAnalysis.suggestions.length > 0 && (
                <div className="byob-section">
                  <div className="byob-section-title">Improvement Suggestions</div>
                  <div style={{ fontSize: 12, color: G.mist, marginBottom: 14 }}>Select the swaps you agree with, then hit Replace. You can accept one, two, or all — your call.</div>
                  {cbAnalysis.suggestions.map((s, i) => (
                    <div
                      key={i}
                      className={"byob-suggestion" + (cbSelectedSwaps.has(i) ? " byob-sug-selected" : "")}
                      onClick={() => setCbSelectedSwaps(prev => { const n = new Set(prev); n.has(i) ? n.delete(i) : n.add(i); return n; })}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                        <span className={"byob-sug-check" + (cbSelectedSwaps.has(i) ? " checked" : "")}>
                          {cbSelectedSwaps.has(i) ? '✓' : ''}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div className="byob-sug-header">Consider replacing:</div>
                          <div className="byob-sug-funds">
                            <span className="byob-sug-from">{s.replace_fund.name}</span>
                            <span className="byob-sug-arrow">→</span>
                            <span className="byob-sug-to">{s.with_fund.name}</span>
                            <span className="byob-sug-delta">+{s.score_improvement} pts</span>
                          </div>
                          <div className="byob-sug-rationale">{s.rationale}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {cbSelectedSwaps.size > 0 && (
                    <button
                      className="byob-sug-replace-btn"
                      disabled={cbLoading}
                      onClick={e => { e.stopPropagation(); handleCbApplySwaps(); }}
                    >
                      {cbLoading
                        ? 'Re-analysing...'
                        : `Replace ${cbSelectedSwaps.size} fund${cbSelectedSwaps.size > 1 ? 's' : ''} & Re-analyse →`}
                    </button>
                  )}
                </div>
              )}
              {cbAnalysis.suggestions.length === 0 && (
                <div className="byob-section" style={{ borderColor: "rgba(39,174,120,0.2)" }}>
                  <div className="byob-section-title">Improvement Suggestions</div>
                  <div style={{ fontSize: 13, color: "#27AE78" }}>All your funds score above the bouquet median — no obvious substitution recommended. Strong selection.</div>
                </div>
              )}

              {/* Cautions & Advisories with alternative fund recommendations */}
              {(() => {
                const norm = (w, defaultDanger) => {
                  if (typeof w === 'string') return { message: w, severity: defaultDanger ? 'high' : 'moderate', alternatives: [], alternatives_note: null };
                  return w;
                };
                const allWarnings = [
                  ...(cbAnalysis.warnings.correlation || []).map(w => norm(w, true)),
                  ...(cbAnalysis.warnings.concentration || []).map(w => norm(w, false)),
                  ...(cbAnalysis.warnings.amc || []).map(w => norm(w, false)),
                  ...(cbAnalysis.warnings.tier || []).map(w => norm(w, false)),
                  ...(cbAnalysis.warnings.expense_ratio || []).map(w => norm(w, false)),
                ];
                if (allWarnings.length === 0) return null;
                const typeLabel = { correlation: 'Correlation', tier: 'Track Record', expense_ratio: 'Cost', concentration: 'Concentration', amc: 'AMC Risk' };
                const typeColor = { high: '#E05555', moderate: '#F0A500', low: '#F0A500' };
                return (
                  <div className="byob-section">
                    <div className="byob-section-title">Cautions & Advisories</div>
                    {allWarnings.map((w, i) => (
                      <div key={i} style={{ marginBottom: 16, background: w.severity === 'high' ? 'rgba(224,85,85,0.06)' : 'rgba(240,165,0,0.06)', border: `1px solid ${w.severity === 'high' ? 'rgba(224,85,85,0.25)' : 'rgba(240,165,0,0.22)'}`, borderRadius: 10, padding: '12px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                          <span style={{ fontSize: 16, flexShrink: 0, lineHeight: 1.3 }}>{w.severity === 'high' ? '⚠' : '●'}</span>
                          <div style={{ flex: 1 }}>
                            {w.type && <div style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', fontWeight: 700, color: typeColor[w.severity] || '#F0A500', marginBottom: 4 }}>{typeLabel[w.type] || w.type} caution</div>}
                            <div style={{ fontSize: 13, color: G.fog, lineHeight: 1.65 }}>{w.message}</div>
                            {w.alternatives_note && (
                              <div style={{ marginTop: 8, fontSize: 11.5, color: G.mist, lineHeight: 1.6, paddingLeft: 10, borderLeft: '2px solid rgba(255,255,255,0.1)' }}>
                                {w.alternatives_note}
                              </div>
                            )}
                            {w.alternatives && w.alternatives.length > 0 && (
                              <div style={{ marginTop: 10 }}>
                                <div style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: G.gold, fontWeight: 700, marginBottom: 8 }}>Consider instead</div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  {w.alternatives.map((alt, ai) => (
                                    <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.15)', borderRadius: 7, padding: '8px 12px' }}>
                                      <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: 12.5, color: G.fog, fontWeight: 500, lineHeight: 1.3 }}>{alt.name}</div>
                                        <div style={{ fontSize: 11, color: G.mist, marginTop: 2 }}>
                                          {alt.amc}
                                          {alt.expense_ratio ? <span style={{ marginLeft: 8, color: '#27AE78' }}>ER {alt.expense_ratio.toFixed(2)}%</span> : null}
                                        </div>
                                      </div>
                                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3, flexShrink: 0 }}>
                                        <div style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: alt.tier === 1 ? 'rgba(39,174,120,0.15)' : 'rgba(240,165,0,0.12)', color: alt.tier === 1 ? '#27AE78' : '#F0A500', border: `1px solid ${alt.tier === 1 ? 'rgba(39,174,120,0.3)' : 'rgba(240,165,0,0.25)'}` }}>
                                          Tier {alt.tier}
                                        </div>
                                        <div style={{ fontSize: 10, color: G.mist }}>{Math.floor(alt.nav_count / 250)}+ yrs history</div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}

              <div style={{ marginTop: 28, padding: "14px 16px", background: "rgba(255,255,255,0.02)", borderRadius: 10, fontSize: 11, color: G.mist, lineHeight: 1.7 }}>
                Research & education only. Projected CAGR is based on historical rolling returns — not a guarantee. All scores use the same algorithm as FundGuldasta curated bouquets.
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );

  if (screen === "loading") return (
    <>
      <style>{css}</style>
      <div className="loading">
        <div className="lt">Curating your bouquets</div>
        <div className="dots"><div className="dot" /><div className="dot" /><div className="dot" /></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: 380, padding: "0 24px" }}>
          {["Eligibility filter across 14,366 fund schemes", "Scoring funds across 6 dimensions", "Computing rolling returns — 20 years of data", "Building correlation matrix", "Computing confidence scores", "Preparing your bouquets"].map((t, i) => (
            <div key={i} className="lstep" style={{ animationDelay: `${0.3 + i * 0.35}s` }}>✓ {t}</div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: G.mist, marginTop: 8 }}>
          <span style={{ color: G.em, fontWeight: 600 }}>● Live Data</span> · Connected to fundguldasta.com API
        </div>
      </div>
    </>
  );

  return (
    <>
      {authModal && <AuthModal />}
      {savedPanel && <SavedPanel />}
      <style>{css}</style>
      <div onClick={() => healthOpen && setHealthOpen(false)}>
        <div className="rbar">
          <div className="rbar-l">
            <div className="rbn">FundGuldasta</div>
            <button className="bbtn" style={{ color: G.mist }} onClick={() => setScreen("about")}>About</button>
            <button className="bbtn" onClick={reset}>← New Search</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px" }} onClick={() => setScreen("custom_builder")}>✎ Build Your Own</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px", background:"rgba(212,175,55,0.08)" }} onClick={() => setScreen("portfolio")}>📊 My Portfolio</button>
            <div className="pill">{goalPill}</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 11, color: G.mist }}>fundguldasta.com · Research & Education · Not Investment Advice</div>
            {pwaPrompt && (
              <button
                onClick={() => { pwaPrompt.prompt(); pwaPrompt.userChoice.then(() => setPwaPrompt(null)); }}
                style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(212,175,55,0.12)', border:'1px solid rgba(212,175,55,0.4)', borderRadius:8, padding:'5px 14px', color:'#D4AF37', fontFamily:'Outfit,sans-serif', fontSize:11, fontWeight:600, cursor:'pointer', letterSpacing:'.04em' }}
              >
                <img src="/logo-bouquet-real.png" alt="" style={{width:20,height:20,objectFit:'cover',borderRadius:4,flexShrink:0}} />
                Install App
              </button>
            )}
            {user ? (
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <button onClick={() => setSavedPanel(true)}
                  style={{ background:"rgba(212,175,55,0.1)", border:`1px solid rgba(212,175,55,0.35)`, borderRadius:8,
                    padding:"5px 12px", color:G.gold, fontSize:11, fontWeight:600, cursor:"pointer",
                    fontFamily:"Outfit,sans-serif", display:"flex", alignItems:"center", gap:5 }}>
                  &#9733; {savedList.length > 0 ? savedList.length : ""} Saved
                </button>
                <span style={{ fontSize:11, color:G.gold, fontWeight:600 }}>{user.display_name}</span>
                <button onClick={handleSignOut}
                  style={{ background:"none", border:`1px solid ${G.bord}`, borderRadius:6, padding:"4px 10px",
                    color:G.slate, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
                  Sign Out
                </button>
              </div>
            ) : (
              <button onClick={() => { setAuthTab("login"); setAuthModal(true); }}
                style={{ background:"rgba(212,175,55,0.1)", border:`1px solid rgba(212,175,55,0.35)`, borderRadius:8,
                  padding:"5px 16px", color:G.gold, fontSize:11, fontWeight:600, cursor:"pointer",
                  fontFamily:"Outfit,sans-serif", letterSpacing:".04em" }}>
                Sign In
              </button>
            )}
            <HealthIndicator />
          </div>
        </div>
        {selectedArch && (
          <div className="sec-nav">
            {[
              ["Composition","sec-composition"],
              ["Direct vs Reg","sec-dvr"],
              ["Metrics","sec-metrics"],
              ["Confidence","sec-confidence"],
              ["Stress Test","sec-stress"],
              ["Correlation","sec-correlation"],
              ["Strengths","sec-strengths"],
              ["Methodology","sec-methodology"],
            ].map(([label, id]) => (
              <button key={id} className="sec-nav-btn" onClick={() => {
                const el = document.getElementById(id);
                if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
              }}>{label}</button>
            ))}
          </div>
        )}
        <div className="rbody">
          <div className="philo">
            <div className="pt">Curation Philosophy</div>
            <p className="pb">
              <strong>Where history is complete — we show you history.</strong> Where history is partial — we show you what exists and tell you what we don't know.
              <strong> We will never give you false assurance. We will never hide uncertainty in footnotes.</strong>
            </p>
          </div>

          {showBehav && (
            <div className="card">
              <div className="ch">
                <span className="ct">Behavioural Calibration</span>
                <button className="bbtn" onClick={() => setShowBehav(false)}>Skip →</button>
              </div>
              <div className="cb">
                <p style={{ fontSize: 13, color: G.mist, marginBottom: 20, lineHeight: 1.7 }}>
                  Optional but important. Research shows investors capture 3–5% less than fund returns due to reactive behaviour. Three real scenarios. Honest answers only.
                </p>
                {!bDone ? (
                  <>
                    <div style={{ fontSize: 11, color: G.mist, marginBottom: 14 }}>Scenario {bStep + 1} of {SCENARIOS.length}</div>
                    {(() => {
                      const sc = SCENARIOS[bStep];
                      return (
                        <div className="sc" style={{ borderLeftColor: sc.borderColor }}>
                          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: ".1em", textTransform: "uppercase", color: sc.borderColor, marginBottom: 10 }}>{sc.title} · {sc.date}</div>
                          <div style={{ fontSize: 13, color: G.fog, lineHeight: 1.8, marginBottom: 16 }} dangerouslySetInnerHTML={{ __html: sc.situation }} />
                          <div style={{ fontSize: 12, color: G.mist, marginBottom: 12, fontStyle: "italic" }}>{sc.question}</div>
                          <div className="opts">
                            {sc.options.map(o => (
                              <button key={o.id} className={`opt${bAns[sc.id]?.optId === o.id ? " sel" : ""}`}
                                onClick={() => handleScenario(sc.id, o.id, o.score)}>{o.text}</button>
                            ))}
                          </div>
                        </div>
                      );
                    })()}
                  </>
                ) : bProf && (
                  <div className="pbox" style={{ borderColor: bProf.color }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: bProf.color, marginBottom: 8 }}>Your Profile: {bProf.type}</div>
                    <p style={{ fontSize: 13, color: G.fog, lineHeight: 1.7 }}>{bProf.text}</p>
                    <div style={{ marginTop: 10, fontSize: 11, color: G.mist }}>Suggested archetype highlighted below. You may select any archetype.</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {approxHorizon && (
            <div className="advisory" style={{ background: "rgba(39,174,120,0.08)", borderColor: "rgba(39,174,120,0.25)" }}>
              <div className="adv-icon">ℹ️</div>
              <div className="adv-body">
                <div className="adv-cat" style={{ color: "#27AE78" }}>Approximate Results</div>
                <div className="adv-msg">Showing bouquets for <strong>{approxHorizon.used}-year</strong> horizon. Your {approxHorizon.requested}-year analysis is computing in background — refresh in ~2 minutes for exact results.</div>
                <button className="adv-dismiss" onClick={() => setApproxHorizon(null)}>Got it</button>
              </div>
            </div>
          )}

          {cagrAdvisory && cagrAdvisory.category !== "realistic" && (
            <div className="advisory">
              <div className="adv-header">
                <span className="adv-title">Research Advisory</span>
                <button className="adv-close" onClick={() => setCagrAdvisory(null)}>×</button>
              </div>
              <div className="adv-sections">
                {cagrAdvisory.horizon_suitability && cagrAdvisory.horizon_suitability.level !== "good" && cagrAdvisory.horizon_suitability.level !== "ideal" && (
                  <div className="adv-row">
                    <div className="adv-row-label">Investment Horizon</div>
                    <div className="adv-row-content">
                      <span className={`adv-badge ${cagrAdvisory.horizon_suitability.level}`}>
                        {{unsuitable:"Not Suitable",caution:"Short Horizon",acceptable:"Acceptable",good:"Good",ideal:"Ideal"}[cagrAdvisory.horizon_suitability.level]}
                      </span>
                      {cagrAdvisory.horizon_suitability.message}
                    </div>
                  </div>
                )}
                <div className="adv-row">
                  <div className="adv-row-label">CAGR Realism Assessment</div>
                  <div className="adv-row-content">
                    <span className={`adv-badge ${cagrAdvisory.category}`}>
                      {{unrealistic:"Historically Unrealistic",aggressive:"Aggressive Target",below_realistic:"Below Typical",below_fd:"Below FD Rate",realistic:"Realistic"}[cagrAdvisory.category] || cagrAdvisory.category}
                    </span>
                    {cagrAdvisory.message}
                  </div>
                  {cagrAdvisory.probability != null && (
                    <div className="adv-prob">Historical probability of achieving this target: <strong>~{cagrAdvisory.probability}%</strong> of rolling windows since 2001</div>
                  )}
                </div>
                {cagrAdvisory.corpus_comparison && (
                  <div className="adv-row">
                    <div className="adv-row-label">₹10 Lakh projection over {cagrAdvisory.corpus_comparison.horizon_years} years</div>
                    <table className="ra-table">
                      <thead><tr><th>Scenario</th><th>CAGR</th><th>Corpus</th></tr></thead>
                      <tbody>
                        <tr><td>FD (approx.)</td><td>{cagrAdvisory.corpus_comparison.fd_cagr}%</td><td>₹{(cagrAdvisory.corpus_comparison.fd_corpus/100000).toFixed(1)}L</td></tr>
                        <tr><td>Realistic MF mid</td><td>{cagrAdvisory.corpus_comparison.realistic_cagr}%</td><td>₹{(cagrAdvisory.corpus_comparison.realistic_corpus/100000).toFixed(1)}L</td></tr>
                        <tr className="ra-target-row"><td>Your target</td><td>{cagrAdvisory.corpus_comparison.target_cagr}%</td><td>₹{(cagrAdvisory.corpus_comparison.target_corpus/100000).toFixed(1)}L</td></tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div className="adv-proceed">
                <button className="adv-proceed-btn" onClick={() => setCagrAdvisory(null)}>I understand — show my bouquets →</button>
              </div>
            </div>
          )}

          <div style={{ marginBottom: 26 }}>
            <div className="slbl">Select Your Risk Archetype</div>
            <div className="spec">
              {archetypes.map(at => (
                <div key={at.id} className={`arch${selectedArch?.id === at.id ? " sel" : ""}`}
                  style={{ "--ac": at.color, "--ar": at.rgb }} onClick={() => setSelectedArch(at)}>
                  <div style={{ fontSize: 22, marginBottom: 8 }}>{at.icon}</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: G.white, marginBottom: 4 }}>{at.label}</div>
                  <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 18, fontWeight: 500, color: at.color, marginBottom: 4 }}>{at.cagrRange}</div>
                  <div style={{ fontSize: 11, color: G.mist }}>{at.risk} Risk</div>
                  {bProf?.archId === at.id && <div style={{ fontSize: 10, fontWeight: 600, color: at.color, marginTop: 6 }}>↑ Suggested for you</div>}
                  {(at.matchLabel === 'Best Match' || at.matchLabel === 'Closest Match')
                    ? <div className="match-best">{at.matchLabel}</div>
                    : at.matchLabel && <div className="match-label">{at.matchLabel}</div>}
                  <button onClick={e => { e.stopPropagation(); handleSaveBouquet(at); }}
                    title={savedMsg[at.id] ? "Saved!" : "Save bouquet"}
                    style={{ marginTop:8, background:"none", border:`1px solid ${savedMsg[at.id] ? at.color : "rgba(255,255,255,0.12)"}`,
                      borderRadius:6, padding:"3px 10px", color:savedMsg[at.id] ? at.color : G.mist,
                      fontSize:10, cursor:"pointer", fontFamily:"Outfit,sans-serif", fontWeight:600, transition:"all .2s" }}>
                    {savedMsg[at.id] ? "✓ Saved" : "☆ Save"}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* GENERATE MORE BOUQUETS */}
          {archetypes.length > 0 && (
            <div>
              {/* Alternative rounds */}
              {altRounds.map((round, ri) => (
                <div key={round.roundNumber}>
                  <div className="alt-round-header">
                    <div className="alt-round-divider" />
                    <div style={{ textAlign: "center" }}>
                      <div className="alt-round-label">Alternative Bouquet Set {round.roundNumber}</div>
                      <div className="alt-round-note">{round.poolSize} eligible funds in universe after previous exclusions</div>
                    </div>
                    <div className="alt-round-divider" style={{ background: "linear-gradient(270deg,rgba(212,175,55,0.2),transparent)" }} />
                  </div>
                  <div className="slbl">Archetype Options — Round {round.roundNumber}</div>
                  <div className="spec">
                    {round.archetypes.map(at => (
                      <div key={at.id + "-r" + round.roundNumber}
                        className={`arch${selectedArch?.id === at.id && selectedArch?.roundNumber === round.roundNumber ? " sel" : ""}`}
                        style={{ "--ac": at.color, "--ar": at.rgb }}
                        onClick={() => setSelectedArch({ ...at, roundNumber: round.roundNumber })}>
                        <div style={{ fontSize: 22, marginBottom: 8 }}>{at.icon}</div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: G.white, marginBottom: 4 }}>{at.label}</div>
                        <div style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 18, fontWeight: 500, color: at.color, marginBottom: 4 }}>{at.cagrRange}</div>
                        <div style={{ fontSize: 11, color: G.mist }}>{at.risk} Risk</div>
                        {(at.matchLabel === "Best Match" || at.matchLabel === "Closest Match")
                          ? <div className="match-best">{at.matchLabel}</div>
                          : at.matchLabel && at.matchLabel !== "Alternative" && <div className="match-label">{at.matchLabel}</div>}
                        <div style={{ fontSize: 9, color: "rgba(255,255,255,0.2)", marginTop: 5, letterSpacing: ".04em" }}>Alt Round {round.roundNumber}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* Loading state */}
              {altLoading && (
                <div className="gen-loading">
                  <div className="gen-spinner" />
                  <div>Scoring {300 - altRounds.length * 20}+ funds from the eligible universe...</div>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.2)" }}>This takes 2-4 minutes. Same engine, different fund pool.</div>
                </div>
              )}

              {/* Pool exhausted */}
              {altPoolExhausted && !altLoading && (
                <div className="gen-exhausted">
                  All unique bouquet combinations from our eligible fund universe have been shown. {altRounds.length + 1} rounds of options curated.
                </div>
              )}

              {/* Generate More CTA */}
              {!altLoading && !altPoolExhausted && altRounds.length < 3 && (
                <div className="gen-more-cta">
                  <div className="gen-more-title">Want another set of bouquets?</div>
                  <div className="gen-more-sub">
                    We will curate another round using different funds from our eligible universe — same scoring engine, no repetition from previous rounds.
                    {altRounds.length === 0 ? " Takes 2-4 minutes." : ""}
                  </div>
                  {altError && <div style={{ color: "#E05555", fontSize: 12, marginBottom: 12 }}>{altError}</div>}
                  <button className="gen-more-btn" onClick={handleGenerateMore}>
                    Curate {altRounds.length === 0 ? "Another" : "One More"} Bouquet Set
                  </button>
                </div>
              )}
            </div>
          )}

          {a && (
            <>
              <div className="exec">
                <div>
                  <h3 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 20, color: G.white, marginBottom: 6 }}>{a.label} · {a.cagrRange} Historical CAGR</h3>
                  <p style={{ fontSize: 13, color: G.slate, lineHeight: 1.6 }}>Research complete. Execute on a SEBI-registered platform — not here.</p>
                </div>
                <div className="exb" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', gap: 4, marginRight: 4 }}>
                    {[{code:"en",label:"EN"},{code:"hi",label:"हि"},{code:"rh",label:"Ro"}].map(lang => (
                      <button key={lang.code}
                        onClick={() => { i18n.changeLanguage(lang.code); localStorage.setItem("fg_lang", lang.code); }}
                        style={{ background: i18n.language === lang.code ? "rgba(212,175,55,0.18)" : "transparent", border: "1px solid " + (i18n.language === lang.code ? "rgba(212,175,55,0.5)" : "rgba(255,255,255,0.12)"), borderRadius: 6, padding: "4px 9px", color: i18n.language === lang.code ? G.gold : G.mist, fontSize: 10, cursor: "pointer", fontFamily: "Outfit,sans-serif", fontWeight: i18n.language === lang.code ? 600 : 400, transition: "all .15s" }}
                      >{lang.label}</button>
                    ))}
                  </div>
                  <button
                    className={"ai-toggle-btn" + (aiPanelOpen ? " active" : "")}
                    onClick={() => { setAiPanelOpen(o => !o); setAiResponse(""); setAiError(null); setAiQuestion(""); }}
                  >
                    <span style={{ fontSize: 14 }}>✶</span> {t("advisor.title")}
                  </button>
                  <button className="bo" title="Coming soon — save bouquets to your profile" disabled style={{ opacity: 0.45, cursor: "not-allowed" }}>💾 Save Research</button>
                  <button className="bg2" title="Coming soon — direct link to Kuvera for execution" disabled style={{ opacity: 0.45, cursor: "not-allowed" }}>Invest via Kuvera →</button>
                </div>
              </div>

              {/* AI PANEL */}
              {aiPanelOpen && (
                <div className="ai-panel">
                  <div className="ai-panel-header">
                    <span className="ai-panel-icon">✦</span>
                    <div>
                      <div className="ai-panel-title">Guldasta Advisor</div>
                      <div className="ai-panel-sub">Powered by Claude AI · MF Research & Education only · Not investment advice</div>
                    </div>
                  </div>

                  {/* Scope statement */}
                  <div style={{ marginBottom: 16, padding: '10px 14px', background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.18)', borderRadius: 9, fontSize: 12, color: G.mist, lineHeight: 1.7 }}>
                    <strong style={{ color: G.gold, display: 'block', marginBottom: 3 }}>Guldasta Advisor is scoped to Indian MF research & education only.</strong>
                    Ask about bouquet composition, fund scores, metrics (Sortino, rolling CAGR, confidence score), correlation, stress tests, rebalancing, SEBI categories, and LTCG/STCG tax rules.
                    <span style={{ display: 'block', marginTop: 4, color: '#E05555' }}>It will not make buy/sell recommendations, predict future returns, or answer questions outside mutual fund research.</span>
                  </div>

                  {/* ── TIER 2/3 TOOL BUTTONS ── */}
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                    {[
                      { id: 'rebal', icon: '📊', label: 'Rebalancing Drift' },
                      { id: 'ltcg',  icon: '🧮', label: 'LTCG Calculator' },
                      { id: 'goal',  icon: '🎯', label: 'Goal Advisor' },
                      { id: 'sip',   icon: '📈', label: 'SIP Planner' },
                    ].map(tool => (
                      <button key={tool.id}
                        onClick={() => setAiToolOpen(aiToolOpen === tool.id ? null : tool.id)}
                        style={{
                          background: aiToolOpen === tool.id ? 'rgba(212,175,55,0.15)' : 'rgba(255,255,255,0.04)',
                          border: `1px solid ${aiToolOpen === tool.id ? 'rgba(212,175,55,0.5)' : 'rgba(255,255,255,0.1)'}`,
                          borderRadius: 8, padding: '5px 12px',
                          color: aiToolOpen === tool.id ? G.gold : G.mist,
                          fontSize: 11, cursor: 'pointer', fontFamily: 'Outfit,sans-serif',
                          display: 'flex', alignItems: 'center', gap: 5, transition: 'all .15s',
                        }}
                      >{tool.icon} {tool.label} {aiToolOpen === tool.id ? '▲' : '▼'}</button>
                    ))}
                  </div>

                  {/* ── REBALANCING DRIFT TOOL ── */}
                  {aiToolOpen === 'rebal' && (
                    <div style={{ marginBottom: 16, padding: '14px 16px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
                      <div style={{ fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: G.mist, marginBottom: 12 }}>Enter Current Market Value of Each Fund (₹)</div>
                      {(a?.funds || []).map((f, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                          <div style={{ flex: 1, fontSize: 12, color: G.fog, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</div>
                          <div style={{ fontSize: 10, color: G.mist, minWidth: 58, textAlign: 'right' }}>Target {f.weight}%</div>
                          <input
                            type="number" placeholder="₹ value"
                            value={rebalValues[f.scheme_code] || ''}
                            onChange={e => setRebalValues(v => ({ ...v, [String(f.scheme_code)]: e.target.value }))}
                            style={{ width: 110, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, padding: '5px 8px', color: G.white, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, outline: 'none', textAlign: 'right' }}
                          />
                        </div>
                      ))}
                      {(() => {
                        const funds = a?.funds || [];
                        const total = funds.reduce((s, f) => s + (parseFloat(rebalValues[String(f.scheme_code)]) || 0), 0);
                        if (total === 0) return <div style={{ fontSize: 11, color: G.mist, marginTop: 6 }}>Fill in current values to see drift analysis.</div>;
                        const rows = funds.map(f => {
                          const val = parseFloat(rebalValues[String(f.scheme_code)]) || 0;
                          const actualPct = total > 0 ? (val / total * 100) : 0;
                          const drift = actualPct - f.weight;
                          return { ...f, val, actualPct, drift };
                        });
                        const driftSummary = rows.map(r =>
                          r.name.split(' ').slice(0, 2).join(' ') + ': target ' + r.weight + '%, actual ' + r.actualPct.toFixed(1) + '%, drift ' + (r.drift > 0 ? '+' : '') + r.drift.toFixed(1) + 'pp'
                        ).join('; ');
                        return (
                          <div style={{ marginTop: 12 }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                              <thead>
                                <tr>{['Fund','Target','Actual','Drift'].map(h => (
                                  <th key={h} style={{ textAlign: h === 'Fund' ? 'left' : 'right', padding: '4px 6px', color: G.mist, fontWeight: 400 }}>{h}</th>
                                ))}</tr>
                              </thead>
                              <tbody>
                                {rows.map((r, i) => (
                                  <tr key={i}>
                                    <td style={{ padding: '4px 6px', color: G.fog, maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name.split(' ').slice(0,3).join(' ')}</td>
                                    <td style={{ textAlign: 'right', padding: '4px 6px', color: G.mist, fontFamily: "'JetBrains Mono',monospace" }}>{r.weight}%</td>
                                    <td style={{ textAlign: 'right', padding: '4px 6px', color: G.fog, fontFamily: "'JetBrains Mono',monospace" }}>{r.actualPct.toFixed(1)}%</td>
                                    <td style={{ textAlign: 'right', padding: '4px 6px', fontFamily: "'JetBrains Mono',monospace", fontWeight: Math.abs(r.drift) > 2 ? 600 : 400, color: Math.abs(r.drift) > 5 ? '#E05555' : Math.abs(r.drift) > 2 ? '#F0A500' : '#27AE78' }}>
                                      {r.drift > 0 ? '+' : ''}{r.drift.toFixed(1)}pp
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            <div style={{ marginTop: 6, fontSize: 10, color: G.mist }}>Total: ₹{total.toLocaleString('en-IN')} · Red = drift &gt;5pp · Orange = drift &gt;2pp</div>
                            <button
                              style={{ marginTop: 10, width: '100%', padding: '8px', background: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: 7, color: G.gold, fontSize: 12, cursor: 'pointer', fontFamily: 'Outfit,sans-serif' }}
                              onClick={() => {
                                const q = 'My current portfolio allocation is: ' + driftSummary + '. Total value: ₹' + total.toLocaleString('en-IN') + '. Please identify overweight and underweight funds, and give a step-by-step tax-efficient rebalancing plan. Prefer SIP redirection to avoid tax where possible. Mention the ₹1.25L LTCG annual exemption if selling is needed.';
                                setAiQuestion(q);
                                handleAskAI(q, 'bouquet', null);
                                setAiToolOpen(null);
                              }}
                            >Ask Advisor for rebalancing plan →</button>
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {/* ── LTCG CALCULATOR TOOL ── */}
                  {aiToolOpen === 'ltcg' && (
                    <div style={{ marginBottom: 16, padding: '14px 16px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
                      <div style={{ fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: G.mist, marginBottom: 12 }}>LTCG / STCG Quick Estimator</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                        {[
                          { key: 'purchase', label: 'Purchase value (₹)' },
                          { key: 'current',  label: 'Current value (₹)' },
                          { key: 'months',   label: 'Holding period (months)' },
                        ].map(f => (
                          <div key={f.key}>
                            <div style={{ fontSize: 10, color: G.mist, marginBottom: 4 }}>{f.label}</div>
                            <input type="number" value={ltcgInputs[f.key] || ''}
                              onChange={e => { setLtcgInputs(v => ({ ...v, [f.key]: e.target.value })); setLtcgResult(null); }}
                              style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, padding: '7px 10px', color: G.white, fontFamily: "'JetBrains Mono',monospace", fontSize: 13, outline: 'none' }}
                            />
                          </div>
                        ))}
                        <div>
                          <div style={{ fontSize: 10, color: G.mist, marginBottom: 4 }}>Fund type</div>
                          <select value={ltcgInputs.fundType || 'equity'}
                            onChange={e => { setLtcgInputs(v => ({ ...v, fundType: e.target.value })); setLtcgResult(null); }}
                            style={{ width: '100%', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, padding: '7px 10px', color: G.white, fontFamily: 'Outfit,sans-serif', fontSize: 13, outline: 'none' }}
                          >
                            <option value="equity">Equity / Flexi Cap / Midcap / Small Cap</option>
                            <option value="debt">Debt / FOF / International (Nasdaq 100)</option>
                          </select>
                        </div>
                      </div>
                      <button
                        style={{ width: '100%', padding: '8px', background: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: 7, color: G.gold, fontSize: 12, cursor: 'pointer', fontFamily: 'Outfit,sans-serif' }}
                        onClick={() => {
                          const p = parseFloat(ltcgInputs.purchase), c = parseFloat(ltcgInputs.current), m = parseInt(ltcgInputs.months);
                          if (!p || !c || !m) return;
                          setLtcgResult(computeLTCG(p, c, m, ltcgInputs.fundType || 'equity'));
                        }}
                      >Calculate →</button>
                      {ltcgResult && (
                        <div style={{ marginTop: 12, padding: '12px 14px', background: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.15)', borderRadius: 8 }}>
                          {[
                            { label: 'Gross gain', value: '₹' + Math.round(Math.abs(ltcgResult.gain)).toLocaleString('en-IN'), color: ltcgResult.gain >= 0 ? '#27AE78' : '#E05555' },
                            { label: 'Tax type', value: ltcgResult.taxType, color: G.fog },
                            { label: 'Estimated tax', value: ltcgResult.tax !== null ? '₹' + Math.round(ltcgResult.tax).toLocaleString('en-IN') : 'At your income slab rate', color: '#F0A500' },
                            { label: 'Net post-tax gain', value: ltcgResult.netGain !== null ? '₹' + Math.round(ltcgResult.netGain).toLocaleString('en-IN') : 'Depends on slab', color: '#27AE78' },
                          ].map((row, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '5px 0', borderBottom: i < 3 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                              <span style={{ color: G.mist }}>{row.label}</span>
                              <span style={{ color: row.color, fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{row.value}</span>
                            </div>
                          ))}
                          <div style={{ marginTop: 8, fontSize: 10, color: G.mist, lineHeight: 1.6 }}>
                            Equity LTCG exemption: ₹1.25L per financial year (FY). Debt/FOF/International funds taxed as ordinary income — no flat rate benefit. Consult a CA for exact computation.
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── GOAL ADVISOR TOOL ── */}
                  {aiToolOpen === 'goal' && (
                    <div style={{ marginBottom: 16, padding: '14px 16px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
                      <div style={{ fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: G.mist, marginBottom: 8 }}>Describe Your Situation — Advisor Maps You to the Right Archetype</div>
                      <div style={{ fontSize: 11, color: G.mist, marginBottom: 10, lineHeight: 1.6 }}>e.g. "I am 34, salaried ₹1.2L/month, investing ₹20K/month SIP. Goal: retire comfortably in 18 years. I can handle some volatility but got nervous in COVID crash. Already have PPF and NPS."</div>
                      <textarea
                        placeholder="Describe your age, income, SIP amount, goal, timeline, and risk tolerance..."
                        value={aiQuestion}
                        onChange={e => setAiQuestion(e.target.value)}
                        rows={3}
                        style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 12px', color: G.white, fontFamily: 'Outfit,sans-serif', fontSize: 13, outline: 'none', resize: 'vertical', lineHeight: 1.6 }}
                      />
                      <button
                        disabled={aiLoading || !aiQuestion.trim()}
                        style={{ marginTop: 8, width: '100%', padding: '8px', background: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: 7, color: G.gold, fontSize: 12, cursor: 'pointer', fontFamily: 'Outfit,sans-serif', opacity: aiLoading || !aiQuestion.trim() ? 0.4 : 1 }}
                        onClick={() => {
                          const fullQ = aiQuestion + '\n\nBased on this profile, which of the 4 FundGuldasta archetypes (Steady Compounder 14-16% CAGR, Balanced Growther 15-17%, Aggressive Achiever 16-19%, High Conviction 18-22%) suits me best? Explain why in plain English. Also tell me which archetype to avoid and why.';
                          handleAskAI(fullQ, 'general', {});
                          setAiToolOpen(null);
                        }}
                      >{aiLoading ? '...' : 'Find My Best Archetype →'}</button>
                    </div>
                  )}

                  {/* ── SIP PLANNER TOOL ── */}
                  {aiToolOpen === 'sip' && (
                    <div style={{ marginBottom: 16, padding: '14px 16px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
                      <div style={{ fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: G.mist, marginBottom: 12 }}>SIP Planner — How Much Monthly to Reach Your Goal</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 10 }}>
                        {[
                          { key: 'targetCorpus', label: 'Target corpus (₹)', ph: '10000000' },
                          { key: 'horizon',      label: 'Time horizon (years)', ph: String(yrs || 7) },
                          { key: 'cagr',         label: 'Expected CAGR (%)', ph: String(a?.metrics?.bouquet_cagr?.toFixed ? a.metrics.bouquet_cagr.toFixed(1) : 14) },
                        ].map(f => (
                          <div key={f.key}>
                            <div style={{ fontSize: 10, color: G.mist, marginBottom: 4 }}>{f.label}</div>
                            <input type="number" value={sipInputs[f.key] || ''} placeholder={f.ph}
                              onChange={e => setSipInputs(v => ({ ...v, [f.key]: e.target.value }))}
                              style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, padding: '7px 10px', color: G.white, fontFamily: "'JetBrains Mono',monospace", fontSize: 13, outline: 'none' }}
                            />
                          </div>
                        ))}
                      </div>
                      {(() => {
                        const corpus = parseFloat(sipInputs.targetCorpus);
                        const horizon = parseFloat(sipInputs.horizon) || (yrs || 7);
                        const cagr = parseFloat(sipInputs.cagr) || (a?.metrics?.bouquet_cagr || 14);
                        if (!corpus) return <div style={{ fontSize: 11, color: G.mist }}>Enter a target corpus to calculate your required SIP.</div>;
                        const r = cagr / 100 / 12;
                        const n = horizon * 12;
                        const sip = r === 0 ? corpus / n : (corpus * r) / (Math.pow(1 + r, n) - 1);
                        const totalInvested = sip * n;
                        const multiplier = corpus / totalInvested;
                        return (
                          <div style={{ padding: '12px 14px', background: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.15)', borderRadius: 8 }}>
                            {[
                              { label: 'Required monthly SIP', value: '₹' + Math.round(sip).toLocaleString('en-IN'), big: true, color: G.gold },
                              { label: 'Total invested over ' + horizon + ' yrs', value: '₹' + Math.round(totalInvested).toLocaleString('en-IN'), color: G.fog },
                              { label: 'Expected corpus', value: '₹' + Math.round(corpus).toLocaleString('en-IN'), color: '#27AE78' },
                              { label: 'Wealth multiplier', value: multiplier.toFixed(1) + 'x', color: '#27AE78' },
                            ].map((row, i) => (
                              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: row.big ? 15 : 12, padding: '5px 0', borderBottom: i < 3 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                                <span style={{ color: G.mist }}>{row.label}</span>
                                <span style={{ color: row.color, fontFamily: "'JetBrains Mono',monospace", fontWeight: row.big ? 700 : 500 }}>{row.value}</span>
                              </div>
                            ))}
                            <div style={{ marginTop: 8, fontSize: 10, color: G.mist, lineHeight: 1.6 }}>
                              Pre-tax returns. Actual SIP needed may be higher to account for LTCG tax on redemption. Adjust CAGR down by 1-2% for conservative planning.
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {/* ── BOUQUET Q&A CHIPS ── */}
                  <div style={{ fontSize: 10, color: G.mist, letterSpacing: '.06em', textTransform: 'uppercase', marginBottom: 7 }}>Bouquet Q&amp;A</div>
                  <div className="ai-chips" style={{ marginBottom: 14 }}>
                    {[
                      { label: "Why these 5 funds together?", q: "Explain why these specific funds were chosen together and what each contributes to the bouquet." },
                      { label: "Explain the correlation numbers", q: "Explain what the inter-fund correlation numbers mean for me as an investor, in plain English." },
                      { label: "What does the confidence score mean?", q: "What does the confidence score mean and what factors drive it up or down?" },
                      { label: "Explain the stress test results", q: "What do the stress test and crisis recovery numbers tell me about how this bouquet might behave in a market crash?" },
                      { label: "Which fund is weakest here?", q: "Looking at the composite scores and dimension scores, which fund in this bouquet is the weakest link and why?" },
                      { label: "How does rebalancing affect CAGR?", q: "Can you explain how failing to rebalance annually could affect the actual CAGR I achieve versus the projected figure?" },
                    ].map((chip, ci) => (
                      <button key={ci} className="ai-chip" onClick={() => { setAiQuestion(chip.q); handleAskAI(chip.q, 'bouquet', null); }}>{chip.label}</button>
                    ))}
                  </div>

                  {/* ── MARKET & TAX EDUCATION CHIPS ── */}
                  <div style={{ fontSize: 10, color: G.mist, letterSpacing: '.06em', textTransform: 'uppercase', marginBottom: 7 }}>Market & Tax Education</div>
                  <div className="ai-chips">
                    {[
                      { label: "Market fell 20% — should I panic?", q: "The market has fallen 20%. Based on this bouquet's stress test and historical crisis recovery data, what typically happens next and what should I actually do? Be honest and data-grounded." },
                      { label: "Why not just buy Nifty 50 index?", q: "What is the realistic difference between this bouquet and simply buying a Nifty 50 index fund? When does active fund selection actually beat an index, and when does it not? Be honest." },
                      { label: "Explain LTCG vs STCG for equity MFs", q: "Explain LTCG and STCG tax rules for Indian equity mutual funds in plain English. Include the ₹1.25L annual exemption, current rates (LTCG 10%, STCG 20%), and why Motilal Nasdaq 100 FOF is taxed differently as a debt/FOF fund." },
                      { label: "What is the SEBI category of each fund?", q: "Explain the SEBI category of each fund in this bouquet (Large Cap, Flexi Cap, Mid Cap etc.) and why category diversity matters for risk management and correlation reduction." },
                      { label: "When should I exit this bouquet?", q: "Under what conditions should I consider exiting or significantly changing this bouquet? What are the early warning signs that it is no longer suitable for my financial goal?" },
                    ].map((chip, ci) => (
                      <button key={ci} className="ai-chip" onClick={() => { setAiQuestion(chip.q); handleAskAI(chip.q, 'bouquet', null); }}>{chip.label}</button>
                    ))}
                  </div>

                  {/* Free-form input */}
                  <div className="ai-input-row">
                    <input
                      className="ai-input"
                      type="text"
                      placeholder="Ask about any fund, metric, SEBI category, tax rule, or rebalancing concept..."
                      value={aiQuestion}
                      onChange={e => setAiQuestion(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !aiLoading) handleAskAI(null, 'bouquet', null); }}
                    />
                    <button className="ai-send-btn" disabled={aiLoading || !aiQuestion.trim()} onClick={() => handleAskAI(null, 'bouquet', null)}>
                      {aiLoading ? '...' : 'Ask Advisor →'}
                    </button>
                  </div>

                  {/* Loading state */}
                  {aiLoading && (
                    <div className="ai-thinking">
                      <span>Guldasta Advisor is thinking</span>
                      <span className="ai-thinking-dots"><span /><span /><span /></span>
                    </div>
                  )}

                  {/* Error state */}
                  {aiError && (
                    <div style={{ marginTop: 14, padding: '10px 14px', background: 'rgba(224,85,85,0.08)', border: '1px solid rgba(224,85,85,0.2)', borderRadius: 8, fontSize: 12, color: '#E05555' }}>
                      {aiError}
                    </div>
                  )}

                  {/* Streamed response */}
                  {aiResponse && (
                    <div>
                      <div className="ai-response">{aiResponse}</div>
                    </div>
                  )}
                </div>
              )}

              {/* BOX 3 — FUNDS */}
              <div className="card" id="sec-composition">
                <div className="ch"><span className="ct">Bouquet Composition</span><span className="badge bg-gold">5 Funds · Direct Plans · No Commission</span>{customizeApplied && <span className="cx-applied">✎ Customized</span>}</div>
                <div className="cb">
                  <div className="fg">
                    {(() => {
                      const appliedCode = customizeApplied?.replacement_slot?.replaced_code;
                      const effectiveFunds = (a.funds || []).map(f =>
                        appliedCode && String(f.scheme_code) === String(appliedCode)
                          ? { ...f, ...customizeApplied.replacement_fund, weight: f.weight, tier: customizeApplied.replacement_fund?.tier || f.tier, composite_score: customizeApplied.replacement_score?.composite_score, customized: true }
                          : f
                      );
                      return effectiveFunds.map((f, i) => {
                        const isTarget = customizeOpen && !customizeApplied && customizeTargetFund?.scheme_code === String(f.scheme_code);
                        const isCustomized = f.customized;
                        return (
                          <div
                            key={i}
                            className={"fc" + (isTarget ? " cx-fund-target" : "") + (isCustomized ? " cx-fund-replaced" : "")}
                            onClick={() => {
                              if (!customizeOpen || customizeApplied) return;
                              setCustomizeTargetFund(isTarget ? null : { scheme_code: String(f.scheme_code), name: f.name, weight: f.weight, category: f.category });
                              setCustomizeComparing(null);
                              setCustomizeSearch('');
                              setCustomizeResults([]);
                            }}
                            style={{ cursor: customizeOpen && !customizeApplied ? 'pointer' : 'default' }}
                          >
                            {isTarget && <div className="cx-target-label">← replacing this</div>}
                            {isCustomized && <div className="cx-replaced-label">✎ Customized</div>}
                            <div className="fw">{f.weight}%</div>
                            <div className="fn">{f.name}</div>
                            <div className="fcat">{f.category}</div>
                            <div className="fm">
                              AMC: <span>{f.amc}</span><br />
                              Score: <span>{f.composite_score?.toFixed ? f.composite_score.toFixed(1) : f.composite_score}</span>
                            </div>
                            <div className={`tier t${f.tier}`}>
                              {f.tier === 1 ? "✅ Full Record" : f.tier === 2 ? "🟢 Substantial" : "🟡 On Potential"}
                            </div>
                            {f.managers && <div style={{ fontSize: 10, color: "rgba(255,255,255,0.45)", marginTop: 4 }}><span style={{ color: "rgba(255,255,255,0.3)" }}>Mgr: </span>{f.managers}</div>}
                            {f.expense_ratio != null && <div style={{ fontSize: 10, marginTop: 2 }}><span style={{ color: "rgba(255,255,255,0.3)" }}>TER: </span><span style={{ color: "#27AE78" }}>{f.expense_ratio.toFixed(2)}%</span></div>}
                            {f.aum_crores != null && <div style={{ fontSize: 10, marginTop: 2 }}><span style={{ color: "rgba(255,255,255,0.3)" }}>AUM: </span><span style={{ color: "rgba(255,255,255,0.6)" }}>₹{f.aum_crores >= 100000 ? (f.aum_crores/100000).toFixed(1)+'L Cr' : f.aum_crores >= 1000 ? (f.aum_crores/1000).toFixed(1)+'K Cr' : f.aum_crores+' Cr'}</span></div>}
                            {f.category !== 'Balanced Advantage' && <div style={{ fontSize: 9, color: "rgba(255,255,255,0.25)", marginTop: 5, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 5 }}>Exit load: 1% if redeemed within 12 months</div>}
                          </div>
                        );
                      });
                    })()}
                  </div>
                </div>
                  <button className="customize-toggle" onClick={() => setCustomizeOpen(o => !o)}>
                    {customizeOpen ? "▲ Close Customization" : "✎ Customize this bouquet"}
                  </button>
                  {customizeOpen && (
                    <div className="customize-panel">
                      {!customizeTargetFund ? (
                        <div style={{ fontSize: 12, color: G.gold, marginBottom: 10, padding: '8px 12px', background: 'rgba(212,175,55,0.07)', borderRadius: 8, border: '1px solid rgba(212,175,55,0.2)' }}>
                          ↑ Click any fund in the composition above to select which one you want to replace
                        </div>
                      ) : (
                        <div style={{ fontSize: 12, color: G.mist, marginBottom: 10 }}>
                          Replacing: <strong style={{ color: G.white }}>{customizeTargetFund.name}</strong> ({customizeTargetFund.weight}%) — search for the fund you prefer
                          <button onClick={() => { setCustomizeTargetFund(null); setCustomizeSearch(''); setCustomizeComparing(null); }} style={{ background: 'none', border: 'none', color: G.mist, cursor: 'pointer', fontSize: 11, marginLeft: 8 }}>✕ change</button>
                        </div>
                      )}
                      <input
                        className="cx-search"
                        type="text"
                        placeholder={customizeTargetFund ? "Search by fund name or AMC..." : "Select a fund above first"}
                        value={customizeSearch}
                        disabled={!customizeTargetFund}
                        onChange={e => handleCustomizeSearch(e.target.value)}
                      />
                      {customizeResults.length > 0 && (
                        <div className="cx-results">
                          {customizeResults.map(f => (
                            <div key={f.scheme_code} className="cx-result" onClick={() => handleCustomizeSelect(f)}>
                              <div className="cx-result-name">{f.name}</div>
                              <div className="cx-result-meta">{f.amc} · {f.category} · {f.tier_label}</div>
                            </div>
                          ))}
                        </div>
                      )}
                      {customizeLoading && <div style={{ color: G.mist, fontSize: 12, marginTop: 10 }}>Analysing substitution...</div>}
                      {customizeComparing && !customizeLoading && (
                        <div className="cx-compare">
                          {customizeComparing.warnings?.map((w, i) => (
                            <div key={i} className="warn-box" style={{ marginBottom: 8 }}>{w}</div>
                          ))}
                          <div style={{ fontSize: 12, color: G.mist, marginBottom: 6 }}>
                            Replacing <strong style={{ color: G.white }}>{customizeComparing.replacement_slot?.replaced_name}</strong> ({customizeComparing.replacement_slot?.replaced_weight}%) with <strong style={{ color: G.gold }}>{customizeComparing.replacement_fund?.name}</strong>
                          </div>
                          <table className="cx-table">
                            <thead><tr><th>Metric</th><th>Original</th><th>Your Choice</th><th>Difference</th></tr></thead>
                            <tbody>
                              {[["Composite Score", customizeComparing.original_score?.composite_score, customizeComparing.replacement_score?.composite_score, "pts"],
                                ["Return Consistency", customizeComparing.original_score?.dimension_scores?.return_consistency, customizeComparing.replacement_score?.dimension_scores?.return_consistency, "pts"],
                                ["Downside Protection", customizeComparing.original_score?.dimension_scores?.downside_behaviour, customizeComparing.replacement_score?.dimension_scores?.downside_behaviour, "pts"],
                                ["Manager Stability", customizeComparing.original_score?.dimension_scores?.manager_stability, customizeComparing.replacement_score?.dimension_scores?.manager_stability, "pts"],
                                ["Risk-Adjusted Quality", customizeComparing.original_score?.dimension_scores?.risk_adjusted, customizeComparing.replacement_score?.dimension_scores?.risk_adjusted, "pts"],
                              ].map(([label, orig, repl, unit]) => {
                                const diff = orig != null && repl != null ? (repl - orig).toFixed(1) : null;
                                const cls = diff > 0 ? "cx-better" : diff < 0 ? "cx-worse" : "";
                                return (
                                  <tr key={label}>
                                    <td>{label}</td>
                                    <td>{orig != null ? orig.toFixed(1) : "—"}</td>
                                    <td className={diff > 0 ? "cx-better" : diff < 0 ? "cx-worse" : ""}>{repl != null ? repl.toFixed(1) : "—"}</td>
                                    <td className={cls}>{diff != null ? (diff > 0 ? "+" : "") + diff : "—"}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                          {customizeComparing.impact?.message && (
                            <div className="cx-impact">📊 {customizeComparing.impact.message}</div>
                          )}
                          <div className="cx-actions">
                            <button className="cx-accept" onClick={() => { setCustomizeApplied(customizeComparing); setCustomizeOpen(false); }}>Accept my preference →</button>
                            <button className="cx-reject" onClick={() => { setCustomizeComparing(null); setCustomizeSearch(""); }}>Keep recommended</button>
                          </div>
                        </div>
                      )}
                      {customizeApplied && (
                        <div style={{ marginTop: 12, fontSize: 12, color: "#27AE78" }}>✓ Customization applied. <button style={{ background: "none", border: "none", color: G.mist, cursor: "pointer", fontSize: 12, padding: 0, marginLeft: 4 }} onClick={() => { setCustomizeApplied(null); setCustomizeSearch(""); setCustomizeComparing(null); }}>Undo</button></div>
                      )}
                    </div>
                  )}
              </div>

              {/* BOX 3.5 — DIRECT vs REGULAR */}
              <div className="card" id="sec-dvr">
                <div className="ch"><span className="ct">Direct vs Regular Plan — What You Save</span><span className="badge" style={{ background: "rgba(39,174,120,0.15)", border: "1px solid rgba(39,174,120,0.3)", color: "#27AE78" }}>Your Advantage</span></div>
                <div className="cb">
                  <p style={{ fontSize: 13, color: G.mist, lineHeight: 1.7, marginBottom: 14 }}>Regular plans pay distributors ~1% extra TER every year. On ₹10L over {parseFloat(yrs)||7} years, this compounds into significant lost wealth — for zero additional service.</p>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                      <thead>
                        <tr>
                          {["Fund", "Direct TER", "Regular (est.)", "Extra wealth on ₹10L"].map(h => (
                            <th key={h} style={{ textAlign: h==="Fund"?"left":"right", padding: "7px 10px", color: G.mist, fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase", borderBottom: `1px solid ${G.bord}` }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(a.funds||[]).map((f,i) => {
                          const ter = typeof f.expense_ratio === "number" ? f.expense_ratio : 0.8;
                          const regTer = ter + 1.0;
                          const yrsN = parseFloat(yrs) || 7;
                          const directCorpus = 10 * Math.pow(1 + (16 - ter)/100, yrsN);
                          const regCorpus = 10 * Math.pow(1 + (16 - regTer)/100, yrsN);
                          const saving = (directCorpus - regCorpus).toFixed(2);
                          return (
                            <tr key={i} style={{ borderBottom: `1px solid rgba(255,255,255,0.03)` }}>
                              <td style={{ padding: "8px 10px", color: G.fog, fontSize: 12 }}>{f.name?.split(' ').slice(0,4).join(' ')}</td>
                              <td style={{ padding: "8px 10px", color: "#27AE78", fontFamily: "'JetBrains Mono',monospace", textAlign: "right" }}>{ter.toFixed(2)}%</td>
                              <td style={{ padding: "8px 10px", color: G.am, fontFamily: "'JetBrains Mono',monospace", textAlign: "right" }}>~{regTer.toFixed(2)}%</td>
                              <td style={{ padding: "8px 10px", color: "#27AE78", fontFamily: "'JetBrains Mono',monospace", textAlign: "right", fontWeight: 600 }}>+₹{saving}L</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ fontSize: 11, color: G.mist, marginTop: 12, lineHeight: 1.6, padding: "10px 14px", background: "rgba(255,255,255,0.02)", borderRadius: 8, borderLeft: `3px solid ${G.gold}` }}>
                    Estimate uses assumed 16% gross return. Regular TER estimated at Direct TER + 1.0% (typical distributor trail). FundGuldasta recommends direct plans only. Verify current TERs on AMFI.
                  </div>
                </div>
              </div>

              {/* BOX 4 — METRICS */}
              <div className="card" id="sec-metrics">
                <div className="ch"><span className="ct">Historical Performance Metrics</span><span className="badge bg-g">Live AMFI Data</span></div>
                <div className="cb" style={{ overflowX: "auto" }}>
                  <table className="mt">
                    <thead>
                      <tr>
                        <th>Period</th><th>Bouquet CAGR</th><th>Post-Tax†</th><th>Real CAGR*</th>
                        <th>Nifty 50</th><th>FD Rate</th><th>FD Real‡</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(a.metrics?.periods || {}).map(([p, r]) => (
                        <tr key={p}>
                          <td>{p}</td>
                          <td className="gc">{r.bouquet}%</td>
                          <td className="zc">{r.postTax}%</td>
                          <td className="ec">{r.realCAGR}%</td>
                          <td className="dc">{r.nifty50 ? `${r.nifty50.toFixed(1)}%` : "—"}</td>
                          <td className="dc">{r.fdRate}%</td>
                          <td className="dc">{(r.fdRate - 6.0).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ marginTop: 14, fontSize: 11, color: G.mist, lineHeight: 1.8 }}>
                    * Real CAGR adjusted for 6% inflation · † Post-Tax assumes 30% slab, 12.5% LTCG · ‡ FD Real = FD Rate minus 6% inflation · All figures from live AMFI NAV data
                  </div>
                  {a.intlTaxWarning && (
                    <div className="itax">⚠️ Tax Alert: Motilal Oswal Nasdaq 100 FOF is taxed as a DEBT fund regardless of holding period. Income slab rate applies — not 12.5% LTCG.</div>
                  )}
                </div>
              </div>

              {/* BOX 5 — CONFIDENCE */}
              <div className="card" id="sec-confidence">
                <div className="ch">
                  <span className="ct">Confidence Score</span>
                  <span className="badge" style={{ background: `rgba(${a.rgb},.12)`, color: a.color }}>{a.confidence?.level}</span>
                </div>
                <div className="cb">
                  <div className="cg">
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                      <div className="dial" style={{ borderColor: a.color }}>
                        <span className="ds" style={{ color: a.color }}>{a.confidence?.score}</span>
                        <span className="dof" style={{ color: a.color }}>/ 100</span>
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: G.white }}>{a.confidence?.level}</span>
                    </div>
                    <div>
                      {Object.entries(a.confidence?.factors || {}).map(([name, f]) => (
                        <div key={name} className="cf">
                          <div className="cfh">
                            <span className="cfn">{name.replace(/_/g, " ")} ({f.weight}%)</span>
                            <span className="cfv">{String(f.value).slice(0, 50)}</span>
                          </div>
                          <div className="bar"><div className="bf" style={{ width: `${f.score}%`, background: f.score >= 70 ? "#22A86A" : f.score >= 40 ? "#E8A000" : "#D84848" }} /></div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div style={{ marginTop: 16, fontSize: 12, color: G.mist, lineHeight: 1.7, padding: "12px 16px", background: G.elv, borderRadius: 8 }}>
                    Score {a.confidence?.score}/100 — computed from {a.confidence?.rolling_period_count} rolling periods.
                    This bouquet beat its target in {a.confidence?.target_beaten_pct}% of all rolling windows.
                    Assessment of historical consistency — not a prediction.
                  </div>
                </div>
              </div>

              {/* BOX 6 — STRESS TEST */}
              <div className="card" id="sec-stress">
                <div className="ch"><span className="ct">Stress Test — Historical Crash Performance</span><span className="badge bg-r">Real Market Data</span></div>
                <div className="cb">
                  <div className="sg">
                    {(a.stressTest?.periods || []).map((s, i) => (
                      <div key={i} className="sk">
                        <div style={{ fontSize: 12, fontWeight: 600, color: G.white, marginBottom: 12 }}>{s.event}</div>
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 10, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 2 }}>Peak Fall</div>
                          <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 18, fontWeight: 500, color: G.ro }}>{s.peakFallPct}%</div>
                        </div>
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 10, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 2 }}>Recovery</div>
                          <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 18, fontWeight: 500, color: G.am }}>{s.recoveryMonths} months</div>
                        </div>
                        {s.postRecoveryCAGR && (
                          <div>
                            <div style={{ fontSize: 10, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 2 }}>Post-Recovery CAGR</div>
                            <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 14, fontWeight: 500, color: G.em }}>+{s.postRecoveryCAGR}%</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* BOX 7 — OVERLAP */}
              <div className="card" id="sec-correlation">
                <div className="ch"><span className="ct">Portfolio Analysis</span><span className="badge bg-g">Correlation Data</span></div>
                <div className="cb">
                  <div style={{ fontSize: 14, color: G.fog, marginBottom: 14 }}>
                    <strong style={{ color: G.white }}>Return Correlation</strong> — computed from daily NAV data
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 52, fontWeight: 500, color: G.em, lineHeight: 1 }}>
                      {a.overlap?.avgCorrelation ?? "—"}
                    </div>
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <div style={{ fontSize: 13, color: G.mist, lineHeight: 1.7 }}>
                        Average inter-fund return correlation across the bouquet. Indian equity funds typically correlate at <strong style={{ color: G.fog }}>0.85–0.95</strong> due to similar large-cap holdings — this is structural, not a flaw.
                      </div>
                      <div style={{ fontSize: 13, color: G.mist, lineHeight: 1.7, marginTop: 6 }}>
                        The Nasdaq 100 allocation provides genuine diversification at correlation ~<strong style={{ color: G.fog }}>0.37</strong> with Indian equity.
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: 14, fontSize: 11, color: G.mist, padding: "8px 12px", background: "rgba(255,255,255,0.02)", borderRadius: 6, lineHeight: 1.6, borderLeft: "3px solid rgba(255,255,255,0.08)" }}>
                    Stock-level overlap (shared holdings) requires individual fund factsheet parsing — that feature is under development. Return correlation above is accurate and computed from 7+ years of daily NAV data.
                  </div>
                </div>
              </div>

              {/* BOX 8 — PROS & CONS */}
              <div className="card" id="sec-strengths">
                <div className="ch"><span className="ct">Strengths & Risks</span><span className="badge bg-gold">Research Perspective</span></div>
                <div className="cb">
                  <div className="pros-cons-grid">
                    <div className="pros-col">
                      <div className="pros-col-header">
                        <span className="pros-col-icon">↑</span> Why This Works
                      </div>
                      <ul className="dl">
                        {(a.pros || []).map((p, i) => (
                          <li key={i} className="di">
                            <span style={{ color: G.em, flexShrink: 0, fontSize: 14, marginTop: 1 }}>✓</span>
                            <span style={{ fontSize: 12, color: G.fog, lineHeight: 1.6 }}>{p}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="cons-col">
                      <div className="cons-col-header">
                        <span className="cons-col-icon">↓</span> Why It Might Not Work
                      </div>
                      <ul className="dl">
                        {(a.devils || []).map((d, i) => (
                          <li key={i} className="di">
                            <span style={{ color: G.ro, flexShrink: 0, fontSize: 14, marginTop: 1 }}>→</span>
                            <span style={{ fontSize: 12, color: G.fog, lineHeight: 1.6 }}>{d}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* REBALANCING GUIDELINES */}
              <div className="card">
                <div className="ch" style={{ cursor: 'pointer' }} onClick={() => setRebalOpen(o => !o)}>
                  <div>
                    <span className="ct">Rebalancing Guidelines</span>
                    <div style={{ fontSize: 11, color: G.mist, marginTop: 3 }}>Portfolio drift silently undermines your target CAGR — rebalancing keeps the bouquet honest</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                    <span className="badge bg-gold">Essential</span>
                    <span style={{ color: G.mist, fontSize: 14 }}>{rebalOpen ? '▲' : '▼'}</span>
                  </div>
                </div>
                {rebalOpen && (
                  <div className="cb">

                    {/* When to rebalance */}
                    <div style={{ marginBottom: 22 }}>
                      <div style={{ fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: G.gold, fontWeight: 700, marginBottom: 12 }}>When to Rebalance</div>
                      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: 200, background: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.15)', borderRadius: 10, padding: '14px 16px' }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: G.gold, marginBottom: 6 }}>Calendar Trigger — Annually</div>
                          <div style={{ fontSize: 12, color: G.fog, lineHeight: 1.7 }}>
                            Pick a fixed date each year — <strong>1st January</strong> works well (post-December NAV
                            prints). Review all fund weights against targets. Set a recurring calendar reminder today.
                          </div>
                        </div>
                        <div style={{ flex: 1, minWidth: 200, background: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.15)', borderRadius: 10, padding: '14px 16px' }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: G.gold, marginBottom: 6 }}>Threshold Trigger — ±5 Points</div>
                          <div style={{ fontSize: 12, color: G.fog, lineHeight: 1.7 }}>
                            Rebalance <em>immediately</em> if any fund drifts <strong>more than 5 percentage points</strong> from
                            its target — regardless of calendar date. Strong bull or bear runs can cause this quickly.
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Target weights table */}
                    <div style={{ marginBottom: 22 }}>
                      <div style={{ fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: G.gold, fontWeight: 700, marginBottom: 12 }}>Target Weights & Rebalancing Bands</div>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.08em', color: G.mist, padding: '7px 10px', borderBottom: `1px solid ${G.bord}` }}>Fund</th>
                            <th style={{ textAlign: 'center', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.08em', color: G.gold, padding: '7px 10px', borderBottom: `1px solid ${G.bord}` }}>Target</th>
                            <th style={{ textAlign: 'center', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.08em', color: '#27AE78', padding: '7px 10px', borderBottom: `1px solid ${G.bord}` }}>Safe Zone</th>
                            <th style={{ textAlign: 'center', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.08em', color: '#E05555', padding: '7px 10px', borderBottom: `1px solid ${G.bord}` }}>Rebalance Trigger</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(a.funds || []).map((f, fi) => {
                            const lo = Math.max(f.weight - 5, 0);
                            const hi = Math.min(f.weight + 5, 100);
                            return (
                              <tr key={fi}>
                                <td style={{ fontSize: 12, color: G.fog, padding: '9px 10px', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                                  {f.name?.length > 38 ? f.name.substring(0, 38) + '…' : f.name}
                                </td>
                                <td style={{ textAlign: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: G.gold, fontWeight: 600, padding: '9px 10px', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>{f.weight}%</td>
                                <td style={{ textAlign: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: '#27AE78', padding: '9px 10px', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>{lo}% – {hi}%</td>
                                <td style={{ textAlign: 'center', fontSize: 12, color: '#E05555', padding: '9px 10px', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                                  {'<'}{lo}% or {'>'}{hi}%
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      <div style={{ fontSize: 11, color: G.mist, marginTop: 8, lineHeight: 1.7 }}>
                        Check your folio statement every January (or quarterly if the market moves sharply).
                        Your platform or AMC app shows current weights — compare against the Target column above.
                      </div>
                    </div>

                    {/* How to rebalance */}
                    <div style={{ marginBottom: 22 }}>
                      <div style={{ fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: G.gold, fontWeight: 700, marginBottom: 12 }}>How to Rebalance</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ display: 'flex', gap: 12, padding: '14px 16px', background: 'rgba(39,174,120,0.05)', border: '1px solid rgba(39,174,120,0.18)', borderRadius: 10 }}>
                          <div style={{ flexShrink: 0, width: 30, height: 30, borderRadius: '50%', background: 'rgba(39,174,120,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#27AE78', fontWeight: 700, marginTop: 1 }}>1</div>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#27AE78', marginBottom: 5 }}>SIP Redirection — Preferred (Zero Tax)</div>
                            <div style={{ fontSize: 12, color: G.fog, lineHeight: 1.7 }}>
                              Pause your SIP in the <em>overweight</em> fund and redirect those monthly contributions to the
                              <em> underweight</em> fund for 3–6 months until weights normalise. No units are sold — no capital
                              gains event is triggered at all. <strong>This is the most tax-efficient rebalancing method for
                              Indian equity investors.</strong> Works best when the drift is moderate ({'<'}10 percentage points).
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 12, padding: '14px 16px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
                          <div style={{ flexShrink: 0, width: 30, height: 30, borderRadius: '50%', background: 'rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: G.fog, fontWeight: 700, marginTop: 1 }}>2</div>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: G.fog, marginBottom: 5 }}>Sell-and-Buy — For Large Drifts</div>
                            <div style={{ fontSize: 12, color: G.fog, lineHeight: 1.7 }}>
                              Redeem units from overweight funds and deploy the proceeds into underweight funds.
                              Two tax rules to keep in mind:
                              <ul style={{ margin: '8px 0 0 0', paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
                                <li><strong style={{ color: G.gold }}>Hold {'>'} 12 months before selling</strong> — Long Term Capital Gains (LTCG) at 10%; Short Term (STCG) at 20%. Always wait for units to age past 12 months where possible.</li>
                                <li><strong style={{ color: G.gold }}>₹1.25 lakh LTCG exemption per financial year</strong> — You can realise up to ₹1.25L of equity LTCG tax-free annually. Plan rebalancing sales to stay within or use this limit efficiently.</li>
                                <li><strong style={{ color: G.gold }}>Exit load</strong> — Most equity funds charge 1% if redeemed within 12 months. Avoid selling units younger than 1 year.</li>
                              </ul>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Why it matters */}
                    <div style={{ padding: '14px 18px', background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.14)', borderRadius: 10, fontSize: 12, color: G.mist, lineHeight: 1.8 }}>
                      <strong style={{ color: G.fog, display: 'block', marginBottom: 5 }}>Why rebalancing is non-negotiable for achieving your target CAGR:</strong>
                      After a strong bull run, your equity funds outperform and your portfolio drifts toward
                      higher-risk, higher-allocation positions. If your Large Cap target is 25% but it grows to 38%,
                      you now have 52% more concentration in one category than intended — your drawdown in the next
                      correction will be deeper, and your actual returns will diverge from this bouquet's projected CAGR.
                      Rebalancing is the maintenance discipline that keeps the portfolio honest to its construction logic.
                      <strong style={{ color: G.gold, display: 'block', marginTop: 8 }}>
                        Research shows disciplined annual rebalancing recovers 0.5–1% of annual CAGR versus a
                        drift-and-forget approach — compounded over {yrs || 7} years, that gap becomes material.
                      </strong>
                    </div>

                  </div>
                )}
              </div>

              {/* BOX 9 — METHODOLOGY */}
              <div className="card" id="sec-methodology">
                <div className="ch"><span className="ct">Selection Methodology</span><span className="badge bg-g">Full Transparency</span></div>
                <div className="cb">
                  <div className="mg">
                    {(a.methodology || []).map((m, i) => (
                      <div key={i} className="mi">
                        <span style={{ color: G.em, flexShrink: 0, fontSize: 13, marginTop: 1 }}>✓</span>
                        <span style={{ fontSize: 12, color: G.fog, lineHeight: 1.5 }}>{m}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 16, padding: '12px 14px', background: 'rgba(240,165,0,0.05)', border: '1px solid rgba(240,165,0,0.15)', borderRadius: 8, fontSize: 11, color: G.mist, lineHeight: 1.7 }}>
                    <strong style={{ color: '#F0A500', display: 'block', marginBottom: 4 }}>Data Transparency â Known Limitations</strong>
                    â¢ <strong>Manager Stability score (15% weight)</strong>: Fund-specific manager data is used for all 13 verified funds — sourced from SIDs and manually verified. Lead manager (earliest appointment = longest tenure) is the primary scoring input; co-manager data is cross-referenced.<br />
                    â¢ <strong>Stock-level portfolio overlap</strong>: Requires parsing AMFI monthly disclosure PDFs. Return correlation (20yr NAV data) is the proxy and is accurate.<br />
                    â¢ <strong>Expense ratio</strong>: Direct plan TER sourced from AMFI; verify current rates at amfiindia.com before investing.
                  </div>
                </div>
              </div>

              {/* BOX 10 — COMPARATOR */}
              <div className="card" id="sec-comparator">
                <div className="ch"><span className="ct">How Does This Compare?</span><span className="badge bg-gold">₹10L Invested · {yrs || 7} Years</span></div>
                <div className="cb">
                  <div className="cog">
                    <div className="coc pri">
                      <div style={{ fontSize: 11, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 12 }}>This Bouquet</div>
                      <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 500, color: G.gold, marginBottom: 5 }}>₹{a.comparator?.bouquetCorpus}L</div>
                      <div style={{ fontSize: 11, color: G.mist }}>{a.cagrRange} historical CAGR</div>
                    </div>
                    <div className="coc">
                      <div style={{ fontSize: 11, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 12 }}>Nifty 50 Index</div>
                      <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 500, color: G.az, marginBottom: 5 }}>₹{a.comparator?.niftyCorpus}L</div>
                      <div style={{ fontSize: 11, color: G.mist }}>~12% CAGR · Passive</div>
                    </div>
                    <div className="coc">
                      <div style={{ fontSize: 11, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 12 }}>Fixed Deposit</div>
                      <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 500, color: G.mist, marginBottom: 5 }}>₹{a.comparator?.fdCorpus}L</div>
                      <div style={{ fontSize: 11, color: G.mist }}>~6.8% · Guaranteed</div>
                    </div>
                    <div className="coc">
                      <div style={{ fontSize: 11, color: G.mist, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 12 }}>FD Real Value</div>
                      <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 500, color: G.ro, marginBottom: 5 }}>₹{a.comparator?.fdCorpus ? (a.comparator.fdCorpus * 0.65).toFixed(1) : "—"}L</div>
                      <div style={{ fontSize: 11, color: G.mist }}>After 6% inflation</div>
                    </div>
                  </div>
                  <div style={{ marginTop: 14, fontSize: 11, color: G.mist, lineHeight: 1.8 }}>
                    All figures illustrative — based on historical CAGR applied to ₹10L lump sum. Not a projection of future returns.
                    The Nifty 50 Index Fund comparison is intentional — a passive fund at ~12% CAGR is a genuine alternative this bouquet must justify exceeding.
                  </div>
                </div>
              </div>

              {/* DATA FRESHNESS */}
              {freshness && (
                <div className="card">
                  <div className="ch">
                    <span className="ct">Data Freshness</span>
                    <span className="badge bg-g">All Sources Disclosed</span>
                    <button
                      className={"nav-refresh-btn" + (navRefreshing ? " spinning" : "")}
                      onClick={handleNavRefresh}
                      disabled={navRefreshing}
                      title="Fetch latest NAV data from AMFI"
                    >
                      {navRefreshing ? "⟳" : "⟳"} {navRefreshing ? "Refreshing..." : "Refresh Data"}
                    </button>
                  </div>
                  <div className="cb">
                    {navRefreshMsg && (
                      <div style={{
                        fontSize: 12,
                        marginBottom: 12,
                        padding: '8px 12px',
                        borderRadius: 8,
                        background: navRefreshMsg.type === 'ok' ? 'rgba(39,174,120,0.1)' : navRefreshMsg.type === 'warn' ? 'rgba(240,165,0,0.1)' : 'rgba(224,85,85,0.1)',
                        border: `1px solid ${navRefreshMsg.type === 'ok' ? 'rgba(39,174,120,0.3)' : navRefreshMsg.type === 'warn' ? 'rgba(240,165,0,0.3)' : 'rgba(224,85,85,0.3)'}`,
                        color: navRefreshMsg.type === 'ok' ? '#27AE78' : navRefreshMsg.type === 'warn' ? '#F0A500' : '#E05555',
                      }}>
                        {navRefreshMsg.text}
                      </div>
                    )}
                    <div className="frg">
                      {(freshness.sources || []).map((s, i) => {
                        const dotClass = s.status === 'ok' ? 'fdg' : s.status === 'warn' ? 'fdw' : 'fda';
                        const dateColor = s.status === 'ok' ? G.em : s.status === 'warn' ? '#F0A500' : '#E05555';
                        return (
                          <div key={i} className="frr" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
                            <div style={{ display: 'flex', width: '100%', alignItems: 'center' }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, color: G.fog }}>{s.name}</div>
                                <div style={{ fontSize: 11, color: G.mist }}>Source: {s.source} · {s.cadence}</div>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: dateColor, fontWeight: 500 }}>{s.lastUpdated}</span>
                                <div className={`fdot ${dotClass}`} />
                              </div>
                            </div>
                            {s.reason && (
                              <div style={{ fontSize: 11, color: G.mist, lineHeight: 1.6, paddingLeft: 0, background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '6px 10px', borderLeft: `2px solid ${s.status === 'warn' ? 'rgba(240,165,0,0.4)' : 'rgba(224,85,85,0.4)'}` }}>
                                {s.reason}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* FINAL EXEC */}
              <div className="exec" style={{ marginBottom: 48 }}>
                <div>
                  <h3 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 20, color: G.white, marginBottom: 6 }}>Ready to invest in this bouquet?</h3>
                  <p style={{ fontSize: 13, color: G.slate, lineHeight: 1.6 }}>
                    FundGuldasta is a research and education platform, not a SEBI-registered investment advisor. All data sourced from AMFI. Past performance does not guarantee future returns. Execute on a SEBI-registered platform — Kuvera, MFU, or your bank's MF portal.
                  </p>
                </div>
                <div className="exb">
                  <button className="bo">Invest via MFU</button>
                  <button className="bg2">Invest via Kuvera →</button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      {/* SEBI Disclaimer — sticky footer */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 200,
        background: 'rgba(9,12,17,0.97)', backdropFilter: 'blur(12px)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        padding: '8px 24px', display: 'flex', alignItems: 'center',
        justifyContent: 'center', gap: 16,
      }}>
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', letterSpacing: '.03em', lineHeight: 1.6, textAlign: 'center', maxWidth: 900 }}>
          <strong style={{ color: 'rgba(255,255,255,0.4)', fontWeight: 600 }}>Disclaimer:</strong> FundGuldasta is a research &amp; education platform — not a SEBI-registered investment advisor or distributor. Information is for educational purposes only and does not constitute investment advice. Mutual fund investments are subject to market risks. Past performance is not indicative of future results. Please read all scheme-related documents carefully before investing. Verify current data on <strong style={{ color: 'rgba(255,255,255,0.4)' }}>amfiindia.com</strong>.
        </span>
      </div>
    </>
  );
}
