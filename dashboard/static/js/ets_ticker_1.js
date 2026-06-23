(() => {
  const track = document.getElementById("etsTickerTrack");
  if (!track) return;

  // ✅ ETS 시세 데이터 (배출권 거래소 시뮬레이션)
  const items = [
    { sym: "KAU25", price: 13250, chgPct: +6.9, cur: "KRW" },     // 한국 배출권
    { sym: "EUA",   price: 72.8,  chgPct: -1.2, cur: "EUR" },     // 유럽 배출권
    { sym: "UKA",   price: 41.8,  chgPct: +0.4, cur: "GBP" },     // 영국 배출권
    { sym: "CCA",   price: 42.0,  chgPct: +0.1, cur: "USD" },     // 캐나다 배출권
    { sym: "RGGI",  price: 25.75, chgPct: +0.3, cur: "USD" },     // 미국 배출권
    { sym: "NZU",   price: 55.0,  chgPct: -0.2, cur: "NZD" },     // 뉴질랜드 배출권
  ];

  const fmt = (n) => {
    const v = Number(n);
    if (!Number.isFinite(v)) return "-";
    return v >= 100 ? v.toLocaleString() : v.toFixed(2);
  };

  function pillHTML(it) {
    const up = Number(it.chgPct) >= 0;
    return `
      <span class="ets-pill">
        <span class="ets-sym">${it.sym}</span>
        <span class="ets-price">${fmt(it.price)} <span style="opacity:.65">${it.cur}</span></span>
        <span class="ets-chg ${up ? "ets-up" : "ets-dn"}">
          ${up ? "▲" : "▼"} ${Math.abs(Number(it.chgPct)).toFixed(1)}%
        </span>
      </span>
    `;
  }

  // ✅ 무한 스크롤을 위해 2번 붙여서 길이 2배 만들기
  function render() {
    track.innerHTML = "";
    const html = items.map(pillHTML).join("");
    track.insertAdjacentHTML("beforeend", html + html);
  }

  render();
})();
