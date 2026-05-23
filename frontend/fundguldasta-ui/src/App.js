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

async function apiImportCas(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/portfolio/import-cas`, { method: "POST", body: form });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "CAS import failed"); }
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

async function apiBacktest(archetypeId, sip, horizonYears, futureYears = 5) {
  const res = await fetch(`${API_BASE}/api/bouquets/${archetypeId}/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ monthly_sip: sip, horizon_years: horizonYears, future_years: futureYears }),
  });
  if (!res.ok) throw new Error("Backtest failed");
  return res.json();
}
async function apiFundDetail(schemeCode) {
  const res = await fetch(`${API_BASE}/api/funds/${schemeCode}/detail`);
  if (!res.ok) throw new Error("Fund detail not available");
  return res.json();
}

async function apiFundEligibility(schemeCode) {
  const res = await fetch(`${API_BASE}/api/funds/${schemeCode}/eligibility`);
  if (!res.ok) throw new Error("Could not load fund eligibility data");
  return res.json();
}

async function apiGetPreferences(token) {
  const res = await fetch(`${API_BASE}/api/user/preferences`, {
    headers: { "Authorization": `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}
async function apiUpdatePreferences(token, prefs) {
  const res = await fetch(`${API_BASE}/api/user/preferences`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify(prefs),
  });
  return res.ok;
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

// Defined at module level so its identity is stable across re-renders.
// Defining components inside a render function causes React to unmount+remount
// the input DOM node on every keystroke, losing focus each time.
function CalcInputRow({ label, value, setter, placeholder, suffix="" }) {
  return (
    <div>
      <div style={{ fontSize:11, color:G.slate, marginBottom:5 }}>{label}</div>
      <div style={{ display:"flex", alignItems:"center", background:G.elv, border:`1px solid ${G.bord}`, borderRadius:8, overflow:"hidden" }}>
        <input
          type="text"
          inputMode="numeric"
          value={value}
          onChange={e => setter(e.target.value)}
          placeholder={placeholder}
          style={{ flex:1, background:"transparent", border:"none", padding:"10px 12px", color:G.white, fontSize:14, fontFamily:"JetBrains Mono,monospace", outline:"none" }}
        />
        {suffix && <span style={{ paddingRight:12, color:G.mist, fontSize:12 }}>{suffix}</span>}
      </div>
    </div>
  );
}

function CalcResultRow({ label, value, color, big=false, border=true }) {
  const col = color || G.white;
  return (
    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding: big?"12px 0":"8px 0", borderBottom: border ? `1px solid ${G.bord}` : "none" }}>
      <span style={{ fontSize: big?13:12, color:G.slate }}>{label}</span>
      <span style={{ fontSize: big?18:14, color:col, fontFamily:"JetBrains Mono,monospace", fontWeight: big?700:500 }}>{value}</span>
    </div>
  );
}

export default function App() {
  const { i18n } = useTranslation();
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
  const [btModal, setBtModal] = useState(false);
  const [btArchetype, setBtArchetype] = useState(null);
  const [btSip, setBtSip] = useState(10000);
  const [btHorizon, setBtHorizon] = useState(7);
  const [btResult, setBtResult] = useState(null);
  const [btLoading, setBtLoading] = useState(false);
  const [fdModal, setFdModal] = useState(false);
  const [, setFdCode] = useState(null);
  const [fdResult, setFdResult] = useState(null);
  const [fdLoading, setFdLoading] = useState(false);
  // Priority 14 state
  const [quizModal, setQuizModal] = useState(false);
  const [quizStep, setQuizStep] = useState(0);
  const [quizAnswers, setQuizAnswers] = useState([]);
  const [quizResult, setQuizResult] = useState(null);
  const [cmpModal, setCmpModal] = useState(false);
  const [cmpA, setCmpA] = useState("steady");
  const [cmpB, setCmpB] = useState("balanced");
  const [wnModal, setWnModal] = useState(false);
  const [wnSearch, setWnSearch] = useState('');
  const [wnResults, setWnResults] = useState([]);
  const [, setWnSelected] = useState(null);
  const [wnLoading, setWnLoading] = useState(false);
  const [wnData, setWnData] = useState(null);
  const [lang, setLang] = useState('en');
  const [userPrefs, setUserPrefs] = useState({ manager_alert: false, monthly_digest: false });
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [calcTab, setCalcTab] = useState('sip');
  const [calcPreFill, setCalcPreFill] = useState(null);
  const [sipMode, setSipMode] = useState('to-corpus');
  const [sipCalcSip, setSipCalcSip] = useState('');
  const [sipCalcCorpus, setSipCalcCorpus] = useState('');
  const [sipCalcYears, setSipCalcYears] = useState('');
  const [sipCalcCagr, setSipCalcCagr] = useState('');
  const [taxCalcInvested, setTaxCalcInvested] = useState('');
  const [taxCalcCurrent, setTaxCalcCurrent] = useState('');
  const [taxCalcMonths, setTaxCalcMonths] = useState('');
  const [taxCalcType, setTaxCalcType] = useState('equity');
  const [taxCalcSlab, setTaxCalcSlab] = useState('30');
  const [pfFunds, setPfFunds] = useState([]);
  const [pfSearch, setPfSearch] = useState('');
  const [pfResults, setPfResults] = useState([]);
  const [pfSearching, setPfSearching] = useState(false);
  const [pfAnalysis, setPfAnalysis] = useState(null);
  const [pfAnalysing, setPfAnalysing] = useState(false);
  const [pfError, setPfError] = useState(null);
  const [casLoading, setCasLoading] = useState(false);
  const [casResult, setCasResult] = useState(null);
  const [casSelected, setCasSelected] = useState(new Set());
  const [casError, setCasError] = useState(null);

  const tr = (en, hi) => lang === 'hi' ? hi : en;

  const HI_HERO = {
    tagline: "म्यूचुअल फंड रिसर्च। बेबाक।",
    secTag: "ईमानदारी से डिज़ाइन किया गया म्यूचुअल फंड रिसर्च",
    headline: "चुने हुए फंड बुके।",
    headlineEm: "ईमानदारी से।",
    sub: "दो इनपुट। चार बुके आर्केटाइप। पारदर्शी रिसर्च की दस परतें। कोई कमीशन नहीं। कोई झूठा आश्वासन नहीं।",
    tabReturn: "रिटर्न लक्ष्य",
    tabCorpus: "कोष लक्ष्य",
    tabSip: "SIP क्षमता",
    labelCAGR: "लक्षित CAGR और निवेश अवधि",
    labelCorpus: "लक्षित कोष और अवधि",
    labelSIP: "मासिक SIP और अवधि",
    labelLumpsum: "शुरुआती एकमुश्त राशि (₹ लाख)",
    btnCurate: "मेरे बुके तैयार करें →",
    btnBYOB: "✎ अपना बुके बनाएं",
    btnPortfolio: "📊 पोर्टफोलियो विश्लेषण",
    btnCalc: "📐 SIP और टैक्स कैलकुलेटर",
    btnRisk: "🎯 मेरी जोखिम प्रोफाइल",
    note: "केवल शोध और शिक्षा · निवेश सलाह नहीं · पिछला प्रदर्शन भविष्य की गारंटी नहीं · सभी डेटा AMFI से · कोई कमीशन नहीं · fundguldasta.com",
    signIn: "साइन इन",
    signOut: "साइन आउट",
    saved: "सहेजे",
    newSearch: "← नई खोज",
    about: "परिचय",
    buildOwn: "✎ खुद बनाएं",
    myPortfolio: "📊 मेरा पोर्टफोलियो",
    calculators: "📐 कैलकुलेटर",
    compare: "⊟ तुलना",
    fundExplorer: "🔍 फंड एक्सप्लोरर",
    riskProfile: "🎯 जोखिम प्रोफाइल",
    savedBouquets: "सहेजे हुए बुके",
  };

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
      apiGetPreferences(token).then(p => p && setUserPrefs(p)).catch(() => {});
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
    if (fundType === 'debt') return { gain, taxType: 'Income slab rate (debt/FOF/International)', tax: null, netGain: null };
    if (months <= 12) return { gain, taxType: 'STCG @ 20% (Budget 2024)', tax: gain * 0.20, netGain: gain * 0.80 };
    const taxable = Math.max(0, gain - 125000);
    return { gain, taxType: 'LTCG @ 12.5% above ₹1.25L (Budget 2024)', tax: taxable * 0.125, netGain: gain - taxable * 0.125 };
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

  const handleBacktest = async (at) => {
    setBtArchetype(at);
    setBtResult(null);
    setBtModal(true);
    setBtLoading(true);
    try {
      const result = await apiBacktest(at.id, btSip, btHorizon, 5);
      setBtResult(result);
    } catch (e) { alert(e.message); }
    finally { setBtLoading(false); }
  };

  const handleFundDetail = async (code) => {
    setFdCode(code);
    setFdResult(null);
    setFdModal(true);
    setFdLoading(true);
    try {
      const result = await apiFundDetail(code);
      setFdResult(result);
    } catch (e) { alert(e.message); }
    finally { setFdLoading(false); }
  };

  // ── Priority 14 helpers ────────────────────────────────────────────────────
  const QUIZ_QUESTIONS = [
    { q: "What is your planned investment horizon?", opts: ["3 years or less","Around 5 years","Around 7 years","10 years or more"], scores:[1,2,3,4] },
    { q: "If your portfolio dropped 30% in a market crash, you would…", opts: ["Sell everything immediately","Get worried but wait it out","Stay put — markets recover","Buy more at lower prices"], scores:[1,2,3,4] },
    { q: "How stable is your primary income?", opts: ["Variable or freelance","Stable salaried job","Business owner / multiple income","Very stable + significant savings"], scores:[1,2,3,4] },
    { q: "This investment represents what share of your total savings?", opts: ["More than 70%","40 to 70%","15 to 40%","Less than 15%"], scores:[1,2,3,4] },
    { q: "Your primary financial goal is…", opts: ["Protect what I have","Grow steadily above FD","Beat inflation by a wide margin","Build maximum long-term wealth"], scores:[1,2,3,4] },
  ];
  const QUIZ_ARCHETYPES = {
    steady:    { label:"Steady Compounder", cagr:14, yrs:7, color:"#4A8FE0", desc:"Low volatility, large-cap dominant. Suited for capital preservation with growth." },
    balanced:  { label:"Balanced Growther",  cagr:15, yrs:7, color:"#27AE78", desc:"Balanced risk-reward. Mix of large and mid-cap. Resilient through cycles." },
    aggressive:{ label:"Aggressive Achiever",cagr:17, yrs:7, color:"#F0A500", desc:"Mid and small-cap driven. Higher volatility, higher growth potential." },
    conviction:{ label:"High Conviction",    cagr:19, yrs:7, color:"#E05555", desc:"Maximum growth orientation. Best for long horizons with high risk tolerance." },
  };
  const quizRecommend = (score) =>
    score <= 9 ? "steady" : score <= 12 ? "balanced" : score <= 16 ? "aggressive" : "conviction";

  const handleQuizAnswer = (optIdx) => {
    const newAnswers = [...quizAnswers, optIdx];
    setQuizAnswers(newAnswers);
    if (newAnswers.length === QUIZ_QUESTIONS.length) {
      const score = newAnswers.reduce((sum, a, i) => sum + QUIZ_QUESTIONS[i].scores[a], 0);
      setQuizResult(quizRecommend(score));
      setQuizStep(QUIZ_QUESTIONS.length);  // show result
    } else {
      setQuizStep(quizStep + 1);
    }
  };
  const handleQuizReset = () => { setQuizStep(0); setQuizAnswers([]); setQuizResult(null); };
  const handleQuizLaunch = (archId) => {
    const at = QUIZ_ARCHETYPES[archId];
    setQuizModal(false);
    setMode("return"); setCAGR(String(at.cagr)); setYrs(String(at.yrs));
    setTimeout(() => handleFind(), 50);
  };

  const handleWnSearch = async (q) => {
    setWnSearch(q);
    if (q.length < 2) { setWnResults([]); return; }
    try {
      const res = await apiFundSearch(q);
      setWnResults(res.slice(0, 8));
    } catch { setWnResults([]); }
  };
  const handleWnSelect = async (fund) => {
    setWnSelected(fund);
    setWnSearch(fund.name || fund.scheme_name || '');
    setWnResults([]);
    setWnLoading(true);
    setWnData(null);
    try {
      const data = await apiFundEligibility(fund.scheme_code);
      setWnData(data);
    } catch (e) { alert(e.message); }
    finally { setWnLoading(false); }
  };

  const handleTogglePref = async (key) => {
    const token = localStorage.getItem("fg_token");
    if (!token) return;
    const newVal = !userPrefs[key];
    setUserPrefs(p => ({ ...p, [key]: newVal }));
    setPrefsSaving(true);
    await apiUpdatePreferences(token, { [key]: newVal });
    setPrefsSaving(false);
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

  const handleCasUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setCasLoading(true); setCasError(null); setCasResult(null); setCasSelected(new Set());
    try {
      const result = await apiImportCas(file);
      setCasResult(result);
      // Pre-select all holdings with confidence ≥ 70
      const preselected = new Set(
        result.holdings.map((_, i) => i).filter(i => (result.holdings[i].confidence || 0) >= 70)
      );
      setCasSelected(preselected);
    } catch(e) { setCasError(e.message); }
    finally { setCasLoading(false); e.target.value = ""; }
  };

  const handleCasImport = () => {
    const toImport = casResult.holdings.filter((_, i) => casSelected.has(i));
    const newFunds = toImport
      .filter(h => h.scheme_code)
      .map(h => ({
        scheme_code: h.scheme_code,
        name: h.matched_name || h.fund_name_raw,
        scheme_name: h.matched_name || h.fund_name_raw,
        allocation_pct: h.allocation_pct,
        category: "",
      }));
    // Merge with existing pfFunds (don't duplicate by scheme_code)
    setPfFunds(prev => {
      const existing = new Set(prev.map(f => String(f.scheme_code)));
      const merged = [...prev];
      for (const f of newFunds) {
        if (!existing.has(String(f.scheme_code))) merged.push(f);
      }
      return merged;
    });
    setCasResult(null); setCasSelected(new Set());
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
          <span style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:20, fontWeight:700 }}>{lang === 'hi' ? HI_HERO.savedBouquets : "Saved Bouquets"}</span>
          <button onClick={() => setSavedPanel(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:18 }}>&#x2715;</button>
        </div>
        {savedList.length === 0 && (
          <p style={{ color:G.slate, fontSize:13 }}>No saved bouquets yet. Click the bookmark icon on any archetype to save it.</p>
        )}
        {/* Alert preference toggles */}
        {savedList.length > 0 && (
          <div style={{ background:"rgba(255,255,255,0.03)", border:`1px solid rgba(255,255,255,0.07)`, borderRadius:10, padding:"12px 14px" }}>
            <div style={{ fontSize:10, color:G.mist, letterSpacing:".08em", textTransform:"uppercase", marginBottom:10, fontWeight:600 }}>Alert Preferences {prefsSaving && <span style={{ color:G.gold }}>· saving…</span>}</div>
            {[
              ["manager_alert", "🔔 Manager change alerts", "Email me when a fund manager changes in my saved bouquets"],
              ["monthly_digest", "📬 Monthly digest", "Receive a monthly summary of my saved bouquets"],
            ].map(([key, label, desc]) => (
              <div key={key} style={{ display:"flex", alignItems:"flex-start", gap:10, marginBottom:10, cursor:"pointer" }} onClick={() => handleTogglePref(key)}>
                <div style={{ width:28, height:16, borderRadius:8, background: userPrefs[key] ? "rgba(212,175,55,0.6)" : "rgba(255,255,255,0.12)", position:"relative", flexShrink:0, marginTop:2, transition:"background .2s" }}>
                  <div style={{ width:12, height:12, borderRadius:6, background:"#fff", position:"absolute", top:2, left: userPrefs[key] ? 14 : 2, transition:"left .2s" }} />
                </div>
                <div>
                  <div style={{ fontSize:12, color: userPrefs[key] ? G.fog : G.mist, fontWeight: userPrefs[key] ? 500 : 400 }}>{label}</div>
                  <div style={{ fontSize:10, color:G.slate, marginTop:2 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
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

            {/* CAS Import */}
            <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:20 }}>
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:10 }}>
                <div>
                  <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:3 }}>📤 Import from CAS PDF</div>
                  <div style={{ color:G.slate, fontSize:11, lineHeight:1.6 }}>Upload a CAMS or KFintech Consolidated Account Statement PDF to auto-populate your portfolio.</div>
                </div>
                <label style={{ background:"rgba(212,175,55,0.1)", border:`1px solid rgba(212,175,55,0.35)`, borderRadius:8, padding:"7px 18px", color:G.gold, fontSize:12, fontWeight:600, cursor:"pointer", fontFamily:"Outfit,sans-serif", flexShrink:0, display:"inline-block" }}>
                  {casLoading ? "Parsing..." : "Choose CAS PDF"}
                  <input type="file" accept=".pdf" style={{ display:"none" }} onChange={handleCasUpload} disabled={casLoading} />
                </label>
              </div>
              {casError && <div style={{ background:"rgba(255,107,107,0.08)", border:"1px solid rgba(255,107,107,0.25)", borderRadius:8, padding:"10px 14px", color:"#FF6B6B", fontSize:12, marginTop:12 }}>{casError}</div>}
              {casResult && (
                <div style={{ marginTop:16 }}>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10 }}>
                    <div style={{ color:G.gold, fontSize:12, fontWeight:600 }}>
                      Found {casResult.fund_count} fund{casResult.fund_count !== 1 ? "s" : ""} · Total value ₹{casResult.total_value.toLocaleString("en-IN", { maximumFractionDigits:0 })}
                      <span style={{ color:G.slate, fontWeight:400, marginLeft:8 }}>({casResult.format.toUpperCase()} format)</span>
                    </div>
                    <div style={{ display:"flex", gap:8 }}>
                      <button onClick={() => setCasSelected(new Set(casResult.holdings.map((_,i)=>i)))} style={{ background:"none", border:`1px solid ${G.bord}`, borderRadius:6, padding:"3px 10px", color:G.slate, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>All</button>
                      <button onClick={() => setCasSelected(new Set())} style={{ background:"none", border:`1px solid ${G.bord}`, borderRadius:6, padding:"3px 10px", color:G.slate, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>None</button>
                    </div>
                  </div>
                  {casResult.parse_errors.length > 0 && (
                    <div style={{ background:"rgba(232,160,0,0.08)", border:"1px solid rgba(232,160,0,0.2)", borderRadius:6, padding:"8px 12px", color:G.am, fontSize:11, marginBottom:10 }}>
                      ⚠ {casResult.parse_errors[0]}
                    </div>
                  )}
                  <div style={{ border:`1px solid ${G.bord}`, borderRadius:8, overflow:"hidden", marginBottom:12 }}>
                    {casResult.holdings.map((h, i) => (
                      <div key={i} onClick={() => setCasSelected(prev => { const s = new Set(prev); s.has(i) ? s.delete(i) : s.add(i); return s; })}
                        style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 14px", borderBottom: i < casResult.holdings.length-1 ? `1px solid ${G.bord}` : "none",
                          background: casSelected.has(i) ? "rgba(212,175,55,0.05)" : "transparent", cursor:"pointer" }}>
                        <div style={{ width:16, height:16, borderRadius:4, border:`1.5px solid ${casSelected.has(i) ? G.gold : G.bord}`, background: casSelected.has(i) ? "rgba(212,175,55,0.2)" : "transparent", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, color:G.gold }}>
                          {casSelected.has(i) ? "✓" : ""}
                        </div>
                        <div style={{ flex:1, minWidth:0 }}>
                          <div style={{ color:G.white, fontSize:12, fontWeight:600, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
                            {h.matched_name || h.fund_name_raw}
                          </div>
                          {h.matched_name && h.matched_name !== h.fund_name_raw && (
                            <div style={{ color:G.mist, fontSize:10, marginTop:1 }}>CAS: {h.fund_name_raw.slice(0,55)}</div>
                          )}
                        </div>
                        <div style={{ textAlign:"right", flexShrink:0 }}>
                          <div style={{ color:G.gold, fontSize:12, fontWeight:700, fontFamily:"JetBrains Mono,monospace" }}>{h.allocation_pct}%</div>
                          <div style={{ color:G.slate, fontSize:10 }}>₹{h.value.toLocaleString("en-IN", { maximumFractionDigits:0 })} · {h.units.toLocaleString("en-IN", { maximumFractionDigits:3 })} units</div>
                          <div style={{ fontSize:9, color: h.confidence >= 85 ? "#27AE78" : h.confidence >= 70 ? G.am : "#E05555", marginTop:1, letterSpacing:".04em" }}>
                            {h.confidence >= 85 ? "✓ Matched" : h.confidence >= 70 ? "~ Likely match" : "? Low confidence"} ({h.confidence}%)
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div style={{ display:"flex", gap:10 }}>
                    <button onClick={handleCasImport} disabled={casSelected.size === 0}
                      style={{ flex:1, padding:"10px 0", background:casSelected.size > 0 ? "rgba(212,175,55,0.15)" : G.elv,
                        border:`1px solid ${casSelected.size > 0 ? "rgba(212,175,55,0.4)" : G.bord}`, borderRadius:8,
                        color: casSelected.size > 0 ? G.gold : G.slate, fontSize:13, fontWeight:600, cursor: casSelected.size > 0 ? "pointer" : "not-allowed", fontFamily:"Outfit,sans-serif" }}>
                      Import {casSelected.size} Fund{casSelected.size !== 1 ? "s" : ""} →
                    </button>
                    <button onClick={() => { setCasResult(null); setCasSelected(new Set()); }}
                      style={{ padding:"10px 18px", background:"none", border:`1px solid ${G.bord}`, borderRadius:8, color:G.slate, fontSize:13, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
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
                      <input type="text" inputMode="numeric" value={f.allocation_pct}
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

                {/* Gap Analysis */}
                {pfAnalysis.gap_analysis && (
                  <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20, marginBottom:16 }}>
                    <div style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:18, fontWeight:700, marginBottom:4 }}>Gap Analysis</div>
                    <p style={{ color:G.slate, fontSize:12, marginBottom:16, marginTop:0 }}>
                      Comparing your portfolio vs the closest matching bouquet — <strong style={{ color:G.fog }}>{ARCHETYPE_LABELS[pfAnalysis.gap_analysis.archetype_id] || pfAnalysis.gap_analysis.archetype_id}</strong> ({pfAnalysis.gap_analysis.overlap_pct}% allocation overlap).
                    </p>
                    {pfAnalysis.gap_analysis.missing_funds.length > 0 && (
                      <div style={{ marginBottom:14 }}>
                        <div style={{ fontSize:10, letterSpacing:".1em", textTransform:"uppercase", color:"#E05555", fontWeight:700, marginBottom:8 }}>
                          Funds in Bouquet You Don't Hold ({pfAnalysis.gap_analysis.missing_funds.length})
                        </div>
                        {pfAnalysis.gap_analysis.missing_funds.map(f => (
                          <div key={f.scheme_code} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"8px 12px", background:"rgba(224,85,85,0.05)", border:"1px solid rgba(224,85,85,0.15)", borderRadius:8, marginBottom:6 }}>
                            <div>
                              <div style={{ color:G.fog, fontSize:12 }}>{f.scheme_name || `Fund ${f.scheme_code}`}</div>
                              <div style={{ color:G.mist, fontSize:10 }}>Bouquet weight: {f.suggested_weight ? f.suggested_weight.toFixed(0) : "—"}%</div>
                            </div>
                            <div style={{ color:"#E05555", fontSize:11, fontWeight:600, letterSpacing:".04em" }}>Missing</div>
                          </div>
                        ))}
                      </div>
                    )}
                    {pfAnalysis.gap_analysis.extra_funds.length > 0 && (
                      <div>
                        <div style={{ fontSize:10, letterSpacing:".1em", textTransform:"uppercase", color:G.am, fontWeight:700, marginBottom:8 }}>
                          Your Funds Not in This Bouquet ({pfAnalysis.gap_analysis.extra_funds.length})
                        </div>
                        {pfAnalysis.gap_analysis.extra_funds.map(f => (
                          <div key={f.scheme_code} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"8px 12px", background:"rgba(232,160,0,0.04)", border:"1px solid rgba(232,160,0,0.15)", borderRadius:8, marginBottom:6 }}>
                            <div style={{ color:G.fog, fontSize:12 }}>{f.scheme_name || `Fund ${f.scheme_code}`}</div>
                            <div style={{ color:G.am, fontSize:11, fontWeight:600 }}>{f.allocation_pct}%</div>
                          </div>
                        ))}
                      </div>
                    )}
                    {pfAnalysis.gap_analysis.missing_funds.length === 0 && pfAnalysis.gap_analysis.extra_funds.length === 0 && (
                      <div style={{ color:"#27AE78", fontSize:13, fontWeight:600 }}>✓ Your portfolio perfectly matches this bouquet's fund selection.</div>
                    )}
                  </div>
                )}

                {pfAnalysis.missing_data_codes?.length > 0 && (
                  <div style={{ color:G.slate, fontSize:11, marginTop:8 }}>Note: No computed data for scheme codes {pfAnalysis.missing_data_codes.join(", ")} — those funds were not scored.</div>
                )}
              </div>
            )}

            {pfFunds.length === 0 && !pfAnalysis && !casResult && (
              <div style={{ textAlign:"center", padding:"60px 20px", color:G.slate, fontSize:13 }}>
                <div style={{ fontSize:32, marginBottom:12 }}>📊</div>
                <div>Upload a CAS PDF above to auto-import your holdings, or search funds manually.</div>
                <div style={{ marginTop:8, fontSize:12 }}>Then click "Analyse Portfolio" to compare against our bouquet archetypes.</div>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

  // ── Backtest Modal ────────────────────────────────────────────────────────
  const BacktestModal = () => {
    const PL = 52, PT = 10, PR = 12, PB = 28;
    const W = 560, H = 180, CW = W - PL - PR, CH = H - PT - PB;
    const fmt = (n) => n >= 1e7 ? `₹${(n/1e7).toFixed(2)}Cr` : n >= 1e5 ? `₹${(n/1e5).toFixed(1)}L` : `₹${n.toLocaleString("en-IN")}`;
    const s = btResult?.series || [];
    const fp = btResult?.future || [];
    const sum = btResult?.summary || {};
    const maxVal = s.length ? Math.max(...s.map(d => d.b)) * 1.08 : 1;
    const xS = (i) => PL + (i / Math.max(s.length - 1, 1)) * CW;
    const yS = (v) => PT + CH - (v / maxVal) * CH;
    const maxFan = fp.length ? Math.max(...fp.map(b => b.p90)) * 1.08 : 1;
    const xF = (yr) => PL + ((yr - 1) / Math.max(fp.length - 1, 1)) * CW;
    const yF = (v) => PT + CH - (v / maxFan) * CH;
    const band90pts = fp.length ? [
      ...fp.map(b => [xF(b.y), yF(b.p90)]),
      ...fp.slice().reverse().map(b => [xF(b.y), yF(b.p10)]),
    ] : [];
    const band75pts = fp.length ? [
      ...fp.map(b => [xF(b.y), yF(b.p75)]),
      ...fp.slice().reverse().map(b => [xF(b.y), yF(b.p25)]),
    ] : [];

    return (
      <div style={{ position:"fixed", inset:0, zIndex:2000, background:"rgba(0,0,0,0.75)", display:"flex", alignItems:"center", justifyContent:"center", padding:16 }}
        onClick={e => { if (e.target === e.currentTarget) setBtModal(false); }}>
        <div style={{ background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:16, width:"100%", maxWidth:640, maxHeight:"90vh", overflowY:"auto", padding:"28px 28px 32px", fontFamily:"Outfit,sans-serif" }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:20 }}>
            <div>
              <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:20, color:G.gold, fontWeight:700 }}>Historical SIP Backtest</div>
              <div style={{ fontSize:12, color:G.mist, marginTop:3 }}>{btArchetype?.label} · Actual NAV data, no hypothetical returns</div>
            </div>
            <button onClick={() => setBtModal(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:20, lineHeight:1 }}>&#x2715;</button>
          </div>

          {/* Controls */}
          <div style={{ display:"flex", gap:12, marginBottom:20, flexWrap:"wrap" }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, flex:1, minWidth:180 }}>
              <span style={{ fontSize:12, color:G.mist, whiteSpace:"nowrap" }}>Monthly SIP ₹</span>
              <input type="text" inputMode="numeric" value={btSip} onChange={e => setBtSip(Number(e.target.value))}
                style={{ flex:1, background:G.elv, border:`1px solid rgba(255,255,255,0.1)`, borderRadius:8, padding:"6px 10px", color:G.white, fontFamily:"JetBrains Mono,monospace", fontSize:14, outline:"none" }} />
            </div>
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ fontSize:12, color:G.mist, whiteSpace:"nowrap" }}>History</span>
              <select value={btHorizon} onChange={e => setBtHorizon(Number(e.target.value))}
                style={{ background:G.elv, border:`1px solid rgba(255,255,255,0.1)`, borderRadius:8, padding:"6px 10px", color:G.white, fontFamily:"Outfit,sans-serif", fontSize:13, outline:"none" }}>
                {[3,5,7,10,12].map(y => <option key={y} value={y}>{y} years</option>)}
              </select>
            </div>
            <button onClick={() => handleBacktest(btArchetype)}
              style={{ padding:"6px 20px", background:"rgba(212,175,55,0.12)", border:`1px solid rgba(212,175,55,0.4)`, borderRadius:8, color:G.gold, fontSize:13, fontWeight:600, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
              Run
            </button>
          </div>

          {btLoading && <div style={{ textAlign:"center", padding:"40px 0", color:G.mist, fontSize:13 }}>Computing backtest...</div>}

          {!btLoading && s.length > 0 && (
            <>
              {/* Historical line chart */}
              <div style={{ background:G.bg, borderRadius:10, padding:"12px 8px", marginBottom:16 }}>
                <div style={{ fontSize:11, color:G.mist, marginBottom:8, paddingLeft:PL }}>Historical SIP Performance ({sum.actual_start?.slice(0,7)} → today)</div>
                <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height:"auto", display:"block" }}>
                  {/* Y-axis labels */}
                  {[0, 0.5, 1].map(pct => (
                    <text key={pct} x={PL - 6} y={PT + CH - pct * CH + 4} textAnchor="end" style={{ fontSize:9, fill:G.mist }}>{fmt(maxVal * pct)}</text>
                  ))}
                  {/* Lines */}
                  <polyline points={s.map((d, i) => `${xS(i)},${yS(d.i)}`).join(" ")} fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" strokeDasharray="4,3" />
                  <polyline points={s.map((d, i) => `${xS(i)},${yS(d.n)}`).join(" ")} fill="none" stroke="#4A8FE0" strokeWidth="1.8" />
                  <polyline points={s.map((d, i) => `${xS(i)},${yS(d.b)}`).join(" ")} fill="none" stroke={G.gold} strokeWidth="2.2" />
                  {/* X labels */}
                  {[0, Math.floor((s.length-1)/2), s.length-1].filter((v,i,a) => a.indexOf(v)===i).map(i => (
                    <text key={i} x={xS(i)} y={H - 6} textAnchor="middle" style={{ fontSize:9, fill:G.mist }}>{s[i].m}</text>
                  ))}
                </svg>
                {/* Legend */}
                <div style={{ display:"flex", gap:16, justifyContent:"center", marginTop:8 }}>
                  {[["Amount Invested","rgba(255,255,255,0.4)","---"],["Nifty 50 SIP","#4A8FE0","—"],["Bouquet SIP",G.gold,"—"]].map(([lbl,col,dash]) => (
                    <div key={lbl} style={{ display:"flex", alignItems:"center", gap:5, fontSize:11, color:G.mist }}>
                      <span style={{ width:18, borderTop:`2px ${dash==="---"?"dashed":"solid"} ${col}`, display:"inline-block" }} />
                      {lbl}
                    </div>
                  ))}
                </div>
              </div>

              {/* Summary stats */}
              <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(120px,1fr))", gap:10, marginBottom:20 }}>
                {[
                  ["Invested", fmt(sum.total_invested), G.mist],
                  ["Bouquet Value", fmt(sum.bouquet_final), G.gold],
                  ["vs Nifty", fmt(sum.nifty_final), "#4A8FE0"],
                  ["vs FD (7%)", fmt(sum.fd_final), "rgba(255,255,255,0.5)"],
                  ["Bouquet CAGR", `${sum.bouquet_cagr}%`, sum.bouquet_cagr >= 12 ? "#27AE78" : sum.bouquet_cagr >= 8 ? G.gold : "#E05555"],
                  ["Nifty CAGR", `${sum.nifty_cagr}%`, "#4A8FE0"],
                ].map(([lbl, val, col]) => (
                  <div key={lbl} style={{ background:G.elv, borderRadius:8, padding:"10px 12px" }}>
                    <div style={{ fontSize:10, color:G.mist, letterSpacing:".08em", textTransform:"uppercase", marginBottom:4 }}>{lbl}</div>
                    <div style={{ fontFamily:"JetBrains Mono,monospace", fontSize:15, fontWeight:600, color:col }}>{val}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Future projection fan chart */}
          {!btLoading && fp.length > 0 && (
            <>
              <div style={{ fontSize:12, color:G.mist, marginBottom:12 }}>
                <span style={{ color:G.gold, fontWeight:600 }}>Forward Projection</span>
                &nbsp;· 500 Monte Carlo simulations using this bouquet's historical return distribution
              </div>
              <div style={{ background:G.bg, borderRadius:10, padding:"12px 8px", marginBottom:16 }}>
                <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height:"auto", display:"block" }}>
                  {/* Bands */}
                  {band90pts.length > 0 && (
                    <polygon points={band90pts.map(p => p.join(",")).join(" ")} fill={`rgba(212,175,55,0.08)`} />
                  )}
                  {band75pts.length > 0 && (
                    <polygon points={band75pts.map(p => p.join(",")).join(" ")} fill={`rgba(212,175,55,0.18)`} />
                  )}
                  {/* Invested line */}
                  <polyline points={fp.map(b => `${xF(b.y)},${yF(b.i)}`).join(" ")} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" strokeDasharray="4,3" />
                  {/* Median line */}
                  <polyline points={fp.map(b => `${xF(b.y)},${yF(b.p50)}`).join(" ")} fill="none" stroke={G.gold} strokeWidth="2.2" />
                  {/* X axis labels */}
                  {fp.map(b => (
                    <text key={b.y} x={xF(b.y)} y={H - 6} textAnchor="middle" style={{ fontSize:9, fill:G.mist }}>Yr {b.y}</text>
                  ))}
                  {/* Y labels */}
                  {[0, 0.5, 1].map(pct => (
                    <text key={pct} x={PL - 6} y={PT + CH - pct * CH + 4} textAnchor="end" style={{ fontSize:9, fill:G.mist }}>{fmt(maxFan * pct)}</text>
                  ))}
                </svg>
                <div style={{ display:"flex", gap:16, justifyContent:"center", marginTop:8 }}>
                  {[["p10–p90 range","rgba(212,175,55,0.2)"],["p25–p75 range","rgba(212,175,55,0.45)"],["Median (p50)",G.gold]].map(([lbl,col]) => (
                    <div key={lbl} style={{ display:"flex", alignItems:"center", gap:5, fontSize:11, color:G.mist }}>
                      <span style={{ width:14, height:10, background:col, display:"inline-block", borderRadius:2 }} />
                      {lbl}
                    </div>
                  ))}
                </div>
              </div>
              {/* Future year table */}
              <div style={{ overflowX:"auto" }}>
                <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                  <thead>
                    <tr>{["Year","Invested","Pessimistic (p25)","Median","Optimistic (p75)"].map(h => (
                      <th key={h} style={{ padding:"6px 10px", color:G.mist, textAlign:h==="Year"?"left":"right", fontSize:10, textTransform:"uppercase", letterSpacing:".06em", borderBottom:`1px solid ${G.bord}` }}>{h}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {fp.map(b => (
                      <tr key={b.y}>
                        <td style={{ padding:"7px 10px", color:G.fog }}>Year {b.y}</td>
                        <td style={{ padding:"7px 10px", textAlign:"right", color:G.mist, fontFamily:"JetBrains Mono,monospace" }}>{fmt(b.i)}</td>
                        <td style={{ padding:"7px 10px", textAlign:"right", color:"rgba(212,175,55,0.6)", fontFamily:"JetBrains Mono,monospace" }}>{fmt(b.p25)}</td>
                        <td style={{ padding:"7px 10px", textAlign:"right", color:G.gold, fontFamily:"JetBrains Mono,monospace", fontWeight:600 }}>{fmt(b.p50)}</td>
                        <td style={{ padding:"7px 10px", textAlign:"right", color:"#27AE78", fontFamily:"JetBrains Mono,monospace" }}>{fmt(b.p75)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ fontSize:10, color:G.mist, marginTop:10, lineHeight:1.7, fontStyle:"italic" }}>
                Projections based on {sum.months}-month historical return distribution via bootstrap resampling. Past distribution does not guarantee future results. For education only.
              </div>
            </>
          )}
        </div>
      </div>
    );
  };

  // ── Fund Detail Modal ─────────────────────────────────────────────────────
  const FundDetailModal = () => {
    const fd = fdResult;
    const PL = 48, PT = 10, PR = 10, PB = 28;
    const W = 520, H = 160, CW = W - PL - PR, CH = H - PT - PB;
    const ns = fd?.nav_series || [];
    const maxNAV = ns.length ? Math.max(...ns.map(d => d.v)) * 1.05 : 1;
    const minNAV = ns.length ? Math.min(...ns.map(d => d.v)) * 0.97 : 0;
    const range = maxNAV - minNAV || 1;
    const xN = (i) => PL + (i / Math.max(ns.length - 1, 1)) * CW;
    const yN = (v) => PT + CH - ((v - minNAV) / range) * CH;
    const rr = fd?.rolling_returns || {};
    const nr = fd?.nifty_rolling || {};

    return (
      <div style={{ position:"fixed", inset:0, zIndex:2100, background:"rgba(0,0,0,0.8)", display:"flex", alignItems:"center", justifyContent:"center", padding:16 }}
        onClick={e => { if (e.target === e.currentTarget) setFdModal(false); }}>
        <div style={{ background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:16, width:"100%", maxWidth:580, maxHeight:"88vh", overflowY:"auto", padding:"24px 24px 28px", fontFamily:"Outfit,sans-serif" }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:16 }}>
            <div style={{ flex:1, paddingRight:16 }}>
              <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:18, color:G.white, fontWeight:600, lineHeight:1.3 }}>{fdLoading ? "Loading…" : fd?.name}</div>
              {fd && <div style={{ fontSize:11, color:G.mist, marginTop:4 }}>{fd.category} · {fd.fund_type}</div>}
            </div>
            <button onClick={() => setFdModal(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:20 }}>&#x2715;</button>
          </div>

          {fdLoading && <div style={{ padding:"40px 0", textAlign:"center", color:G.mist, fontSize:13 }}>Loading fund data…</div>}

          {!fdLoading && fd && (
            <>
              {/* Fund info chips */}
              <div style={{ display:"flex", flexWrap:"wrap", gap:10, marginBottom:20 }}>
                {[
                  ["Manager", fd.manager_name || "—"],
                  ["TER", fd.expense_ratio != null ? `${fd.expense_ratio.toFixed(2)}%` : "—"],
                  ["AUM", fd.aum_cr != null ? (fd.aum_cr >= 1000 ? `₹${(fd.aum_cr/1000).toFixed(1)}K Cr` : `₹${fd.aum_cr} Cr`) : "—"],
                  ["Current NAV", fd.current_nav != null ? `₹${fd.current_nav.toFixed(2)}` : "—"],
                ].map(([lbl, val]) => (
                  <div key={lbl} style={{ background:G.elv, borderRadius:8, padding:"8px 14px" }}>
                    <div style={{ fontSize:10, color:G.mist, letterSpacing:".06em", textTransform:"uppercase", marginBottom:3 }}>{lbl}</div>
                    <div style={{ fontSize:13, color:G.fog, fontWeight:500 }}>{val}</div>
                  </div>
                ))}
              </div>

              {/* NAV chart */}
              {ns.length > 0 && (
                <div style={{ background:G.bg, borderRadius:10, padding:"12px 8px", marginBottom:16 }}>
                  <div style={{ fontSize:11, color:G.mist, marginBottom:8, paddingLeft:PL }}>NAV — last 5 years</div>
                  <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height:"auto", display:"block" }}>
                    <defs>
                      <linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={G.gold} stopOpacity="0.25" />
                        <stop offset="100%" stopColor={G.gold} stopOpacity="0.01" />
                      </linearGradient>
                    </defs>
                    {/* Fill area */}
                    <polygon points={[
                      ...ns.map((d, i) => `${xN(i)},${yN(d.v)}`),
                      `${xN(ns.length-1)},${PT + CH}`,
                      `${xN(0)},${PT + CH}`,
                    ].join(" ")} fill="url(#navGrad)" />
                    {/* Line */}
                    <polyline points={ns.map((d, i) => `${xN(i)},${yN(d.v)}`).join(" ")} fill="none" stroke={G.gold} strokeWidth="2" />
                    {/* Y labels */}
                    {[minNAV, (minNAV+maxNAV)/2, maxNAV].map((v, i) => (
                      <text key={i} x={PL - 5} y={yN(v) + 4} textAnchor="end" style={{ fontSize:9, fill:G.mist }}>₹{Math.round(v)}</text>
                    ))}
                    {/* X labels */}
                    {[0, Math.floor((ns.length-1)/2), ns.length-1].filter((v,i,a) => a.indexOf(v)===i && ns[v]).map(i => (
                      <text key={i} x={xN(i)} y={H - 6} textAnchor="middle" style={{ fontSize:9, fill:G.mist }}>{ns[i].m}</text>
                    ))}
                  </svg>
                </div>
              )}

              {/* Rolling returns table */}
              {(Object.keys(rr).length > 0 || Object.keys(nr).length > 0) && (
                <div style={{ background:G.elv, border:`1px solid rgba(255,255,255,0.07)`, borderRadius:10, overflow:"hidden" }}>
                  <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                    <thead>
                      <tr style={{ borderBottom:`1px solid ${G.bord}` }}>
                        {["Period","Fund CAGR","Nifty 50 CAGR","Alpha"].map((h, i) => (
                          <th key={h} style={{ padding:"9px 12px", color:G.mist, textAlign:i===0?"left":"right", fontSize:10, textTransform:"uppercase", letterSpacing:".08em" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {["1yr","3yr","5yr"].filter(p => rr[p] != null || nr[p] != null).map(period => {
                        const fv = rr[period]; const nv = nr[period];
                        const alpha = (fv != null && nv != null) ? (fv - nv).toFixed(2) : "—";
                        const alphaNum = parseFloat(alpha);
                        return (
                          <tr key={period} style={{ borderBottom:`1px solid rgba(255,255,255,0.04)` }}>
                            <td style={{ padding:"9px 12px", color:G.fog, textTransform:"uppercase", fontSize:11 }}>{period}</td>
                            <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"JetBrains Mono,monospace", color:fv >= 0 ? "#27AE78" : "#E05555" }}>{fv != null ? `${fv > 0 ? "+" : ""}${fv}%` : "—"}</td>
                            <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"JetBrains Mono,monospace", color:G.mist }}>{nv != null ? `${nv > 0 ? "+" : ""}${nv}%` : "—"}</td>
                            <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"JetBrains Mono,monospace", color:!isNaN(alphaNum) && alphaNum >= 0 ? "#27AE78" : "#E05555" }}>{!isNaN(alphaNum) ? `${alphaNum >= 0 ? "+" : ""}${alpha}%` : "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div style={{ fontSize:10, color:G.mist, marginTop:10, fontStyle:"italic" }}>
                Rolling returns use actual NAV data. Alpha = fund return − Nifty 50 return. For research only.
              </div>

              {/* Direct Plan Invest Section */}
              <div style={{ marginTop:18, background:"rgba(39,174,120,0.05)", border:"1px solid rgba(39,174,120,0.15)", borderRadius:10, padding:"14px 16px" }}>
                <div style={{ fontSize:11, color:"#27AE78", fontWeight:700, letterSpacing:".08em", textTransform:"uppercase", marginBottom:10 }}>Invest Direct (No Commission)</div>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:12, flexWrap:"wrap" }}>
                  <div style={{ fontSize:11, color:G.mist }}>AMFI Scheme Code:</div>
                  <div style={{ fontFamily:"JetBrains Mono,monospace", fontSize:14, color:G.gold, background:"rgba(212,175,55,0.1)", borderRadius:6, padding:"3px 10px" }}>{fdResult?.scheme_code}</div>
                  <button onClick={() => navigator.clipboard?.writeText(fdResult?.scheme_code || '').then(() => alert('Copied!'))}
                    style={{ background:"none", border:"1px solid rgba(255,255,255,0.12)", borderRadius:6, padding:"3px 10px", color:G.mist, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
                    Copy Code
                  </button>
                </div>
                <div style={{ fontSize:11, color:G.mist, marginBottom:8 }}>Search this fund by name on any direct-plan platform:</div>
                <div style={{ display:"flex", flexWrap:"wrap", gap:8 }}>
                  {[["Kuvera","https://kuvera.in"],["Zerodha Coin","https://coin.zerodha.com/mf"],["Groww","https://groww.in/mutual-funds"],["Paytm Money","https://www.paytmmoney.com/mutual-funds"],["ET Money","https://www.etmoney.com/mutual-funds"]].map(([name, url]) => (
                    <a key={name} href={url} target="_blank" rel="noopener noreferrer"
                      style={{ display:"inline-block", padding:"5px 12px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.1)", borderRadius:6, color:G.fog, fontSize:11, textDecoration:"none", fontFamily:"Outfit,sans-serif", cursor:"pointer" }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor="rgba(39,174,120,0.35)"; e.currentTarget.style.color="#27AE78"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor="rgba(255,255,255,0.1)"; e.currentTarget.style.color=G.fog; }}>
                      {name} ↗
                    </a>
                  ))}
                </div>
                <div style={{ fontSize:10, color:G.mist, marginTop:10, fontStyle:"italic" }}>These are independent platforms — FundGuldasta has no commercial relationship with them. Always verify fund details before investing.</div>
              </div>
            </>
          )}
        </div>
      </div>
    );
  };

  // ── Risk Profiler Quiz Modal (14a) ──────────────────────────────────────────
  const QuizModal = () => {
    const q = QUIZ_QUESTIONS[quizStep];
    const atId = quizResult;
    const at = atId ? QUIZ_ARCHETYPES[atId] : null;
    return (
      <div style={{ position:"fixed", inset:0, zIndex:2200, background:"rgba(0,0,0,0.8)", display:"flex", alignItems:"center", justifyContent:"center", padding:16 }}
        onClick={e => { if (e.target === e.currentTarget) setQuizModal(false); }}>
        <div style={{ background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:16, width:"100%", maxWidth:520, padding:"28px 28px 32px", fontFamily:"Outfit,sans-serif" }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
            <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:20, color:G.gold, fontWeight:700 }}>Risk Profile Quiz</div>
            <button onClick={() => setQuizModal(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:20 }}>&#x2715;</button>
          </div>

          {!at && q && (
            <>
              {/* Progress */}
              <div style={{ display:"flex", gap:6, marginBottom:20 }}>
                {QUIZ_QUESTIONS.map((_, i) => (
                  <div key={i} style={{ flex:1, height:3, borderRadius:2, background: i < quizStep ? G.gold : i === quizStep ? "rgba(212,175,55,0.4)" : "rgba(255,255,255,0.08)" }} />
                ))}
              </div>
              <div style={{ fontSize:11, color:G.mist, marginBottom:8, letterSpacing:".06em" }}>QUESTION {quizStep + 1} OF {QUIZ_QUESTIONS.length}</div>
              <div style={{ fontSize:17, color:G.white, fontWeight:500, marginBottom:22, lineHeight:1.5 }}>{q.q}</div>
              <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
                {q.opts.map((opt, idx) => (
                  <button key={idx} onClick={() => handleQuizAnswer(idx)}
                    style={{ background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.1)", borderRadius:10, padding:"12px 16px", color:G.fog, fontSize:13, textAlign:"left", cursor:"pointer", fontFamily:"Outfit,sans-serif", transition:"all .15s" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor="rgba(212,175,55,0.4)"; e.currentTarget.style.color=G.white; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor="rgba(255,255,255,0.1)"; e.currentTarget.style.color=G.fog; }}>
                    {opt}
                  </button>
                ))}
              </div>
              {quizStep > 0 && (
                <button onClick={() => { setQuizStep(quizStep-1); setQuizAnswers(quizAnswers.slice(0,-1)); }}
                  style={{ background:"none", border:"none", color:G.mist, cursor:"pointer", fontSize:12, marginTop:16, fontFamily:"Outfit,sans-serif" }}>
                  ← Back
                </button>
              )}
            </>
          )}

          {at && (
            <div style={{ textAlign:"center" }}>
              <div style={{ fontSize:13, color:G.mist, marginBottom:6 }}>Your risk profile matches</div>
              <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:32, color:at.color, fontWeight:700, marginBottom:8 }}>{at.label}</div>
              <div style={{ fontSize:13, color:G.fog, lineHeight:1.7, marginBottom:24, maxWidth:360, margin:"0 auto 24px" }}>{at.desc}</div>
              <div style={{ display:"flex", gap:12, justifyContent:"center", flexWrap:"wrap" }}>
                <button onClick={() => handleQuizLaunch(atId)}
                  style={{ padding:"11px 28px", background:`rgba(${at.color === "#4A8FE0" ? "74,143,224" : at.color === "#27AE78" ? "39,174,120" : at.color === "#F0A500" ? "240,165,0" : "224,85,85"},0.15)`, border:`1px solid ${at.color}`, borderRadius:10, color:at.color, fontFamily:"Outfit,sans-serif", fontSize:13, fontWeight:600, cursor:"pointer" }}>
                  See {at.label} Bouquet →
                </button>
                <button onClick={handleQuizReset}
                  style={{ padding:"11px 20px", background:"none", border:`1px solid rgba(255,255,255,0.12)`, borderRadius:10, color:G.mist, fontFamily:"Outfit,sans-serif", fontSize:13, cursor:"pointer" }}>
                  Retake Quiz
                </button>
              </div>
              <div style={{ fontSize:10, color:G.mist, marginTop:20, fontStyle:"italic" }}>Risk profiling is a guide, not a prescription. You always decide what's right for you.</div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ── Compare Archetypes Modal (14b) ────────────────────────────────────────
  const CompareModal = () => {
    const archetypeIds = ["steady","balanced","aggressive","conviction"];
    const byId = archetypes.reduce((m, a) => { m[a.id] = a; return m; }, {});
    const A = byId[cmpA]; const B = byId[cmpB];
    if (!A || !B) return null;
    const wExp = (at) => {
      const funds = at.funds || [];
      const total = funds.reduce((s, f) => s + (f.weight || 20), 0) || 100;
      return funds.reduce((s, f) => s + (f.expense_ratio || 0) * (f.weight || 20) / total, 0);
    };
    const avgScore = (at) => {
      const funds = at.funds || [];
      const scores = funds.map(f => f.composite_score).filter(v => v != null);
      return scores.length ? scores.reduce((a,b) => a+b, 0) / scores.length : null;
    };
    const metrics = [
      ["CAGR Range", a => a.cagrRange, null],
      ["Risk Level", a => a.risk, null],
      ["Confidence Score", a => a.confidence?.overall_score?.toFixed(1) ?? "—", (va, vb) => parseFloat(va) > parseFloat(vb)],
      ["Avg Fund Score", a => avgScore(a)?.toFixed(1) ?? "—", (va, vb) => parseFloat(va) > parseFloat(vb)],
      ["Wtd Expense Ratio", a => wExp(a).toFixed(2) + "%", (va, vb) => parseFloat(va) < parseFloat(vb)],
      ["Fund Count", a => (a.funds || []).length, null],
      ["Crash 2020 Max DD", a => {
        const s = a.stressTest || {};
        const sc = s.scenarios || s;
        const entry = Object.values(sc).find(v => typeof v === "object" && v?.max_drawdown != null);
        return entry ? entry.max_drawdown?.toFixed(1) + "%" : "—";
      }, (va, vb) => parseFloat(va) > parseFloat(vb)],
    ];
    const winnerCol = (va, vb, fn) => {
      if (!fn || va === "—" || vb === "—") return [false, false];
      try { return [fn(va, vb), fn(vb, va)]; } catch { return [false, false]; }
    };
    return (
      <div style={{ position:"fixed", inset:0, zIndex:2300, background:"rgba(0,0,0,0.8)", display:"flex", alignItems:"center", justifyContent:"center", padding:16 }}
        onClick={e => { if (e.target === e.currentTarget) setCmpModal(false); }}>
        <div style={{ background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:16, width:"100%", maxWidth:660, maxHeight:"88vh", overflowY:"auto", padding:"24px 24px 28px", fontFamily:"Outfit,sans-serif" }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
            <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:20, color:G.gold, fontWeight:700 }}>Compare Archetypes</div>
            <button onClick={() => setCmpModal(false)} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:20 }}>&#x2715;</button>
          </div>
          {/* Pickers */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr auto 1fr", gap:10, alignItems:"center", marginBottom:20 }}>
            {[["cmpA", cmpA, setCmpA], ["cmpB", cmpB, setCmpB]].map(([id, val, setter]) => (
              <select key={id} value={val} onChange={e => setter(e.target.value)}
                style={{ background:G.elv, border:`1px solid rgba(255,255,255,0.1)`, borderRadius:8, padding:"8px 12px", color:G.white, fontFamily:"Outfit,sans-serif", fontSize:13, outline:"none" }}>
                {archetypeIds.map(a => <option key={a} value={a}>{byId[a]?.label || a}</option>)}
              </select>
            ))}
            <div style={{ textAlign:"center", color:G.mist, fontSize:16 }}>vs</div>
          </div>
          {/* Comparison table */}
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse" }}>
              <thead>
                <tr style={{ borderBottom:`1px solid ${G.bord}` }}>
                  <th style={{ padding:"8px 12px", textAlign:"left", fontSize:10, color:G.mist, textTransform:"uppercase", letterSpacing:".08em" }}>Metric</th>
                  {[A, B].map(at => (
                    <th key={at.id} style={{ padding:"8px 12px", textAlign:"right", fontSize:11, color:at.color, fontWeight:700, letterSpacing:".04em" }}>{at.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.map(([label, extractor, betterFn]) => {
                  const va = String(extractor(A)); const vb = String(extractor(B));
                  const [aBetter, bBetter] = winnerCol(va, vb, betterFn);
                  return (
                    <tr key={label} style={{ borderBottom:`1px solid rgba(255,255,255,0.04)` }}>
                      <td style={{ padding:"10px 12px", color:G.mist, fontSize:12 }}>{label}</td>
                      <td style={{ padding:"10px 12px", textAlign:"right", fontFamily:"JetBrains Mono,monospace", fontSize:12, color: aBetter ? "#27AE78" : G.fog }}>{va}{aBetter ? " ✓" : ""}</td>
                      <td style={{ padding:"10px 12px", textAlign:"right", fontFamily:"JetBrains Mono,monospace", fontSize:12, color: bBetter ? "#27AE78" : G.fog }}>{vb}{bBetter ? " ✓" : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {/* Fund lists */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginTop:20 }}>
            {[A, B].map(at => (
              <div key={at.id}>
                <div style={{ fontSize:11, color:at.color, fontWeight:700, letterSpacing:".06em", textTransform:"uppercase", marginBottom:10 }}>{at.label}</div>
                {(at.funds || []).map((f, i) => (
                  <div key={i} style={{ fontSize:11, color:G.fog, marginBottom:6, display:"flex", justifyContent:"space-between" }}>
                    <span style={{ flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", paddingRight:8 }}>{f.name}</span>
                    <span style={{ color:G.mist, flexShrink:0 }}>{f.weight}%</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ── Why Not In Bouquet Modal (14c) ────────────────────────────────────────
  const WhyNotModal = () => {
    const wd = wnData;
    const elig = wd?.eligibility;
    const checks = elig ? [
      ["Direct Plan", elig.passes_direct, elig.is_direct_plan ? "Yes" : "No — regular plan detected"],
      [`AUM ≥ ₹500Cr`, elig.passes_aum, elig.aum_crores != null ? `₹${elig.aum_crores.toFixed(0)}Cr` : "Data missing"],
      ["Expense Ratio ≤ 1.5%", elig.passes_expense, elig.expense_ratio != null ? `${elig.expense_ratio.toFixed(2)}%` : "Data missing"],
      [`NAV History ≥ 2 years`, elig.passes_tier, `${elig.nav_years}yr (Tier ${elig.tier})`],
    ] : [];
    return (
      <div style={{ position:"fixed", inset:0, zIndex:2400, background:"rgba(0,0,0,0.8)", display:"flex", alignItems:"center", justifyContent:"center", padding:16 }}
        onClick={e => { if (e.target === e.currentTarget) { setWnModal(false); setWnSearch(''); setWnData(null); setWnSelected(null); setWnResults([]); } }}>
        <div style={{ background:G.sur, border:`1px solid ${G.bordG}`, borderRadius:16, width:"100%", maxWidth:580, maxHeight:"90vh", overflowY:"auto", padding:"24px 24px 28px", fontFamily:"Outfit,sans-serif" }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:18 }}>
            <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:18, color:G.gold, fontWeight:700 }}>Fund Explorer</div>
            <button onClick={() => { setWnModal(false); setWnSearch(''); setWnData(null); setWnSelected(null); setWnResults([]); }} style={{ background:"none", border:"none", color:G.slate, cursor:"pointer", fontSize:20 }}>&#x2715;</button>
          </div>
          <div style={{ fontSize:12, color:G.mist, marginBottom:14 }}>Search any fund to see its eligibility status and why it is or isn't in a bouquet.</div>
          {/* Search input */}
          <div style={{ position:"relative", marginBottom:4 }}>
            <input value={wnSearch} onChange={e => handleWnSearch(e.target.value)} placeholder="Search fund name or AMC…"
              style={{ width:"100%", background:G.elv, border:`1px solid rgba(255,255,255,0.1)`, borderRadius:8, padding:"10px 14px", color:G.white, fontFamily:"Outfit,sans-serif", fontSize:13, outline:"none", boxSizing:"border-box" }} />
            {wnResults.length > 0 && (
              <div style={{ position:"absolute", top:"100%", left:0, right:0, background:G.sur, border:`1px solid ${G.bord}`, borderRadius:8, zIndex:10, boxShadow:"0 8px 24px rgba(0,0,0,0.4)" }}>
                {wnResults.map(r => (
                  <div key={r.scheme_code} onClick={() => handleWnSelect(r)}
                    style={{ padding:"10px 14px", cursor:"pointer", borderBottom:`1px solid rgba(255,255,255,0.04)` }}
                    onMouseEnter={e => e.currentTarget.style.background="rgba(212,175,55,0.07)"}
                    onMouseLeave={e => e.currentTarget.style.background="transparent"}>
                    <div style={{ fontSize:13, color:G.white }}>{r.name || r.scheme_name}</div>
                    <div style={{ fontSize:11, color:G.mist }}>{r.amc} · {r.category}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {wnLoading && <div style={{ padding:"30px 0", textAlign:"center", color:G.mist, fontSize:13 }}>Loading eligibility data…</div>}
          {wd && !wnLoading && (
            <>
              <div style={{ marginTop:16, marginBottom:12 }}>
                <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:16, color:G.white, fontWeight:600, lineHeight:1.3 }}>{wd.name}</div>
                <div style={{ fontSize:11, color:G.mist, marginTop:3 }}>{wd.category} · Scheme code: {wd.scheme_code}</div>
              </div>

              {/* In bouquet badge */}
              {wd.in_bouquets?.length > 0 ? (
                <div style={{ background:"rgba(39,174,120,0.1)", border:"1px solid rgba(39,174,120,0.25)", borderRadius:10, padding:"12px 16px", marginBottom:16 }}>
                  <div style={{ color:"#27AE78", fontWeight:600, fontSize:13, marginBottom:4 }}>✓ This fund is in a bouquet archetype</div>
                  {wd.in_bouquets.map(b => (
                    <div key={b.archetype_id} style={{ fontSize:12, color:G.fog }}>
                      {b.archetype_id.charAt(0).toUpperCase() + b.archetype_id.slice(1)} — Weight: {b.weight}%
                      {b.composite_score != null && ` · Score: ${b.composite_score.toFixed(1)}/100`}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ background:"rgba(240,165,0,0.08)", border:"1px solid rgba(240,165,0,0.2)", borderRadius:10, padding:"12px 16px", marginBottom:16 }}>
                  <div style={{ color:"#F0A500", fontWeight:600, fontSize:13 }}>Not currently in any bouquet archetype</div>
                </div>
              )}

              {/* Eligibility checks */}
              <div style={{ marginBottom:16 }}>
                <div style={{ fontSize:11, color:G.mist, letterSpacing:".08em", textTransform:"uppercase", marginBottom:10, fontWeight:600 }}>Eligibility Criteria</div>
                {checks.map(([label, pass, detail]) => (
                  <div key={label} style={{ display:"flex", alignItems:"flex-start", gap:10, marginBottom:8 }}>
                    <span style={{ flexShrink:0, color: pass ? "#27AE78" : "#E05555", fontWeight:700, marginTop:1 }}>{pass ? "✓" : "✗"}</span>
                    <div>
                      <span style={{ fontSize:12, color: pass ? G.fog : "#E05555", fontWeight: pass ? 400 : 500 }}>{label}</span>
                      <span style={{ fontSize:11, color:G.mist, marginLeft:8 }}>{detail}</span>
                    </div>
                  </div>
                ))}
                {elig?.overall_eligible && <div style={{ fontSize:11, color:"#27AE78", marginTop:6 }}>✓ Passes all eligibility filters</div>}
              </div>

              {/* Explanation */}
              {wd.reasons_not_included?.length > 0 && !(wd.in_bouquets?.length > 0) && (
                <div>
                  <div style={{ fontSize:11, color:G.mist, letterSpacing:".08em", textTransform:"uppercase", marginBottom:10, fontWeight:600 }}>Why It's Not Included</div>
                  {wd.reasons_not_included.map((reason, i) => (
                    <div key={i} style={{ fontSize:12, color:G.fog, lineHeight:1.7, marginBottom:8, paddingLeft:12, borderLeft:"2px solid rgba(240,165,0,0.3)" }}>{reason}</div>
                  ))}
                </div>
              )}
              {wd.lowest_bouquet_score != null && !(wd.in_bouquets?.length > 0) && elig?.overall_eligible && (
                <div style={{ fontSize:11, color:G.mist, marginTop:10, fontStyle:"italic" }}>
                  Lowest composite score in current bouquets: {wd.lowest_bouquet_score}/100
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

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
        <div className="tagline">{lang === 'hi' ? HI_HERO.tagline : "Mutual Fund Research. Unfiltered."}</div>
        <div className="gold-rule" />
        <div className="sec-tag">{lang === 'hi' ? HI_HERO.secTag : "Honest-by-Design Mutual Fund Research"}</div>
        <h1 className="h1">{lang === 'hi' ? HI_HERO.headline : "Curated fund bouquets."}<br /><em>{lang === 'hi' ? HI_HERO.headlineEm : "Honest by design."}</em></h1>
        <p className="sub">{lang === 'hi' ? HI_HERO.sub : "Two inputs. Four bouquet archetypes. Ten layers of transparent research. No commission. No false assurance."}</p>
        <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
          style={{ display:'inline-block', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', borderRadius:8, padding:'5px 14px', color:G.mist, fontFamily:'Outfit,sans-serif', fontSize:12, cursor:'pointer', letterSpacing:'.04em', marginBottom:8 }}>
          {lang === 'en' ? 'हिंदी में पढ़ें' : 'Read in English'}
        </button>
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
            {[["return", tr("Return target","रिटर्न लक्ष्य")], ["corpus", tr("Corpus target","कोष लक्ष्य")], ["sip", tr("SIP capacity","SIP क्षमता")]].map(([id, lbl]) => (
              <button key={id} className={`tab${mode === id ? " on" : ""}`} onClick={() => { setMode(id); setInputWarn(""); }}>{lbl}</button>
            ))}
          </div>
          {mode === "return" && (
            <div style={{ marginBottom: 24 }}>
              <label className="lbl">Target CAGR & investment horizon (any value — we'll show you what it means)</label>
              <div className="row">
                <div className="iw"><input className="inp" type="text" inputMode="numeric" placeholder="16" value={cagr} onChange={e => setCAGR(e.target.value)} /><span className="sfx">% CAGR</span></div>
                <div className="iw"><input className="inp" type="text" inputMode="numeric" placeholder="7" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx">Years</span></div>
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
                  <div className="iw"><input className="inp inp-sm" type="text" inputMode="numeric" placeholder="50" value={corpus} onChange={e => setCorpus(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>₹ Lakhs</span></div>
                  <div className="iw"><input className="inp inp-sm" type="text" inputMode="numeric" placeholder="7" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>Yrs</span></div>
                </div>
              </div>
              <div style={{ marginBottom: 14 }}>
                <label className="lbl">Starting lump sum (₹ Lakhs)</label>
                <div className="iw"><input className="inp inp-sm" type="text" inputMode="numeric" placeholder="10" value={ls} onChange={e => setLs(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>₹ L</span></div>
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
                  <div className="iw"><input className="inp inp-sm" type="text" inputMode="numeric" placeholder="15000" value={sip} onChange={e => setSip(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>/mo</span></div>
                  <div className="iw"><input className="inp inp-sm" type="text" inputMode="numeric" placeholder="10" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx" style={{ fontSize: 11 }}>Yrs</span></div>
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
          <button className="btn-p" disabled={!isValid} onClick={handleFind}>{tr("Curate My Bouquets →","मेरे बुके तैयार करें →")}</button>
          <button className="byob-entry" style={{ marginTop: 8 }} onClick={() => setScreen("custom_builder")}>{tr("✎ Build Your Own Bouquet", HI_HERO.btnBYOB)}</button>
          <button className="byob-entry" style={{ marginTop: 8, background:"rgba(212,175,55,0.08)" }} onClick={() => setScreen("portfolio")}>{tr("📊 Analyse My Portfolio", HI_HERO.btnPortfolio)}</button>
          <button className="byob-entry" style={{ marginTop: 8, background:"rgba(212,175,55,0.06)" }} onClick={() => { setCalcPreFill(null); setCalcTab('sip'); setScreen("calculators"); }}>{tr("📐 SIP & Tax Calculators", HI_HERO.btnCalc)}</button>
          <button className="byob-entry" style={{ marginTop: 8, background:"rgba(212,175,55,0.04)" }} onClick={() => { handleQuizReset(); setQuizModal(true); }}>{tr("🎯 Find My Risk Profile", HI_HERO.btnRisk)}</button>
          <p className="note">{lang === 'hi' ? HI_HERO.note : "Research & education only · Not investment advice · Past performance does not guarantee future returns\nAll fund data sourced from AMFI · No commission earned on any recommendation · fundguldasta.com"}</p>
        </div>
      </div>
    </>
  );


  // ── CALCULATORS SCREEN (Priority 12) ────────────────────────────────────────
  if (screen === "calculators") {
    document.title = "Calculators — FundGuldasta";

    const fmtINR = (n) => isNaN(n) ? '—' : '₹' + Math.round(n).toLocaleString('en-IN');
    const fmtCr = (n) => {
      if (isNaN(n) || n === 0) return '—';
      if (n >= 10000000) return '₹' + (n/10000000).toFixed(2) + ' Cr';
      if (n >= 100000) return '₹' + (n/100000).toFixed(2) + ' L';
      return fmtINR(n);
    };

    // ── SIP maths ──
    const sipYrsN = parseFloat(sipCalcYears) || 0;
    const sipCagrN = parseFloat(sipCalcCagr) || 0;
    const r = sipCagrN / 100 / 12;
    const n = sipYrsN * 12;
    let sipResult = null;
    if (sipMode === 'to-corpus' && sipCalcSip && sipYrsN && sipCagrN) {
      const P = parseFloat(sipCalcSip);
      const corpus = r === 0 ? P * n : P * ((Math.pow(1+r,n)-1)/r) * (1+r);
      const invested = P * n;
      sipResult = { corpus, invested, gain: corpus-invested, mult: corpus/invested };
    } else if (sipMode === 'to-sip' && sipCalcCorpus && sipYrsN && sipCagrN) {
      const FV = parseFloat(sipCalcCorpus);
      const sip = r === 0 ? FV/n : (FV * r) / ((Math.pow(1+r,n)-1) * (1+r));
      const invested = sip * n;
      sipResult = { corpus: FV, invested, gain: FV-invested, sip, mult: FV/invested };
    }

    // ── Tax maths ──
    let taxResult = null;
    const taxInv = parseFloat(taxCalcInvested);
    const taxCur = parseFloat(taxCalcCurrent);
    const taxMo = parseInt(taxCalcMonths);
    if (taxInv > 0 && taxCur > 0 && taxMo > 0) {
      taxResult = computeLTCG(taxInv, taxCur, taxMo, taxCalcType);
      if (taxResult.tax === null) {
        const slab = parseFloat(taxCalcSlab)/100;
        taxResult.tax = taxResult.gain * slab;
        taxResult.netGain = taxResult.gain * (1 - slab);
      }
      taxResult.postTaxCorpus = taxCur - Math.max(0, taxResult.tax || 0);
      const yrsHeld = taxMo / 12;
      taxResult.postTaxCagr = yrsHeld > 0 ? ((Math.pow(taxResult.postTaxCorpus / taxInv, 1/yrsHeld) - 1) * 100) : 0;
    }

    // ── Goal templates ──
    const goals = [
      { icon:"🎓", label:"Child's Education", desc:"Build a corpus for higher education fees", years:15, cagr:14, corpus:5000000, archetype:"Balanced Growther", color:"#4A9EFF" },
      { icon:"🏠", label:"House Down Payment", desc:"Save for a home down payment", years:7, cagr:13, corpus:3000000, archetype:"Steady Compounder", color:"#27AE78" },
      { icon:"🌅", label:"Retirement Corpus", desc:"Long-horizon wealth compounding", years:25, cagr:15, corpus:50000000, archetype:"Aggressive Achiever", color:G.gold },
    ];

    const TabBtn = ({ id, label }) => (
      <button onClick={() => setCalcTab(id)} style={{
        flex:1, padding:"10px 0", background: calcTab===id ? "rgba(212,175,55,0.15)" : "transparent",
        border:"none", borderBottom: calcTab===id ? `2px solid ${G.gold}` : "2px solid transparent",
        color: calcTab===id ? G.gold : G.slate, fontSize:13, fontWeight:600, cursor:"pointer",
        fontFamily:"Outfit,sans-serif", transition:"all .2s"
      }}>{label}</button>
    );

    // CalcInputRow and CalcResultRow are defined at module level (stable identity — no focus loss)

    return (
      <>
        <style>{css}</style>
        <div style={{ minHeight:"100vh", background:G.bg, fontFamily:"Outfit,sans-serif" }}>
          {/* Header */}
          <div style={{ padding:"20px 24px 0", maxWidth:820, margin:"0 auto" }}>
            <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:28 }}>
              <button onClick={() => setScreen("hero")} style={{ background:"none", border:`1px solid ${G.bord}`, borderRadius:8, padding:"5px 14px", color:G.slate, fontSize:12, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>← Back</button>
              <span style={{ color:G.gold, fontFamily:"Cormorant Garamond,serif", fontSize:26, fontWeight:700 }}>Investment Calculators</span>
              {calcPreFill && <span style={{ fontSize:11, color:G.mist, background:G.elv, padding:"3px 10px", borderRadius:6 }}>Pre-filled: {calcPreFill.label} · {calcPreFill.cagr}% CAGR</span>}
            </div>

            {/* Tabs */}
            <div style={{ display:"flex", background:G.sur, border:`1px solid ${G.bord}`, borderRadius:10, overflow:"hidden", marginBottom:24 }}>
              <TabBtn id="sip" label="📈 SIP Calculator" />
              <TabBtn id="goals" label="🎯 Goal Planner" />
              <TabBtn id="tax" label="🧾 Tax Calculator" />
            </div>
          </div>

          <div style={{ padding:"0 24px 80px", maxWidth:820, margin:"0 auto" }}>

            {/* ── SIP CALCULATOR TAB ── */}
            {calcTab === 'sip' && (
              <div>
                {/* Mode toggle */}
                <div style={{ display:"flex", gap:10, marginBottom:20 }}>
                  {[['to-corpus','SIP → Final Corpus'],['to-sip','Target Corpus → SIP Needed']].map(([m,l]) => (
                    <button key={m} onClick={() => setSipMode(m)} style={{
                      padding:"8px 18px", borderRadius:8, border:`1px solid ${sipMode===m ? G.bordG : G.bord}`,
                      background: sipMode===m ? "rgba(212,175,55,0.12)" : G.sur,
                      color: sipMode===m ? G.gold : G.slate, fontSize:12, fontWeight:600, cursor:"pointer", fontFamily:"Outfit,sans-serif"
                    }}>{l}</button>
                  ))}
                </div>

                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:24 }}>
                  {/* Inputs */}
                  <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:24, display:"flex", flexDirection:"column", gap:16 }}>
                    <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:4 }}>Inputs</div>
                    {sipMode === 'to-corpus'
                      ? <CalcInputRow label="Monthly SIP (₹)" value={sipCalcSip} setter={setSipCalcSip} placeholder="10000" suffix="₹/mo" />
                      : <CalcInputRow label="Target Corpus (₹)" value={sipCalcCorpus} setter={setSipCalcCorpus} placeholder="10000000" suffix="₹" />
                    }
                    <CalcInputRow label="Investment Horizon (years)" value={sipCalcYears} setter={setSipCalcYears} placeholder="7" suffix="yrs" />
                    <CalcInputRow label="Expected CAGR (%)" value={sipCalcCagr} setter={setSipCalcCagr} placeholder={calcPreFill ? String(calcPreFill.cagr) : "14"} suffix="%" />
                    {/* Quick CAGR presets */}
                    <div>
                      <div style={{ fontSize:10, color:G.mist, marginBottom:6 }}>Quick CAGR presets:</div>
                      <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                        {[12,14,15,16,18].map(c => (
                          <button key={c} onClick={() => setSipCalcCagr(String(c))} style={{
                            padding:"3px 10px", borderRadius:6, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif",
                            border:`1px solid ${parseFloat(sipCalcCagr)===c ? G.bordG : G.bord}`,
                            background: parseFloat(sipCalcCagr)===c ? "rgba(212,175,55,0.12)" : "transparent",
                            color: parseFloat(sipCalcCagr)===c ? G.gold : G.mist
                          }}>{c}%</button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Results */}
                  <div style={{ background:G.sur, border:`1px solid ${sipResult ? G.bordG : G.bord}`, borderRadius:12, padding:24 }}>
                    <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:16 }}>Results</div>
                    {!sipResult ? (
                      <div style={{ color:G.mist, fontSize:12, marginTop:24, textAlign:"center" }}>Fill in the inputs to see your projection</div>
                    ) : (
                      <>
                        {sipMode === 'to-sip' && <CalcResultRow label="Required monthly SIP" value={fmtINR(sipResult.sip)} color={G.gold} big={true} />}
                        <CalcResultRow label="Final corpus" value={fmtCr(sipResult.corpus)} color="#27AE78" big={sipMode==='to-corpus'} />
                        <CalcResultRow label="Total invested" value={fmtCr(sipResult.invested)} color={G.fog} />
                        <CalcResultRow label="Wealth gain" value={fmtCr(sipResult.gain)} color="#27AE78" />
                        <CalcResultRow label="Wealth multiplier" value={sipResult.mult.toFixed(2)+'x'} color={G.gold} border={false} />
                        {/* Visual bar */}
                        <div style={{ marginTop:16 }}>
                          <div style={{ display:"flex", height:12, borderRadius:6, overflow:"hidden", marginBottom:6 }}>
                            <div style={{ width: (sipResult.invested/sipResult.corpus*100)+'%', background:`rgba(255,255,255,0.15)`, transition:"width .5s" }} />
                            <div style={{ flex:1, background:"rgba(39,174,120,0.5)" }} />
                          </div>
                          <div style={{ display:"flex", gap:16, fontSize:10, color:G.mist }}>
                            <span>■ Invested: {(sipResult.invested/sipResult.corpus*100).toFixed(0)}%</span>
                            <span style={{ color:"rgba(39,174,120,0.8)" }}>■ Returns: {(sipResult.gain/sipResult.corpus*100).toFixed(0)}%</span>
                          </div>
                        </div>
                        <div style={{ marginTop:14, fontSize:10, color:G.mist, lineHeight:1.6 }}>
                          Projection based on constant CAGR — actual returns will vary. Adjust CAGR down 1–2% for conservative planning. Does not account for LTCG tax on redemption.
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Comparison table at different CAGRs */}
                {sipYrsN > 0 && (sipMode==='to-corpus' ? !!sipCalcSip : !!sipCalcCorpus) && (
                  <div style={{ marginTop:20, background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20 }}>
                    <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:14 }}>CAGR Sensitivity — how much does it matter?</div>
                    <div style={{ overflowX:"auto" }}>
                      <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                        <thead>
                          <tr>{["CAGR","Final Corpus","Total Invested","Wealth Gain","Multiplier"].map(h=>(
                            <th key={h} style={{ padding:"8px 12px", textAlign:"right", color:G.mist, fontWeight:600, borderBottom:`1px solid ${G.bord}`, whiteSpace:"nowrap" }}>{h}</th>
                          ))}</tr>
                        </thead>
                        <tbody>
                          {[10,12,14,15,16,18].map(c => {
                            const rr = c/100/12;
                            const nn = sipYrsN*12;
                            let corp, inv, sipp;
                            if (sipMode==='to-corpus') {
                              const P = parseFloat(sipCalcSip);
                              corp = rr===0 ? P*nn : P*((Math.pow(1+rr,nn)-1)/rr)*(1+rr);
                              inv = P*nn; sipp = P;
                            } else {
                              const FV = parseFloat(sipCalcCorpus);
                              sipp = rr===0 ? FV/nn : (FV*rr)/((Math.pow(1+rr,nn)-1)*(1+rr));
                              inv = sipp*nn; corp = FV;
                            }
                            const highlight = Math.abs(c - (parseFloat(sipCalcCagr)||0)) < 0.5;
                            return (
                              <tr key={c} style={{ background: highlight ? "rgba(212,175,55,0.06)" : "transparent" }}>
                                <td style={{ padding:"8px 12px", textAlign:"right", color: highlight ? G.gold : G.mist, fontWeight: highlight?700:400, fontFamily:"JetBrains Mono,monospace" }}>{c}%</td>
                                <td style={{ padding:"8px 12px", textAlign:"right", color:"#27AE78", fontFamily:"JetBrains Mono,monospace" }}>{fmtCr(corp)}</td>
                                <td style={{ padding:"8px 12px", textAlign:"right", color:G.fog, fontFamily:"JetBrains Mono,monospace" }}>{fmtCr(inv)}</td>
                                <td style={{ padding:"8px 12px", textAlign:"right", color:"rgba(39,174,120,0.7)", fontFamily:"JetBrains Mono,monospace" }}>{fmtCr(corp-inv)}</td>
                                <td style={{ padding:"8px 12px", textAlign:"right", color:G.gold, fontFamily:"JetBrains Mono,monospace" }}>{(corp/inv).toFixed(2)}x</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── GOAL PLANNER TAB ── */}
            {calcTab === 'goals' && (
              <div>
                <p style={{ color:G.slate, fontSize:13, marginBottom:20, marginTop:0 }}>Pick a goal to pre-fill the SIP calculator. Each goal maps to the most suitable FundGuldasta archetype.</p>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(240px,1fr))", gap:16, marginBottom:28 }}>
                  {goals.map(g => (
                    <div key={g.label} style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:14, padding:24, cursor:"pointer", transition:"all .2s" }}
                      onClick={() => {
                        setSipCalcYears(String(g.years));
                        setSipCalcCagr(String(g.cagr));
                        setSipCalcCorpus(String(g.corpus));
                        setSipMode('to-sip');
                        setCalcTab('sip');
                      }}
                      onMouseEnter={e => e.currentTarget.style.border=`1px solid ${g.color}`}
                      onMouseLeave={e => e.currentTarget.style.border=`1px solid ${G.bord}`}>
                      <div style={{ fontSize:32, marginBottom:12 }}>{g.icon}</div>
                      <div style={{ color:G.white, fontSize:15, fontWeight:700, marginBottom:6 }}>{g.label}</div>
                      <div style={{ color:G.slate, fontSize:12, lineHeight:1.6, marginBottom:14 }}>{g.desc}</div>
                      <div style={{ display:"flex", flexDirection:"column", gap:6, marginBottom:16 }}>
                        {[[`${g.years}-year horizon`, g.color],[`${g.cagr}% target CAGR`, g.color],[`Target: ${fmtCr(g.corpus)}`, G.white]].map(([t,c])=>(
                          <div key={t} style={{ fontSize:12, color:c, fontFamily:"JetBrains Mono,monospace" }}>{t}</div>
                        ))}
                      </div>
                      <div style={{ borderTop:`1px solid ${G.bord}`, paddingTop:12, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                        <div style={{ fontSize:11, color:G.mist }}>Suggested archetype</div>
                        <div style={{ fontSize:11, color:g.color, fontWeight:600 }}>{g.archetype}</div>
                      </div>
                      <div style={{ marginTop:10, padding:"7px 14px", background:`rgba(${g.color==='#4A9EFF'?'74,158,255':g.color==='#27AE78'?'39,174,120':'212,175,55'},0.1)`, borderRadius:7, color:g.color, fontSize:12, fontWeight:600, textAlign:"center" }}>
                        Use this goal →
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20 }}>
                  <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:10 }}>Custom Goal</div>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12, marginBottom:14 }}>
                    <CalcInputRow label="Target Corpus (₹)" value={sipCalcCorpus} setter={setSipCalcCorpus} placeholder="5000000" />
                    <CalcInputRow label="Horizon (years)" value={sipCalcYears} setter={setSipCalcYears} placeholder="10" />
                    <CalcInputRow label="Expected CAGR (%)" value={sipCalcCagr} setter={setSipCalcCagr} placeholder="14" />
                  </div>
                  <button onClick={() => { setSipMode('to-sip'); setCalcTab('sip'); }}
                    style={{ padding:"8px 22px", background:"rgba(212,175,55,0.12)", border:`1px solid ${G.bordG}`, borderRadius:8, color:G.gold, fontSize:12, fontWeight:600, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
                    Calculate SIP Required →
                  </button>
                </div>
              </div>
            )}

            {/* ── TAX CALCULATOR TAB ── */}
            {calcTab === 'tax' && (
              <div>
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:24 }}>
                  <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
                    <div style={{ background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:24, display:"flex", flexDirection:"column", gap:14 }}>
                      <div style={{ color:G.white, fontSize:13, fontWeight:600 }}>Investment Details</div>
                      <CalcInputRow label="Amount Invested (₹)" value={taxCalcInvested} setter={setTaxCalcInvested} placeholder="500000" />
                      <CalcInputRow label="Current Value (₹)" value={taxCalcCurrent} setter={setTaxCalcCurrent} placeholder="850000" />
                      <CalcInputRow label="Holding Period (months)" value={taxCalcMonths} setter={setTaxCalcMonths} placeholder="24" />
                      <div>
                        <div style={{ fontSize:11, color:G.slate, marginBottom:6 }}>Fund Type</div>
                        <div style={{ display:"flex", gap:8 }}>
                          {[['equity','Equity / Hybrid (≥65%)'],['debt','Debt / FOF / International']].map(([v,l]) => (
                            <button key={v} onClick={() => setTaxCalcType(v)} style={{
                              flex:1, padding:"8px 10px", borderRadius:8, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif", textAlign:"center",
                              border:`1px solid ${taxCalcType===v ? G.bordG : G.bord}`,
                              background: taxCalcType===v ? "rgba(212,175,55,0.1)" : G.elv,
                              color: taxCalcType===v ? G.gold : G.slate, fontWeight: taxCalcType===v ? 600 : 400
                            }}>{l}</button>
                          ))}
                        </div>
                      </div>
                      {taxCalcType === 'debt' && (
                        <div>
                          <div style={{ fontSize:11, color:G.slate, marginBottom:6 }}>Your Income Tax Slab</div>
                          <div style={{ display:"flex", gap:8 }}>
                            {[['0','Nil (below ₹3L)'],['5','5%'],['10','10%'],['15','15%'],['20','20%'],['30','30%']].map(([v,l]) => (
                              <button key={v} onClick={() => setTaxCalcSlab(v)} style={{
                                padding:"5px 8px", borderRadius:6, fontSize:10, cursor:"pointer", fontFamily:"Outfit,sans-serif",
                                border:`1px solid ${taxCalcSlab===v ? G.bordG : G.bord}`,
                                background: taxCalcSlab===v ? "rgba(212,175,55,0.1)" : "transparent",
                                color: taxCalcSlab===v ? G.gold : G.mist
                              }}>{l}</button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{ background:G.sur, border:`1px solid ${taxResult ? G.bordG : G.bord}`, borderRadius:12, padding:24 }}>
                    <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:16 }}>Tax Estimate</div>
                    {!taxResult ? (
                      <div style={{ color:G.mist, fontSize:12, marginTop:24, textAlign:"center" }}>Fill in investment details to calculate</div>
                    ) : (
                      <>
                        <CalcResultRow label="Amount invested" value={fmtINR(taxCalcInvested)} color={G.fog} />
                        <CalcResultRow label="Current value" value={fmtINR(taxCalcCurrent)} color="#27AE78" />
                        <CalcResultRow label="Gross gain" value={fmtINR(taxResult.gain)} color={taxResult.gain>=0?"#27AE78":"#E05555"} />
                        <CalcResultRow label="Tax type" value={taxResult.taxType} color={G.mist} />
                        {taxCalcType==='equity' && parseInt(taxCalcMonths)>12 && taxResult.gain > 0 && (
                          <CalcResultRow label="Exempt (₹1.25L/yr)" value={fmtINR(Math.min(taxResult.gain, 125000))} color={G.mist} />
                        )}
                        <CalcResultRow label="Estimated tax" value={taxResult.tax > 0 ? fmtINR(taxResult.tax) : '₹0'} color="#E8A000" big />
                        <CalcResultRow label="Post-tax corpus" value={fmtINR(taxResult.postTaxCorpus)} color="#27AE78" big />
                        <CalcResultRow label="Post-tax CAGR" value={taxResult.postTaxCagr > 0 ? taxResult.postTaxCagr.toFixed(2)+'%' : '—'} color={G.gold} border={false} />
                        <div style={{ marginTop:16, padding:"10px 14px", background:"rgba(255,255,255,0.03)", borderRadius:8, fontSize:10, color:G.mist, lineHeight:1.7 }}>
                          <strong style={{ color:G.slate }}>Budget 2024 rates:</strong> Equity LTCG 12.5% (above ₹1.25L/yr exemption), STCG 20%. Debt/FOF/International funds taxed at income slab rate regardless of holding. Always consult a CA for your exact liability.
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Equity vs Debt comparison */}
                <div style={{ marginTop:20, background:G.sur, border:`1px solid ${G.bord}`, borderRadius:12, padding:20 }}>
                  <div style={{ color:G.white, fontSize:13, fontWeight:600, marginBottom:8 }}>Why fund type matters for tax</div>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
                    {[
                      { type:"Equity Fund (≥65% equity)", stcg:"20% (held ≤12 months)", ltcg:"12.5% above ₹1.25L/yr (held >12 months)", note:"Nifty Index funds, large cap, mid cap, flexi cap, ELSS", color:"#27AE78" },
                      { type:"Debt / FOF / International", stcg:"Slab rate (any holding)", ltcg:"Slab rate (any holding)", note:"Motilal Nasdaq 100 FOF, any debt fund, fund of funds", color:"#E8A000" },
                    ].map(t => (
                      <div key={t.type} style={{ padding:"14px 16px", background:G.elv, borderRadius:10, border:`1px solid ${G.bord}` }}>
                        <div style={{ color:t.color, fontSize:12, fontWeight:700, marginBottom:10 }}>{t.type}</div>
                        <div style={{ fontSize:11, color:G.slate, marginBottom:4 }}>Short-term: <span style={{ color:G.white }}>{t.stcg}</span></div>
                        <div style={{ fontSize:11, color:G.slate, marginBottom:8 }}>Long-term: <span style={{ color:G.white }}>{t.ltcg}</span></div>
                        <div style={{ fontSize:10, color:G.mist, fontStyle:"italic" }}>{t.note}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }


  // ── SEO CONTENT SCREENS (Priority 11) ──────────────────────────────────────

  const LearnBack = ({ label = "← Back" }) => (
    <button onClick={() => setScreen("hero")}
      style={{ background:"none", border:"none", color:G.mist, fontSize:13, cursor:"pointer",
        fontFamily:"Outfit,sans-serif", display:"flex", alignItems:"center", gap:6, padding:0, marginBottom:48 }}>
      {label}
    </button>
  );

  const LearnPage = ({ title, subtitle, children }) => (
    <>
      <style>{css}</style>
      <div className="about-screen">
        <div className="about-inner">
          <LearnBack />
          <div style={{ marginBottom:56 }}>
            <div style={{ fontFamily:"Cormorant Garamond,serif", fontSize:"clamp(28px,5vw,46px)", color:G.white, fontWeight:600, lineHeight:1.15, marginBottom:12 }}>{title}</div>
            <div style={{ fontSize:15, color:G.gold, fontStyle:"italic", fontFamily:"Cormorant Garamond,serif" }}>{subtitle}</div>
          </div>
          {children}
          <div style={{ marginTop:56, padding:"28px 32px", background:"linear-gradient(135deg,rgba(212,175,55,0.07),rgba(212,175,55,0.02))", border:`1px solid rgba(212,175,55,0.2)`, borderRadius:16 }}>
            <div style={{ color:G.white, fontSize:14, fontWeight:600, marginBottom:8 }}>Try it yourself</div>
            <div style={{ color:G.fog, fontSize:13, lineHeight:1.8, marginBottom:16 }}>FundGuldasta applies all of these principles automatically. Enter your investment horizon and target CAGR to see research-backed bouquets.</div>
            <button onClick={() => setScreen("hero")}
              style={{ background:"rgba(212,175,55,0.15)", border:`1px solid ${G.bordG}`, borderRadius:10, padding:"10px 28px", color:G.gold, fontSize:13, fontWeight:600, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
              Start Research →
            </button>
          </div>
        </div>
      </div>
    </>
  );

  const LearnCard = ({ title, children }) => (
    <div className="about-card" style={{ marginBottom:16 }}>
      <div className="about-card-title">{title}</div>
      <div className="about-card-body">{children}</div>
    </div>
  );

  if (screen === "learn-algorithm") {
    document.title = "How Our Algorithm Works — FundGuldasta";
    return (
      <LearnPage title="How Our Algorithm Works" subtitle="Five layers. No shortcuts. No conflicts of interest.">
        <div style={{ marginBottom:32 }}>
          <div style={{ fontSize:10, letterSpacing:".14em", textTransform:"uppercase", color:G.gold, fontWeight:700, marginBottom:20 }}>The Five-Layer Engine</div>
          {[
            ["Layer 1 — Eligibility Filter", "We start with all 14,000+ mutual fund schemes and immediately discard everything that does not meet our baseline: Direct Plan only (no regular plans that pay distributor commissions), AUM ≥ ₹500 Crore (liquidity protection), and expense ratio ≤ 1.5%. Schemes with fewer than 3 years of NAV history are also excluded as unproven. This alone removes roughly 85% of schemes."],
            ["Layer 2 — Six-Dimension Scoring", "Each surviving fund is scored across six dimensions: Return Consistency (25%) — what percentage of rolling periods beat the target CAGR; Risk-Adjusted Quality (20%) — Sortino and Sharpe ratios that penalise downside volatility more than upside; Downside Behaviour (20%) — max drawdown, recovery speed, and capture ratios; Manager Stability (15%) — tenure, historical track record, and absence of recent manager changes; Portfolio Quality (10%) — concentration, style consistency; Forward Context (10%) — category tailwinds and benchmark relative performance."],
            ["Layer 3 — Bouquet Construction", "Funds are assembled into a 4–6 fund bouquet using category diversity as the primary constraint. We do not allow two funds from the same SEBI category unless the category is large enough to warrant it (e.g., Flexi Cap + Large Cap). A correlation check is run as a secondary filter — Indian equity funds typically correlate at 0.85–0.98, so we focus on category diversity rather than raw correlation numbers. International and sectoral funds are added only when their category diversification benefit justifies inclusion."],
            ["Layer 4 — Confidence Scoring", "Every bouquet gets an honest confidence score (0–100) based on five factors: Rolling Consistency (30%) — what fraction of 3-year rolling windows would have achieved the target; Downside Protection (20%) — behaviour during 2008, 2011, 2015, 2020 drawdowns; Manager Stability (20%) — no recent manager change flag; Category Tailwind (15%) — SEBI category performance context; Cost Efficiency (15%) — composite expense ratio vs category average. A score below 60 triggers a warning."],
            ["Layer 5 — Pre-computation", "Results are pre-computed nightly for all supported horizons (5, 7, 10, 15 years) and stored in a database cache. The API never triggers live computation during user requests — this guarantees sub-100ms response times regardless of traffic. Cache freshness is monitored; if data is older than 48 hours, an alert fires automatically."],
          ].map(([title, body], i) => (
            <div key={i} style={{ display:"flex", gap:16, padding:"20px 24px", borderRadius:12, background:"rgba(255,255,255,0.025)", border:`1px solid rgba(255,255,255,0.05)`, marginBottom:12 }}>
              <div style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:G.gold, fontWeight:700, flexShrink:0, marginTop:2, minWidth:28 }}>0{i+1}</div>
              <div>
                <div style={{ fontSize:14, color:G.white, fontWeight:600, marginBottom:8 }}>{title}</div>
                <div style={{ fontSize:13, color:G.fog, lineHeight:1.8 }}>{body}</div>
              </div>
            </div>
          ))}
        </div>
        <LearnCard title="What we do not do">
          We do not use star ratings (backward-looking and marketing-driven). We do not rank funds by recent 1-year returns. We do not consider regular plans. We do not accept any commission, trail fee, or referral fee from any AMC. The algorithm has no financial incentive to prefer one fund over another.
        </LearnCard>
        <LearnCard title="Data sources">
          NAV data is ingested daily from <strong>AMFI (amfiindia.com)</strong> — the official regulator-mandated source. Benchmark data comes from NSE indices. Fund manager data is sourced from SEBI-mandated Scheme Information Documents. No third-party data vendor is used.
        </LearnCard>
      </LearnPage>
    );
  }

  if (screen === "learn-rolling-returns") {
    document.title = "Rolling Returns Explained — FundGuldasta";
    return (
      <LearnPage title="Rolling Returns Explained" subtitle="Why point-to-point returns can mislead you — and what to use instead.">
        <LearnCard title="What is a point-to-point return?">
          When a fund says "15% CAGR over 5 years," it means: if you had invested on a specific date exactly 5 years ago and redeemed today, your annualised return would be 15%. <strong>The problem:</strong> this single number depends entirely on which two dates you pick. A fund that crashed 40% two months ago can show a stellar 5-year return if the starting date happened to be another crash. Point-to-point returns are a snapshot, not a pattern.
        </LearnCard>
        <LearnCard title="What is a rolling return?">
          A rolling return is calculated for <strong>every possible start date</strong> over a given period. For a 3-year rolling window with daily data over 7 years, we calculate roughly 1,000+ different 3-year CAGRs — starting January 1 Year 1, January 2 Year 1, January 3 Year 1… and so on. The result is a <em>distribution</em> of returns, not a single number. This tells you: in what fraction of 3-year periods did this fund beat 15%? What was the worst 3-year CAGR? What was the median?
        </LearnCard>
        <LearnCard title="Why does FundGuldasta use rolling returns?">
          Rolling returns are resistant to cherry-picking. A fund cannot look artificially good or bad just because of market timing at the endpoints. For an Indian retail investor with a 5–10 year horizon who will invest via SIP (not lump sum on a single date), the rolling return distribution is a far more honest measure of what they are likely to experience. <strong>Our Return Consistency score</strong> specifically measures the percentage of 3-year rolling windows where a fund beat the target CAGR — a fund that beats 15% in 87% of all 3-year windows is genuinely more consistent than one that beat it in 45%.
        </LearnCard>
        <LearnCard title="The SIP angle">
          With a monthly SIP, you are effectively investing at many different starting points simultaneously. Your actual return is the internal rate of return (XIRR) across all those entry points — which converges toward the rolling return distribution, not the point-to-point number. This is why our algorithm prioritises rolling consistency over headline 1-year or 3-year returns.
        </LearnCard>
        <LearnCard title="Realistic CAGR bands for Indian equity MF">
          Historical rolling return analysis shows: over any 7-year window, Indian large cap equity funds have delivered 10–16% CAGR in most periods. Mid and small caps show higher variance — exceptional in bull runs, brutal in bear ones. Our advisory system flags targets above 20% over 7 years as aggressive and above 22% as unrealistic — not to discourage you, but to give you honest expectations.
        </LearnCard>
      </LearnPage>
    );
  }

  if (screen === "learn-survivorship") {
    document.title = "Survivorship Bias in Mutual Funds — FundGuldasta";
    return (
      <LearnPage title="Survivorship Bias" subtitle="Why most fund performance data is silently flattering — and how we deal with it.">
        <LearnCard title="What is survivorship bias?">
          Survivorship bias is the logical error of focusing only on entities that "survived" a selection process while overlooking those that did not. In mutual funds: funds that performed poorly are quietly merged into other funds or wound up. After 10 years, only the survivors remain in the data. If you calculate the average performance of funds that exist <em>today</em> with 10-year history, you are looking only at the funds that did well enough to survive — the bad ones are gone from the dataset.
        </LearnCard>
        <LearnCard title="How bad is this in Indian MF?">
          AMFI data shows that hundreds of schemes have been merged or wound up over the past decade. Many of these were underperformers. A naive analysis of "average 10-year return of Indian equity funds" would exclude all of them and show an inflated result. Studies on global fund data consistently show survivorship bias inflates apparent average returns by 1–3% per year — a massive distortion over long horizons.
        </LearnCard>
        <LearnCard title="Why star ratings are especially vulnerable">
          Most star rating systems rate funds that exist today on their historical performance. By construction, 5-star funds are mostly survivors. The 1-star and 2-star funds that later got merged or wound up never dragged down the averages. This is one reason why picking funds based on star ratings alone produces disappointing real-world results.
        </LearnCard>
        <LearnCard title="What FundGuldasta does about it">
          We cannot fully eliminate survivorship bias — AMFI's live data only contains active schemes. However, we mitigate it in several ways: <strong>(1)</strong> We require a minimum 3-year NAV history (new launches with no track record are excluded). <strong>(2)</strong> We rely on rolling return distributions rather than absolute performance ranks — a distribution-based approach is less sensitive to which specific funds exist. <strong>(3)</strong> We disclose this limitation explicitly. <strong>(4)</strong> We use category-level benchmark comparisons, which include index-level data not affected by fund-level survivorship.
        </LearnCard>
        <LearnCard title="What this means for you">
          When you see that "the average large cap fund returned 13% over 10 years," treat it with scepticism. The funds that underperformed or got wound up are not in that average. The honest benchmark is a low-cost index fund — which has no survivorship bias because an index includes all constituents, including underperformers. This is one reason why our bouquets always compare against Nifty 50 and Nifty 500, not the average fund.
        </LearnCard>
      </LearnPage>
    );
  }

  if (screen === "learn-confidence") {
    document.title = "Confidence Score Guide — FundGuldasta";
    return (
      <LearnPage title="Confidence Score Guide" subtitle="What our 0–100 confidence score means and how it is calculated.">
        <div className="about-card" style={{ marginBottom:24 }}>
          <div className="about-card-title">What the score means</div>
          <div className="about-card-body">
            The confidence score is our honest assessment of how likely a bouquet is to achieve its target CAGR over the stated horizon — given historical patterns, manager stability, and category conditions. A score of <strong style={{ color:G.white }}>80+</strong> means strong historical evidence. <strong style={{ color:G.white }}>65–79</strong> means reasonable confidence with some uncertainty. <strong style={{ color:"#E8A000" }}>Below 60</strong> triggers a visible warning — we still show the bouquet but flag that the target may be ambitious or conditions are unfavourable. The score is never hidden or smoothed.
          </div>
        </div>
        <div style={{ fontSize:10, letterSpacing:".14em", textTransform:"uppercase", color:G.gold, fontWeight:700, marginBottom:16 }}>The Five Factors</div>
        {[
          ["Rolling Consistency — 30%", "What percentage of all 3-year rolling windows in the fund's history achieved the target CAGR? A fund that hits 15%+ in 85% of all 3-year windows scores higher than one that hits it in 50%. This is the single largest factor because it directly measures whether the target is historically realistic — not just theoretically possible."],
          ["Downside Protection — 20%", "How did the constituent funds behave during the four major Indian market drawdowns: the 2008 global financial crisis, 2011 European debt contagion, 2015–16 China slowdown, and the 2020 COVID crash? Funds that recovered faster and drew down less score higher. A bouquet that crumbles 60% during a crash is unlikely to compound to its target even if the arithmetic says it should."],
          ["Manager Stability — 20%", "Fund manager continuity matters significantly in active management. A fund with the same manager for 7+ years who built the performance history is more predictable than one that just changed managers 6 months ago. We flag recent manager changes (within 18 months) as risk factors. This factor uses available SID data — we disclose when data is incomplete."],
          ["Category Tailwind — 15%", "Is the SEBI category the fund operates in currently in a favourable environment? Categories that have recently shown strong benchmark performance relative to their history get a positive tailwind. Categories that are extremely overheated (e.g., mid/small caps after a 3-year bull run) get a slight headwind flag. This is forward-looking context, not a prediction."],
          ["Cost Efficiency — 15%", "The expense ratio is the one return you are guaranteed to give up every year. A bouquet with a weighted average expense ratio of 0.6% scores higher than one at 1.2%. Over a 7-year horizon, the difference of 0.6% per year compounds to roughly 4–5% of your corpus. We normalise this against category averages — a small cap fund at 1.5% may be fine; a large cap fund at 1.5% is overpriced."],
        ].map(([title, body], i) => (
          <div key={i} style={{ marginBottom:12, padding:"20px 24px", borderRadius:12, background:"rgba(255,255,255,0.025)", border:`1px solid rgba(255,255,255,0.05)` }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:8 }}>
              <div style={{ fontSize:14, color:G.white, fontWeight:600 }}>{title.split("—")[0]}</div>
              <div style={{ fontSize:11, color:G.gold, fontWeight:700, fontFamily:"JetBrains Mono,monospace", flexShrink:0, marginLeft:12 }}>{title.split("—")[1]?.trim()}</div>
            </div>
            <div style={{ fontSize:13, color:G.fog, lineHeight:1.8 }}>{body}</div>
          </div>
        ))}
        <LearnCard title="What confidence is NOT">
          The confidence score is not a guarantee or a prediction of the future. Markets are non-deterministic. A high confidence score means "based on historical patterns, this target has been achievable consistently" — not "you will definitely get this return." All investments involve risk. The score is one honest data point, not a promise.
        </LearnCard>
      </LearnPage>
    );
  }

  if (screen === "learn-direct-plans") {
    document.title = "Why Direct Plans Matter — FundGuldasta";
    return (
      <LearnPage title="Why Direct Plans Matter" subtitle="The single most important financial decision most Indian investors don't know they're making.">
        <LearnCard title="What is the difference?">
          Every mutual fund scheme in India exists in two versions: <strong>Regular Plan</strong> and <strong>Direct Plan</strong>. The underlying portfolio is identical — the same fund manager, same stocks, same strategy. The only difference is the expense ratio. Regular plans include a distributor commission (typically 0.5–1.5% per year) paid to whoever sold you the fund — your bank, broker, or app. Direct plans have no distributor commission. SEBI mandates that AMCs offer both.
        </LearnCard>
        <LearnCard title="How big is the difference?">
          For a large cap fund: Regular plan expense ratio ≈ 1.5–2.0%. Direct plan expense ratio ≈ 0.5–1.0%. The gap is roughly 0.8–1.2% per year. That may sound small. Over 10 years on ₹10 lakh invested at 14% in a direct plan vs 13.2% in a regular plan: <strong>Direct plan corpus: ~₹37.1L. Regular plan corpus: ~₹34.6L. Difference: ~₹2.5 lakh — or 25% of your original investment, silently paid in commissions.</strong>
        </LearnCard>
        <LearnCard title="Why do most investors still use regular plans?">
          <strong>(1)</strong> Most investment apps (especially bank apps and large brokers) default to regular plans — they earn trail commission on every rupee you invest. <strong>(2)</strong> Financial advisors paid by commission have an incentive to recommend regular plans. <strong>(3)</strong> The difference is invisible — both plans show returns on the same scale, so you never see the absolute amount you're paying. <strong>(4)</strong> The SEBI naming convention ("Regular" vs "Direct") makes regular plans sound more standard.
        </LearnCard>
        <LearnCard title="Where to invest in direct plans">
          Direct plans are available through: <strong>MF Central</strong> (mfcentral.com — official AMFI/CAMS/KFintech portal), <strong>AMC websites directly</strong> (Mirae, PPFAS, HDFC AMC etc.), <strong>MF Utilities</strong> (mfuonline.com), and platforms that explicitly offer direct plans like Coin by Zerodha, Groww (select direct plan explicitly), Kuvera, and Paytm Money. FundGuldasta recommends only direct plans — all scheme codes in our algorithm are Direct Plan codes.
        </LearnCard>
        <LearnCard title="The SEBI regulation">
          SEBI made direct plans mandatory for all mutual fund schemes from January 1, 2013 (SEBI Circular CIR/IMD/DF/21/2012). This was a landmark investor-protection regulation. Despite being a decade old, a significant portion of industry AUM still flows through regular plans. The expense ratio differential is fully disclosed in the Scheme Information Document — it is public information that most investors simply do not check.
        </LearnCard>
        <LearnCard title="FundGuldasta's position">
          We only research and recommend direct plans. We do not earn commission from any AMC. We do not have a distribution license. We cannot and do not facilitate transactions — our role is research and education only. When you use our bouquets, please ensure you invest in the Direct Plan variant on a direct platform. The scheme codes we display are always Direct Plan codes.
        </LearnCard>
      </LearnPage>
    );
  }

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

          <div style={{ marginTop:40, marginBottom:32 }}>
            <div style={{ fontSize:10, letterSpacing:".14em", textTransform:"uppercase", color:G.gold, fontWeight:700, marginBottom:16 }}>Learn More</div>
            <div style={{ display:"flex", flexWrap:"wrap", gap:10 }}>
              {[["How Our Algorithm Works","learn-algorithm"],["Rolling Returns Explained","learn-rolling-returns"],["Survivorship Bias","learn-survivorship"],["Confidence Score Guide","learn-confidence"],["Why Direct Plans Matter","learn-direct-plans"]].map(([label, sid]) => (
                <button key={sid} onClick={() => setScreen(sid)}
                  style={{ background:"rgba(212,175,55,0.07)", border:"1px solid rgba(212,175,55,0.2)", borderRadius:8, padding:"8px 16px", color:G.mist, fontSize:12, cursor:"pointer", fontFamily:"Outfit,sans-serif" }}>
                  {label} →
                </button>
              ))}
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
              <div className="footer-links" style={{ marginTop:8 }}>
                <span style={{ fontSize:10, color:G.mist, marginRight:4, letterSpacing:".06em", textTransform:"uppercase" }}>Learn:</span>
                <button className="footer-link" onClick={() => { setCalcPreFill(null); setCalcTab('sip'); setScreen("calculators"); }}>📐 Calculators</button>
                <button className="footer-link" onClick={() => setScreen("learn-algorithm")}>How It Works</button>
                <button className="footer-link" onClick={() => setScreen("learn-rolling-returns")}>Rolling Returns</button>
                <button className="footer-link" onClick={() => setScreen("learn-survivorship")}>Survivorship Bias</button>
                <button className="footer-link" onClick={() => setScreen("learn-confidence")}>Confidence Score</button>
                <button className="footer-link" onClick={() => setScreen("learn-direct-plans")}>Direct Plans</button>
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
                    type="text"
                    inputMode="numeric"
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
              <input className="byob-horizon-input" type="text" inputMode="numeric" value={cbHorizon} onChange={e => setCbHorizon(e.target.value)} />
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
      {btModal && <BacktestModal />}
      {fdModal && <FundDetailModal />}
      {quizModal && <QuizModal />}
      {cmpModal && archetypes.length >= 2 && <CompareModal />}
      {wnModal && <WhyNotModal />}
      <style>{css}</style>
      <div onClick={() => healthOpen && setHealthOpen(false)}>
        <div className="rbar">
          <div className="rbar-l">
            <div className="rbn">FundGuldasta</div>
            <button className="bbtn" style={{ color: G.mist }} onClick={() => setScreen("about")}>About</button>
            <button className="bbtn" onClick={reset}>← New Search</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px" }} onClick={() => setScreen("custom_builder")}>✎ Build Your Own</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px", background:"rgba(212,175,55,0.08)" }} onClick={() => setScreen("portfolio")}>📊 My Portfolio</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px", background:"rgba(212,175,55,0.06)" }} onClick={() => { setCalcPreFill(selectedArch ? { cagr: (selectedArch.metrics?.bouquet_cagr||selectedArch.cagrRange||14), label: selectedArch.label } : null); setCalcTab('sip'); setScreen("calculators"); }}>📐 Calculators</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px", background:"rgba(212,175,55,0.04)" }} onClick={() => { setCmpA("steady"); setCmpB("balanced"); setCmpModal(true); }}>⊟ Compare</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px", background:"rgba(212,175,55,0.03)" }} onClick={() => { setWnSearch(''); setWnData(null); setWnSelected(null); setWnResults([]); setWnModal(true); }}>🔍 Fund Explorer</button>
            <div className="pill">{goalPill}</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 11, color: G.mist }}>{tr("fundguldasta.com · Research & Education · Not Investment Advice","fundguldasta.com · केवल शोध और शिक्षा · निवेश सलाह नहीं")}</div>
            <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
              style={{ background:"rgba(255,255,255,0.05)", border:"1px solid rgba(255,255,255,0.1)", borderRadius:6, padding:"3px 10px", color:G.mist, fontSize:11, cursor:"pointer", fontFamily:"Outfit,sans-serif", letterSpacing:".04em", flexShrink:0 }}>
              {lang === 'en' ? 'हिंदी' : 'EN'}
            </button>
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
                  {tr("Sign Out","साइन आउट")}
                </button>
              </div>
            ) : (
              <button onClick={() => { setAuthTab("login"); setAuthModal(true); }}
                style={{ background:"rgba(212,175,55,0.1)", border:`1px solid rgba(212,175,55,0.35)`, borderRadius:8,
                  padding:"5px 16px", color:G.gold, fontSize:11, fontWeight:600, cursor:"pointer",
                  fontFamily:"Outfit,sans-serif", letterSpacing:".04em" }}>
                {tr("Sign In","साइन इन")}
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
                  <div style={{ display:"flex", gap:6, marginTop:8, flexWrap:"wrap" }}>
                    <button onClick={e => { e.stopPropagation(); handleSaveBouquet(at); }}
                      title={savedMsg[at.id] ? "Saved!" : "Save bouquet"}
                      style={{ background:"none", border:`1px solid ${savedMsg[at.id] ? at.color : "rgba(255,255,255,0.12)"}`,
                        borderRadius:6, padding:"3px 10px", color:savedMsg[at.id] ? at.color : G.mist,
                        fontSize:10, cursor:"pointer", fontFamily:"Outfit,sans-serif", fontWeight:600, transition:"all .2s" }}>
                      {savedMsg[at.id] ? "✓ Saved" : "☆ Save"}
                    </button>
                    <button onClick={e => { e.stopPropagation(); handleBacktest(at); }}
                      title="Historical SIP backtest"
                      style={{ background:"none", border:"1px solid rgba(255,255,255,0.12)",
                        borderRadius:6, padding:"3px 10px", color:G.mist,
                        fontSize:10, cursor:"pointer", fontFamily:"Outfit,sans-serif", fontWeight:600, transition:"all .2s" }}>
                      ⬡ Backtest
                    </button>
                  </div>
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
                  <div>Curating alternative bouquets from our eligible universe...</div>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.2)" }}>Same 6-dimension scoring engine, different fund pool.</div>
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
                    {altRounds.length === 0 ? " Pre-curated for speed — typically ready in seconds." : ""}
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
                    <span style={{ fontSize: 14 }}>✶</span> {tr("advisor.title", "advisor.title")}
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
                            type="text" inputMode="numeric" placeholder="₹ value"
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
                            <input type="text" inputMode="numeric" value={ltcgInputs[f.key] || ''}
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
                            <input type="text" inputMode="numeric" value={sipInputs[f.key] || ''} placeholder={f.ph}
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
                            <div className="fn" onClick={e => { e.stopPropagation(); handleFundDetail(String(f.scheme_code)); }}
                              style={{ cursor:"pointer", textDecoration:"underline dotted", textDecorationColor:"rgba(255,255,255,0.25)", textUnderlineOffset:3 }}
                              title="View fund detail">{f.name}</div>
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
