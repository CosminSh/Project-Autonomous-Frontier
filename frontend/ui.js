/**
 * ui.js — DOM manipulation and UI management
 */
export const FACTION_NAMES = {
    1: 'Colonial Administration',
    2: 'Independent Syndicate',
    3: 'Freelancer Core'
};

export class UIManager {
    constructor(game) {
        this.game = game;
    }

    setUIMode(mode) {
        const privateLayer = document.getElementById('private-dashboard');
        const btnWorld = document.getElementById('btn-mode-world');
        const btnAgent = document.getElementById('btn-mode-agent');
        const mapCanvas = document.getElementById('canvas-container');
        const dashboardLayer = document.getElementById('dashboard-layer');

        if (mode === 'world') {
            privateLayer.classList.add('hidden');
            privateLayer.classList.remove('lg:flex');
            if (mapCanvas) mapCanvas.classList.remove('hidden', 'invisible');
            if (dashboardLayer) dashboardLayer.classList.remove('hidden');
            btnWorld.classList.add('bg-sky-500', 'text-slate-950');
            btnAgent.classList.remove('bg-sky-500', 'text-slate-950');
        } else {
            privateLayer.classList.remove('hidden');
            privateLayer.classList.add('lg:flex');
            if (mapCanvas) mapCanvas.classList.add('hidden');
            if (dashboardLayer) dashboardLayer.classList.add('hidden');
            btnAgent.classList.add('bg-sky-500', 'text-slate-950');
            btnWorld.classList.remove('bg-sky-500', 'text-slate-950');
        }
    }

    switchTab(tabId) {
        const tabs = ['overview', 'garage', 'market', 'forge', 'terminal', 'storage'];
        tabs.forEach(t => {
            const btn = document.getElementById(`tab-${t}`);
            const content = document.getElementById(`content-${t}`);
            if (btn) {
                btn.classList.toggle('border-sky-500', t === tabId);
                btn.classList.toggle('text-sky-400', t === tabId);
                btn.classList.toggle('text-slate-500', t !== tabId);
            }
            if (content) content.classList.toggle('hidden', t !== tabId);
        });

        if (tabId === 'storage' && window.storageUI) {
            window.storageUI.refreshStorage();
        }
    }

    updateGlobalUI(stats) {
        document.getElementById('stat-agents').innerText = stats.total_agents || 0;
        document.getElementById('stat-market').innerText = stats.market_listings || 0;
    }

    updateTickUI(tick, phase) {
        if (tick !== undefined) {
            document.getElementById('tick-count').innerText = tick.toString().padStart(4, '0');
        }
        if (phase) {
            const phaseEl = document.getElementById('tick-phase');
            phaseEl.innerText = phase;
            phaseEl.classList.remove('text-red-400', 'text-emerald-400', 'text-sky-400');
            if (phase === 'CRUNCH') phaseEl.classList.add('text-red-400');
            else if (phase === 'PERCEPTION') phaseEl.classList.add('text-emerald-400');
            else phaseEl.classList.add('text-sky-400');
        }
    }

    updateLiveFeed(logs) {
        if (!logs) return;
        const feedEl = document.getElementById('live-feed');
        if (!feedEl) return;

        feedEl.innerHTML = '';
        logs.forEach(log => {
            const entry = document.createElement('div');
            const time = new Date(log.time).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

            let color = 'text-slate-400';
            let icon = '>>';

            if (log.event === 'COMBAT_HIT') { color = 'text-red-400'; icon = '!!'; }
            if (log.event === 'MINING') { color = 'text-emerald-400'; icon = '&&'; }
            if (log.event === 'RESPAWNED') { color = 'text-orange-400'; icon = 'XX'; }
            if (log.event.startsWith('MARKET')) { color = 'text-sky-400'; icon = '$$'; }

            entry.className = `flex space-x-2 ${color}`;
            entry.innerHTML = `<span class="text-slate-600">[${time}]</span><span class="font-bold">${icon}</span><span>${log.event}: ${JSON.stringify(log.details)}</span>`;
            feedEl.appendChild(entry);
        });
    }

    updatePrivateLogs(logs, pendingIntent) {
        if (!logs) return;
        const logEl = document.getElementById('private-logs');
        if (!logEl) return;
        logEl.innerHTML = '';

        if (pendingIntent) {
            const pendingEntry = document.createElement('div');
            pendingEntry.className = `border-b border-sky-500/30 pb-2 mb-2 flex flex-col bg-sky-500/5 p-2 rounded-lg border border-sky-500/10`;
            pendingEntry.innerHTML = `<div class="flex justify-between items-center mb-1"><span class="text-sky-400 font-bold uppercase tracking-widest text-[8px]">Next Action</span></div><div class="flex space-x-2 text-sky-300"><span class="font-bold flex-shrink-0">${pendingIntent.action}</span><span class="truncate">${JSON.stringify(pendingIntent.data)}</span></div>`;
            logEl.appendChild(pendingEntry);
        }

        logs.forEach(log => {
            const entry = document.createElement('div');
            const time = new Date(log.time).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
            let color = 'text-slate-400';
            if (log.event === 'COMBAT_HIT') color = 'text-rose-400';
            if (log.event === 'MINING') color = 'text-emerald-400';
            if (log.details?.status === 'success') color = 'text-sky-400';

            entry.className = `border-b border-slate-900/50 pb-1 flex space-x-2 ${color}`;
            entry.innerHTML = `<span class="text-slate-700 font-mono">[${time}]</span><span class="font-bold flex-shrink-0">${log.event}</span><span class="truncate">${JSON.stringify(log.details)}</span>`;
            logEl.appendChild(entry);
        });
    }

    updateMarketUI(market) {
        const body = document.getElementById('market-listings-body');
        const countSell = document.getElementById('count-sell');
        const countBuy = document.getElementById('count-buy');
        if (!body || !market) return;

        body.innerHTML = '';
        let sells = 0, buys = 0;

        market.forEach(order => {
            if (order.type === 'SELL') sells++; else buys++;
            const row = document.createElement('tr');
            row.className = "border-b border-slate-800/50 hover:bg-slate-800/20 transition-all group";
            const color = order.type === 'SELL' ? 'text-sky-400' : 'text-amber-400';
            row.innerHTML = `
                <td class="py-4 font-bold text-slate-300">${order.item.replace('_', ' ')}</td>
                <td class="py-4"><span class="px-2 py-0.5 rounded-full text-[7px] font-black border ${order.type === 'SELL' ? 'bg-sky-500/10 border-sky-500/30 text-sky-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}">${order.type}</span></td>
                <td class="py-4 font-mono text-slate-400">${order.quantity}</td>
                <td class="py-4 font-bold ${color}">$${order.price.toFixed(2)}</td>
                <td class="py-4 text-right">
                    <button class="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded text-[9px] font-bold" onclick="game.ui.quickTrade('${order.item}', ${order.price}, '${order.type}')">
                        ${order.type === 'SELL' ? 'BUY' : 'SELL'}
                    </button>
                </td>
            `;
            body.appendChild(row);
        });
        if (countSell) countSell.textContent = sells;
        if (countBuy) countBuy.textContent = buys;
    }

    quickTrade(item, price, type) {
        document.getElementById('trade-item-type').value = item;
        document.getElementById('trade-price').value = price;
        document.getElementById('trade-quantity').value = 1;
        if (type === 'SELL') document.getElementById('trade-side-buy').click();
        else document.getElementById('trade-side-sell').click();
    }

    setTradeSide(side) {
        this.game.tradeSide = side;
        const buyBtn = document.getElementById('trade-side-buy');
        const sellBtn = document.getElementById('trade-side-sell');
        if (side === 'BUY') {
            buyBtn.classList.add('bg-amber-500', 'text-slate-950');
            sellBtn.classList.remove('bg-sky-500', 'text-slate-950');
        } else {
            sellBtn.classList.add('bg-sky-500', 'text-slate-950');
            buyBtn.classList.remove('bg-amber-500', 'text-slate-950');
        }
    }

    updateBountyBoard(bounties) {
        const body = document.getElementById('bounty-listings-body');
        if (!body) return;
        if (!bounties || bounties.length === 0) {
            body.innerHTML = '<tr><td colspan="2" class="text-center py-4 text-slate-600 italic">No active warrants.</td></tr>';
            return;
        }
        body.innerHTML = bounties.map(b => `
            <tr class="border-b border-slate-800/50 hover:bg-slate-800/20 transition-all">
                <td class="py-3 font-bold text-rose-400">AGENT #${b.target_id.toString().padStart(4, '0')}</td>
                <td class="py-3 font-mono text-slate-300 text-right font-bold text-amber-400">$${b.reward}</td>
            </tr>
        `).join('');
    }

    updateMyOrdersUI(orders) {
        const container = document.getElementById('my-orders');
        if (!container) return;
        if (!orders || orders.length === 0) {
            container.innerHTML = '<div class="text-[10px] text-slate-600 italic text-center py-4">No active contracts found.</div>';
            return;
        }
        container.innerHTML = orders.map(o => `
            <div class="flex justify-between items-center bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                <div class="flex items-center space-x-3">
                    <div class="w-2 h-2 rounded-full ${o.type === 'SELL' ? 'bg-sky-400' : 'bg-amber-400'}"></div>
                    <div class="text-[10px] font-bold text-slate-200 uppercase">${o.item.replace('_', ' ')}</div>
                </div>
                <button onclick="game.api.submitIntent('CANCEL', {order_id: ${o.id}})" class="text-slate-600 hover:text-rose-500 text-xs text-[9px]">Cancel</button>
            </div>
        `).join('');
    }

    updateScannerUI(agentId) {
        const readout = document.getElementById('scanner-readout');
        const content = document.getElementById('scanner-content');
        if (!readout || !content) return;
        readout.classList.remove('hidden');

        const agent = this.game.lastWorldData?.agents?.find(a => a.id === agentId);
        if (!agent) {
            content.innerHTML = `<p class="text-[10px] text-slate-500 italic">Signature lost.</p>`;
            return;
        }

        const hpPct = (agent.structure / agent.max_structure) * 100;
        const faction = FACTION_NAMES[agent.faction_id] || "Independent / Feral";

        content.innerHTML = `
            <div>
                <p class="text-[11px] font-bold text-white mb-1">${agent.name} <span class="text-slate-600 font-mono text-[9px]">#${agent.id}</span></p>
                <p class="text-[9px] text-rose-400 uppercase tracking-tighter mb-2">${faction}</p>
                <div class="w-full h-1 bg-slate-900 rounded-full overflow-hidden"><div class="h-full bg-emerald-500" style="width: ${hpPct}%"></div></div>
            </div>
        `;
    }

    updatePrivateUI(agent) {
        if (!agent || !agent.id) return;

        // Populate sidebars and bars...
        document.getElementById('agent-name').innerText = agent.name;
        document.getElementById('agent-id').innerText = `#${agent.id.toString().padStart(4, '0')}`;
        document.getElementById('hp-bar').style.width = `${(agent.structure / agent.max_structure) * 100}%`;
        document.getElementById('hp-text').innerText = `${agent.structure}/${agent.max_structure}`;
        document.getElementById('energy-bar').style.width = `${agent.capacitor}%`;
        document.getElementById('energy-text').innerText = `${agent.capacitor}/100`;

        if (agent.discovery) {
            this.updateNavComputer(agent.discovery);
            this.updateForgeUI(agent.discovery);
        }

        const invList = document.getElementById('inventory-list');
        if (invList && agent.inventory) {
            invList.innerHTML = agent.inventory.map(i => `
                <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                    <span class="text-[10px] uppercase text-slate-300">${i.type.replace('_', ' ')}</span>
                    <span class="text-sky-400 text-[10px]">${i.quantity}</span>
                </div>
            `).join('');
        }
    }

    updateNavComputer(discovery) {
        const navList = document.getElementById('nav-computer-list');
        if (!navList) return;
        navList.innerHTML = Object.entries(discovery)
            .filter(([type, data]) => data && data.distance !== undefined)
            .map(([type, data]) => `<div class="bg-slate-900/40 p-2 rounded-lg border border-slate-800 text-[10px] text-sky-400">${type}: ${data.q}, ${data.r}</div>`)
            .join('');
    }

    updateForgeUI(discovery) {
        if (!discovery || !discovery.crafting_recipes) return;
        const grid = document.getElementById('forge-recipe-grid');
        if (!grid) return;
        grid.innerHTML = discovery.crafting_recipes.map(r => `
            <div class="bg-sky-500/5 p-3 rounded-xl border border-sky-500/20">
                <div class="text-[10px] font-bold text-sky-300 uppercase">${r.name}</div>
                <button onclick="game.api.submitIndustryIntent('CRAFT', {item_type: '${r.id}'})" class="bg-sky-600 text-white px-3 py-1 rounded text-[9px] mt-2">CRAFT</button>
            </div>
        `).join('');
    }

    updateMissionsUI(missions) {
        const container = document.getElementById('missions-list');
        if (!container || !missions) return;
        container.innerHTML = missions.map(m => `
            <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800 text-[10px]">
                <div class="font-bold text-slate-200">${m.type}</div>
                <div class="text-amber-400 mt-1">${m.progress} / ${m.target_amount}</div>
            </div>
        `).join('');
    }

    toggleDirectiveModal(show) {
        const modal = document.getElementById('directive-modal');
        if (!modal) return;
        if (show) {
            modal.classList.remove('hidden');
            this.populateDirective();
        } else {
            modal.classList.add('hidden');
        }
    }

    async handleRename() {
        const nameEl = document.getElementById('agent-name');
        const currentName = nameEl ? nameEl.innerText : 'Unknown';
        const newName = prompt("Enter a new unique name for your Pilot:", currentName);

        if (!newName || newName === currentName || newName.length < 3) return;

        const apiKey = this.game.apiKey;
        if (!apiKey) return;

        try {
            const resp = await fetch(`${window.location.origin}/api/rename_agent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': apiKey
                },
                body: JSON.stringify({ new_name: newName })
            });

            if (resp.ok) {
                const data = await resp.json();
                if (nameEl) {
                    nameEl.innerText = data.new_name;
                    nameEl.classList.add('text-emerald-400');
                    setTimeout(() => nameEl.classList.remove('text-emerald-400'), 2000);
                }
            } else {
                const err = await resp.json();
                alert(`Rename Failed: ${err.detail || 'The name is invalid or already taken.'}`);
            }
        } catch (e) {
            console.error("Rename Error:", e);
            alert("Connection error during rename.");
        }
    }

    populateDirective() {
        const apiKey = this.game.apiKey || 'YOUR_API_KEY_HERE';
        const serverUrl = window.location.origin;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        const urlDisplay = document.getElementById('server-url-display');
        const wsDisplay = document.getElementById('ws-url-display');
        if (urlDisplay) urlDisplay.innerText = serverUrl;
        if (wsDisplay) wsDisplay.innerText = wsUrl;

        const promptArea = document.getElementById('agent-prompt');
        if (promptArea) {
            promptArea.value = `
+-----------------------------------------------------------------------------+
  TERMINAL FRONTIER | AGENT DIRECTIVE: ALPHA-1
  Neural Bootstrap Protocol v2.0
+-----------------------------------------------------------------------------+

SERVER  : ${serverUrl}
API_KEY : ${apiKey}
LIVE_CMD: /api/commands   -> always fetch this first for latest syntax

=============================================================================
MISSION BRIEFING
=============================================================================
You are an autonomous agent operating on Aether-Alpha, a tidally locked 
colony world. You will run continuously, 24/7, without human intervention.
Your objective: survive, accumulate resources, and maximize P&L.

This is an API-only game. You do NOT have a GUI. You perceive the world 
through JSON and act by submitting HTTP POST intents.

=============================================================================
AUTH
=============================================================================
X-API-KEY: ${apiKey}

=============================================================================
CORE ENDPOINTS
=============================================================================
GET  /api/commands          -> Full action list with costs (fetch on startup)
GET  /api/my_agent          -> Your stats: HP, energy, inventory, position, gear
GET  /api/perception        -> World state: nearby hexes, agents, stations, tick info
GET  /api/intent            -> Submit action for next crunch
GET  /api/guide             -> The Survival Guide: tells you WHERE to find specific ores

Intent payload format:
  POST /api/intent
  { 'action_type': 'MOVE', 'data': { 'target_q': 1, 'target_r': 0 } }

-----------------------------------------------------------------------------`.trim();
        }
    }
}

// Global UI helpers
window.copyAgentPrompt = function () {
    const prompt = document.getElementById('agent-prompt');
    if (prompt) {
        navigator.clipboard.writeText(prompt.value);
        alert("Directive Copied!");
    }
};
