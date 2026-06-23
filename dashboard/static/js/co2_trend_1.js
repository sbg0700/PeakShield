(function () {
  const canvas = document.getElementById("costTrendCO2");
  if (!canvas) return;

  const labels = window.CO2_MONTH_LABELS || [];
  const values = window.CO2_MONTH_VALUES || [];
  const ctx = canvas.getContext("2d");

  function getIsLight() {
    const root = document.documentElement;
    const body = document.body;
    return (
      root.classList.contains("light") ||
      body.classList.contains("light") ||
      root.dataset.theme === "light" ||
      body.dataset.theme === "light"
    );
  }

  function render() {
    const isLight = getIsLight();

    const colors = isLight
      ? {
          bar: "rgba(16,185,129,0.78)",
          barHover: "rgba(16,185,129,0.92)",
          line: "rgba(4,120,87,1)",

          grid: "rgba(15,23,42,0.12)",
          tick: "rgba(15,23,42,0.78)",

          tipBg: "rgba(255,255,255,0.98)",
          tipBorder: "rgba(15,23,42,0.14)",
          tipTitle: "rgba(15,23,42,0.92)",
          tipBody: "rgba(15,23,42,0.82)",
        }
      : {
          bar: "rgba(94,234,212,0.22)",
          barHover: "rgba(94,234,212,0.32)",
          line: "rgba(94,234,212,0.95)",
          grid: "rgba(255,255,255,0.06)",
          tick: "rgba(255,255,255,0.55)",
          tipBg: "rgba(15,23,42,0.92)",
          tipBorder: "rgba(255,255,255,0.12)",
          tipTitle: "rgba(255,255,255,0.92)",
          tipBody: "rgba(255,255,255,0.82)",
        };

    if (window.__CO2_TREND_CHART__) {
      window.__CO2_TREND_CHART__.destroy();
    }

    // MoM 계산
    let momRate = null;
    if (values.length >= 2) {
      const last = values[values.length - 1];
      const prev = values[values.length - 2];
      momRate = ((last - prev) / prev) * 100;
    }

    const pulseDotPlugin = {
      id: "pulseDot",
      afterDatasetsDraw(chart, args, pluginOptions) {
        const { ctx } = chart;

        const dsIndex = pluginOptions?.datasetIndex ?? 1; // 라인 인덱스
        const meta = chart.getDatasetMeta(dsIndex);
        if (!meta || !meta.data || meta.data.length === 0) return;

        const p = meta.data[meta.data.length - 1];
        if (!p) return;

        const x = p.x, y = p.y;

        // ✅ 확산 리플: 0→1 진행률이 계속 증가, 1 되면 다시 0으로
        const speed = pluginOptions?.speed ?? 1200; // ms
        const t = performance.now() % speed;
        const k = t / speed; // 0..1

        const minR = pluginOptions?.minRadius ?? 6;
        const maxR = pluginOptions?.maxRadius ?? 22;

        // 바깥으로만 커짐
        const r = minR + (maxR - minR) * k;

        // 커질수록 사라짐 (TradingView 느낌)
        const alpha = (pluginOptions?.alpha ?? 0.35) * (1 - k);

        const ringColor = pluginOptions?.ringColor ?? `rgba(94,234,212,${alpha})`;
        const dotColor = pluginOptions?.dotColor ?? "rgba(94,234,212,0.95)";

        ctx.save();

        // 링
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.strokeStyle = ringColor.replace(/rgba\(([^)]+),[^)]+\)/, `rgba($1,${alpha})`);
        ctx.lineWidth = 2;
        ctx.stroke();

        // 중앙 점 (고정)
        ctx.beginPath();
        ctx.arc(x, y, 3.8, 0, Math.PI * 2);
        ctx.fillStyle = dotColor;
        ctx.fill();

        ctx.restore();
      }
    };


    // ✅ y축 자동 최적화: 데이터 기반 min/max + 아주 얕은 패딩
    const nums = (values || []).filter(v => Number.isFinite(v));
    let yMin = 0, yMax = 1;

    if (nums.length) {
      const mn = Math.min(...nums);
      const mx = Math.max(...nums);
      const pad = (mx - mn) * 0.08;          // 패딩 8% (원하면 0.06)
      yMin = Math.max(0, mn - pad);
      yMax = mx + pad;
    }


    window.__CO2_TREND_CHART__ = new Chart(ctx, {
      data: {
        labels,
        datasets: [
          {
            type: "bar",
            label: "월별 탄소비용 (KRW)",
            data: values,
            borderWidth: 0,
            borderRadius: 8,
            barPercentage: 0.65,
            categoryPercentage: 0.75,
            backgroundColor: colors.bar,
            hoverBackgroundColor: colors.barHover,
          },
          {
            type: "line",
            label: "추세",
            data: values,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 3.5,
            pointHoverRadius: 4,
            borderColor: colors.line,
            backgroundColor: colors.line,
            fill: false,
          },
        ],
      },

      options: {
        responsive: true,
        maintainAspectRatio: false,

        // ✅ 하단 여백 줄이기 (y축 여유를 줄여서 프레임 꽉 차게)
        scales: {
          x: {
            grid: { color: colors.grid },
            ticks: { color: colors.tick, maxRotation: 0, autoSkip: true },
          },
          y: {
            beginAtZero: true,
            grace: "3%", // ✅ 여백 축소 (기존 없음/기본값이 커 보일 수 있음)
            grid: { color: colors.grid },
            ticks: { color: colors.tick, callback: (v) => `${Number(v).toLocaleString()}원` },
          },
        },

        animation: { duration: 450 },
        interaction: { mode: "index", intersect: false },

        plugins: {
          legend: {
            display: true,
            labels: { color: colors.tick, usePointStyle: true, boxWidth: 10 },
          },
          tooltip: {
            backgroundColor: colors.tipBg,
            borderColor: colors.tipBorder,
            borderWidth: 1,
            titleColor: colors.tipTitle,
            bodyColor: colors.tipBody,
            callbacks: { label: (c) => `${c.parsed.y.toLocaleString()}원` },
          },
        },
      },

      // ✅ 플러그인 등록은 여기(최상위)
      plugins: [pulseDotPlugin],
    });

    // ✅ 리플 계속 돌리기 (중복 방지)
    // ✅ 리플만 부드럽게: update() 대신 draw() (호버/툴팁 안 늦어짐)
    if (window.__CO2_RAF__) cancelAnimationFrame(window.__CO2_RAF__);

    const tick = () => {
      const c = window.__CO2_TREND_CHART__;
      if (!c) return;

      // update는 레이아웃/이벤트까지 건드려서 hover가 밀림
      // draw는 화면만 다시 그림(리플 갱신에 충분)
      c.draw();

      window.__CO2_RAF__ = requestAnimationFrame(tick);
    };

    window.__CO2_RAF__ = requestAnimationFrame(tick);



    // 배지
    const badge = document.getElementById("co2TrendYoY");
    if (badge && momRate !== null) {
      const positive = momRate >= 0;
      badge.innerHTML = `${positive ? "▲" : "▼"} ${Math.abs(momRate).toFixed(1)}% MoM`;
      badge.className =
        "text-xs px-2 py-1 rounded-full border " +
        (positive
          ? "bg-red-500/10 text-red-400 border-red-500/20"
          : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20");
    }
  }

  // 최초 렌더
  render();

  // ✅ 테마 토글 시(클래스/데이터셋 변경) 자동 재렌더
  const obs = new MutationObserver(() => render());
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme"] });
  obs.observe(document.body, { attributes: true, attributeFilter: ["class", "data-theme"] });
})();


