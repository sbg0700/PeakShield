// static/js/kau25_monthly_chart.js
(() => {
  let chart = null;
  let rafId = null; // ✅ 추가 (RAF 루프 중복/정지 방지)

const $id = (...ids) => {
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) return el;
  }
  return null;
};

    // --- 마지막 포인트 TradingView 스타일 리플(펄스) ---
    const LastPointPulse = {
      id: "lastPointPulse",
      afterDatasetsDraw(chart, args, pluginOptions) {
        const { ctx } = chart;
        const datasetIndex = pluginOptions?.datasetIndex ?? 0;
        const color = pluginOptions?.color ?? "#00e5ff";
        const ringColor = pluginOptions?.ringColor ?? "rgba(0,229,255,0.35)";
        const minR = pluginOptions?.minRadius ?? 3;
        const maxR = pluginOptions?.maxRadius ?? 16;
        const speed = pluginOptions?.speed ?? 1200; // ms

        const meta = chart.getDatasetMeta(datasetIndex);
        if (!meta || !meta.data || meta.data.length === 0) return;

        // 마지막 유효 포인트(값이 null이면 뒤에서부터 찾기)
        const dataArr = chart.data.datasets[datasetIndex]?.data ?? [];
        let lastIdx = dataArr.length - 1;
        while (lastIdx >= 0 && (dataArr[lastIdx] == null || Number.isNaN(Number(dataArr[lastIdx])))) lastIdx--;
        if (lastIdx < 0) return;

        const pt = meta.data[lastIdx];
        if (!pt) return;

        const x = pt.x;
        const y = pt.y;

        // 시간 기반 펄스(0~1)
        const t = (Date.now() % speed) / speed;
        const ease = t * (2 - t); // easeOutQuad
        const r = minR + (maxR - minR) * ease;
        const alpha = 1 - t;

        ctx.save();

        // 1) 중심 점(선명)
        ctx.beginPath();
        ctx.fillStyle = color;
        ctx.arc(x, y, minR + 1, 0, Math.PI * 2);
        ctx.fill();

        // 2) 바깥 리플 링(커졌다가 사라짐)
        ctx.beginPath();
        ctx.strokeStyle = ringColor.replace(/[\d.]+\)$/g, `${(0.35 * alpha).toFixed(3)})`); // alpha 반영
        ctx.lineWidth = 2;
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.stroke();

        // 3) 살짝 글로우(선택)
        ctx.beginPath();
        ctx.fillStyle = `rgba(0,229,255,${(0.10 * alpha).toFixed(3)})`;
        ctx.arc(x, y, r * 0.65, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }
    };



  function isLightTheme() {
    return document.documentElement.getAttribute("data-theme") === "light";
  }

  function theme() {
    const light = isLightTheme();
    return {
      tick: light ? "rgba(15,23,42,0.65)" : "rgba(156,163,175,0.80)",
      grid: light ? "rgba(15,23,42,0.10)" : "rgba(255,255,255,0.06)",
      tooltipBg: light ? "rgba(255,255,255,0.96)" : "rgba(0,0,0,0.85)",
      tooltipText: light ? "rgba(15,23,42,0.92)" : "rgba(235,245,255,0.90)",
      tooltipBorder: light ? "rgba(15,23,42,0.12)" : "rgba(255,255,255,0.12)",
    };
  }

  function fmt(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "-";
    return v.toLocaleString();
  }

  function fmtPct(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
  }

  async function fetchMonthly() {
    const res = await fetch("/api/kau25-monthly");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json(); // {labels:[], closes:[]}
  }

  // =============================
  // ETS Ticker (hardcoded + KAU25 sync)
  // =============================
  const TICKER_ITEMS = [
    { sym: "EUA",  price: 72.80, chgPct: -1.2, cur: "EUR" },
    { sym: "UKA",  price: 41.80, chgPct: +0.4, cur: "GBP" },
    { sym: "CCA",  price: 42.00, chgPct: +0.1, cur: "USD" },
    { sym: "RGGI", price: 25.75, chgPct: +0.3, cur: "USD" },
    { sym: "NZU",  price: 55.00, chgPct: -0.2, cur: "NZD" },
  ];

  function fmtTickerPx(n){
    const v = Number(n);
    if (!Number.isFinite(v)) return "-";
    return v >= 100 ? v.toLocaleString() : v.toFixed(2);
  }

  function renderTicker(extraKAU25) {
    const track = document.getElementById("etsTickerTrack");
    if (!track) return;

    // KAU25를 맨 앞에
    const items = [
      extraKAU25 || { sym:"KAU25", price: 13250, chgPct: +0.0, cur:"KRW" },
      ...TICKER_ITEMS
    ];

    const pill = (it) => {
      const chg = Number(it.chgPct);
      const cls = chg > 0 ? "krx-up" : chg < 0 ? "krx-dn" : "krx-flat";
      const arrow = chg > 0 ? "▲" : chg < 0 ? "▼" : "•";
      return `
        <span class="krx-pill">
          <span class="krx-sym">${it.sym}</span>
          <span class="krx-px">${fmtTickerPx(it.price)} <span style="opacity:.65">${it.cur}</span></span>
          <span class="krx-chg ${cls}">${arrow} ${Math.abs(chg).toFixed(1)}%</span>
          <span class="krx-dot"></span>
        </span>
      `;
    };

    // ✅ 애니메이션이 "눈에 띄게" 되려면 길이가 충분해야 함 → 2배 복제
    const html = items.map(pill).join("");
    track.innerHTML = html + html;
  }



  function updateMiniKpis(closes) {
    const priceEl = document.getElementById("kau25BoardPrice");
    const changeEl = document.getElementById("kau25BoardChange");
    const momEl = document.getElementById("kau25MoM");

    if (!Array.isArray(closes) || closes.length === 0) {
      if (priceEl) priceEl.textContent = "-";
      if (changeEl) changeEl.textContent = "-";
      if (momEl) momEl.textContent = "-";
      renderTicker(null);
      return;
    }

    // 마지막 유효 값
    let i = closes.length - 1;
    while (i >= 0 && (closes[i] == null || Number.isNaN(Number(closes[i])))) i--;
    if (i < 0) {
      if (priceEl) priceEl.textContent = "-";
      if (changeEl) changeEl.textContent = "-";
      if (momEl) momEl.textContent = "-";
      renderTicker(null);
      return;
    }

    const lastClose = Number(closes[i]);

    // 전월 유효 값
    let j = i - 1;
    while (j >= 0 && (closes[j] == null || Number.isNaN(Number(closes[j])))) j--;

    let mom = null;
    if (j >= 0) {
      const prev = Number(closes[j]);
      mom = prev ? ((lastClose - prev) / prev) * 100 : null;
    }

    // ✅ 상단 보드 반영
    if (priceEl) priceEl.textContent = lastClose.toLocaleString();

    const momText =
      (mom == null || !Number.isFinite(mom))
        ? "-"
        : `${mom >= 0 ? "▲" : "▼"} ${Math.abs(mom).toFixed(1)}% MoM`;

    if (changeEl) {

      const isDown = mom != null && Number.isFinite(mom) && mom < 0;

      // 텍스트 부분만 표시
      changeEl.innerHTML = `
        <span class="krx-tri-spin"></span>
        <span class="krx-mom-text">
          ${mom == null || !Number.isFinite(mom)
            ? "-"
            : `${Math.abs(mom).toFixed(1)}% MoM`}
        </span>
      `;

      // 배경/색상 토글
      changeEl.className =
        "krx-mom text-sm font-black px-2 py-1 rounded-xl border tabular-nums " +
        (isDown
          ? "bg-blue-500/12 text-blue-200 border-blue-500/20 is-down"
          : "bg-red-600/10 text-red-200 border-red-600/25");
    }

    if (momEl) {
      momEl.textContent = (mom == null || !Number.isFinite(mom))
        ? "-"
        : `전월 대비 ${mom >= 0 ? "+" : ""}${mom.toFixed(1)}%`;
    }

    // ✅ 티커도 같이 갱신 (KAU25만 실데이터로 동기화)
    renderTicker({ sym:"KAU25", price:lastClose, chgPct: mom ?? 0, cur:"KRW" });
  }

  function draw(labels, closes) {
    const canvas = document.getElementById("kau25MonthlyClose");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (chart) chart.destroy();

    const t = theme();

    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels, // "2025/02" ~ "2026/02"
        datasets: [{
          label: "KAU25 월봉 종가",
          data: closes,
          borderWidth: 2,
          tension: 0.35,
          pointRadius: 0,
          pointHoverRadius: 4,
          hitRadius: 10,         // hover 잡히는 영역
          borderColor: "#00e5ff",
          pointBackgroundColor: "#00e5ff",
          fill: true,
          backgroundColor: "rgba(0,229,255,0.08)",
          // 원하면 null 구간 이어그리기
          // spanGaps: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,

        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.tooltipBg,
            borderColor: t.tooltipBorder,
            borderWidth: 1,
            titleColor: t.tooltipText,
            bodyColor: t.tooltipText,
            displayColors: false,
            padding: 10,
            callbacks: {
              title: (items) =>
                `#${(items?.[0]?.dataIndex ?? 0) + 1} (${labels?.[items?.[0]?.dataIndex ?? 0] ?? ""})`,
              label: (c) => `종가: ${fmt(c.raw)}원`
            }
          },

          // ✅ 우리가 만든 플러그인 옵션은 여기!
          lastPointPulse: {
            datasetIndex: 0,
            color: "#00e5ff",
            ringColor: "rgba(0,229,255,0.35)",
            minRadius: 3,
            maxRadius: 16,
            speed: 1200
          }
        },

        scales: {
          x: { ticks: { color: t.tick, maxRotation: 0 }, grid: { display: false } },
          y: { ticks: { color: t.tick, callback: v => fmt(v) }, grid: { color: t.grid }, grace: "10%" }
        }
      },

      // ✅ 플러그인 등록은 options 밖!
      plugins: [LastPointPulse],
    });



// ✅ 리플 애니메이션 루프 (중복 방지 + 확정 동작)
if (rafId) cancelAnimationFrame(rafId);

const tick = () => {
  if (!chart) return;
  chart.update("none"); // ✅ 매 프레임 플러그인 훅 실행
  rafId = requestAnimationFrame(tick);
};

rafId = requestAnimationFrame(tick);
updateMiniKpis(closes);
  }

  function applyTheme() {
    if (!chart) return;
    const t = theme();
    chart.options.scales.x.ticks.color = t.tick;
    chart.options.scales.y.ticks.color = t.tick;
    chart.options.scales.y.grid.color = t.grid;
    chart.options.plugins.tooltip.backgroundColor = t.tooltipBg;
    chart.options.plugins.tooltip.borderColor = t.tooltipBorder;
    chart.options.plugins.tooltip.titleColor = t.tooltipText;
    chart.options.plugins.tooltip.bodyColor = t.tooltipText;
    // (선택) 테마에 맞춰 펄스 링 톤 조정
    if (chart.options?.plugins?.lastPointPulse) {
      chart.options.plugins.lastPointPulse.ringColor = isLightTheme()
        ? "rgba(0,229,255,0.25)"
        : "rgba(0,229,255,0.35)";
    }

    chart.update();
  }

  async function init() {
    try {
      const data = await fetchMonthly();
      draw(data.labels || [], data.closes || []);
    } catch (e) {
      // 필요하면 콘솔만
      console.error("KAU25 API 호출 실패:", e);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
  window.addEventListener("themechange", applyTheme); // 너희 테마 토글과 동일 이벤트 사용


(function etsClock(){
  const el = document.getElementById("etsNowTime");
  if (!el) return;

  const fmt = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });

  function tick(){
    el.textContent = fmt.format(new Date());
  }

  tick();
  setInterval(tick, 1000);

})();

})();
