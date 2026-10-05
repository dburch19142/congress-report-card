// Fixed ad slots. Each page marks where an ad may go with <div class="ad-slot" data-ad="…">.
// A slot stays empty and takes no space until its ad unit ID is filled in below.
//
// To get an ID: in AdSense open Ads → By ad unit → Display ads, create a responsive unit and
// copy the number after data-ad-slot= in its code. One unit can be used for all three, or make
// one per placement to see in AdSense which placement earns what.
const AD_CLIENT = "ca-pub-7873162278456307";
const AD_SLOTS = {
  home: "",    // home page, between the grade summary and the list of members
  member: "",  // member pages, between the scores and the share buttons
  page: "",    // end of the methodology page and the weekly digest
};

for (const box of document.querySelectorAll(".ad-slot")) {
  const slot = AD_SLOTS[box.dataset.ad];
  if (!slot) continue;
  box.innerHTML = `<span class="ad-label">Advertisement</span>
    <ins class="adsbygoogle" style="display:block" data-ad-client="${AD_CLIENT}" data-ad-slot="${slot}"
      data-ad-format="${box.dataset.format || "auto"}" data-full-width-responsive="true"></ins>`;
  box.classList.add("on");
  (window.adsbygoogle = window.adsbygoogle || []).push({});
}
