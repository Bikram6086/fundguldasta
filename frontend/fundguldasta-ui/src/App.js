import React, { useState, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000";

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
.brand{display:flex;align-items:center;gap:14px;margin-bottom:52px;animation:up .9s ease .1s both}
.bmark{width:46px;height:46px;background:linear-gradient(135deg,${G.gold},${G.goldD});border-radius:10px;display:flex;align-items:center;justify-content:center;font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:700;color:${G.bg}}
.bname{font-family:'Cormorant Garamond',serif;font-size:26px;font-weight:600;color:${G.gold}}
.btag{font-size:11px;color:${G.mist};margin-top:2px;letter-spacing:.08em}
.h1{font-family:'Cormorant Garamond',serif;font-size:clamp(38px,6vw,74px);font-weight:700;line-height:1.06;text-align:center;color:${G.white};max-width:840px;margin-bottom:14px;animation:up .9s ease .3s both}
.h1 em{color:${G.gold};font-style:normal}
.tagline{font-family:'Cormorant Garamond',serif;font-size:clamp(18px,2.4vw,26px);color:${G.gold};margin-bottom:14px;letter-spacing:.04em;font-style:italic;animation:up .9s ease .38s both}
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
.warn-box{background:rgba(232,160,0,0.08);border:1px solid rgba(232,160,0,0.25);border-radius:10px;padding:14px 16px;font-size:13px;color:${G.am};line-height:1.7;margin-bottom:20px}
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
@keyframes up{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
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
      const fdata = await getFreshness().catch(() => null);
      setFreshness(fdata);
      setScreen("results");
    } catch (err) {
      setApiError("Could not connect to API. Please ensure the backend is running on port 8000.");
      setScreen("hero");
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
    setScreen("hero"); setSelectedArch(null); setBStep(0);
    setBAns({}); setBDone(false); setBProf(null);
    setShowBehav(true); setCurationResult(null); setApiError(null);
  };

  const a = selectedArch;
  const archetypes = curationResult?.archetypes || [];

  if (screen === "hero") return (
    <>
      <style>{css}</style>
      <div className="hero">
        <div className="mesh" />
        <div className="brand">
          <div className="bmark">F</div>
          <div><div className="bname">FundGuldasta</div><div className="btag">fundguldasta.com · Mutual Fund Research · Unfiltered</div></div>
        </div>
        <h1 className="h1">Curated fund bouquets.<br /><em>Honest by design.</em></h1>
        <div className="tagline">Mutual Fund Research. Unfiltered.</div>
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
              <label className="lbl">Target CAGR & investment horizon</label>
              <div className="row">
                <div className="iw"><input className="inp" type="number" placeholder="16" value={cagr} onChange={e => setCAGR(e.target.value)} /><span className="sfx">% CAGR</span></div>
                <div className="iw"><input className="inp" type="number" placeholder="7" value={yrs} onChange={e => setYrs(e.target.value)} /><span className="sfx">Years</span></div>
              </div>
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
          <p className="note">Research & education only · Not investment advice · Past performance does not guarantee future returns<br />All fund data sourced from AMFI · No commission earned on any recommendation · fundguldasta.com</p>
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
                </div>
              ))}
            </div>
          </div>

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
                <div className="ch"><span className="ct">Bouquet Composition</span><span className="badge bg-gold">5 Funds · Direct Plans · No Commission</span></div>
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
              </div>

              {/* BOX 4 — METRICS */}
              <div className="card">
                <div className="ch"><span className="ct">Historical Performance Metrics</span><span className="badge bg-g">Live AMFI Data</span></div>
                <div className="cb" style={{ overflowX: "auto" }}>
                  <table className="mt">
                    <thead>
                      <tr>
                        <th>Period</th><th>Bouquet CAGR</th><th>Real CAGR*</th><th>Post-Tax†</th>
                        <th>Nifty 50</th><th>FD Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(a.metrics?.periods || {}).map(([p, r]) => (
                        <tr key={p}>
                          <td>{p}</td>
                          <td className="gc">{r.bouquet}%</td>
                          <td className="ec">{r.realCAGR}%</td>
                          <td className="zc">{r.postTax}%</td>
                          <td className="dc">{r.nifty50 ? `${r.nifty50.toFixed(1)}%` : "—"}</td>
                          <td className="dc">{r.fdRate}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ marginTop: 14, fontSize: 11, color: G.mist, lineHeight: 1.8 }}>
                    * Real CAGR adjusted for 6% inflation · † Post-Tax assumes 30% slab, 12.5% LTCG · All figures computed from live AMFI NAV data
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
