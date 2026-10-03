// Member pages: draws the shareable image card and wires up the share and embed buttons.
// The card's contents come from the data-card attribute written by build_pages.py.
(function () {
  const box = document.getElementById("share");
  if (!box) return;
  const d = JSON.parse(box.dataset.card);
  const $ = (id) => document.getElementById(id);

  const W = 1200, H = 630;
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

  function draw(photo) {
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    const c = canvas.getContext("2d");
    c.fillStyle = BG; c.fillRect(0, 0, W, H);
    c.fillStyle = "#fff"; c.strokeStyle = LINE; c.lineWidth = 2;
    c.beginPath(); c.roundRect(40, 40, W - 80, H - 80, 24); c.fill(); c.stroke();

    c.textBaseline = "alphabetic";
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
    const room = 880 - x;
    let size = 60;
    do { c.font = `700 ${size}px ${SERIF}`; size -= 2; } while (c.measureText(d.name).width > room && size > 30);
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

  let cardBlob = null;
  async function card() {
    if (cardBlob) return cardBlob;
    const toBlob = (canvas) => new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    try {
      cardBlob = await toBlob(draw(await loadPhoto()));
    } catch {
      cardBlob = null;
    }
    cardBlob ??= await toBlob(draw(null)); // the photo made the canvas unreadable; redraw without it
    return cardBlob;
  }
  const fileName = `${d.name.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase()}-report-card.png`;

  function flash(button, text) {
    const old = button.textContent;
    button.textContent = text;
    setTimeout(() => { button.textContent = old; }, 1800);
  }
  async function copy(button, text) {
    try { await navigator.clipboard.writeText(text); flash(button, "Copied"); }
    catch { flash(button, "Couldn't copy"); }
  }

  card().then((blob) => {
    const img = $("share-preview");
    img.src = URL.createObjectURL(blob);
    img.hidden = false;
  });

  $("share-download").addEventListener("click", async () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await card());
    a.download = fileName;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  $("share-copy").addEventListener("click", (e) => copy(e.currentTarget, d.url));
  $("embed-copy").addEventListener("click", (e) => copy(e.currentTarget, $("embed-code").value));
  $("embed-code").addEventListener("focus", (e) => e.currentTarget.select());

  // Phones and some desktop browsers can hand the image straight to another app.
  if (navigator.share) {
    const native = $("share-native");
    native.hidden = false;
    native.addEventListener("click", async () => {
      const text = `${d.name} gets a grade of ${d.grade} on Congress Report Card`;
      const file = new File([await card()], fileName, { type: "image/png" });
      const withImage = { files: [file], title: document.title, text, url: d.url };
      try {
        await navigator.share(navigator.canShare?.(withImage) ? withImage : { title: document.title, text, url: d.url });
      } catch {} // the visitor closed the share sheet
    });
  }
})();
