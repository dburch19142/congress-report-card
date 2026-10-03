// Google AdSense. Once AdSense approves the site, paste the publisher ID between the quotes
// (it looks like "ca-pub-1234567890123456"). That one change turns ads on for every page and
// makes the next deploy publish ads.txt.
//
// While it is empty, no ad code loads and the site sets no cookies.
//
// The cookie-consent message for visitors in Europe is shown by this same Google script. Turn
// it on in AdSense under Privacy & messaging → European regulations. Google only serves ads in
// Europe through a consent tool it has certified, so a home-made banner would not count.
const ADSENSE_CLIENT = "";

if (ADSENSE_CLIENT) {
  const s = document.createElement("script");
  s.async = true;
  s.crossOrigin = "anonymous";
  s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`;
  document.head.append(s);
}
