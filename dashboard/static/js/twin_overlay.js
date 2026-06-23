// static/js/twin_overlay.js
(() => {
  const overlay = document.getElementById("twin-overlay");
  const openBtn = document.getElementById("openTwinBtn");
  const closeBtn = document.getElementById("closeTwinBtn");

  const sidebar = document.getElementById("twinSidebar");
  const closePanelBtn = document.getElementById("closePanelBtn");

  const titleEl = document.getElementById("twinTitle");
  const moduleTagEl = document.getElementById("twinModuleTag");
  const inputEl = document.getElementById("twinInput");
  const runBtn = document.getElementById("runAnalyzeBtn");

  const resultEl = document.getElementById("twinResult");
  const statusEl = document.getElementById("twinStatusText");

  let selectedModule = null;
  let twinChart = null;

  function openOverlay() {
    overlay.classList.add("active");
    overlay.setAttribute("aria-hidden", "false");
  }

  function closeOverlay() {
    overlay.classList.remove("active");
    overlay.setAttribute("aria-hidden", "true");
    closePanel();
  }

  function openPanel(moduleName) {
    selectedModule = moduleName;
    titleEl.textContent = `${moduleName} 공정 리포트`;
    moduleTagEl.textContent = moduleName;

    sidebar.classList.add("active");
    overlay.classList.add("panel-open");

    sidebar.classList.remove("expanded");
    resultEl.classList.remove("visible");
    statusEl.textContent = "상태: -";

    // input reset
    inputEl.value = "";
    setTimeout(() => inputEl.focus(), 350);
  }

  function closePanel() {
    sidebar.classList.remove("active", "expanded");
    overlay.classList.remove("panel-open");
    resultEl.classList.remove("visible");
    selectedModule = null;
  }

  async function requestAnalysis() {
    const val = inputEl.value;
    if (!selectedModule || val === "" || val === null) return;

    sidebar.classList.add("expanded");
    resultEl.classList.add("visible");

    const payload = { module: selectedModule, value: val };

    let resJson;
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      resJson = await res.json();
    } catch (e) {
      statusEl.textContent = "상태: API 호출 실패";
      return;
    }

    statusEl.textContent = `상태: ${resJson.status || "-"}`;

    drawChart({
      labels: resJson.labels || [],
      trend: resJson.trend || [],
    });
  }

  function drawChart(data) {
    const canvas = document.getElementById("twinChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (twinChart) twinChart.destroy();

    twinChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [{
          data: data.trend,
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900, easing: "easeOutQuart" },
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: true,
            backgroundColor: "rgba(0, 0, 0, 0.85)",
            padding: 12,
            intersect: false,
            mode: "index",
          }
        },
        interaction: { intersect: false, mode: "index" },
        scales: {
          x: { ticks: { color: "rgba(255,255,255,0.0)" }, grid: { display: false } },
          y: { ticks: { color: "rgba(255,255,255,0.0)" }, grid: { color: "rgba(255,255,255,0.05)" } }
        }
      }
    });

    // 팀원 accent 컬러를 dataset에 적용(Chart.js 옵션으로 직접)
    // 차트 생성 후에 넣어도 되고, 생성 전에 넣어도 됨
    twinChart.data.datasets[0].borderColor = "#00e5ff";
    twinChart.data.datasets[0].pointBackgroundColor = "#00e5ff";
    twinChart.data.datasets[0].backgroundColor = "rgba(0, 229, 255, 0.06)";
    twinChart.update();
  }

  // --- Events ---
  if (openBtn) openBtn.addEventListener("click", openOverlay);
  if (closeBtn) closeBtn.addEventListener("click", closeOverlay);

  // overlay 바깥(어두운 배경) 클릭하면 닫기
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeOverlay();
    });
  }

  if (closePanelBtn) closePanelBtn.addEventListener("click", closePanel);
  if (runBtn) runBtn.addEventListener("click", requestAnalysis);

  if (inputEl) {
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") requestAnalysis();
    });
  }

  // SVG 클릭 영역 바인딩
  document.querySelectorAll("#twin-overlay .clickable-area").forEach((el) => {
    el.addEventListener("click", () => {
      const moduleName = el.getAttribute("data-module");
      if (!overlay.classList.contains("active")) openOverlay();
      openPanel(moduleName);
    });
  });
})();


