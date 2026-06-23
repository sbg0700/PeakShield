// static/js/monthly_cost_charts_1.js
// ✅ 월별 전기료 추이: 캡슐 바 + 상단 축약 라벨 + 상단 링
// ✅ (단위: ...)는 캔버스 아래 DOM으로 고정(리사이즈해도 안 튐)
// ✅ 라이트/다크 테마 전환 시 축/그리드/툴팁/단위 색 자동 동기화

(() => {
  // -----------------------------
  // 0) Data & 변수 선언 (중복 선언 방지 통합)
  // -----------------------------
  
  // 백엔드 데이터 우선 로드
  const humanCosts = Array.isArray(window.MONTHLY_HUMAN_DATA) ? window.MONTHLY_HUMAN_DATA : [0,0,0,0,0,0,0,0,0,0,0,0];
  const aiCosts = Array.isArray(window.MONTHLY_AI_DATA) ? window.MONTHLY_AI_DATA : [0,0,0,0,0,0,0,0,0,0,0,0];

  const monthLabels = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];
  const highlightIndex = new Date().getMonth(); 

  const forecast = { 
    before: humanCosts[highlightIndex] || 0, 
    after: aiCosts[highlightIndex] || 0 
  };

  // -----------------------------
  // 1) Helper Functions (내부 함수 선언)
  // -----------------------------
  function isLightTheme() { return document.documentElement.getAttribute("data-theme") === "light"; }
  function axisText() { return isLightTheme() ? "rgba(15,23,42,0.78)" : "rgba(235,245,255,0.72)"; }
  function axisGrid() { return isLightTheme() ? "rgba(15,23,42,0.10)" : "rgba(255,255,255,0.08)"; }
  function tooltipNow() {
    const light = isLightTheme();
    return {
      backgroundColor: light ? "rgba(255,255,255,0.96)" : "rgba(10,12,18,0.96)",
      borderColor: light ? "rgba(15,23,42,0.12)" : "rgba(255,255,255,0.12)",
      borderWidth: 1, padding: 12,
      titleColor: light ? "rgba(15,23,42,0.92)" : "rgba(235,245,255,0.90)",
      bodyColor: light ? "rgba(15,23,42,0.92)" : "rgba(235,245,255,0.90)",
      displayColors: true
    };
  }
  function unitTextColor() { return isLightTheme() ? "rgba(15,23,42,0.55)" : "rgba(235,245,255,0.55)"; }
  function fmtWon(v) { return Number(v).toLocaleString("ko-KR"); }
  
  function formatCompactWon(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return String(n);
    const abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
    return (v / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  }

  function getUnitCaption(maxVal) {
    const abs = Math.abs(Number(maxVal));
    if (abs >= 1e9) return "(단위: B원 = 10억)";
    return "(단위: M원 = 100만)";
  }

  // 🚨 [필수 확인] 아래 변수들은 이 위치에서 한 번만 선언되어야 합니다.
  const maxMonthly = Math.max(...humanCosts, ...aiCosts, 1);
  const unitCaption = getUnitCaption(maxMonthly);

  // -----------------------------
  // 2) Plugin: 상단 라벨 + 링 (데이터셋 0번 기준 유지)
  // -----------------------------
  const CapsuleTopLabelPlugin = {
    id: "capsuleTopLabelPlugin",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      // 최적화 이후(데이터셋 1번) 위에 수치 표시
      const meta = chart.getDatasetMeta(1); 
      if (!meta || chart.data.datasets.length < 2) return;

      const data = chart.data.datasets[1].data;
      ctx.save();
      ctx.font = `800 11px system-ui`;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";

      meta.data.forEach((bar, i) => {
        if (data[i] === 0) return; // 데이터가 0이면 그리지 않음
        const txt = formatCompactWon(data[i]);
        ctx.fillStyle = isLightTheme() ? "rgba(0,0,0,0.6)" : "#ffffff";
        ctx.fillText(txt, bar.x, bar.y - 10);
      });
      ctx.restore();
    }
  };

  // -----------------------------
  // 3) (단위: ...) DOM 캡션을 캔버스 아래 고정
  // -----------------------------
  function ensureUnitCaptionUnderCanvas(canvas, text) {
    const parent = canvas?.parentElement;
    if (!parent) return;

    parent.classList.add("parent-flex-fix");

    // 부모를 세로 플렉스로: (캔버스 위 / 캡션 아래)
    const ps = getComputedStyle(parent);
    if (ps.display !== "flex") {
      parent.style.display = "flex";
      parent.style.flexDirection = "column";
      parent.style.minHeight = "0";
    }
    canvas.style.flex = "1 1 auto";
    canvas.style.minHeight = "0";

    let el = parent.querySelector(".unit-caption");
    if (!el) {
      el = document.createElement("div");
      el.className = "unit-caption";
      parent.appendChild(el);

      Object.assign(el.style, {
        marginTop: "14px",      // ✅ 월 라벨 아래로 더 띄움
        paddingBottom: "6px",
        textAlign: "center",
        fontSize: "12px",
        fontWeight: "700",
        lineHeight: "1",
        userSelect: "none",
        pointerEvents: "none",
        opacity: "0.78",
      });
    }

    el.style.color = unitTextColor();
    el.textContent = text;
  }

  // -----------------------------
  // 4) Chart instances
  // -----------------------------
  let forecastChart = null;
  let monthlyTrendChart = null;

  // 4-A) 이번 달 예측 전기료
  const fCanvas = document.getElementById("monthlyForecastBar");
  if (fCanvas) {
    forecastChart = new Chart(fCanvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["최적화 전", "최적화 후"],
        datasets: [{
          data: [forecast.before, forecast.after],
          borderRadius: 8,
          backgroundColor: ["rgba(148,163,184,0.5)", "rgba(0,160,255,0.9)"],
        }]
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: tooltipNow() },
        scales: {
          x: { ticks: { color: axisText(), callback: v => formatCompactWon(v) }, grid: { color: axisGrid() } },
          y: { ticks: { color: axisText(), font: { weight: "800" } }, grid: { display: false } }
        }
      }
    });
  }

  // 4-B) 월별 전기료 추이 (비교형 바 차트)
  const mCanvas = document.getElementById("monthlyCostTrend");
  if (mCanvas) {
    ensureUnitCaptionUnderCanvas(mCanvas, unitCaption);
    monthlyTrendChart = new Chart(mCanvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: monthLabels,
        datasets: [
          {
            label: "최적화 전",
            data: humanCosts,
            backgroundColor: isLightTheme() ? "rgba(15,23,42,0.1)" : "rgba(255,255,255,0.1)",
            borderRadius: 5,
          },
          {
            label: "최적화 후",
            data: aiCosts,
            backgroundColor: "rgba(0,160,255,0.8)",
            borderRadius: 5,
          }
        ]
      },
      plugins: [CapsuleTopLabelPlugin],
      options: {
        responsive: true, maintainAspectRatio: false,
        layout: { padding: { top: 20 } },
        plugins: {
          legend: { display: false },
          tooltip: tooltipNow(),
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: axisText(), font: { weight: "800" },
              callback: function(v, i) { return i === highlightIndex ? "이번달" : monthLabels[i]; }
            }
          },
          y: { display: false, suggestedMax: maxMonthly * 1.2 }
        }
      }
    });
  }

  // -----------------------------
  // 5) Theme apply + auto sync
  // -----------------------------
  function applyThemeToCharts() {
    // Forecast
    if (forecastChart) {
      const t = tooltipNow();
      forecastChart.options.scales.x.ticks.color = axisText();
      forecastChart.options.scales.x.grid.color = axisGrid();
      forecastChart.options.scales.y.ticks.color = axisText();

      forecastChart.options.plugins.tooltip.backgroundColor = t.backgroundColor;
      forecastChart.options.plugins.tooltip.borderColor = t.borderColor;
      forecastChart.options.plugins.tooltip.titleColor = t.titleColor;
      forecastChart.options.plugins.tooltip.bodyColor = t.bodyColor;

      forecastChart.update();
    }

    // Monthly trend
    if (monthlyTrendChart) {
      const t = tooltipNow();
      monthlyTrendChart.options.scales.x.ticks.color = axisText();

      monthlyTrendChart.options.plugins.tooltip.backgroundColor = t.backgroundColor;
      monthlyTrendChart.options.plugins.tooltip.borderColor = t.borderColor;
      monthlyTrendChart.options.plugins.tooltip.titleColor = t.titleColor;
      monthlyTrendChart.options.plugins.tooltip.bodyColor = t.bodyColor;

      monthlyTrendChart.update();
    }

    // Unit caption recolor
    const mc = document.getElementById("monthlyCostTrend");
    if (mc) ensureUnitCaptionUnderCanvas(mc, unitCaption);
  }

  // themechange 이벤트가 있으면 그걸로, 없어도 MutationObserver로 따라감
  window.addEventListener("themechange", applyThemeToCharts);
  window.addEventListener("resize", applyThemeToCharts);

  const mo = new MutationObserver((mutList) => {
    for (const m of mutList) {
      if (m.type === "attributes" && m.attributeName === "data-theme") {
        applyThemeToCharts();
      }
    }
  });
  mo.observe(document.documentElement, { attributes: true });

  // 최초 1회
  applyThemeToCharts();
})();