/**
 * [통합 모니터링 시스템 메인 컨트롤러 - 시뮬레이션 고도화 버전]
 */

(function() {
    // [1] 5대 핵심 파라미터 설정 (Digital Twin Variables)
    const STAGE_CONFIG = {
        'stage-1': { order: 1, name: 'Iron Ore Feed', base: 100, min: 50, max: 200, step: 1, unit: 'ton/h', color: 'cyan' },
        'stage-2': { order: 2, name: 'Furnace Temp', base: 1550, min: 1400, max: 1700, step: 10, unit: '°C', color: 'indigo' },
        'stage-3': { order: 3, name: 'Motor Rate', base: 85, min: 50, max: 100, step: 1, unit: '%', color: 'emerald' },
        'stage-4': { order: 4, name: 'Capacitor Rate', base: 90, min: 50, max: 100, step: 1, unit: '%', color: 'amber' },
        'stage-5': { order: 5, name: 'Carbon Content', base: 0.18, min: 0.05, max: 0.5, step: 0.01, unit: '%', color: 'rose' }
    };

    let activeStages = new Set();
    const twinStage = document.getElementById('twinStage');
    const sidebar = document.getElementById('twinSidebar');
    const accordionContainer = document.getElementById('accordionContainer');

	function initRealtimeStream() {
		const source = new EventSource("/stream");

		// SSE 연결 성공 확인
		source.onopen = function() {
			console.log("🟢 [SSE Connection] 서버와 실시간 스트리밍이 연결되었습니다.");
		};

		// SSE 연결 실패 확인
		source.onerror = function(err) {
			console.error("🔴 [SSE Error] 서버 연결에 실패했거나 끊어졌습니다.", err);
		};

		source.onmessage = function(event) {
			// [디버깅 핵심] 서버에서 들어오는 날것의 데이터를 무조건 출력
			console.log("🔵 [SSE Data Received]", event.data); 

			try {
				const data = JSON.parse(event.data);
				
				// 데이터 타입 검증 로그
				if (data.type !== "all_in_one") {
					console.warn("⚠️ [Type Mismatch] 기대한 type('all_in_one')이 아닙니다. 현재 type:", data.type);
				}

				if (data.type === "all_in_one") {
					if (data.cost && Object.keys(data.cost).length > 0) {
						const costData = { time: data.time, ...data.cost };
						updateCostChart(costData);
						updatePSIGauge('before', data.cost.psi_before);
						updatePSIGauge('after', data.cost.psi_after);
						updateLiveKPIs(data.cost);
					}
					
					if (data.processes && data.processes.length > 0) {
						data.processes.forEach(proc => {
							// 모듈 매칭 디버깅
							if (!Object.values(STAGE_CONFIG).some(conf => conf.name === proc.module)) {
								console.warn("⚠️ [Module Mismatch] 정의되지 않은 모듈 이름이 수신되었습니다:", proc.module);
							}
							updateProcessUI(proc);
							checkAlarmThreshold(proc);
						});
					}
				}
				
			} catch (e) {
				console.error("❌ [Parsing Error] 데이터 업데이트 중 에러 발생:", e);
			}
		};
	}
	
	// [추가] 차트 및 게이지 실시간 업데이트 함수 (복구됨)
    function updateCostChart(data) {
        if (typeof Chart === 'undefined') return;
        const costChart = Chart.getChart("costTrend");
        if (costChart) {
            costChart.data.labels.push(data.time || new Date().toLocaleTimeString('ko-KR'));
            if(costChart.data.datasets[0]) costChart.data.datasets[0].data.push(data.actual);
            if(costChart.data.datasets[1]) costChart.data.datasets[1].data.push(data.projected);

            // 화면에 보여줄 데이터 개수 제한 (흐르는 효과)
            if (costChart.data.labels.length > 12) {
                costChart.data.labels.shift();
                costChart.data.datasets.forEach(ds => ds.data.shift());
            }
            costChart.update('none'); // 애니메이션 없이 즉시 렌더링
        }
    }

    function updatePSIGauge(type, value) {
        if (value === undefined || value === null) return;

        const safeVal = Math.max(0, Math.min(100, parseFloat(value)));

        // ✅ psi_gauge_1.js의 window.setPSI를 호출 (애니메이션 포함)
        if (window.setPSI) {
            window.setPSI(type, safeVal);
        } else {
            // 폴백: window.setPSI가 없으면 수동 업데이트 (애니메이션 없음)
            const needle = document.querySelector(`[data-psi-needle="${type}"]`);
            if (needle) {
                const angle = (safeVal / 100) * 180 - 90;
                // ✅ SVG transform attribute 사용: 정확한 중심 좌표로 회전
                needle.setAttribute("transform", `rotate(${angle} 110 120)`);
            }
        }
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

    function updateLiveKPIs(data) {
        if (!data) return;
        const costEl = document.getElementById('realtime-accumulated-cost');
        const savingsEl = document.getElementById('realtime-potential-savings');

        if (costEl && data.total_human_cost !== undefined) {
            costEl.textContent = Math.floor(data.total_human_cost).toLocaleString();
        }
        if (savingsEl && data.potential_savings !== undefined) {
            savingsEl.textContent = Math.floor(data.potential_savings).toLocaleString() + " 원";
        }
    }

    // [3] 사이드바 및 아코디언 로직 (슬라이더 적용)
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
                <div class="flex flex-col">
                    <div class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">PARAMETER 0${conf.order}</div>
                    <div class="text-xs font-black text-slate-200 uppercase">${conf.name}</div>
                </div>
                <span class="text-${conf.color}-400 font-mono text-sm font-bold" id="side-val-${id}">${conf.base}${conf.unit}</span>
            </div>
            <div class="accordion-content pt-4 space-y-4">
                <div class="w-full">
                    <div class="flex justify-between text-[10px] text-slate-400 mb-2 font-bold">
                        <span>${conf.min}</span>
                        <span class="text-${conf.color}-400 animate-pulse">Adjust to Simulate</span>
                        <span>${conf.max}</span>
                    </div>
                    <input type="range" id="slider-${id}" min="${conf.min}" max="${conf.max}" step="${conf.step}" value="${conf.base}" 
                           class="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                           oninput="document.getElementById('side-val-${id}').innerText = this.value + '${conf.unit}'">
                </div>
                <div class="flex gap-2 mt-4 border-t border-white/5 pt-3">
                    <button onclick="removeItem('${id}')" class="flex-1 py-2 text-[9px] bg-red-500/5 text-red-500/40 rounded border border-red-500/10 hover:bg-red-500/20 font-bold transition-all">CLOSE PANEL</button>
                </div>
            </div>`;
        
        const existing = Array.from(accordionContainer.children);
        const next = existing.find(el => parseInt(el.dataset.order) > conf.order);
        if (next) accordionContainer.insertBefore(item, next);
        else accordionContainer.appendChild(item);
    }

    window.removeItem = function(id) {
        document.getElementById(`item-${id}`)?.remove();
        activeStages.delete(id);
        if (activeStages.size === 0) {
            window.clearAllStages();
        }
    };

    window.clearAllStages = function() {
        activeStages.clear();
        if (accordionContainer) accordionContainer.innerHTML = '';
        if (twinStage) twinStage.classList.remove('sidebar-open');
        if (sidebar) {
            sidebar.style.width = '0px';
            setTimeout(() => { sidebar.style.visibility = 'hidden'; }, 500);
        }
    };
	
	// [복구] 사이드바 단독 닫기 함수
    window.closeSidebar = function() {
        const twinStage = document.getElementById('twinStage');
        const sidebar = document.getElementById('twinSidebar');
        
        if (twinStage) twinStage.classList.remove('sidebar-open');
        if (sidebar) {
            sidebar.style.width = '0px';
            // CSS 트랜지션 시간(0.5초)이 끝난 후 완전히 숨김 처리
            setTimeout(() => { sidebar.style.visibility = 'hidden'; }, 500);
        }
    };
	
	// [2] 🚀 [복구] 공정 실시간 수치를 HTML 카드에 반영하는 함수
	// [수정된 updateProcessUI] ID 매칭을 더 명확하게 처리
    function updateProcessUI(data) {
        // STAGE_CONFIG를 순회하며 서버에서 온 module(이름)과 일치하는 카드를 찾음
        Object.keys(STAGE_CONFIG).forEach(id => {
            const conf = STAGE_CONFIG[id];
            
            // 이름이 정확히 일치할 때만 실행
            if (conf.name === data.module) {
                // ✅ [지도 위 메인 카드만 업데이트] 숫자 갱신 (예: val-stage-1)
                // 사이드바의 파라미터는 사용자가 수동으로 조정할 수 있도록 고정
                const mainValEl = document.getElementById(`val-${id}`);
                if (mainValEl) {
                    mainValEl.innerText = data.value;
                    // 바뀔 때마다 반짝이는 애니메이션 효과
                    mainValEl.classList.add('text-white');
                    setTimeout(() => mainValEl.classList.remove('text-white'), 500);
                }
            }
        });
    }

    // [3] 🚀 [복구] 알람 임계치 체크 함수
    function checkAlarmThreshold(data) {
        // 각 파라미터별 위험 임계치 임의 설정 (필요시 STAGE_CONFIG 안에 threshold 키로 뺄 수 있음)
        const thresholds = {
            "Iron Ore Feed": 180, // 180 ton/h 초과 시 경고
            "Furnace Temp": 1650, // 1650도 초과 시 경고
            "Motor Rate": 95      // 모터 95% 초과 시 경고
        };

        const limit = thresholds[data.module];
        
        // 임계치가 설정되어 있고, 넘어온 값이 그 임계치를 초과했다면 알람 트리거
        if (limit && parseFloat(data.value) > limit) {
            if (typeof window.triggerAlarm === 'function') {
                window.triggerAlarm(data.module, data.value, data.unit);
            }
        }
    }
	
	

    // [4] 가상 시뮬레이션 및 리포트 제어 로직
    let lastReportData = null;

    function getCurrentSimulatedParams() {
        const params = {};
        for (let i = 1; i <= 5; i++) {
            const slider = document.getElementById(`slider-stage-${i}`);
            // 슬라이더가 렌더링되어 있으면 그 값을, 아니면 STAGE_CONFIG의 기본값을 가져옴
            params[`stage-${i}`] = slider ? parseFloat(slider.value) : STAGE_CONFIG[`stage-${i}`].base;
        }
        return params;
    }

    function initReportControls() {
        // Report 버튼 클릭 시 API 호출
        const btnReport = document.getElementById('btn-report');
        if (btnReport) {
            btnReport.addEventListener('click', () => {
                const params = getCurrentSimulatedParams();
                
                fetch('/api/simulate_report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(params)
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success') {
                        lastReportData = data;
                        
                        // UI 텍스트 업데이트
                        document.getElementById('reportTime').innerText = new Date().toLocaleString('ko-KR');
                        document.getElementById('rep-usage').innerHTML = `${data.results.usage_kwh.toLocaleString()} <span class="text-lg text-slate-500">kWh</span>`;
                        document.getElementById('rep-psi').innerText = data.results.psi;
                        document.getElementById('rep-co2').innerHTML = `${data.results.co2_saved_kg.toLocaleString()} <span class="text-lg text-emerald-600/50">kg</span>`;
                        
                        // 인사이트 불릿 포인트 업데이트
                        const insightsUl = document.getElementById('rep-insights');
                        if (insightsUl) {
                            insightsUl.innerHTML = '';
                            data.insights.forEach(insight => {
                                const li = document.createElement('li');
                                li.className = "flex items-start gap-2";
                                // 마크다운 볼드체(**) 변환
                                let formattedText = insight.replace(/\*\*(.*?)\*\*/g, '<b class="text-white">$1</b>');
                                li.innerHTML = `<span class="text-cyan-500 mt-0.5">▪</span><span>${formattedText.substring(2)}</span>`;
                                insightsUl.appendChild(li);
                            });
                        }
                        
                        // 리포트 패널 노출 (부드러운 스크롤 포함)
                        const panel = document.getElementById('reportPanel');
                        if (panel) {
                            panel.classList.remove('hidden');
                            setTimeout(() => {
                                panel.scrollIntoView({ behavior: 'smooth', block: 'end' });
                            }, 100);
                        }
                    }
                })
                .catch(err => console.error("리포트 생성 중 오류:", err));
            });
        }

        // Export Data 버튼 클릭 시 Markdown 파일 다운로드
        const btnExport = document.getElementById('btn-export');
        if (btnExport) {
            btnExport.addEventListener('click', () => {
                if (!lastReportData) {
                    alert("먼저 'Report' 버튼을 눌러 시뮬레이션 결과를 생성해주세요.");
                    return;
                }
                
                const d = lastReportData;
                const dateStr = new Date().toLocaleString('ko-KR');
                
                let mdContent = `# 📊 스마트 팩토리 AI 공정 최적화 시뮬레이션 리포트\n\n`;
                mdContent += `**생성 일시:** ${dateStr}\n\n`;
                mdContent += `## 1. 입력 파라미터 설정 (Virtual Parameters)\n`;
                mdContent += `- 원료 투입량 (Iron Ore Feed): ${d.parameters['stage-1']} ton/h\n`;
                mdContent += `- 로 온도 (Furnace Temp): ${d.parameters['stage-2']} °C\n`;
                mdContent += `- 모터 가동률 (Motor Rate): ${d.parameters['stage-3']} %\n`;
                mdContent += `- 콘덴서 가동률 (Capacitor Rate): ${d.parameters['stage-4']} %\n`;
                mdContent += `- 목표 탄소 함량 (Carbon Content): ${d.parameters['stage-5']} %\n\n`;
                
                mdContent += `## 2. 예측 결과 (Simulated Outcomes)\n`;
                mdContent += `- **예측 전력 사용량:** ${d.results.usage_kwh} kWh\n`;
                mdContent += `- **공정 스트레스 지수 (PSI):** ${d.results.psi} / 100\n`;
                mdContent += `- **CO2 저감 효과:** ${d.results.co2_saved_kg} kg\n\n`;
                
                mdContent += `## 3. AI 전문가 인사이트 (AI Expert Insights)\n`;
                d.insights.forEach(msg => { mdContent += `${msg}\n`; });
                
                const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `AI_Simulation_Report_${Date.now()}.md`;
                link.click();
                URL.revokeObjectURL(link.href);
            });
        }
    }

    // [5] 탭 및 테마 등 기본 UI 유틸리티
    const initTabs = () => {
        const tabBtns = document.querySelectorAll(".tab-btn");
        const views = document.querySelectorAll("[data-view]");
        tabBtns.forEach(btn => btn.addEventListener("click", () => {
            const tabName = btn.dataset.tab;
            tabBtns.forEach(b => b.dataset.active = (b.dataset.tab === tabName ? "true" : "false"));
            views.forEach(v => v.classList.toggle("active", v.dataset.view === tabName));
        }));
    };

    // DOM 로드 완료 후 모든 기능 초기화
    document.addEventListener('DOMContentLoaded', () => {
        initTabs();
        initRealtimeStream();
        initReportControls();
        console.log("System Master Controller Ready.");
    });

})();