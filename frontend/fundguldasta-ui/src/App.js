import React, { useState, useEffect, useCallback } from "react";

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
.bmark{width:108px;height:108px;background:linear-gradient(145deg,${G.gold} 0%,${G.goldD} 55%,#7A5810 100%);border-radius:18px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 48px rgba(212,175,55,0.55),inset 0 1px 0 rgba(255,255,255,0.18);flex-shrink:0}
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
.rbar{background:rgba(9,12,17,0.96);backdrop-filter:blur(16px);border-bottom:1px solid ${G.bord};padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
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
.di{display:flex;gap:12px;align-items:flex-start;padding:13px 15px;background:rgba(216,72,72,0.05);border-radius:10px;border-left:3px solid ${G.ro}}
.mg{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(max-width:700px){.mg{grid-template-columns:1fr}}
.mi{display:flex;gap:10px;align-items:flex-start;background:${G.elv};border-radius:8px;padding:11px 13px}
.cog{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:700px){.cog{grid-template-columns:repeat(2,1fr)}}
.coc{background:${G.elv};border-radius:12px;padding:18px 14px;text-align:center}
.coc.pri{background:rgba(212,175,55,0.08);border:1px solid rgba(212,175,55,0.2)}
.frg{display:flex;flex-direction:column;gap:8px}
.frr{display:flex;align-items:center;justify-content:space-between;background:${G.elv};border-radius:8px;padding:10px 14px}
.fdot{width:8px;height:8px;border-radius:50%}
.fdg{background:${G.em}}.fda{background:${G.am}}
.slbl{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:${G.gold};margin-bottom:14px}
.itax{margin-top:14px;padding:13px 15px;background:rgba(232,160,0,0.07);border:1px solid rgba(232,160,0,0.2);border-radius:10px;font-size:12px;color:${G.am};line-height:1.7}
.customize-toggle{display:flex;align-items:center;gap:8px;background:transparent;border:1px solid rgba(212,175,55,0.25);border-radius:8px;padding:8px 16px;color:${G.mist};font-family:'Outfit',sans-serif;font-size:12px;cursor:pointer;transition:all .2s;margin-top:16px}.customize-toggle:hover{border-color:rgba(212,175,55,0.5);color:${G.gold}}.customize-panel{margin-top:16px;border:1px solid rgba(212,175,55,0.15);border-radius:12px;padding:20px;background:rgba(212,175,55,0.03)}.cx-search{width:100%;background:${G.elv};border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:10px 14px;color:${G.white};font-family:'Outfit',sans-serif;font-size:13px;outline:none;box-sizing:border-box}.cx-search:focus{border-color:rgba(212,175,55,0.35)}.cx-results{margin-top:4px;background:${G.sur};border:1px solid ${G.bord};border-radius:8px;overflow:hidden}.cx-result{padding:12px 14px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,0.04);transition:background .15s}.cx-result:last-child{border-bottom:none}.cx-result:hover{background:rgba(212,175,55,0.06)}.cx-result-name{font-size:13px;color:${G.white};margin-bottom:2px}.cx-result-meta{font-size:11px;color:${G.mist}}.cx-compare{margin-top:16px}.cx-table{width:100%;border-collapse:collapse;margin-top:10px}.cx-table th{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:${G.mist};padding:8px 10px;text-align:left;border-bottom:1px solid ${G.bord}}.cx-table th:not(:first-child){text-align:right}.cx-table td{padding:9px 10px;font-size:12px;color:${G.fog};border-bottom:1px solid rgba(255,255,255,0.03)}.cx-table td:not(:first-child){text-align:right;font-family:'JetBrains Mono',monospace}.cx-table tr:last-child td{border-bottom:none}.cx-better{color:#27AE78}.cx-worse{color:#E05555}.cx-impact{margin-top:12px;padding:12px 14px;background:rgba(255,255,255,0.03);border-radius:8px;font-size:12px;color:${G.mist};line-height:1.7}.cx-actions{display:flex;gap:10px;margin-top:14px}.cx-accept{flex:1;padding:10px;background:rgba(39,174,120,0.15);border:1px solid rgba(39,174,120,0.3);border-radius:8px;color:#27AE78;font-family:'Outfit',sans-serif;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}.cx-accept:hover{background:rgba(39,174,120,0.25)}.cx-reject{flex:1;padding:10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:${G.mist};font-family:'Outfit',sans-serif;font-size:13px;cursor:pointer;transition:all .2s}.cx-reject:hover{background:rgba(255,255,255,0.07)}.cx-applied{display:inline-flex;align-items:center;gap:5px;font-size:10px;background:rgba(39,174,120,0.12);border:1px solid rgba(39,174,120,0.25);border-radius:6px;padding:3px 8px;color:#27AE78;margin-left:8px}.match-best{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;background:rgba(39,174,120,0.15);border:1px solid rgba(39,174,120,0.3);border-radius:4px;padding:2px 7px;color:#27AE78;margin-top:7px;display:inline-block}.match-label{font-size:9px;color:rgba(255,255,255,0.3);margin-top:6px;letter-spacing:.04em}.gen-more-cta{margin:32px 0 0;padding:28px 24px;border:1px dashed rgba(212,175,55,0.25);border-radius:16px;text-align:center;background:rgba(212,175,55,0.02)}.gen-more-title{font-family:Cormorant Garamond,serif;font-size:20px;color:;margin-bottom:8px;font-weight:600}.gen-more-sub{font-size:13px;color:;line-height:1.7;margin-bottom:20px;max-width:480px;margin-left:auto;margin-right:auto}.gen-more-btn{background:transparent;border:1px solid rgba(212,175,55,0.4);border-radius:10px;padding:12px 32px;color:;font-family:Outfit,sans-serif;font-size:14px;font-weight:600;cursor:pointer;letter-spacing:.04em;transition:all .2s}.gen-more-btn:hover{background:rgba(212,175,55,0.08);border-color:rgba(212,175,55,0.7)}.gen-more-btn:disabled{opacity:.4;cursor:not-allowed}.alt-round-header{display:flex;align-items:center;gap:14px;margin:40px 0 20px}.alt-round-divider{flex:1;height:1px;background:linear-gradient(90deg,rgba(212,175,55,0.2),transparent)}.alt-round-label{font-family:Cormorant Garamond,serif;font-size:16px;color:;white-space:nowrap;letter-spacing:.04em}.alt-round-note{font-size:11px;color:;margin-top:4px;text-align:center}.gen-loading{display:flex;flex-direction:column;align-items:center;gap:16px;padding:40px;color:;font-size:13px}.gen-spinner{width:36px;height:36px;border:2px solid rgba(212,175,55,0.15);border-top-color:rgba(212,175,55,0.7);border-radius:50%;animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.gen-exhausted{margin:24px 0;padding:16px 20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;text-align:center;font-size:12px;color:}.byob-entry{display:inline-flex;align-items:center;gap:8px;background:transparent;border:1px solid rgba(212,175,55,0.3);border-radius:10px;padding:10px 22px;color:${G.gold};font-family:'Outfit',sans-serif;font-size:13px;cursor:pointer;transition:all .2s;margin-top:12px}.byob-entry:hover{background:rgba(212,175,55,0.07);border-color:rgba(212,175,55,0.6)}.byob-screen{min-height:100vh;background:${G.bg};padding:48px 24px 80px}.byob-inner{max-width:780px;margin:0 auto}.byob-back{background:none;border:none;color:${G.mist};font-size:13px;cursor:pointer;font-family:Outfit,sans-serif;display:flex;align-items:center;gap:6px;padding:0;margin-bottom:32px}.byob-back:hover{color:${G.gold}}.byob-title{font-family:'Cormorant Garamond',serif;font-size:36px;color:${G.white};margin-bottom:6px;font-weight:600}.byob-sub{font-size:13px;color:${G.mist};margin-bottom:36px;line-height:1.7}.byob-search{position:relative}.byob-input{width:100%;background:${G.elv};border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:13px 16px;color:${G.white};font-family:'Outfit',sans-serif;font-size:14px;outline:none;box-sizing:border-box}.byob-input:focus{border-color:rgba(212,175,55,0.4)}.byob-dropdown{position:absolute;top:calc(100% + 4px);left:0;right:0;background:${G.sur};border:1px solid ${G.bord};border-radius:10px;overflow:hidden;z-index:50;box-shadow:0 8px 32px rgba(0,0,0,0.4)}.byob-opt{padding:13px 16px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,0.04);transition:background .12s}.byob-opt:last-child{border-bottom:none}.byob-opt:hover{background:rgba(212,175,55,0.07)}.byob-opt-name{font-size:13px;color:${G.white};margin-bottom:2px}.byob-opt-meta{font-size:11px;color:${G.mist}}.byob-fund-list{margin-top:20px}.byob-fund-row{display:flex;align-items:center;gap:12px;padding:14px 16px;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:10px;margin-bottom:8px}.byob-fund-info{flex:1;min-width:0}.byob-fund-name{font-size:13px;color:${G.white};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.byob-fund-meta{font-size:11px;color:${G.mist};margin-top:2px}.byob-weight-input{width:64px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:6px 10px;color:${G.white};font-family:'JetBrains Mono',monospace;font-size:13px;text-align:right;outline:none}.byob-weight-input:focus{border-color:rgba(212,175,55,0.4)}.byob-pct{font-size:12px;color:${G.mist}}.byob-remove{background:none;border:none;color:${G.mist};font-size:16px;cursor:pointer;padding:4px;line-height:1;border-radius:4px}.byob-remove:hover{color:#E05555}.byob-total{text-align:right;font-size:12px;margin-top:8px;font-family:'JetBrains Mono',monospace}.byob-total.ok{color:#27AE78}.byob-total.warn{color:#E05555}.byob-controls{display:flex;align-items:center;gap:16px;margin-top:28px;flex-wrap:wrap}.byob-horizon-wrap{display:flex;align-items:center;gap:10px}.byob-horizon-label{font-size:12px;color:${G.mist}}.byob-horizon-input{width:56px;background:${G.elv};border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 10px;color:${G.white};font-family:'JetBrains Mono',monospace;font-size:14px;text-align:center;outline:none}.byob-horizon-input:focus{border-color:rgba(212,175,55,0.4)}.byob-analyse-btn{flex:1;min-width:200px;padding:13px 24px;background:rgba(212,175,55,0.12);border:1px solid rgba(212,175,55,0.4);border-radius:10px;color:${G.gold};font-family:'Outfit',sans-serif;font-size:14px;font-weight:600;cursor:pointer;letter-spacing:.04em;transition:all .2s}.byob-analyse-btn:hover{background:rgba(212,175,55,0.2);border-color:rgba(212,175,55,0.7)}.byob-analyse-btn:disabled{opacity:.4;cursor:not-allowed}.byob-results{margin-top:40px}.byob-result-header{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:28px}.byob-metric-card{flex:1;min-width:160px;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:20px 22px}.byob-metric-label{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:${G.mist};margin-bottom:8px}.byob-metric-value{font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:500;color:${G.gold}}.byob-metric-sub{font-size:11px;color:${G.mist};margin-top:4px}.byob-table{width:100%;border-collapse:collapse;margin-top:6px}.byob-table th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:${G.mist};padding:8px 12px;text-align:left;border-bottom:1px solid ${G.bord}}.byob-table th:not(:first-child){text-align:right}.byob-table td{font-size:12px;color:${G.fog};padding:11px 12px;border-bottom:1px solid rgba(255,255,255,0.03)}.byob-table td:not(:first-child){text-align:right;font-family:'JetBrains Mono',monospace}.byob-table tr:last-child td{border-bottom:none}.byob-score-bar{display:inline-block;width:36px;height:4px;border-radius:2px;margin-left:8px;vertical-align:middle}.byob-section{margin-top:24px;background:${G.elv};border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:20px 22px}.byob-section-title{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:${G.mist};margin-bottom:14px;font-weight:600}.byob-warn-item{font-size:12px;color:${G.fog};line-height:1.7;margin-bottom:8px;padding-left:14px;position:relative}.byob-warn-item::before{content:'';position:absolute;left:0;top:7px;width:5px;height:5px;border-radius:50%;background:#F0A500}.byob-warn-item.danger::before{background:#E05555}.byob-suggestion{background:rgba(39,174,120,0.06);border:1px solid rgba(39,174,120,0.15);border-radius:10px;padding:14px 16px;margin-bottom:10px}.byob-sug-header{font-size:12px;color:${G.fog};margin-bottom:6px}.byob-sug-funds{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.byob-sug-from{font-size:13px;color:${G.mist};text-decoration:line-through}.byob-sug-arrow{color:${G.gold};font-size:16px}.byob-sug-to{font-size:13px;color:#27AE78;font-weight:500}.byob-sug-delta{font-size:11px;color:#27AE78;background:rgba(39,174,120,0.12);border-radius:4px;padding:2px 7px;margin-left:6px}.byob-sug-rationale{font-size:11px;color:${G.mist};margin-top:6px;line-height:1.6}@keyframes up{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}
`;

export default function App() {
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
  const [apiError, setApiError] = useState(null);
  const [cagrAdvisory, setCagrAdvisory] = useState(null);
  const [approxHorizon, setApproxHorizon] = useState(null);
  const [customizeOpen, setCustomizeOpen] = useState(false);
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

  const handleCbAnalyse = async () => {
    if (cbFunds.length < 1) return;
    const total = cbFunds.reduce((s, f) => s + f.weight, 0);
    if (Math.abs(total - 100) > 2) { setCbError(`Weights sum to ${total.toFixed(1)}% — please adjust to 100%.`); return; }
    setCbLoading(true); setCbError(null); setCbAnalysis(null);
    try {
      const result = await apiCall('POST', '/api/bouquets/analyse-custom', {
        funds: cbFunds.map(f => ({ scheme_code: f.scheme_code, weight: f.weight })),
        horizonYears: parseFloat(cbHorizon) || 7,
      });
      setCbAnalysis(result);
    } catch (e) {
      setCbError('Analysis failed. Please try again.');
    } finally {
      setCbLoading(false);
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
    setCustomizeLoading(false);
  }, [selectedArch]);

  const a = selectedArch;
  const archetypes = curationResult?.archetypes || [];

  if (screen === "hero") return (
    <>
      <style>{css}</style>
      <div className="hero">
        <div className="mesh" />
        <div className="brand">
          <div className="bmark">
            <svg viewBox="0 0 100 100" width="98" height="98" xmlns="http://www.w3.org/2000/svg">

              {/* ── Soil / pot base ── */}
              <ellipse cx="50" cy="86" rx="18" ry="4.5" fill="rgba(0,0,0,0.32)"/>
              <ellipse cx="50" cy="83" rx="13" ry="3" fill="rgba(0,0,0,0.22)"/>

              {/* ── Stalks from common base (50, 82) ── */}

              {/* LC — Large Cap — far left */}
              <path d="M50 82 Q28 65 16 46" stroke="rgba(0,0,0,0.45)" strokeWidth="2.2" strokeLinecap="round" fill="none"/>

              {/* MC — Mid Cap — left */}
              <path d="M50 82 Q36 60 28 38" stroke="rgba(0,0,0,0.45)" strokeWidth="2.2" strokeLinecap="round" fill="none"/>

              {/* FC — Flexi Cap — centre, tallest */}
              <line x1="50" y1="82" x2="50" y2="18" stroke="rgba(0,0,0,0.45)" strokeWidth="2.2" strokeLinecap="round"/>

              {/* VF — Value Fund — right */}
              <path d="M50 82 Q64 60 72 38" stroke="rgba(0,0,0,0.45)" strokeWidth="2.2" strokeLinecap="round" fill="none"/>

              {/* SC — Small Cap — far right */}
              <path d="M50 82 Q72 65 84 46" stroke="rgba(0,0,0,0.45)" strokeWidth="2.2" strokeLinecap="round" fill="none"/>

              {/* ── Leaves (proper pointed shape) ── */}

              {/* LC — deep green, rotate −38° */}
              <g transform="translate(14,40) rotate(-38)">
                <path d="M0 10 C-7 5 -7 -5 0 -10 C7 -5 7 5 0 10Z" fill="#145C37"/>
                <line x1="0" y1="8" x2="0" y2="-8" stroke="rgba(255,255,255,0.22)" strokeWidth="0.9"/>
              </g>
              <text x="14" y="42.5" fontSize="6.2" textAnchor="middle" fill="white" fontWeight="700" fontFamily="'Outfit',sans-serif">LC</text>

              {/* MC — deep blue, rotate −18° */}
              <g transform="translate(26,31) rotate(-18)">
                <path d="M0 10 C-7 5 -7 -5 0 -10 C7 -5 7 5 0 10Z" fill="#14437A"/>
                <line x1="0" y1="8" x2="0" y2="-8" stroke="rgba(255,255,255,0.22)" strokeWidth="0.9"/>
              </g>
              <text x="26" y="33.5" fontSize="6.2" textAnchor="middle" fill="white" fontWeight="700" fontFamily="'Outfit',sans-serif">MC</text>

              {/* FC — dark translucent centre */}
              <g transform="translate(50,12)">
                <path d="M0 10 C-7 5 -7 -5 0 -10 C7 -5 7 5 0 10Z" fill="rgba(0,0,0,0.48)"/>
                <line x1="0" y1="8" x2="0" y2="-8" stroke="rgba(255,255,255,0.22)" strokeWidth="0.9"/>
              </g>
              <text x="50" y="14.5" fontSize="6.2" textAnchor="middle" fill="white" fontWeight="700" fontFamily="'Outfit',sans-serif">FC</text>

              {/* VF — deep plum, rotate +18° */}
              <g transform="translate(74,31) rotate(18)">
                <path d="M0 10 C-7 5 -7 -5 0 -10 C7 -5 7 5 0 10Z" fill="#4E2880"/>
                <line x1="0" y1="8" x2="0" y2="-8" stroke="rgba(255,255,255,0.22)" strokeWidth="0.9"/>
              </g>
              <text x="74" y="33.5" fontSize="6.2" textAnchor="middle" fill="white" fontWeight="700" fontFamily="'Outfit',sans-serif">VF</text>

              {/* SC — deep crimson, rotate +38° */}
              <g transform="translate(86,40) rotate(38)">
                <path d="M0 10 C-7 5 -7 -5 0 -10 C7 -5 7 5 0 10Z" fill="#8B1A1A"/>
                <line x1="0" y1="8" x2="0" y2="-8" stroke="rgba(255,255,255,0.22)" strokeWidth="0.9"/>
              </g>
              <text x="86" y="42.5" fontSize="6.2" textAnchor="middle" fill="white" fontWeight="700" fontFamily="'Outfit',sans-serif">SC</text>

            </svg>
          </div>
          <div>
            <div className="bname">FundGuldasta</div>
            <div className="btag">Fund selection ka ek rasta</div>
            <div style={{ fontSize: 13, color: "rgba(212,175,55,0.5)", fontFamily: "Outfit,sans-serif", marginTop: 4, letterSpacing: "0.06em", textTransform: "uppercase" }}>Mutual Fund Research · Unfiltered</div>
          </div>
        </div>
        <div className="tagline">Mutual Fund Research. Unfiltered.</div>
        <div className="gold-rule" />
        <div className="sec-tag">India's First Honest-by-Design Mutual Fund Research Platform</div>
        <h1 className="h1">Curated fund bouquets.<br /><em>Honest by design.</em></h1>
        <p className="sub">Two inputs. Four bouquet archetypes. Ten layers of transparent research. No commission. No false assurance.</p>
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
                return <div style={{ fontSize: 11, color: hintColor, marginTop: 6, lineHeight: 1.5 }}>{hint}</div>;
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
          <p className="note">Research & education only · Not investment advice · Past performance does not guarantee future returns<br />All fund data sourced from AMFI · No commission earned on any recommendation · fundguldasta.com</p>
        </div>
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
            <div className="byob-results">
              <div style={{ width: 40, height: 1, background: "rgba(212,175,55,0.3)", margin: "0 0 28px" }} />

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
                  <div style={{ fontSize: 12, color: G.mist, marginBottom: 14 }}>These substitutions could strengthen your bouquet — same category, higher composite score. Your choice entirely.</div>
                  {cbAnalysis.suggestions.map((s, i) => (
                    <div key={i} className="byob-suggestion">
                      <div className="byob-sug-header">Consider replacing:</div>
                      <div className="byob-sug-funds">
                        <span className="byob-sug-from">{s.replace_fund.name}</span>
                        <span className="byob-sug-arrow">→</span>
                        <span className="byob-sug-to">{s.with_fund.name}</span>
                        <span className="byob-sug-delta">+{s.score_improvement} pts</span>
                      </div>
                      <div className="byob-sug-rationale">{s.rationale}</div>
                    </div>
                  ))}
                </div>
              )}
              {cbAnalysis.suggestions.length === 0 && (
                <div className="byob-section" style={{ borderColor: "rgba(39,174,120,0.2)" }}>
                  <div className="byob-section-title">Improvement Suggestions</div>
                  <div style={{ fontSize: 13, color: "#27AE78" }}>All your funds score above the bouquet median — no obvious substitution recommended. Strong selection.</div>
                </div>
              )}

              {/* Warnings */}
              {(() => {
                const allWarnings = [
                  ...(cbAnalysis.warnings.correlation || []).map(w => ({ text: w, danger: true })),
                  ...(cbAnalysis.warnings.concentration || []).map(w => ({ text: w, danger: false })),
                  ...(cbAnalysis.warnings.amc || []).map(w => ({ text: w, danger: false })),
                  ...(cbAnalysis.warnings.tier || []).map(w => ({ text: w, danger: false })),
                  ...(cbAnalysis.warnings.expense_ratio || []).map(w => ({ text: w, danger: false })),
                ];
                if (allWarnings.length === 0) return null;
                return (
                  <div className="byob-section">
                    <div className="byob-section-title">Cautions & Advisories</div>
                    {allWarnings.map((w, i) => (
                      <div key={i} className={`byob-warn-item${w.danger ? " danger" : ""}`}>{w.text}</div>
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
      <style>{css}</style>
      <div>
        <div className="rbar">
          <div className="rbar-l">
            <div className="rbn">FundGuldasta</div>
            <button className="bbtn" onClick={reset}>← New Search</button>
            <button className="byob-entry" style={{ marginTop: 0, fontSize: 11, padding: "5px 14px" }} onClick={() => setScreen("custom_builder")}>✎ Build Your Own</button>
            <div className="pill">{goalPill}</div>
          </div>
          <div style={{ fontSize: 11, color: G.mist }}>fundguldasta.com · Research & Education · Not Investment Advice</div>
        </div>
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
                <div className="exb">
                  <button className="bo">💾 Save Research</button>
                  <button className="bg2">Invest via Kuvera →</button>
                </div>
              </div>

              {/* BOX 3 — FUNDS */}
              <div className="card">
                <div className="ch"><span className="ct">Bouquet Composition</span><span className="badge bg-gold">5 Funds · Direct Plans · No Commission</span>{customizeApplied && <span className="cx-applied">✎ Customized</span>}</div>
                <div className="cb">
                  <div className="fg">
                    {(a.funds || []).map((f, i) => (
                      <div key={i} className="fc">
                        <div className="fw">{f.weight}%</div>
                        <div className="fn">{f.name}</div>
                        <div className="fcat">{f.category}</div>
                        <div className="fm">
                          AMC: <span>{f.amc}</span><br />
                          Score: <span>{f.composite_score?.toFixed(1)}</span>
                        </div>
                        <div className={`tier t${f.tier}`}>
                          {f.tier === 1 ? "✅ Full Record" : f.tier === 2 ? "🟢 Substantial" : "🟡 On Potential"}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                  <button className="customize-toggle" onClick={() => setCustomizeOpen(o => !o)}>
                    {customizeOpen ? "▲ Close Customization" : "✎ Customize this bouquet"}
                  </button>
                  {customizeOpen && (
                    <div className="customize-panel">
                      <div style={{ fontSize: 12, color: G.mist, marginBottom: 10 }}>Search any eligible fund by name or AMC to substitute in this bouquet</div>
                      <input
                        className="cx-search"
                        type="text"
                        placeholder="e.g. Parag Parikh, HDFC, Axis Midcap..."
                        value={customizeSearch}
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

              {/* BOX 4 — METRICS */}
              <div className="card">
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
              <div className="card">
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
                          <div className="bar"><div className="bf" style={{ width: `${f.score}%`, background: a.color }} /></div>
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
              <div className="card">
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
              <div className="card">
                <div className="ch"><span className="ct">Portfolio Analysis</span><span className="badge bg-g">Correlation Data</span></div>
                <div className="cb">
                  <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 72, fontWeight: 500, color: G.em, lineHeight: 1 }}>
                      {a.overlap?.avgOverlapPct || 0}%
                    </div>
                    <div>
                      <div style={{ fontSize: 14, color: G.fog, marginBottom: 8 }}><strong style={{ color: G.white }}>Average stock overlap</strong> across all 5 funds</div>
                      <div style={{ fontSize: 13, color: G.mist, lineHeight: 1.7 }}>
                        Average inter-fund return correlation: <strong style={{ color: G.fog }}>{a.overlap?.avgCorrelation}</strong><br />
                        Note: Indian equity funds typically correlate at 0.85–0.95 with each other due to similar large cap holdings.
                        International allocation (Nasdaq) provides genuine diversification at correlation ~0.37.
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* BOX 8 — DEVIL */}
              <div className="card">
                <div className="ch"><span className="ct">Why This Bouquet Might Not Work</span><span className="badge bg-r">Read Before Deciding</span></div>
                <div className="cb">
                  <ul className="dl">
                    {(a.devils || []).map((d, i) => (
                      <li key={i} className="di">
                        <span style={{ color: G.ro, flexShrink: 0, fontSize: 15, marginTop: 1 }}>→</span>
                        <span style={{ fontSize: 13, color: G.fog, lineHeight: 1.6 }}>{d}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* BOX 9 — METHODOLOGY */}
              <div className="card">
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
                </div>
              </div>

              {/* BOX 10 — COMPARATOR */}
              <div className="card">
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
                  <div className="ch"><span className="ct">Data Freshness</span><span className="badge bg-g">All Sources Disclosed</span></div>
                  <div className="cb">
                    <div className="frg">
                      {(freshness.sources || []).map((s, i) => (
                        <div key={i} className="frr">
                          <div>
                            <div style={{ fontSize: 13, color: G.fog }}>{s.name}</div>
                            <div style={{ fontSize: 11, color: G.mist }}>Source: {s.source}</div>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: G.mist }}>{s.lastUpdated}</span>
                            <div className={`fdot ${s.isStale ? "fda" : "fdg"}`} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* FINAL EXEC */}
              <div className="exec" style={{ marginBottom: 0 }}>
                <div>
                  <h3 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 20, color: G.white, marginBottom: 6 }}>Ready to invest in this bouquet?</h3>
                  <p style={{ fontSize: 13, color: G.slate, lineHeight: 1.6 }}>
                    FundGuldasta provides research only. Execute on a SEBI-registered platform.
                    Each fund purchased individually or through Kuvera / MFU for unified multi-AMC execution.
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
    </>
  );
}
