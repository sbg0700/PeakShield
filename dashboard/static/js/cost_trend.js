// static/js/cost_trend.js
const raw = window.COST_TREND_DATA || [];

// 1분(60초) 데이터만 표시
const MAX_POINTS = 60;
const displayData = raw.length > MAX_POINTS ? raw.slice(-MAX_POINTS) : raw;

// 기준 시간 설정 (첫 데이터 시간 또는 현재 시간)
let startTime = new Date();
if (displayData.length > 0 && displayData[0].time) {
  const timeStr = displayData[0].time;
  const [h, m] = timeStr.split(':').map(Number);
  startTime = new Date();
  startTime.setHours(h, m, 0, 0);
}

// 각 데이터포인트에 대해 실제 시간을 계산 (초 단위)
const labels = displayData.map((d, i) => {
  const time = new Date(startTime);
  time.setSeconds(startTime.getSeconds() + i);
  const h = String(time.getHours()).padStart(2, '0');
  const m = String(time.getMinutes()).padStart(2, '0');
  const s = String(time.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
});

const actual = displayData.map(d => d.actual);
const projected = displayData.map(d => d.projected ?? null);

// Last point pulse (TV ripple)
let costTrendRafId = null;
window.__SHOW_PROJECTION__ = window.__SHOW_PROJECTION__ ?? false;

const CostTrendLastPointPulse = {
  id: "costTrendLastPointPulse",
  afterDatasetsDraw(chart, args, pluginOptions) {
    const { ctx } = chart;
    const wantProjection = (window.__SHOW_PROJECTION__ === true);
    const targetIdxs = wantProjection ? [0, 1] : [0];

    targetIdxs.forEach((datasetIndex) => {
      const meta = chart.getDatasetMeta(datasetIndex);
      if (!meta || !meta.data || meta.data.length === 0) return;

      const ds = chart.data.datasets[datasetIndex] || {};
      const baseColor = (typeof ds.borderColor === "string" ? ds.borderColor : null) || (pluginOptions?.color ?? "#00e5ff");

      function toRgba(color, a) {
        if (!color) return `rgba(0,229,255,${a})`;
        const hex = color.replace("#", "");
        if (hex.length === 6) {
          const r = parseInt(hex.slice(0, 2), 16);
          const g = parseInt(hex.slice(2, 4), 16);
          const b = parseInt(hex.slice(4, 6), 16);
          return `rgba(${r},${g},${b},${a})`;
        }
        return (color.startsWith("rgb") ? color.replace(/[\d.]+\)$/g, `${a})`) : `rgba(0,229,255,${a})`);
      }

      const minR = pluginOptions?.minRadius ?? 3;
      const maxR = pluginOptions?.maxRadius ?? 16;
      const speed = pluginOptions?.speed ?? 2000;

      const ringBaseA = wantProjection ? 0.32 : 0.35;
      const ringColorBase = pluginOptions?.ringColor ?? toRgba(baseColor, ringBaseA);

      const dataArr = ds.data ?? [];
      let lastIdx = dataArr.length - 1;
      while (lastIdx >= 0 && (dataArr[lastIdx] == null || Number.isNaN(Number(dataArr[lastIdx])))) lastIdx--;
      if (lastIdx < 0) return;

      const pt = meta.data[lastIdx];
      if (!pt) return;

      const x = pt.x;
      const y = pt.y;

      const tt = (Date.now() % speed) / speed;
      const ease = tt * (2 - tt);
      const r = minR + (maxR - minR) * ease;
      const alpha = 1 - tt;

      ctx.save();

      // Center point
      ctx.beginPath();
      ctx.fillStyle = baseColor;
      ctx.arc(x, y, minR + 2, 0, Math.PI * 2);
      ctx.fill();

      // Ripple ring
      ctx.beginPath();
      ctx.strokeStyle = ringColorBase.replace(/[\d.]+\)$/g, `${(0.35 * alpha).toFixed(3)})`);
      ctx.lineWidth = 2;
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.stroke();

      // Glow
      ctx.beginPath();
      ctx.fillStyle = toRgba(baseColor, (0.10 * alpha).toFixed(3));
      ctx.arc(x, y, r * 0.65, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    });
  }
};

const canvas = document.getElementById("costTrend");
if (!canvas) {
  console.warn("[cost_trend] #costTrend canvas not found");
} else {
  const ctx = canvas.getContext("2d");
  let showProjection = false;
  window.__SHOW_PROJECTION__ = showProjection;

  function makeAreaGradient(ctx, canvas) {
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height || 300);
    grad.addColorStop(0, "rgba(0, 229, 255, 0.30)");
    grad.addColorStop(1, "rgba(0, 229, 255, 0.02)");
    return grad;
  }

  let grad = makeAreaGradient(ctx, canvas);

  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "실제 전기료",
          data: actual,
          fill: "start",
          tension: 0.35,
          borderColor: "#00e5ff",
          backgroundColor: grad,
          pointBackgroundColor: "#00e5ff",
          pointBorderColor: "rgba(0,0,0,0.0)",
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
        },
        {
          label: "절감 후 예상",
          data: projected,
          fill: false,
          tension: 0.35,
          hidden: true,
          borderColor: "#a78bfa",
          pointBackgroundColor: "#a78bfa",
          borderWidth: 2,
          borderDash: [6, 6],
          pointRadius: 2,
          pointHoverRadius: 4,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 1000,
        easing: "easeOutCubic",
      },
      animations: {
        x: { duration: 1000, easing: "easeOutCubic" },
        y: { duration: 1000, easing: "easeOutCubic" },
      },
      plugins: {
        legend: {
          labels: {
            color: "rgba(229,231,235,0.75)",
            font: { weight: "700" }
          },
          onClick: (e, legendItem, legend) => {
            const idx = legendItem?.datasetIndex ?? -1;
            if (idx === 1) {
              showProjection = !showProjection;
              window.__SHOW_PROJECTION__ = showProjection;
              chart.data.datasets[1].hidden = !showProjection;
              chart.update("none");
              requestAnimationFrame(() => chart && chart.update("none"));
              return;
            }
            const defaultOnClick = Chart.defaults.plugins.legend.onClick;
            if (typeof defaultOnClick === "function") {
              defaultOnClick(e, legendItem, legend);
            }
          }
        },
        tooltip: {
          backgroundColor: "rgba(0,0,0,0.85)",
          borderWidth: 1,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (ctx2) => {
              if (ctx2.raw === null || ctx2.raw === undefined) return "";
              return `${ctx2.dataset.label}: ${Number(ctx2.raw).toLocaleString()}원`;
            }
          }
        },
        costTrendLastPointPulse: {
          minRadius: 3,
          maxRadius: 16,
          speed: 2000
        }
      },
      interaction: { intersect: false, mode: "index" },
      scales: {
        x: {
          type: "category",
          ticks: {
            color: "rgba(156,163,175,0.8)",
            autoSkip: false,
            maxRotation: 45,
            minRotation: 0
          },
          grid: { color: "rgba(255,255,255,0.06)" }
        },
        y: {
          grace: "10%",
          ticks: {
            color: "rgba(156,163,175,0.8)",
            callback: (v) => Number(v).toLocaleString()
          },
          title: { display: true, text: "전기료(원)", color: "rgba(156,163,175,0.85)" },
          grid: { color: "rgba(255,255,255,0.06)" }
        }
      }
    },
    plugins: [CostTrendLastPointPulse],
  });

  if (costTrendRafId) cancelAnimationFrame(costTrendRafId);

  const costTrendTick = () => {
    if (!chart) return;
    chart.draw();
    costTrendRafId = requestAnimationFrame(costTrendTick);
  };

  costTrendRafId = requestAnimationFrame(costTrendTick);

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("toggleProjection");
    if (!btn) return;
    btn.addEventListener("click", () => {
      showProjection = !showProjection;
      window.__SHOW_PROJECTION__ = showProjection;
      chart.data.datasets[1].hidden = !showProjection;
      chart.update();
    });
  });

  window.updateCostTrendData = (newRows) => {
    try {
      if (!newRows || newRows.length === 0) return;
      
      // 기준 시간 계산
      let startTime = new Date();
      if (newRows.length > 0 && newRows[0].time) {
        const timeStr = newRows[0].time;
        const [h, m] = timeStr.split(':').map(Number);
        startTime = new Date();
        startTime.setHours(h, m, 0, 0);
      }
      
      // 시간 레이블 생성
      chart.data.labels = newRows.map((d, i) => {
        const time = new Date(startTime);
        time.setSeconds(startTime.getSeconds() + i);
        const h = String(time.getHours()).padStart(2, '0');
        const m = String(time.getMinutes()).padStart(2, '0');
        const s = String(time.getSeconds()).padStart(2, '0');
        return `${h}:${m}:${s}`;
      });
      
      chart.data.datasets[0].data = newRows.map(d => d.actual);
      chart.data.datasets[1].data = newRows.map(d => d.projected ?? null);
      
      chart.update("none");
    } catch (e) {
      console.warn("[cost_trend] updateCostTrendData failed", e);
    }
  };

  window.appendCostTrendPoint = (pt) => {
    try {
      if (!pt) return;
      
      // 시간 계산 (마지막 라벨 기준)
      let newTime;
      const lastLabel = chart.data.labels[chart.data.labels.length - 1];
      
      if (lastLabel) {
        const [h, m, s] = lastLabel.split(':').map(Number);
        newTime = new Date();
        newTime.setHours(h, m, s, 0);
        newTime.setSeconds(newTime.getSeconds() + 1);
      } else {
        newTime = new Date();
      }
      
      const h = String(newTime.getHours()).padStart(2, '0');
      const m = String(newTime.getMinutes()).padStart(2, '0');
      const s = String(newTime.getSeconds()).padStart(2, '0');
      const newLabel = `${h}:${m}:${s}`;
      
      chart.data.labels.push(newLabel);
      chart.data.datasets[0].data.push(pt.actual);
      chart.data.datasets[1].data.push(pt.projected ?? null);
      
      // 60초 초과 시 왼쪽 데이터 제거
      if (chart.data.labels.length > MAX_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
      }
      
      chart.update();
    } catch (e) {
      console.warn("[cost_trend] appendCostTrendPoint failed", e);
    }
  };
}

