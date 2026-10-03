// Visitor counts by GoatCounter (https://www.goatcounter.com). It uses no cookies and stores
// nothing that identifies a visitor. Put the site code between the quotes: it is the first
// part of the dashboard address, e.g. "congressreportcard" for congressreportcard.goatcounter.com.
//
// While it is empty, nothing is counted and no outside script loads.
const GOATCOUNTER_CODE = "congressreportcard";

if (GOATCOUNTER_CODE) {
  const s = document.createElement("script");
  s.async = true;
  s.dataset.goatcounter = `https://${GOATCOUNTER_CODE}.goatcounter.com/count`;
  s.src = "https://gc.zgo.at/count.js";
  document.head.append(s);
}
