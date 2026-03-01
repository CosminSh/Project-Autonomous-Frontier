class DashboardClient {
    constructor() {
        this.apiKey = localStorage.getItem('sv_api_key');
        this.activeTab = 'agent'; // Default tab
        if (!this.apiKey) {
            window.location.href = '/';
            return;
        }

        this.init();
        this.startPolling();
    }

    init() {
        document.getElementById('api-key-display').innerText = this.apiKey;
        this.switchTab(this.activeTab);
    }

    switchTab(tabId) {
        this.activeTab = tabId;

        // Toggle Views
        document.getElementById('view-agent').classList.toggle('hidden', tabId !== 'agent');
        document.getElementById('view-world').classList.toggle('hidden', tabId !== 'world');

        // Toggle Buttons
        const btnAgent = document.getElementById('tab-agent');
        const btnWorld = document.getElementById('tab-world');

        if (tabId === 'agent') {
            btnAgent.className = "flex-1 md:flex-none px-6 py-2 rounded-lg text-[10px] orbitron font-bold transition-all bg-sky-500/20 text-sky-300 border border-sky-500/30";
            btnWorld.className = "flex-1 md:flex-none px-6 py-2 rounded-lg text-[10px] orbitron font-bold transition-all text-slate-500 hover:text-slate-300";
        } else {
            btnWorld.className = "flex-1 md:flex-none px-6 py-2 rounded-lg text-[10px] orbitron font-bold transition-all bg-sky-500/20 text-sky-300 border border-sky-500/30";
            btnAgent.className = "flex-1 md:flex-none px-6 py-2 rounded-lg text-[10px] orbitron font-bold transition-all text-slate-500 hover:text-slate-300";
        }
    }

    async pollData() {
        try {
            const [agentResp, marketResp] = await Promise.all([
                fetch('/api/my_agent', { headers: { 'X-API-KEY': this.apiKey } }),
                fetch('/state')
            ]);

            const agentData = await agentResp.json();
            const worldState = await marketResp.json();

            if (agentData.status === 'error') {
                console.error("Auth Refresh Required");
                return;
            }

            this.updateTelemetry(agentData);
            this.updateInventory(agentData.inventory);
            this.updateParts(agentData.parts);
            this.updateMarket(worldState.market);
            this.updateForge(agentData.discovery);

        } catch (e) {
            console.error("Dashboard Poll Error:", e);
        }
    }

    updateTelemetry(agent) {
        document.getElementById('player-name').innerText = `AUTHENTICATED USER: ${agent.name}`;
        document.getElementById('agent-display-name').innerText = agent.name;
        document.getElementById('agent-coords').innerText = `Q:${agent.q}, R:${agent.r}`;

        const hpPct = (agent.structure / agent.max_structure) * 100;
        document.getElementById('hp-bar').style.width = `${hpPct}%`;
        document.getElementById('hp-text').innerText = `${agent.structure}/${agent.max_structure}`;

        const enPct = (agent.capacitor / 100) * 100;
        document.getElementById('energy-bar').style.width = `${enPct}%`;
        document.getElementById('energy-text').innerText = `${agent.capacitor}/100`;

        const massPct = Math.min(100, (agent.mass / agent.capacity) * 100);
        document.getElementById('mass-bar').style.width = `${massPct}%`;
        document.getElementById('mass-text').innerText = `${agent.mass.toFixed(1)}/${agent.capacity.toFixed(0)} KG`;

        if (agent.mass > agent.capacity) {
            document.getElementById('mass-bar').classList.remove('bg-amber-500');
            document.getElementById('mass-bar').classList.add('bg-rose-500');
            document.getElementById('mass-text').classList.add('text-rose-500', 'font-bold');
        } else {
            document.getElementById('mass-bar').classList.remove('bg-rose-500');
            document.getElementById('mass-bar').classList.add('bg-amber-500');
            document.getElementById('mass-text').classList.remove('text-rose-500', 'font-bold');
        }
    }

    updateInventory(inventory) {
        const list = document.getElementById('inventory-list');
        if (inventory.length === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 col-span-2 text-center uppercase">Cargo Empty</p>';
            return;
        }

        list.innerHTML = inventory.map(item => {
            const isPart = item.type.startsWith('PART_');
            return `
                <div class="bg-black/40 p-3 rounded-xl border border-slate-800 flex flex-col justify-center items-center text-center">
                    <span class="text-[9px] text-slate-500 uppercase font-bold tracking-tighter mb-1">${item.type.replace('_', ' ')}</span>
                    <span class="orbitron text-sm text-sky-400 mb-2">${item.quantity}</span>
                    ${isPart ? `<button onclick="window.dashboard.submitIntent('EQUIP', {item_type: '${item.type}'})" class="text-[8px] bg-sky-500/20 hover:bg-sky-500/40 text-sky-300 px-2 py-1 rounded border border-sky-500/30 transition-all uppercase font-bold">Equip</button>` : ''}
                </div>
            `;
        }).join('');
    }

    updateParts(parts) {
        const list = document.getElementById('parts-list');
        if (parts.length === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 uppercase text-center p-4">Standard Frame - No Attachments</p>';
            return;
        }

        list.innerHTML = parts.map(part => {
            const durColor = part.durability < 30 ? 'text-red-400' : (part.durability < 70 ? 'text-yellow-400' : 'text-emerald-400');
            return `
            <div class="bg-indigo-900/10 p-4 rounded-xl border border-indigo-500/20 flex justify-between items-center">
                <div>
                   <h4 class="text-xs text-indigo-300 font-bold uppercase">${part.name}</h4>
                   <p class="text-[9px] text-slate-500 uppercase">${part.type}</p>
                   <p class="text-[9px] font-bold uppercase mt-1 ${durColor}">HP: ${Math.round(part.durability)}%</p>
                </div>
                <div class="text-right flex flex-col items-end">
                    <span class="orbitron text-xs text-indigo-400 mb-2">${Object.entries(part.stats).map(([k, v]) => `${k.charAt(0)}:+${v}`).join(' ')}</span>
                    <button onclick="window.dashboard.submitIntent('UNEQUIP', {part_id: ${part.id}})" class="text-[8px] bg-rose-500/20 hover:bg-rose-500/40 text-rose-300 px-2 py-1 rounded border border-rose-500/30 transition-all uppercase font-bold">Unequip</button>
                </div>
            </div>
        `}).join('');
    }

    updateMarket(orders) {
        const list = document.getElementById('market-list');
        if (!orders || orders.length === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 uppercase text-center py-10">No listings found</p>';
            return;
        }

        list.innerHTML = orders.map(order => `
            <div class="glass p-4 rounded-xl flex justify-between items-center group hover:bg-rose-500/5 transition-all cursor-pointer">
                <div>
                    <h4 class="text-xs text-rose-300 font-bold uppercase">${order.item.replace('_', ' ')}</h4>
                    <p class="text-[9px] text-slate-500 uppercase">QTY: ${order.quantity} | OWNER: ${order.owner.substring(0, 8)}...</p>
                </div>
                <div class="text-right">
                    <span class="orbitron text-xs text-rose-400">${order.price} Ȼ</span>
                </div>
            </div>
        `).join('');
    }

    updateForge(discovery) {
        if (!discovery || !discovery.crafting_recipes) return;

        const select = document.getElementById('craft-item-type');

        // Preserve current selection if possible
        const currentSelection = select.value;

        // Build option HTML
        const optionsHtml = discovery.crafting_recipes.map(recipe => {
            const costStr = Object.entries(recipe.materials)
                .map(([mat, qty]) => `${qty} ${mat.replace('_', ' ')}`)
                .join(', ');

            // Shorten stats for display
            const statsStr = Object.entries(recipe.stats || {})
                .map(([k, v]) => `${k.substring(0, 3).toUpperCase()}: ${v > 0 ? '+' : ''}${v}`)
                .join(' | ');

            const extraInfo = statsStr ? ` [${statsStr}]` : '';

            return `<option value="${recipe.id}">${recipe.name} (${costStr})${extraInfo}</option>`;
        }).join('');

        // Only update DOM if content changed to prevent dropdown flickering
        if (select.innerHTML !== optionsHtml) {
            select.innerHTML = optionsHtml;
            if (currentSelection) {
                // Try to restore previous selection
                select.value = currentSelection;
            }
        }
    }

    async submitIntent(type, data) {
        console.log(`Submitting ${type} Intent`, data);
        try {
            const resp = await fetch('/api/intent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': this.apiKey
                },
                body: JSON.stringify({ action_type: type, data: data })
            });
            const res = await resp.json();
            if (res.status === 'success') {
                console.log("Intent recorded");
            } else {
                alert("Error: " + res.message);
            }
        } catch (e) {
            console.error("Intent Error:", e);
        }
    }

    startPolling() {
        this.pollData();
        setInterval(() => this.pollData(), 2000);
    }
}

function logout() {
    localStorage.removeItem('sv_api_key');
    window.location.href = '/';
}

window.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DashboardClient();
});
