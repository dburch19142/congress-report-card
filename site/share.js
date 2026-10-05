// Member pages: draws the shareable image cards and wires up the share and embed buttons.
// The card's contents come from the data-card attribute written by build_pages.py.
(function () {
  const box = document.getElementById("share");
  if (!box) return;
  const d = JSON.parse(box.dataset.card);
  const $ = (id) => document.getElementById(id);

  const INK = "#1c1f24", MUTED = "#5d6470", LINE = "#e2dfd6", BG = "#f7f6f2", ACCENT = "#1f3a5f";
  const GRADE = { A: "#1d7a4b", B: "#4f8a2c", C: "#b58a12", D: "#c4631c", F: "#b3372f" };
  const PARTY = { Democrat: "#2f5fa7", Republican: "#b3372f" };
  const SANS = '"Segoe UI", system-ui, -apple-system, sans-serif';
  const SERIF = 'Georgia, "Times New Roman", serif';
  const gradeColor = (letter) => GRADE[letter[0]] || MUTED;

  // The photo is on another site. If it can't be loaded for drawing, the card goes without it.
  function loadPhoto() {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      setTimeout(() => resolve(null), 4000);
      img.src = d.photo;
    });
  }

  function canvasOf(w, h, inset, radius) {
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    const c = canvas.getContext("2d");
    c.fillStyle = BG; c.fillRect(0, 0, w, h);
    c.fillStyle = "#fff"; c.strokeStyle = LINE; c.lineWidth = 2;
    c.beginPath(); c.roundRect(inset.x, inset.y, w - inset.x * 2, inset.h ?? h - inset.y * 2, radius); c.fill(); c.stroke();
    c.textBaseline = "alphabetic";
    return [canvas, c];
  }

  // Sets the largest font from `size` down to `min` at which the text fits in `room`.
  function fit(c, text, size, min, room, font) {
    do { c.font = font(size); size -= 2; } while (c.measureText(text).width > room && size > min);
  }

  // Wide card (1200×630) for link previews, X, Facebook and messages.
  function drawWide(photo) {
    const W = 1200, H = 630;
    const [canvas, c] = canvasOf(W, H, { x: 40, y: 40 }, 24);

    c.fillStyle = MUTED; c.font = `600 22px ${SANS}`;
    c.fillText(`CONGRESS REPORT CARD  ·  ${d.congress.toUpperCase()}`, 90, 110);

    let x = 90;
    if (photo) {
      c.save();
      c.beginPath(); c.roundRect(90, 145, 150, 184, 12); c.clip();
      c.drawImage(photo, 90, 145, 150, 184);
      c.restore();
      x = 275;
    }

    // Name, shrunk until it fits beside the grade
    fit(c, d.name, 60, 30, 880 - x, (s) => `700 ${s}px ${SERIF}`);
    c.fillStyle = INK; c.fillText(d.name, x, 225);
    c.font = `600 30px ${SANS}`;
    c.fillStyle = PARTY[d.party] || "#6b5a9a"; c.fillText(d.party, x, 278);
    const partyWidth = c.measureText(d.party).width;
    c.fillStyle = MUTED; c.font = `30px ${SANS}`; c.fillText(`  ·  ${d.seat}`, x + partyWidth, 278);

    // Overall grade
    const color = gradeColor(d.grade);
    c.strokeStyle = color; c.lineWidth = 8;
    c.beginPath(); c.arc(1005, 235, 95, 0, Math.PI * 2); c.stroke();
    c.fillStyle = color; c.font = `700 104px ${SERIF}`; c.textAlign = "center";
    c.fillText(d.grade, 1005, 271);
    c.textAlign = "left";

    // The three scores
    d.scores.forEach((s, i) => {
      const y = 395 + i * 50, col = gradeColor(s.letter);
      c.fillStyle = INK; c.font = `600 24px ${SANS}`; c.fillText(s.label, 90, y + 8);
      c.fillStyle = LINE; c.beginPath(); c.roundRect(320, y - 8, 700, 16, 8); c.fill();
      if (s.score > 0) { c.fillStyle = col; c.beginPath(); c.roundRect(320, y - 8, Math.max(16, 7 * s.score), 16, 8); c.fill(); }
      c.fillStyle = col; c.font = `700 30px ${SERIF}`; c.textAlign = "right"; c.fillText(s.letter, 1110, y + 10);
      c.textAlign = "left";
    });

    c.fillStyle = ACCENT; c.font = `600 22px ${SANS}`; c.fillText("congressreportcard.org", 90, 560);
    return canvas;
  }

  // Tall card (1080×1920) for TikTok, Reels and Stories. Everything sits in the middle of the
  // frame: those apps cover the top, the bottom and the right edge with their own buttons.
  function drawTall(photo) {
    const W = 1080, H = 1920, mid = 480; // content is centred left of the apps' right-hand buttons
    const [canvas, c] = canvasOf(W, H, { x: 60, y: 230, h: 1340 }, 36);
    c.textAlign = "center";

    c.fillStyle = MUTED; c.font = `600 30px ${SANS}`;
    c.fillText(`CONGRESS REPORT CARD  ·  ${d.congress.toUpperCase()}`, mid, 320);

    let y = 380;
    if (photo) {
      c.save();
      c.beginPath(); c.roundRect(mid - 130, y, 260, 318, 18); c.clip();
      c.drawImage(photo, mid - 130, y, 260, 318);
      c.restore();
      y += 318;
    }

    fit(c, d.name, 76, 40, 780, (s) => `700 ${s}px ${SERIF}`);
    c.fillStyle = INK; c.fillText(d.name, mid, y + 95);
    c.font = `600 38px ${SANS}`;
    const party = d.party, rest = `  ·  ${d.seat}`;
    const partyWidth = c.measureText(party).width;
    c.font = `38px ${SANS}`;
    const start = mid - (partyWidth + c.measureText(rest).width) / 2;
    c.textAlign = "left";
    c.font = `600 38px ${SANS}`; c.fillStyle = PARTY[d.party] || "#6b5a9a"; c.fillText(party, start, y + 160);
    c.font = `38px ${SANS}`; c.fillStyle = MUTED; c.fillText(rest, start + partyWidth, y + 160);

    // Overall grade
    const color = gradeColor(d.grade), gy = photo ? 1030 : 800;
    c.strokeStyle = color; c.lineWidth = 12;
    c.beginPath(); c.arc(mid, gy, 125, 0, Math.PI * 2); c.stroke();
    c.fillStyle = color; c.font = `700 140px ${SERIF}`; c.textAlign = "center";
    c.fillText(d.grade, mid, gy + 48);

    // The three scores
    d.scores.forEach((s, i) => {
      const sy = 1225 + i * 70, col = gradeColor(s.letter);
      c.textAlign = "left";
      c.fillStyle = INK; c.font = `600 32px ${SANS}`; c.fillText(s.label, 110, sy + 11);
      c.fillStyle = LINE; c.beginPath(); c.roundRect(390, sy - 10, 400, 20, 10); c.fill();
      if (s.score > 0) { c.fillStyle = col; c.beginPath(); c.roundRect(390, sy - 10, Math.max(20, 4 * s.score), 20, 10); c.fill(); }
      c.fillStyle = col; c.font = `700 40px ${SERIF}`; c.textAlign = "right"; c.fillText(s.letter, 880, sy + 14);
    });

    c.textAlign = "center";
    c.fillStyle = INK; c.font = `700 40px ${SERIF}`; c.fillText("How did your representative score?", mid, 1465);
    c.fillStyle = ACCENT; c.font = `600 32px ${SANS}`; c.fillText("congressreportcard.org", mid, 1525);
    return canvas;
  }

  const DRAW = { wide: drawWide, tall: drawTall };
  const cards = {};
  function card(kind = "wide") {
    return (cards[kind] ??= (async () => {
      const toBlob = (canvas) => new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      let blob = null;
      try { blob = await toBlob(DRAW[kind](await loadPhoto())); } catch {}
      return blob ?? toBlob(DRAW[kind](null)); // the photo made the canvas unreadable; redraw without it
    })());
  }
  const slug = d.name.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase();
  const fileName = (kind) => `${slug}-report-card${kind === "tall" ? "-tall" : ""}.png`;

  function flash(button, text) {
    const old = button.textContent;
    button.textContent = text;
    setTimeout(() => { button.textContent = old; }, 1800);
  }
  async function copy(button, text) {
    try { await navigator.clipboard.writeText(text); flash(button, "Copied"); }
    catch { flash(button, "Couldn't copy"); }
  }
  async function download(kind) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await card(kind));
    a.download = fileName(kind);
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  card().then((blob) => {
    const img = $("share-preview");
    img.src = URL.createObjectURL(blob);
    img.hidden = false;
  });

  $("share-download").addEventListener("click", () => download("wide"));
  $("share-download-tall").addEventListener("click", () => download("tall"));
  $("share-copy").addEventListener("click", (e) => copy(e.currentTarget, d.url));
  $("embed-copy").addEventListener("click", (e) => copy(e.currentTarget, $("embed-code").value));
  $("embed-code").addEventListener("focus", (e) => e.currentTarget.select());

  // Phones and some desktop browsers can hand the image straight to another app.
  if (navigator.share) {
    const native = $("share-native");
    native.hidden = false;
    native.addEventListener("click", async () => {
      const text = `${d.name} gets a grade of ${d.grade} on Congress Report Card`;
      const file = new File([await card()], fileName("wide"), { type: "image/png" });
      const withImage = { files: [file], title: document.title, text, url: d.url };
      try {
        await navigator.share(navigator.canShare?.(withImage) ? withImage : { title: document.title, text, url: d.url });
      } catch {} // the visitor closed the share sheet
    });
  }
})();
