// ------------------------------------------------------------------ grading
// All grading rules live here so they are easy to find and change.
const GRADING = {
  weights: { attendance: 40, sponsored: 35, cosponsored: 25 },
  attendanceFloor: 0.85,                       // attendance at or below this scores 0
  stagePoints: { introduced: 1, committee: 3, passed: 6, law: 10 },
  letters: [[93, "A"], [90, "A-"], [87, "B+"], [83, "B"], [80, "B-"], [77, "C+"],
            [73, "C"], [70, "C-"], [67, "D+"], [63, "D"], [60, "D-"], [0, "F"]],
  partialTerm: 0.5,                            // eligible for < 50% of votes → partial term
  // Bill scores come from chamber percentile ranks. They are mapped onto
  // percentileFloor..100 so the chamber average (50th percentile) earns a C, not an F.
  percentileFloor: 50,
};

const LABELS = { attendance: "Vote attendance", sponsored: "Bills written", cosponsored: "Bills supported" };
const PARTY = { Democrat: "D", Republican: "R", Independent: "I" };
const STATES = {AL:"Alabama",AK:"Alaska",AS:"American Samoa",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",GU:"Guam",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",MP:"Northern Mariana Islands",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",PR:"Puerto Rico",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VI:"U.S. Virgin Islands",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"};

// Delegates/Resident Commissioner vote only in Committee of the Whole, so they are
// eligible for far fewer roll calls; that is not a partial term.
const DELEGATE_STATES = new Set(["DC", "PR", "GU", "AS", "VI", "MP"]);
const SPEAKER_ID = "J000299"; // Speaker of the House votes only at their discretion

const data = window.REPORT_DATA;
const members = data.members;
let weights = loadWeights();

const clamp = (x) => Math.max(0, Math.min(100, x));
const pct = (x) => `${(x * 100).toFixed(1)}%`;
const letterOf = (score) => GRADING.letters.find(([min]) => score >= min)[1];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function legislativePoints(bills) {
  return Object.entries(bills.stages).reduce((sum, [k, n]) => sum + n * GRADING.stagePoints[k], 0);
}

// Percentile rank within chamber (ties share the midpoint), 0–100.
function percentileScorer(getValue) {
  const byChamber = {};
  for (const m of members) {
    const v = getValue(m);
    if (v != null) (byChamber[m.chamber] ??= []).push(v);
  }
  for (const list of Object.values(byChamber)) list.sort((a, b) => a - b);
  return (m) => {
    const v = getValue(m), list = byChamber[m.chamber];
    if (v == null || !list || list.length < 2) return null;
    let below = 0, equal = 0;
    for (const x of list) { if (x < v) below++; else if (x === v) equal++; }
    return clamp(((below + (equal - 1) / 2) / (list.length - 1)) * 100);
  };
}

const fromPercentile = (p) =>
  p == null ? null : GRADING.percentileFloor + (p * (100 - GRADING.percentileFloor)) / 100;

function computeGrades() {
  const sponsorScore = percentileScorer((m) => (m.bills ? legislativePoints(m.bills) : null));
  const cosponsorScore = percentileScorer((m) => (m.bills ? m.bills.cosponsored : null));
  for (const m of members) {
    const v = m.votes;
    m.attendance = v.eligible ? 1 - v.missed / v.eligible : null;
    m.pctl = { sponsored: sponsorScore(m), cosponsored: cosponsorScore(m) };
    m.delegate = m.chamber === "House" && DELEGATE_STATES.has(m.state);
    m.partial = !m.delegate && v.eligible < v.chamberTotal * GRADING.partialTerm;
    m.scores = {
      attendance: m.attendance == null ? null
        : clamp(((m.attendance - GRADING.attendanceFloor) / (1 - GRADING.attendanceFloor)) * 100),
      sponsored: fromPercentile(m.pctl.sponsored),
      cosponsored: fromPercentile(m.pctl.cosponsored),
    };
    let total = 0, w = 0;
    for (const [k, s] of Object.entries(m.scores)) {
      if (s != null && weights[k] > 0) { total += s * weights[k]; w += weights[k]; }
    }
    m.score = w ? total / w : null;
    m.grade = m.score == null ? "—" : letterOf(m.score);
  }
}

// ------------------------------------------------------------------ weights UI
function loadWeights() {
  try {
    const saved = JSON.parse(localStorage.getItem("rc-weights"));
    if (saved && Object.keys(GRADING.weights).every((k) => typeof saved[k] === "number")) return saved;
  } catch {}
  return { ...GRADING.weights };
}
function saveWeights() {
  try { localStorage.setItem("rc-weights", JSON.stringify(weights)); } catch {}
}

function renderSliders() {
  const box = document.querySelector(".sliders");
  box.innerHTML = Object.keys(GRADING.weights).map((k) => {
    const disabled = k !== "attendance" && !data.hasBills;
    return `<div><label for="w-${k}"><span>${LABELS[k]}</span><span id="wv-${k}">${weights[k]}</span></label>
      <input type="range" id="w-${k}" data-k="${k}" min="0" max="100" step="5" value="${weights[k]}" ${disabled ? "disabled" : ""}></div>`;
  }).join("");
  box.querySelectorAll("input").forEach((el) => el.addEventListener("input", () => {
    weights[el.dataset.k] = Number(el.value);
    document.getElementById(`wv-${el.dataset.k}`).textContent = el.value;
    saveWeights(); computeGrades(); render();
  }));
}

// ------------------------------------------------------------------ list
const $ = (id) => document.getElementById(id);
let gradeFilter = "";

function photo(m, cls = "") {
  return `<img class="${cls}" src="https://unitedstates.github.io/images/congress/225x275/${m.id}.jpg" alt="" loading="lazy"
    onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'photo-fallback'}))">`;
}
function seat(m) {
  if (m.chamber === "Senate") return `Senator · ${m.state}`;
  if (DELEGATE_STATES.has(m.state)) return `Delegate · ${m.state}`;
  return m.district === 0 || m.district == null ? `Rep. · ${m.state} At-large` : `Rep. · ${m.state}-${m.district}`;
}
function filtered() {
  const q = $("q").value.trim().toLowerCase();
  const ch = $("chamber").value, st = $("state").value, pa = $("party").value;
  let list = members.filter((m) =>
    (!ch || m.chamber === ch) && (!st || m.state === st) && (!pa || m.party === pa) &&
    (!q || m.name.toLowerCase().includes(q) || m.state.toLowerCase() === q ||
      (STATES[m.state] || "").toLowerCase().includes(q)));
  const sorts = {
    grade: (a, b) => (b.score ?? -1) - (a.score ?? -1),
    "grade-asc": (a, b) => (a.score ?? 999) - (b.score ?? 999),
    "attendance-asc": (a, b) => (a.attendance ?? 2) - (b.attendance ?? 2),
    name: (a, b) => a.last.localeCompare(b.last),
  };
  const base = list.sort(sorts[$("sort").value]);
  return { base, shown: gradeFilter ? base.filter((m) => m.grade[0] === gradeFilter) : base };
}

function render() {
  const { base, shown } = filtered();
  // grade distribution for the current filters
  const counts = { A: 0, B: 0, C: 0, D: 0, F: 0 };
  base.forEach((m) => { if (counts[m.grade[0]] != null) counts[m.grade[0]]++; });
  const max = Math.max(1, ...Object.values(counts));
  $("summary").innerHTML = Object.entries(counts).map(([l, n]) =>
    `<button class="g-${l}" data-g="${l}" aria-pressed="${gradeFilter === l}" title="Show only ${l} grades">
      <span class="l">${l}</span><span class="n">${n} member${n === 1 ? "" : "s"}</span>
      <div class="bar" style="width:${(n / max) * 100}%"></div></button>`).join("");

  $("count").textContent = `${shown.length} of ${members.length} members` + (gradeFilter ? ` · showing ${gradeFilter} grades` : "");
  $("grid").innerHTML = shown.map((m) => `
    <button class="member" data-id="${m.id}">
      ${photo(m)}
      <div class="who">
        <div class="name">${esc(m.name)}</div>
        <div class="meta"><span class="party-${PARTY[m.party] || "I"}">${esc(m.party)}</span> · ${seat(m)}</div>
        <div class="meta">${m.attendance == null ? "No votes recorded" : `${pct(m.attendance)} of votes`}
          ${m.partial ? ' <span class="tag">Partial term</span>' : ""}</div>
      </div>
      <div class="grade g-${m.grade[0]}" aria-label="Grade ${m.grade}">${m.grade}</div>
    </button>`).join("");
}

// ------------------------------------------------------------------ detail card
function subject(k, m, detail, extra = "") {
  const s = m.scores[k];
  const l = s == null ? "—" : letterOf(s);
  return `<div class="subject g-${l[0]}">
    <h3>${LABELS[k]} <span class="tag">${weights[k]}% of grade</span></h3>
    <span class="sg">${l}</span>
    <div class="meter"><span style="width:${s ?? 0}%"></span></div>
    <div class="detail">${detail}</div>${extra}</div>`;
}

function openCard(id) {
  const m = members.find((x) => x.id === id);
  const v = m.votes, b = m.bills;
  const stageNames = { introduced: "Introduced", committee: "Committee action", passed: "Passed a chamber", law: "Became law" };
  const chamberWord = m.chamber === "Senate" ? "senators" : "representatives";
  const noBills = "Bill data not loaded. Run the data build with a Congress.gov API key.";

  const html = `
    <button class="close" aria-label="Close">×</button>
    <div class="card-head">
      ${photo(m)}
      <div>
        <h2 id="card-name">${esc(m.name)}</h2>
        <div class="meta"><span class="party-${PARTY[m.party] || "I"}">${esc(m.party)}</span> · ${seat(m)}</div>
        <div class="meta">${STATES[m.state] || m.state} · ${data.congress}th Congress
          ${m.partial ? ' · <span class="tag">Partial term</span>' : ""}</div>
      </div>
      <div class="grade g-${m.grade[0]}" aria-label="Overall grade ${m.grade}">${m.grade}</div>
    </div>
    <div class="subjects">
      ${subject("attendance", m, v.eligible
        ? `Voted on ${v.eligible - v.missed} of ${v.eligible} roll calls (${pct(m.attendance)}); missed ${v.missed}.`
        : "No roll-call votes recorded this Congress.")
        + (m.id === SPEAKER_ID ? " By custom the Speaker votes only occasionally; votes skipped as Speaker are not counted against them." : "")
        + (m.delegate ? " Delegates may vote only in the Committee of the Whole, so they are eligible for fewer roll calls." : "")}
      ${subject("sponsored", m, b
        ? `Sponsored ${b.sponsored} bill${b.sponsored === 1 ? "" : "s"} and joint resolutions, more legislative progress than ${Math.round(m.pctl.sponsored ?? 0)}% of ${chamberWord}.${b.resolutions ? ` (Also ${b.resolutions} simple resolution${b.resolutions === 1 ? "" : "s"}, not graded.)` : ""}`
        : noBills,
        b ? `<div class="stages">${Object.entries(stageNames).map(([k, n]) => `<div><b>${b.stages[k]}</b>${n}</div>`).join("")}</div>` : "")}
      ${subject("cosponsored", m, b
        ? `Cosponsored ${b.cosponsored} bills, more than ${Math.round(m.pctl.cosponsored ?? 0)}% of ${chamberWord}.`
        : noBills)}
    </div>
    ${b && b.notable.length ? `<div class="advanced"><h4>Bills that advanced</h4><ul class="notable">
      ${b.notable.map((n) => `<li><span class="tag">${stageNames[n.stage]}</span><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.id)}: ${esc(n.title)}</a></li>`).join("")}
    </ul></div>` : ""}
    <div class="card-links">
      <a href="https://www.congress.gov/member/${m.id}" target="_blank" rel="noopener">Full record on Congress.gov ↗</a>
      ${m.url ? `<a href="${esc(m.url)}" target="_blank" rel="noopener">Official website ↗</a>` : ""}
    </div>`;
  const dlg = $("card");
  dlg.querySelector(".card-body").innerHTML = html;
  dlg.querySelector(".close").onclick = () => dlg.close();
  dlg.showModal();
  history.replaceState(null, "", `#${m.id}`);
}

// ------------------------------------------------------------------ boot
function init() {
  $("congress-label").textContent = `${data.congress}th Congress · ${data.congress === 119 ? "2025–2027" : ""}`;
  $("generated").textContent = `Updated ${data.generated}.`;
  if (!data.hasBills) {
    $("notice").hidden = false;
    $("notice").innerHTML = "<strong>Grades currently reflect vote attendance only.</strong> Bill data hasn't been loaded yet. See the README to add a free Congress.gov API key.";
  }
  const states = [...new Set(members.map((m) => m.state))].sort((a, b) => (STATES[a] || a).localeCompare(STATES[b] || b));
  $("state").innerHTML += states.map((s) => `<option value="${s}">${STATES[s] || s}</option>`).join("");

  ["q", "chamber", "state", "party", "sort"].forEach((id) => $(id).addEventListener("input", render));
  $("summary").addEventListener("click", (e) => {
    const g = e.target.closest("button")?.dataset.g;
    if (g) { gradeFilter = gradeFilter === g ? "" : g; render(); }
  });
  $("grid").addEventListener("click", (e) => {
    const card = e.target.closest(".member");
    if (card) openCard(card.dataset.id);
  });
  const dlg = $("card");
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener("close", () => history.replaceState(null, "", location.pathname));

  $("weights-btn").addEventListener("click", () => {
    const box = $("weights"), open = box.hidden;
    box.hidden = !open;
    $("weights-btn").setAttribute("aria-expanded", open);
  });
  $("reset-weights").addEventListener("click", () => {
    weights = { ...GRADING.weights }; saveWeights(); renderSliders(); computeGrades(); render();
  });

  renderSliders();
  computeGrades();
  render();
  const hash = location.hash.slice(1);
  if (hash && members.some((m) => m.id === hash)) openCard(hash);
}
init();
