class DashboardClient {
    constructor() {
        this.apiKey = localStorage.getItem('sv_api_key');
        if (!this.apiKey) {
            window.location.href = '/';
            return;
        }

        this.init();
        this.startPolling();
    }

    init() {
        document.getElementById('api-key-display').innerText = this.apiKey;
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
    }

    updateInventory(inventory) {
        const list = document.getElementById('inventory-list');
        if (inventory.length === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 col-span-2 text-center uppercase">Cargo Empty</p>';
            return;
        }

        list.innerHTML = inventory.map(item => `
            <div class="bg-black/40 p-3 rounded-xl border border-slate-800 flex flex-col justify-center items-center text-center">
                <span class="text-[9px] text-slate-500 uppercase font-bold tracking-tighter mb-1">${item.type.replace('_', ' ')}</span>
                <span class="orbitron text-sm text-sky-400">${item.quantity}</span>
            </div>
        `).join('');
    }

    updateParts(parts) {
        const list = document.getElementById('parts-list');
        if (parts.length === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 uppercase text-center p-4">Standard Frame - No Attachments</p>';
            return;
        }

        list.innerHTML = parts.map(part => `
            <div class="bg-indigo-900/10 p-4 rounded-xl border border-indigo-500/20 flex justify-between items-center">
                <div>
                   <h4 class="text-xs text-indigo-300 font-bold uppercase">${part.name}</h4>
                   <p class="text-[9px] text-slate-500 uppercase">${part.type}</p>
                </div>
                <div class="text-right">
                    <span class="orbitron text-xs text-indigo-400">+${part.stats.power || 0}</span>
                </div>
            </div>
        `).join('');
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

    startPolling() {
        this.pollData();
        setInterval(() => this.pollData(), 1000);
    }
}

function logout() {
    localStorage.removeItem('sv_api_key');
    window.location.href = '/';
}

window.addEventListener('DOMContentLoaded', () => {
    new DashboardClient();
});
