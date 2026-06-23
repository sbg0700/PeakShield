/**
 * [통합 모니터링 시스템 메인 컨트롤러]
 * 최종 수정일: 2026-02-26 (안정화 버전)
 */

(function() {
    // [1] 전역 설정 및 상태 관리
    const STAGE_CONFIG = {
        'stage-1': { order: 1, name: 'Blast Furnace', base: 1240, range: 10, unit: '°C', threshold: 1246, color: 'cyan' },
        'stage-2': { order: 2, name: 'Oxygen Supply', base: 450, range: 20, unit: 'Nm³/h', threshold: 465, color: 'indigo' },
        'stage-3': { order: 3, name: 'Rolling Mill', base: 8.5, range: 0.5, unit: 'm/s', threshold: 8.9, color: 'emerald' }
    };

    let activeStages = new Set();
    const twinStage = document.getElementById('twinStage');
    const sidebar = document.getElementById('twinSidebar');
    const accordionContainer = document.getElementById('accordionContainer');

    // [2] 실시간 데이터 스트리밍 (SSE)
    function initRealtimeStream() {
        const source = new EventSource("/stream");

        source.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                // 데이터 타입에 따른 분기 처리
                if (data.type === "cost") {
                    updateCostChart(data);
                    updatePSIGauge('before', data.psi_before);
                    updatePSIGauge('after', data.psi_after);
                    updateLiveKPIs(data); // 상단 수치 실시간 업데이트
                } 
                else if (data.type === "process") {
                    updateProcessUI(data);
                    updateProcessCharts(data);
                    checkAlarmThreshold(data);
                }
            } catch (e) {
                console.error("데이터 업데이트 중 에러 발생:", e);
            }
        };

        source.onerror = function() {
            console.warn("SSE 연결 끊김. 브라우저가 재연결을 시도합니다.");
        };
    }

    /**
     * 상단 KPI 숫자를 실시간으로 갈아끼우는 함수 (안전 모드)
     */
    function updateLiveKPIs(data) {
        if (!data) return;

        // HTML에 정의한 ID들을 찾습니다.
		const costEl = document.getElementById('realtime-accumulated-cost');
		const savingsEl = document.getElementById('realtime-potential-savings');

        // 1. 이번 달 누적 전기료 업데이트
		if (costEl && data.total_human_cost !== undefined) {
			// 소수점 버림 처리 후 천단위 콤마 포맷팅
			const formattedCost = Math.floor(data.total_human_cost).toLocaleString();
			costEl.textContent = formattedCost;
		}

        // 2. 이번 달 절감 가능액 업데이트
		if (savingsEl && data.potential_savings !== undefined) {
			const formattedSavings = Math.floor(data.potential_savings).toLocaleString();
			savingsEl.textContent = formattedSavings + " 원";
		}
    }

    /**
     * PSI 게이지 바늘과 텍스트 업데이트
     */
    function updatePSIGauge(type, value) {
        if (value === undefined || value === null) return;

        const safeVal = Math.max(0, Math.min(100, parseFloat(value)));
        const displayVal = safeVal.toFixed(1);

        const needle = document.querySelector(`[data-psi-needle="${type}"]`);
        if (needle) {
            const angle = (safeVal / 100) * 180 - 90;
            needle.setAttribute("transform", `rotate(${angle}, 110, 120)`);
        }

        const textCenter = document.querySelector(`[data-psi-text="${type}"]`);
        const textTop = document.querySelector(`[data-psi-value="${type}"]`);
        if (textCenter) textCenter.textContent = displayVal;
        if (textTop) textTop.textContent = `${displayVal} PSI`;

        const badge = document.querySelector(`[data-psi-badge="${type}"]`);
        if (badge) updatePSIBadge(badge, safeVal);
    }

    function updatePSIBadge(el, val) {
        el.className = "psi-badge px-2 py-0.5 rounded text-[10px] font-bold tracking-widest border";
        if (val < 35) {
            el.textContent = "STABLE";
            el.classList.add("text-emerald-400", "bg-emerald-400/10", "border-emerald-400/20");
        } else if (val < 75) {
            el.textContent = "WARNING";
            el.classList.add("text-amber-400", "bg-amber-400/10", "border-amber-400/20");
        } else {
            el.textContent = "CRITICAL";
            el.classList.add("text-red-400", "bg-red-400/10", "border-red-400/20", "animate-pulse");
        }
    }

    // 전기료 추이 차트 업데이트 (흐르는 효과)
    function updateCostChart(data) {
        const costChart = Chart.getChart("costTrend");
        if (costChart) {
            costChart.data.labels.push(data.time || new Date().toLocaleTimeString());
            if(costChart.data.datasets[0]) costChart.data.datasets[0].data.push(data.actual);
            if(costChart.data.datasets[1]) costChart.data.datasets[1].data.push(data.projected);

            if (costChart.data.labels.length > 12) {
                costChart.data.labels.shift();
                costChart.data.datasets.forEach(ds => ds.data.shift());
            }
            costChart.update('none');
        }
    }
	
	// ==========================================
    // [4] 사이드바 및 아코디언 인터랙션 로직 (복구)
    // ==========================================

    // 1. 공정 카드 클릭 시 사이드바 열기
    window.toggleControl = function(id) {
        if (!id || !STAGE_CONFIG[id]) return;
        
        const twinStage = document.getElementById('twinStage');
        const sidebar = document.getElementById('twinSidebar');
        
        if (twinStage && sidebar) {
            twinStage.classList.add('sidebar-open');
            sidebar.style.width = '400px'; // 강제 너비 할당
            sidebar.style.visibility = 'visible';
        }
        renderAccordion(id);
    };

    // 2. 아코디언 생성 및 렌더링
    function renderAccordion(id) {
        // 이미 열려있는 스테이지면 중복 생성 방지
        if (activeStages.has(id) || !accordionContainer) return;
        
        activeStages.add(id);
        const conf = STAGE_CONFIG[id];
        const item = document.createElement('div');
        
        item.id = `item-${id}`;
        item.dataset.order = conf.order;
        item.className = `accordion-item border border-slate-800 rounded-xl p-4 bg-slate-900/30 mb-4 active active-${conf.color}`;
        
        item.innerHTML = `
            <div class="flex justify-between items-center cursor-pointer" onclick="this.parentElement.classList.toggle('active')">
                <div class="flex flex-col">
                    <div class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">STAGE 0${conf.order}</div>
                    <div class="text-xs font-black text-slate-200 uppercase">${conf.name}</div>
                </div>
                <span class="text-${conf.color}-400 font-mono text-sm font-bold" id="side-val-${id}">${conf.base}${conf.unit}</span>
            </div>
            <div class="accordion-content pt-4 space-y-4">
                <div class="h-[120px] bg-black/20 rounded-lg p-2">
                    <canvas id="chart-${id}"></canvas>
                </div>
                <div class="flex justify-between text-[10px] text-slate-500 uppercase border-t border-white/5 pt-3">
                    <span>Safety Threshold</span>
                    <span class="text-amber-500" id="threshold-val-${id}">${conf.threshold}${conf.unit}</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="removeItem('${id}')" class="flex-1 py-2 text-[9px] bg-red-500/5 text-red-500/40 rounded border border-red-500/10 hover:bg-red-500/20 font-bold transition-all">REMOVE PANEL</button>
                </div>
            </div>`;

        // 순서에 맞게 삽입
        const existing = Array.from(accordionContainer.children);
        const next = existing.find(el => parseInt(el.dataset.order) > conf.order);
        if (next) accordionContainer.insertBefore(item, next);
        else accordionContainer.appendChild(item);

        // 아코디언 내 상세 차트 초기화 (잠시 후 실행)
        setTimeout(() => initAccordionChart(id, conf), 50);
    }

    // 3. 사이드바 닫기 함수
    window.closeSidebar = function() {
        const twinStage = document.getElementById('twinStage');
        const sidebar = document.getElementById('twinSidebar');
        if (twinStage) twinStage.classList.remove('sidebar-open');
        if (sidebar) {
            sidebar.style.width = '0px';
            setTimeout(() => { sidebar.style.visibility = 'hidden'; }, 500);
        }
    };

    // 4. 아코디언 아이템 삭제
    window.removeItem = function(id) {
        const item = document.getElementById(`item-${id}`);
        if (item) item.remove();
        activeStages.delete(id);
        
        if (activeStages.size === 0) {
            window.closeSidebar();
        }
    };

    // 5. 모든 판넬 초기화
    window.clearAllStages = function() {
        activeStages.clear();
        if (accordionContainer) accordionContainer.innerHTML = '';
        window.closeSidebar();
    };

    // 6. 아코디언 내 미니 차트 초기화 함수
    function initAccordionChart(id, conf) {
        const ctx = document.getElementById(`chart-${id}`)?.getContext('2d');
        if (!ctx) return;
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(10).fill(''),
                datasets: [{
                    data: Array(10).fill(conf.base),
                    borderColor: conf.color === 'cyan' ? '#22d3ee' : (conf.color === 'indigo' ? '#818cf8' : '#34d199'),
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    backgroundColor: 'rgba(0,0,0,0)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#475569', font: { size: 8 } }
                    }
                }
            }
        });
    }
	

    // 공정 수치 텍스트 업데이트
    function updateProcessUI(data) {
        Object.keys(STAGE_CONFIG).forEach(id => {
            const conf = STAGE_CONFIG[id];
            if (conf.name === data.module) {
                const sideValEl = document.getElementById(`side-val-${id}`);
                const mainValEl = document.getElementById(`val-${id}`);
                
                if (sideValEl) sideValEl.innerText = `${data.value}${conf.unit}`;
                if (mainValEl) {
                    mainValEl.innerText = data.value;
                    mainValEl.classList.add('animate-pulse');
                    setTimeout(() => mainValEl.classList.remove('animate-pulse'), 500);
                }
            }
        });
    }

    // 알람 임계치 체크 전용 로직
    function checkAlarmThreshold(data) {
        Object.keys(STAGE_CONFIG).forEach(id => {
            const conf = STAGE_CONFIG[id];
            if (conf.name === data.module && data.value > conf.threshold) {
                if (typeof window.triggerAlarm === 'function') {
                    window.triggerAlarm(conf.name, data.value, conf.unit);
                }
            }
        });
    }

    // 공정 상세 차트들 업데이트
    function updateProcessCharts(data) {
        if (typeof Chart !== 'undefined' && Chart.instances) {
            Object.values(Chart.instances).forEach(instance => {
                if (instance.canvas.id === "costTrend") return;

                instance.data.labels.push(data.timestamp || new Date().toLocaleTimeString());
                instance.data.datasets.forEach(dataset => dataset.data.push(data.value));

                if (instance.data.labels.length > 10) {
                    instance.data.labels.shift();
                    instance.data.datasets.forEach(dataset => dataset.data.shift());
                }
                instance.update('none');
            });
        }
    }

    // [3] 테마 및 탭 제어 로직
    const initTheme = () => {
        const root = document.documentElement;
        const btn = document.getElementById("themeToggle");
        const icon = document.getElementById("themeIcon");
        if (!btn) return;

        function setTheme(theme) {
            root.setAttribute("data-theme", theme);
            localStorage.setItem("theme", theme);
            if (icon) icon.textContent = (theme === "light") ? "☀️" : "🌙";
            window.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
        }

        setTheme(localStorage.getItem("theme") || "dark");
        btn.addEventListener("click", () => {
            const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
            setTheme(next);
        });
    };

    const initTabs = () => {
        const tabBtns = document.querySelectorAll(".tab-btn");
        const views = document.querySelectorAll("[data-view]");
        tabBtns.forEach(btn => btn.addEventListener("click", () => {
            const tabName = btn.dataset.tab;
            tabBtns.forEach(b => b.dataset.active = (b.dataset.tab === tabName ? "true" : "false"));
            views.forEach(v => v.classList.toggle("active", v.dataset.view === tabName));
        }));
    };

    // [4] 사이드바 및 아코디언 로직
    window.toggleControl = function(id) {
        if (!id || !STAGE_CONFIG[id]) return;
        if (twinStage && sidebar) {
            twinStage.classList.add('sidebar-open');
            sidebar.style.width = '400px';
            sidebar.style.visibility = 'visible';
        }
        renderAccordion(id);
    };

    function renderAccordion(id) {
        if (activeStages.has(id) || !accordionContainer) return;
        activeStages.add(id);
        const conf = STAGE_CONFIG[id];
        const item = document.createElement('div');
        item.id = `item-${id}`;
        item.dataset.order = conf.order;
        item.className = `accordion-item border border-slate-800 rounded-xl p-4 bg-slate-900/30 mb-4 active active-${conf.color}`;
        item.innerHTML = `
            <div class="flex justify-between items-center cursor-pointer" onclick="this.parentElement.classList.toggle('active')">
                <div class="text-xs font-black text-slate-400 uppercase tracking-tighter">${conf.name}</div>
                <span class="text-${conf.color}-400 font-mono text-sm font-bold" id="side-val-${id}">${conf.base}${conf.unit}</span>
            </div>
            <div class="accordion-content pt-4 space-y-4">
                <div class="flex justify-between text-[10px] text-slate-500 uppercase">
                    <span>Safety Threshold</span>
                    <span class="text-amber-500" id="threshold-val-${id}">${conf.threshold}${conf.unit}</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="removeItem('${id}')" class="flex-1 py-2 text-[9px] bg-red-500/5 text-red-500/40 rounded border border-red-500/10 hover:bg-red-500/20 font-bold">REMOVE</button>
                </div>
            </div>`;
        const existing = Array.from(accordionContainer.children);
        const next = existing.find(el => parseInt(el.dataset.order) > conf.order);
        if (next) accordionContainer.insertBefore(item, next);
        else accordionContainer.appendChild(item);
    }
	
	// 현재 화면에 설정된 파라미터 값을 모두 긁어오는 함수
	function getCurrentSimulatedParams() {
		const params = {};
		// stage-1 부터 stage-5 까지 슬라이더 값을 긁어옵니다.
		for (let i = 1; i <= 5; i++) {
			const slider = document.getElementById(`slider-stage-${i}`);
			if (slider) {
				params[`stage-${i}`] = slider.value;
			} else {
				// 슬라이더가 렌더링되지 않았으면 STAGE_CONFIG의 기본값을 사용
				params[`stage-${i}`] = STAGE_CONFIG[`stage-${i}`].base;
			}
		}
		return params;
	}

	// 글로벌 변수에 최신 리포트 데이터를 저장해둠 (Export용)
	let lastReportData = null;

	// [기능 1] Report 버튼 클릭 이벤트
	document.getElementById('btn-report').addEventListener('click', () => {
		const params = getCurrentSimulatedParams();
		
		// API 호출
		fetch('/api/simulate_report', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(params)
		})
		.then(res => res.json())
		.then(data => {
			if (data.status === 'success') {
				lastReportData = data; // 저장
				
				// UI 업데이트
				document.getElementById('reportTime').innerText = new Date().toLocaleString();
				document.getElementById('rep-usage').innerText = `${data.results.usage_kwh} kWh`;
				document.getElementById('rep-psi').innerText = data.results.psi;
				document.getElementById('rep-co2').innerText = `${data.results.co2_saved_kg} kg`;
				
				// 인사이트 업데이트
				const insightsUl = document.getElementById('rep-insights');
				insightsUl.innerHTML = '';
				data.insights.forEach(insight => {
					const li = document.createElement('li');
					// 마크다운 형식의 별표(**)를 굵은 글씨(<b>)로 변환
					li.innerHTML = insight.replace(/\*\*(.*?)\*\*/g, '<b class="text-white">$1</b>'); 
					insightsUl.appendChild(li);
				});
				
				// 패널 부드럽게 표시 (Slide down 효과)
				const panel = document.getElementById('reportPanel');
				panel.classList.remove('hidden');
				panel.scrollIntoView({ behavior: 'smooth', block: 'end' });
			}
		});
	});

	// [기능 2] Export Data 버튼 클릭 이벤트 (Markdown 다운로드)
	document.getElementById('btn-export').addEventListener('click', () => {
		if (!lastReportData) {
			alert("먼저 'Report' 버튼을 눌러 시뮬레이션 결과를 생성해주세요.");
			return;
		}
		
		const d = lastReportData;
		const dateStr = new Date().toLocaleString();
		
		// Markdown 텍스트 생성
		let mdContent = `# 📊 스마트 팩토리 AI 공정 최적화 리포트\n\n`;
		mdContent += `**생성 일시:** ${dateStr}\n\n`;
		
		mdContent += `## 1. 입력 파라미터 설정\n`;
		mdContent += `- 원료 투입량 (Iron Ore): ${d.parameters['stage-1']} ton/h\n`;
		mdContent += `- 로 온도 (Furnace Temp): ${d.parameters['stage-2']} °C\n`;
		mdContent += `- 모터 가동률 (Motor Rate): ${d.parameters['stage-3']} %\n`;
		mdContent += `- 콘덴서 제어 (Cap Rate): ${d.parameters['stage-4']} %\n`;
		mdContent += `- 목표 탄소 함량 (Carbon): ${d.parameters['stage-5']} %\n\n`;
		
		mdContent += `## 2. 시뮬레이션 결과 예측\n`;
		mdContent += `- **예측 전력 사용량:** ${d.results.usage_kwh} kWh\n`;
		mdContent += `- **공정 스트레스 지수 (PSI):** ${d.results.psi} / 100\n`;
		mdContent += `- **CO2 저감 효과:** ${d.results.co2_saved_kg} kg\n\n`;
		
		mdContent += `## 3. AI 제어 인사이트\n`;
		d.insights.forEach(msg => {
			mdContent += `${msg}\n`;
		});
		
		// Blob을 이용해 가상의 파일 생성 후 다운로드 트리거
		const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' });
		const link = document.createElement('a');
		link.href = URL.createObjectURL(blob);
		link.download = `AI_Simulation_Report_${Date.now()}.md`;
		link.click();
		URL.revokeObjectURL(link.href);
	});
	
	
	

    window.removeItem = function(id) {
        document.getElementById(`item-${id}`)?.remove();
        activeStages.delete(id);
        if (activeStages.size === 0) {
            twinStage.classList.remove('sidebar-open');
            sidebar.style.width = '0px';
        }
    };

    // [5] DOM 로드 완료 후 실행
    document.addEventListener('DOMContentLoaded', () => {
        initTheme();
        initTabs();
        initRealtimeStream();
        console.log("System Master Controller Ready.");
    });

})();