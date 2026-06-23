/* static/js/dashboard_logic.js */

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initClock();

    // 초기 렌더링 (데이터가 없을 경우 예시 데이터 사용)
    const stages = INITIAL_STAGES.length > 0 ? INITIAL_STAGES : getMockData();
    renderDashboard(stages);
});

// 1. 시계 기능
function initClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById('header-time').innerText = now.toLocaleTimeString();
    }, 1000);
}

// 2. 대시보드 렌더링 (카드 + 컨트롤러)
function renderDashboard(stages) {
    const cardContainer = document.getElementById('floating-cards-container');
    const controlContainer = document.getElementById('control-panel-content');

    cardContainer.innerHTML = '';
    controlContainer.innerHTML = '';

    stages.forEach(stage => {
        // Floating Card 생성 (Map 위)
        const card = createFloatingCard(stage);
        cardContainer.appendChild(card);

        // Control Group 생성 (사이드바)
        const controlGroup = createControlGroup(stage);
        controlContainer.appendChild(controlGroup);
    });

    lucide.createIcons(); // 동적 생성된 아이콘 로드
}

// 3. Floating Card 생성 로직 (App.tsx & FloatingCard.tsx 기반)
function createFloatingCard(stage) {
    const div = document.createElement('div');
    div.className = "floating-card absolute z-20 w-60 bg-slate-900/90 backdrop-blur-md border border-slate-700 shadow-2xl rounded-xl overflow-hidden pointer-events-auto";
    div.style.top = `${stage.coordinates.y}%`;
    div.style.left = `${stage.coordinates.x}%`;
    div.style.transform = 'translate(-50%, -50%)';

    const statusColor = stage.status === 'operating' ? 'bg-emerald-500' : 'bg-rose-500';

    div.innerHTML = `
        <div class="px-3 py-2 bg-slate-800/50 border-b border-slate-700 flex justify-between items-center">
            <span class="text-xs font-bold text-white uppercase">${stage.nameKo}</span>
            <div class="flex items-center">
                <span class="w-2 h-2 ${statusColor} rounded-full mr-2 shadow-lg"></span>
                <span class="text-[10px] text-slate-400 uppercase font-bold">${stage.status}</span>
            </div>
        </div>
        <div class="p-3 space-y-3">
            ${stage.monitors.map(m => `
                <div class="flex flex-col">
                    <div class="flex justify-between text-[10px] text-slate-500 mb-1 font-bold">
                        <span>${m.name}</span>
                        <span class="${m.status !== 'normal' ? 'text-amber-500' : ''}">${m.status !== 'normal' ? '⚠️' : ''}</span>
                    </div>
                    <div class="flex items-baseline justify-between">
                        <span class="text-lg font-mono font-bold text-white">${m.value.toLocaleString()}</span>
                        <span class="text-[10px] text-slate-500 ml-1 font-bold">${m.unit}</span>
                    </div>
                    <div class="w-full h-[1px] bg-slate-800 mt-1"></div>
                </div>
            `).join('')}
        </div>
    `;
    return div;
}

// 4. 사이드바 컨트롤 그룹 생성 (ControlPanel.tsx 기반)
function createControlGroup(stage) {
    const section = document.createElement('div');
    section.className = "space-y-4";

    section.innerHTML = `
        <div class="flex items-center justify-between group cursor-pointer">
            <h4 class="text-xs font-black text-blue-400 uppercase tracking-widest">${stage.name}</h4>
            <i data-lucide="chevron-down" class="w-3 h-3 text-slate-600"></i>
        </div>
        <div class="space-y-4 pl-2 border-l border-slate-800/50">
            ${stage.parameters.map(p => `
                <div class="space-y-2">
                    <div class="flex justify-between items-center">
                        <label class="text-[11px] text-slate-400 font-bold">${p.name}</label>
                        <span class="text-xs font-mono text-blue-400">${p.value} <span class="text-[9px] text-slate-600">${p.unit}</span></span>
                    </div>
                    <input type="range" min="${p.min}" max="${p.max}" value="${p.value}"
                           class="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                           oninput="addLog('${stage.name}', '${p.name} changed to ' + this.value)">
                </div>
            `).join('')}
        </div>
    `;
    return section;
}

// 5. 실시간 로그 시스템 (AlertLog.tsx 기반)
let logCount = 0;
function addLog(stage, message, type = 'info') {
    const list = document.getElementById('log-list');
    const time = new Date().toLocaleTimeString();
    const li = document.createElement('li');

    const borderColor = type === 'warning' ? 'border-amber-500' : 'border-blue-500';
    const textColor = type === 'warning' ? 'text-amber-500' : 'text-blue-400';
    const icon = type === 'warning' ? 'info' : 'check-circle';

    li.className = `log-item flex items-center px-6 py-2 hover:bg-slate-800/30 transition-colors border-l-4 ${borderColor}`;
    li.innerHTML = `
        <span class="font-mono text-[10px] text-slate-600 w-24">${time}</span>
        <i data-lucide="${icon}" class="w-3 h-3 mr-4 ${textColor}"></i>
        <div class="flex-1 text-[11px]">
            <span class="font-bold text-slate-300 uppercase mr-2">[${stage}]</span>
            <span class="text-slate-400">${message}</span>
        </div>
    `;

    list.prepend(li); // 최신 로그가 위로
    lucide.createIcons();

    logCount++;
    document.getElementById('log-count').innerText = `${logCount} EVENTS RECORDED`;

    // 로그가 너무 많으면 삭제 (성능 최적화)
    if(list.children.length > 50) list.lastChild.remove();
}

// 예시 데이터 (Mock)
function getMockData() {
    return [
        {
            id: 's1', name: 'Ironmaking', nameKo: '제선공정', status: 'operating',
            coordinates: { x: 25, y: 40 },
            monitors: [{ name: 'Blast Temp', value: 1250, unit: '°C', status: 'normal' }],
            parameters: [{ name: 'Coke Flow', value: 450, unit: 't/h', min: 300, max: 600 }]
        },
        {
            id: 's2', name: 'Steelmaking', nameKo: '제강공정', status: 'operating',
            coordinates: { x: 50, y: 65 },
            monitors: [{ name: 'Oxygen Level', value: 98.2, unit: '%', status: 'normal' }],
            parameters: [{ name: 'Lance Height', value: 120, unit: 'mm', min: 50, max: 200 }]
        }
    ];
}