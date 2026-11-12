/* Paradise Patrimoine – mesure d'audience anonyme, sans cookie.
   Compte une visite par session avec sa provenance (Google, réseaux sociaux, accès direct…) et les annonces
   consultées. Seuls des totaux par jour sont envoyés à un compteur public (abacus.jasoncameron.dev, espace
   « paradisepatrimoine-gh ») ; outils/statistiques.py les recopie chaque nuit dans stats/historique.json,
   lu par l'onglet « Statistiques » de l'espace privé. Les visites du propriétaire (navigateur où l'espace
   privé a été ouvert, ou adresse avec ?nostats=1) ne sont pas comptées. */
(function () {
  var NS = "paradisepatrimoine-gh", HIT = "https://abacus.jasoncameron.dev/hit/" + NS + "/";
  var off = !/^https:$/.test(location.protocol);
  try {
    if (/[?&]nostats=1(&|$)/.test(location.search)) localStorage.setItem("pp_nostats", "1");
    if (localStorage.getItem("pp_nostats") === "1") off = true;
  } catch (e) {}
  if (navigator.webdriver || /bot|crawl|spider|slurp|headless|lighthouse|facebookexternalhit|preview|inspection/i.test(navigator.userAgent || "")) off = true;

  function day() {
    try { return new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris" }).format(new Date()).replace(/\D/g, ""); }
    catch (e) { var d = new Date(); return "" + d.getFullYear() + ("0" + (d.getMonth() + 1)).slice(-2) + ("0" + d.getDate()).slice(-2); }
  }
  function hit(key) {
    if (off) return;
    try { fetch(HIT + key, { mode: "no-cors", credentials: "omit", keepalive: true, cache: "no-store" }).catch(function () {}); }
    catch (e) { try { new Image().src = HIT + key; } catch (_) {} }
  }
  function once(flag) {
    try { if (sessionStorage.getItem(flag)) return false; sessionStorage.setItem(flag, "1"); } catch (e) {}
    return true;
  }
  var KNOWN = { google: "google", facebook: "facebook", fb: "facebook", instagram: "instagram", ig: "instagram",
    tiktok: "tiktok", tt: "tiktok", youtube: "youtube", yt: "youtube", linkedin: "linkedin", leboncoin: "leboncoin" };
  function source() {
    var m = /[?&](?:src|utm_source)=([^&#]+)/i.exec(location.search);
    if (m) { var s = ""; try { s = decodeURIComponent(m[1]).toLowerCase(); } catch (e) {} return KNOWN[s] || "autres"; }
    var h = "";
    try { h = new URL(document.referrer).hostname.toLowerCase(); } catch (e) {}
    if (!h) return "direct";
    if (h === location.hostname) return null;                       // navigation à l'intérieur du site
    if (/(^|\.)google\.|googlequicksearchbox/.test(h)) return "google";
    if (/(^|\.)(bing|qwant|duckduckgo|ecosia|yahoo|yandex|startpage|lilo|brave)\./.test(h)) return "moteurs";
    if (/(^|\.)(facebook\.com|fb\.com|fb\.me|fb\.watch|messenger\.com)$/.test(h)) return "facebook";
    if (/(^|\.)instagram\.com$/.test(h)) return "instagram";
    if (/(^|\.)tiktok\.com$/.test(h)) return "tiktok";
    if (/(^|\.)(youtube\.com|youtu\.be)$/.test(h)) return "youtube";
    if (/(^|\.)(linkedin\.com|lnkd\.in)$/.test(h)) return "linkedin";
    if (/(^|\.)leboncoin\.fr$/.test(h)) return "leboncoin";
    return "autres";
  }
  var s = source();
  if (s && once("pp-st")) { var d = day(); hit(d + "-v"); hit(d + "-s-" + s); }
  window.PPStat = {
    view: function (id) {
      id = String(id || "").replace(/[^A-Za-z0-9_.-]/g, "").slice(0, 50);
      if (id && once("pp-sa-" + id)) hit(day() + "-a-" + id);
    }
  };
  var me = document.currentScript, a = me && me.getAttribute("data-annonce");
  if (a) window.PPStat.view(a);
})();
