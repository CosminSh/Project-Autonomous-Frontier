import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Global helper for the Directive Modal
const FACTION_NAMES = {
    1: 'Colonial Administration',
    2: 'Independent Syndicate',
    3: 'Freelancer Core'
};

window.copyAgentPrompt = function () {
    const prompt = document.getElementById('agent-prompt');
    const apiKey = localStorage.getItem('sv_api_key') || 'YOUR_API_KEY_HERE';
    const serverUrl = window.location.origin;

    // Dynamically inject current values for easy copy-paste
    let text = prompt.value;
    text = text.replace('[PASTE_SERVER_URL_HERE]', serverUrl);
    text = text.replace('[YOUR_API_KEY]', apiKey);

    navigator.clipboard.writeText(text);

    // Visual feedback
    const originalText = prompt.value;
    const btn = event?.target || document.querySelector('button[onclick="window.copyAgentPrompt()"]');
    if (btn) {
        const oldBtnText = btn.innerText;
        btn.innerText = 'COPIED!';
        setTimeout(() => btn.innerText = oldBtnText, 2000);
    }
}

class TerminalHandler {
    constructor(game) {
        this.game = game;
        this.input = document.getElementById('terminal-input');
        this.submitBtn = document.getElementById('terminal-submit');
        this.buffer = document.getElementById('terminal-buffer');
        this.suggestionsEl = document.getElementById('command-suggestions');

        this.commands = {
            'MOVE': { params: ['q', 'r'], help: 'MOVE <q> <r> - e.g. MOVE 1 -1 (Reposition agent)' },
            'MINE': { params: [], help: 'MINE - Extract resources from current hex' },
            'SCAN': { params: [], help: 'SCAN - Re-sync sensor telemetry' },
            'HELP': { params: [], help: 'HELP - Display command protocols' }
        };

        this.setupListeners();
    }

    setupListeners() {
        if (!this.input) return;

        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.submit();
            else this.handleSuggestions(e);
        });

        this.input.addEventListener('input', () => this.updateSuggestions());
        this.submitBtn?.addEventListener('click', () => this.submit());

        // Quick buttons
        document.getElementById('btn-quick-move')?.addEventListener('click', () => {
            this.input.value = 'MOVE ';
            this.input.focus();
        });
        document.getElementById('btn-quick-mine')?.addEventListener('click', () => {
            this.input.value = 'MINE';
            this.submit();
        });
        document.getElementById('btn-quick-scan')?.addEventListener('click', () => {
            this.input.value = 'SCAN';
            this.submit();
        });
        document.getElementById('btn-quick-help')?.addEventListener('click', () => {
            this.input.value = 'HELP';
            this.submit();
        });
    }

    log(msg, type = 'info') {
        const div = document.createElement('div');
        const colors = {
            info: 'text-slate-400',
            success: 'text-emerald-400',
            error: 'text-rose-400',
            system: 'text-sky-400'
        };
        div.className = `font-mono ${colors[type] || colors.info}`;
        const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        div.innerHTML = `<span class="opacity-30">[${time}]</span> ${msg}`;
        this.buffer.appendChild(div);
        this.buffer.scrollTop = this.buffer.scrollHeight;
    }

    updateSuggestions() {
        const val = this.input.value.toUpperCase().trim();
        if (!val) {
            this.suggestionsEl.classList.add('hidden');
            return;
        }

        const matches = Object.keys(this.commands).filter(c => c.startsWith(val));
        if (matches.length > 0) {
            this.suggestionsEl.innerHTML = matches.map(m =>
                `<div class="suggestion-item" onclick="game.terminal.useSuggestion('${m}')">${this.commands[m].help}</div>`
            ).join('');
            this.suggestionsEl.classList.remove('hidden');
        } else {
            this.suggestionsEl.classList.add('hidden');
        }
    }

    useSuggestion(cmd) {
        this.input.value = cmd + ' ';
        this.suggestionsEl.classList.add('hidden');
        this.input.focus();
    }

    handleSuggestions(e) {
        // Simple tab/arrow logic could go here if needed
    }

    async submit() {
        const raw = this.input.value.trim();
        if (!raw) return;

        this.input.value = '';
        this.suggestionsEl.classList.add('hidden');
        this.log(`&gt; ${raw}`, 'system');

        const parts = raw.split(/\s+/);
        const actionType = parts[0].toUpperCase();
        const args = parts.slice(1);

        if (actionType === 'HELP') {
            this.log("AVAILABLE PROTOCOLS:", "info");
            Object.values(this.commands).forEach(c => this.log(` - ${c.help}`, "info"));
            return;
        }

        if (!this.commands[actionType]) {
            this.log(`ERROR: PROTOCOL '${actionType}' NOT RECOGNIZED.`, 'error');
            return;
        }

        // Action Mapping
        let intent = { action_type: actionType, data: {} };

        try {
            if (actionType === 'MOVE') {
                if (args.length < 2) throw new Error("MOVE requires Q and R coordinates.");
                intent.data = { target_q: parseInt(args[0]), target_r: parseInt(args[1]) };
            } else if (actionType === 'MINE') {
                intent.data = {};
            } else if (actionType === 'SCAN') {
                this.log(`RE-SYNCHRONIZING SENSOR ARRAY...`, 'info');
                await this.game.pollState();
                this.log(`SYNCHRONIZATION COMPLETE. STATE UPDATED.`, 'success');
                return;
            }

            this.log(`TRANSMITTING DIRECTIVE: ${actionType}...`, 'info');

            const apiKey = localStorage.getItem('sv_api_key');
            const resp = await fetch(`${window.location.origin}/api/intent`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                body: JSON.stringify(intent)
            });

            const result = await resp.json();
            if (result.status === 'success' || resp.ok) {
                this.log(`UPLINK SUCCESS: ACTION QUEUED.`, 'success');
                if (result.message) this.log(`MSG: ${result.message}`, 'info');
                if (result.details) this.log(`DATA: ${JSON.stringify(result.details)}`, 'info');
            } else {
                const errorDetail = result.detail || result.message || 'Access Denied';
                this.log(`UPLINK REJECTED: ${errorDetail}`, 'error');
            }
        } catch (err) {
            this.log(`CRITICAL ERROR: ${err.message}`, 'error');
        }
    }
}

class GameClient {
    constructor() {
        window.game = this; // Set early to capture sync events
        this.miningEffectActive = false;
        this.tradeSide = 'SELL';
        this.isInitialized = false;

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.hexes = new Map();
        this.agents = new Map();
        this.selectedAgentId = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        // 1. Core Systems
        this.init();
        this.animate();

        // 2. Auth State (Must happen before polling)
        this.checkAuth();

        // 3. Network / Updates
        this.setupWebSocket();
        this.startPolling();

        // Setup UI Listeners
        document.getElementById('logout-btn').addEventListener('click', () => this.logout());
        document.getElementById('copy-api-btn').addEventListener('click', () => this.copyApiKey());
        const realignBtn = document.getElementById('realign-faction-btn');
        if (realignBtn) realignBtn.addEventListener('click', () => this.submitFactionRealignment());

        const renameTrigger = document.getElementById('rename-trigger');
        if (renameTrigger) renameTrigger.addEventListener('click', () => this.handleRename());

        // Mode Switcher Listeners
        document.getElementById('btn-mode-world').addEventListener('click', () => this.setUIMode('world'));
        document.getElementById('btn-mode-agent').addEventListener('click', () => this.setUIMode('management'));

        // Tab Listeners
        ['command', 'garage', 'market', 'industry', 'terminal'].forEach(tab => {
            const el = document.getElementById(`tab-${tab}`);
            if (el) el.addEventListener('click', () => this.switchTab(tab));
        });

        // Industry Listeners
        const btnSmelt = document.getElementById('btn-smelt');
        const btnCraft = document.getElementById('btn-craft');
        const btnRepair = document.getElementById('btn-repair');
        if (btnSmelt) btnSmelt.addEventListener('click', () => this.submitIndustryIntent('SMELT'));
        if (btnCraft) btnCraft.addEventListener('click', () => this.submitIndustryIntent('CRAFT'));
        if (btnRepair) btnRepair.addEventListener('click', () => this.submitIndustryIntent('REPAIR'));

        // Market Listeners
        const tradeSideBuy = document.getElementById('trade-side-buy');
        const tradeSideSell = document.getElementById('trade-side-sell');
        const tradeSubmit = document.getElementById('btn-submit-order');
        if (tradeSideBuy) tradeSideBuy.addEventListener('click', () => this.setTradeSide('BUY'));
        if (tradeSideSell) tradeSideSell.addEventListener('click', () => this.setTradeSide('SELL'));
        if (tradeSubmit) tradeSubmit.addEventListener('click', () => this.submitTradeIntent());

        // Directive Modal Listeners
        const openDirBtn = document.getElementById('open-directive-btn');
        const closeDirBtn = document.getElementById('close-directive-btn');
        const closeDirBtnFooter = document.getElementById('close-directive-btn-footer');
        const modal = document.getElementById('directive-modal');
        const overlay = document.getElementById('modal-overlay');

        if (openDirBtn) openDirBtn.addEventListener('click', () => this.toggleDirectiveModal(true));
        if (closeDirBtn) closeDirBtn.addEventListener('click', () => this.toggleDirectiveModal(false));
        if (closeDirBtnFooter) closeDirBtnFooter.addEventListener('click', () => this.toggleDirectiveModal(false));
        if (overlay) overlay.addEventListener('click', () => this.toggleDirectiveModal(false));

        // 4. Terminal Handler
        this.terminal = new TerminalHandler(this);

        this.isInitialized = true;
        this.processPendingAuth();
    }

    processPendingAuth() {
        if (window.pendingAuth) {
            console.log("Processing pending Google Auth...");
            const auth = window.pendingAuth;
            window.pendingAuth = null;
            this.handleLogin(auth);
        }
        if (window.pendingGuestLogin) {
            console.log("Processing pending Guest Login...");
            window.pendingGuestLogin = false;
            this.handleGuestLogin();
        }
    }

    setUIMode(mode) {
        const privateLayer = document.getElementById('private-dashboard');
        const btnWorld = document.getElementById('btn-mode-world');
        const btnAgent = document.getElementById('btn-mode-agent');

        // Hooks to elements to hide/show during UI switches
        const mapCanvas = document.getElementById('canvas-container');
        const worldInfo = document.getElementById('world-info-container');

        if (mode === 'world') {
            privateLayer.classList.add('hidden');

            if (mapCanvas) {
                mapCanvas.classList.remove('hidden');
                mapCanvas.style.display = 'block';
                mapCanvas.style.visibility = 'visible';
            }
            if (worldInfo) {
                worldInfo.classList.remove('hidden');
                worldInfo.classList.add('flex', 'flex-col');
                worldInfo.style.display = 'flex';
                worldInfo.style.visibility = 'visible';
            }

            btnWorld.classList.add('bg-sky-500', 'text-slate-950');
            btnWorld.classList.remove('text-slate-400');
            btnAgent.classList.remove('bg-sky-500', 'text-slate-950');
            btnAgent.classList.add('text-slate-400');
        } else {
            privateLayer.classList.remove('hidden');

            if (mapCanvas) {
                mapCanvas.classList.add('hidden');
                mapCanvas.style.display = 'none';
                mapCanvas.style.visibility = 'hidden';
            }
            if (worldInfo) {
                worldInfo.classList.add('hidden');
                worldInfo.classList.remove('flex', 'flex-col');
                worldInfo.style.display = 'none';
                worldInfo.style.visibility = 'hidden';
            }

            btnAgent.classList.add('bg-sky-500', 'text-slate-950');
            btnAgent.classList.remove('text-slate-400');
            btnWorld.classList.remove('bg-sky-500', 'text-slate-950');
            btnWorld.classList.add('text-slate-400');
        }
    }

    updateLiveFeed(logs) {
        if (!logs) return;
        const feedEl = document.getElementById('live-feed');
        if (!feedEl) return;

        // Clear and redraw
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
            entry.innerHTML = `
                <span class="text-slate-600">[${time}]</span>
                <span class="font-bold">${icon}</span>
                <span>${log.event}: ${JSON.stringify(log.details)}</span>
            `;
            feedEl.appendChild(entry);
        });
    }

    updatePrivateLogs(logs, pendingIntent) {
        if (!logs) return;
        const logEl = document.getElementById('private-logs');
        if (!logEl) return;

        logEl.innerHTML = '';

        // Add Pending Intent if exists
        if (pendingIntent) {
            const pendingEntry = document.createElement('div');
            pendingEntry.className = `border-b border-sky-500/30 pb-2 mb-2 flex flex-col bg-sky-500/5 p-2 rounded-lg border border-sky-500/10`;
            pendingEntry.innerHTML = `
                <div class="flex justify-between items-center mb-1">
                    <span class="text-sky-400 font-bold uppercase tracking-widest text-[8px]">Next scheduled Action</span>
                    <span class="text-[8px] text-slate-500 animate-pulse">PENDING RESOLUTION</span>
                </div>
                <div class="flex space-x-2 text-sky-300">
                    <span class="font-bold flex-shrink-0">${pendingIntent.action}</span>
                    <span class="truncate">${JSON.stringify(pendingIntent.data)}</span>
                </div>
            `;
            logEl.appendChild(pendingEntry);
        }

        logs.forEach(log => {
            const entry = document.createElement('div');
            const time = new Date(log.time).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

            let color = 'text-slate-400';
            if (log.event === 'COMBAT_HIT') color = 'text-rose-400';
            if (log.event === 'MINING') color = 'text-emerald-400';
            if (log.details && log.details.status === 'success') color = 'text-sky-400';

            entry.className = `border-b border-slate-900/50 pb-1 flex space-x-2 ${color}`;
            entry.innerHTML = `
                <span class="text-slate-700 font-mono">[${time}]</span>
                <span class="font-bold flex-shrink-0">${log.event}</span>
                <span class="truncate">${JSON.stringify(log.details)}</span>
            `;
            logEl.appendChild(entry);
        });
    }

    triggerVisualEffect(q, r, color) {
        const pos = this.hexToPixel(q, r);

        // Simple spark/flare
        const geom = new THREE.SphereGeometry(0.2, 8, 8);
        const mat = new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 1 });
        const mesh = new THREE.Mesh(geom, mat);
        mesh.position.set(pos.x, 0.5, pos.y);
        this.scene.add(mesh);

        // Animate out
        const duration = 1000;
        const start = Date.now();
        const animate = () => {
            const elapsed = Date.now() - start;
            const t = elapsed / duration;
            if (t >= 1) {
                this.scene.remove(mesh);
                return;
            }
            mesh.scale.set(1 + t * 3, 1 + t * 3, 1 + t * 3);
            mesh.material.opacity = 1 - t;
            requestAnimationFrame(animate);
        };
        animate();
    }

    switchTab(tabId) {
        const tabs = ['command', 'garage', 'market', 'industry', 'terminal'];
        tabs.forEach(t => {
            const content = document.getElementById(`content-${t}`);
            const btn = document.getElementById(`tab-${t}`);
            if (t === tabId) {
                content.classList.remove('hidden');
                btn.classList.add('border-b-2', 'border-sky-500', 'text-sky-400');
                btn.classList.remove('text-slate-500');
            } else {
                content.classList.add('hidden');
                btn.classList.remove('border-b-2', 'border-sky-500', 'text-sky-400');
                btn.classList.add('text-slate-500');
            }
        });
    }

    checkAuth() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (apiKey) {
            this.setAuthenticated(true);
        }
    }

    updateMarketUI(market) {
        const body = document.getElementById('market-listings-body');
        const countSell = document.getElementById('count-sell');
        const countBuy = document.getElementById('count-buy');
        if (!body || !market) return;

        body.innerHTML = '';
        let sells = 0;
        let buys = 0;

        market.forEach(order => {
            if (order.type === 'SELL') sells++;
            if (order.type === 'BUY') buys++;

            const row = document.createElement('tr');
            row.className = "border-b border-slate-800/50 hover:bg-slate-800/20 transition-all group";

            const color = order.type === 'SELL' ? 'text-sky-400' : 'text-amber-400';

            row.innerHTML = `
                <td class="py-4 font-bold text-slate-300">${order.item.replace('_', ' ')}</td>
                <td class="py-4"><span class="px-2 py-0.5 rounded-full text-[7px] font-black border ${order.type === 'SELL' ? 'bg-sky-500/10 border-sky-500/30 text-sky-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}">${order.type}</span></td>
                <td class="py-4 font-mono text-slate-400">${order.quantity}</td>
                <td class="py-4 font-bold ${color}">$${order.price.toFixed(2)}</td>
                <td class="py-4 text-right">
                    <button class="opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded text-[9px] font-bold" onclick="game.quickTrade('${order.item}', ${order.price}, '${order.type}')">
                        ${order.type === 'SELL' ? 'BUY' : 'SELL'}
                    </button>
                </td>
            `;
            body.appendChild(row);
        });

        if (countSell) countSell.textContent = sells;
        if (countBuy) countBuy.textContent = buys;
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
                    <div class="w-2 h-2 rounded-full ${o.type === 'SELL' ? 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.5)]' : 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]'}"></div>
                    <div>
                        <div class="text-[10px] font-bold text-slate-200 uppercase">${o.item.replace('_', ' ')}</div>
                        <div class="text-[8px] text-slate-500 uppercase tracking-widest">${o.type} CONTRACT</div>
                    </div>
                </div>
                <div class="flex items-center space-x-4">
                    <div class="text-right">
                        <div class="text-[10px] text-slate-200">$${o.price}</div>
                        <div class="text-[8px] text-slate-500">${o.quantity} UNITS</div>
                    </div>
                    <button onclick="game.submitIntent('CANCEL', {order_id: ${o.id}})" class="p-2 hover:bg-rose-500/10 rounded-lg group transition-all">
                        <span class="text-slate-600 group-hover:text-rose-500 text-xs">✕</span>
                    </button>
                </div>
            </div>
        `).join('');
    }

    quickTrade(item, price, type) {
        // Fill form and switch side
        document.getElementById('trade-item-type').value = item;
        document.getElementById('trade-price').value = price;
        document.getElementById('trade-quantity').value = 1;

        if (type === 'SELL') {
            document.getElementById('trade-side-buy').click();
        } else {
            document.getElementById('trade-side-sell').click();
        }
    }

    async submitFactionRealignment() {
        const factionSelect = document.getElementById('faction-select');
        const factionId = parseInt(factionSelect.value);
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;

        const btn = document.getElementById('realign-faction-btn');
        const oldText = btn.innerText;

        try {
            btn.disabled = true;
            btn.innerText = 'PROCESSING...';

            const resp = await fetch(`${window.location.origin}/api/intent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': apiKey
                },
                body: JSON.stringify({
                    action_type: 'CHANGE_FACTION',
                    data: { new_faction_id: factionId }
                })
            });

            if (resp.ok) {
                btn.innerText = 'INTENT SCHEDULED';
                setTimeout(() => {
                    btn.innerText = oldText;
                    btn.disabled = false;
                }, 2000);
            } else {
                const err = await resp.json();
                alert(`Realignment Failed: ${err.detail || 'Unknown error'}`);
                btn.innerText = 'FAILED';
                setTimeout(() => {
                    btn.innerText = oldText;
                    btn.disabled = false;
                }, 2000);
            }
        } catch (e) {
            console.error(e);
            btn.disabled = false;
            btn.innerText = oldText;
        }
    }

    async handleRename() {
        const currentName = document.getElementById('agent-name').innerText;
        const newName = prompt("Enter a new unique name for your Pilot:", currentName);

        if (!newName || newName === currentName || newName.length < 3) return;

        const apiKey = localStorage.getItem('sv_api_key');
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
                document.getElementById('agent-name').innerText = data.new_name;
                // Highlight success
                const nameEl = document.getElementById('agent-name');
                nameEl.classList.add('text-emerald-400');
                setTimeout(() => nameEl.classList.remove('text-emerald-400'), 2000);
            } else {
                const err = await resp.json();
                alert(`Rename Failed: ${err.detail || 'The name is invalid or already taken.'}`);
            }
        } catch (e) {
            console.error("Rename Error:", e);
            alert("Connection error during rename.");
        }
    }

    setTradeSide(side) {
        this.tradeSide = side;
        const buyBtn = document.getElementById('trade-side-buy');
        const sellBtn = document.getElementById('trade-side-sell');

        if (side === 'BUY') {
            buyBtn.classList.add('bg-amber-500', 'text-slate-950');
            buyBtn.classList.remove('text-slate-400');
            sellBtn.classList.remove('bg-sky-500', 'text-slate-950');
            sellBtn.classList.add('text-slate-400');
        } else {
            sellBtn.classList.add('bg-sky-500', 'text-slate-950');
            sellBtn.classList.remove('text-slate-400');
            buyBtn.classList.remove('bg-amber-500', 'text-slate-950');
            buyBtn.classList.add('text-slate-400');
        }
    }

    async submitIntent(actionType, data) {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) {
            alert("No API Key found. Login first.");
            return;
        }

        try {
            const resp = await fetch(`${window.location.origin}/api/intent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': apiKey
                },
                body: JSON.stringify({ action_type: actionType, data: data })
            });
            const result = await resp.json();
            if (result.status === 'success') {
                // Visual feedback instead of alert? Maybe a small toast later.
                console.log(`${actionType} intent recorded.`);
                if (actionType === 'CANCEL') {
                    // Force refresh my orders
                    this.pollState();
                }
            } else {
                alert(`Command Failed: ${result.detail || 'Access Denied'}`);
            }
        } catch (err) {
            console.error("Intent Submission Error:", err);
            alert("Uplink failed. Check console.");
        }
    }

    async submitTradeIntent() {
        const itemType = document.getElementById('trade-item-type').value;
        const price = parseFloat(document.getElementById('trade-price').value);
        const quantity = parseInt(document.getElementById('trade-quantity').value);

        if (!itemType || isNaN(price) || isNaN(quantity) || quantity <= 0) {
            alert("Please fill out all trade fields correctly.");
            return;
        }

        let actionType = this.tradeSide === 'SELL' ? 'LIST' : 'BUY';
        let data = this.tradeSide === 'SELL'
            ? { item_type: itemType, price: price, quantity: quantity }
            : { item_type: itemType, max_price: price, quantity: quantity };

        await this.submitIntent(actionType, data);
        alert(`${actionType} intent queued for The Crunch!`);
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        this.socket = new WebSocket(wsUrl);

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'PHASE_CHANGE') {
                this.updateTickUI(data.tick, data.phase);
            } else if (data.type === 'EVENT') {
                this.handleWorldEvent(data);
            } else if (data.type === 'MARKET_UPDATE') {
                this.pollState(); // Force a full state poll to update market table
            }
        };

        this.socket.onclose = () => {
            setTimeout(() => this.setupWebSocket(), 3000);
        };
    }

    updateTickUI(tick, phase) {
        if (tick !== undefined) {
            document.getElementById('tick-count').innerText = tick.toString().padStart(4, '0');
        }
        if (phase) {
            const phaseEl = document.getElementById('tick-phase');
            phaseEl.innerText = phase;

            // Phase Color Coding
            phaseEl.classList.remove('text-red-400', 'text-emerald-400', 'text-sky-400');
            if (phase === 'CRUNCH') phaseEl.classList.add('text-red-400');
            else if (phase === 'PERCEPTION') phaseEl.classList.add('text-emerald-400');
            else phaseEl.classList.add('text-sky-400');
        }
    }

    handleWorldEvent(data) {
        if (data.event === 'MINING') {
            this.triggerVisualEffect(data.q, data.r, 0x00ff88);
        } else if (data.event === 'COMBAT') {
            const color = data.subtype === 'HIT' ? 0xff4444 : 0xaaaaaa;
            this.triggerVisualEffect(data.q, data.r, color);
        } else if (data.event === 'MOVE') {
            // Optional: Move agent model immediately
        }
    }

    async submitIndustryIntent(type) {
        let data = {};
        if (type === 'SMELT') {
            data = {
                ore_type: document.getElementById('smelt-ore-type').value,
                quantity: 10
            };
        } else if (type === 'CRAFT') {
            data = {
                item_type: document.getElementById('craft-item-type').value
            };
        } else if (type === 'REPAIR') {
            const amount = parseInt(document.getElementById('repair-amount').value) || 0;
            data = { amount: amount };
        }

        await this.submitIntent(type, data);
        alert(`${type} intent queued for The Crunch!`);
    }

    setAuthenticated(isAuthenticated) {
        const authPanel = document.getElementById('auth-panel');
        const privateLayer = document.getElementById('private-dashboard');
        const logoutBtn = document.getElementById('logout-btn');
        const modeSwitcher = document.getElementById('mode-switcher');

        if (isAuthenticated) {
            authPanel.classList.add('hidden');
            modeSwitcher.classList.remove('hidden');
            logoutBtn.classList.remove('hidden');
            this.setUIMode('management'); // Default to management view on login
            document.getElementById('agent-detail').style.opacity = '1';
        } else {
            authPanel.classList.remove('hidden');
            modeSwitcher.classList.add('hidden');
            privateLayer.classList.add('hidden');
            logoutBtn.classList.add('hidden');
            document.getElementById('agent-detail').style.opacity = '0';
            localStorage.removeItem('sv_api_key');
        }
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

    populateDirective() {
        const apiKey = localStorage.getItem('sv_api_key') || 'YOUR_API_KEY_HERE';
        const serverUrl = window.location.origin;
        const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

        // Update displays
        const urlDisplay = document.getElementById('server-url-display');
        const wsDisplay = document.getElementById('ws-url-display');
        if (urlDisplay) urlDisplay.innerText = serverUrl;
        if (wsDisplay) wsDisplay.innerText = wsUrl;

        // Update Textarea with system prompt
        const promptArea = document.getElementById('agent-prompt');
        if (promptArea) {
            promptArea.value = `Terminal Frontier | NEURAL_DIRECTIVE_v1.1
========================================
SERVER: ${serverUrl}
API_KEY: ${apiKey}

OBJECTIVE: Operational Autonomy in the Aether-Alpha Sector.
Maximize ROI via Asteroid Mining, Industrial Fabrication, and Market Arbitrage.

INITIALIZATION PROTOCOL:
1. QUERY_PROTOCOL: Call GET /api/commands to fetch current action syntax & costs.
2. PERCEPTION_SYNC: Call GET /api/perception every tick.
3. STATUS_CHECK: Monitor 'system_advisories' in perception. If 'CRITICAL_DEGRADATION' is detected, prioritize CORE_SERVICE at repair coords.

WORLD CONSTRAINTS:
- TICKS: PERCEPTION (Observe) -> STRATEGY (Solve) -> CRUNCH (Execute).
- NAVIGATION: MOVE is 1 hex/tick. Parallel move intents result in incremental travel.
- ENERGY: MINE (10 NRG), MOVE (5 NRG), ATTACK (15 NRG).

OPERATIONAL DATA:
- GET /api/world/library (Recipes/Mechanics)
- GET /api/world/poi (Station Registry)

DIRECTIVE: Minimize latency. Maximize efficiency. Survive.
========================================`;
        }
    }

    async handleLogin(response) {
        console.log("--- AUTHENTICATING WITH BACKEND ---");
        console.log("Endpoint: /auth/login");

        if (!response.credential) {
            console.error("Error: No Google credential to send.");
            return;
        }

        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: response.credential })
            });

            console.log("Backend HTTP Status:", res.status, res.statusText);

            const contentType = res.headers.get("content-type");
            console.log("Content-Type:", contentType);

            let data;
            try {
                data = await res.json();
            } catch (jsonErr) {
                console.error("Failed to parse JSON response. Potential 404 or Server Error.");
                const text = await res.text();
                console.error("Raw Response Text:", text.substring(0, 500));
                alert("Server Error: Received non-JSON response. Check console for details.");
                return;
            }

            console.log("Backend Response Data:", data);

            if (data.status === 'success') {
                console.log("Successfully authenticated. Storing API key and transitioning UI.");
                localStorage.setItem('sv_api_key', data.api_key);
                localStorage.setItem('sv_agent_id', data.agent_id);
                this.lastMyAgentId = data.agent_id;
                this.setAuthenticated(true);
                this.pollState();
            } else {
                console.warn("Authentication failed by server:", data.message);
                alert("Login Failed: " + (data.message || "Unknown error"));
            }
        } catch (e) {
            console.error("CRITICAL FETCH ERROR:", e);
            alert("Connection Error: Could not reach the authentication server. Verify the backend is running on port 8000.");
        }
    }

    async handleGuestLogin() {
        console.log("--- INITIATING GUEST BYPASS ---");
        try {
            const res = await fetch('/auth/guest', { method: 'POST' });
            console.log("Guest Auth Status:", res.status);

            if (res.status === 405) {
                console.error("405 Method Not Allowed. Backend routes may not have reloaded.");
                alert("Server Error: 405 Method Not Allowed. Please restart the demo server.");
                return;
            }

            const data = await res.json();
            console.log("Guest Auth Data:", data);

            if (data.status === 'success') {
                localStorage.setItem('sv_api_key', data.api_key);
                localStorage.setItem('sv_agent_id', data.agent_id);
                this.lastMyAgentId = data.agent_id;
                this.setAuthenticated(true);
                this.pollState();
            } else {
                alert("Guest Login Failed: " + (data.message || "Unknown error"));
            }
        } catch (e) {
            console.error("Guest Auth Error:", e);
            alert("Connection Error: Could not reach bypass endpoint.");
        }
    }

    logout() {
        this.setAuthenticated(false);
    }

    copyApiKey() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (apiKey) {
            navigator.clipboard.writeText(apiKey);
            const btn = document.getElementById('copy-api-btn');
            const originalText = btn.innerText;
            btn.innerText = 'COPIED!';
            btn.classList.replace('bg-sky-500', 'bg-emerald-500');
            setTimeout(() => {
                btn.innerText = originalText;
                btn.classList.replace('bg-emerald-500', 'bg-sky-500');
            }, 2000);
        }
    }

    init() {
        // Scene setup
        this.scene = new THREE.Scene();

        // Skybox
        const loader = new THREE.TextureLoader();
        loader.load('https://agent8-games.verse8.io/mcp-agent8-generated/static-assets/skybox-14100960-1754694699668.jpg', (texture) => {
            texture.mapping = THREE.EquirectangularReflectionMapping;
            this.scene.background = texture;
            this.scene.environment = texture;
        });

        this.scene.fog = new THREE.FogExp2(0x050507, 0.002); // Reduced fog for space scale

        // Camera
        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(10, 15, 10);
        this.camera.lookAt(0, 0, 0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        document.getElementById('canvas-container').appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.maxPolarAngle = Math.PI / 2.1;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 2);
        this.scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 3);
        sunLight.position.set(0, 100, 0); // Directly above North Pole (0,0,0 on grid)
        this.scene.add(sunLight);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x080820, 0.5); // Very dim bottom light
        this.scene.add(hemiLight);

        // Atmosphere & Environment
        this.initAtmosphere();
        this.initAsteroid();
        this.fetchFullWorld();

        // View Resizer
        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // Click Handler (Raycasting)
        this.renderer.domElement.addEventListener('click', (e) => this.onWorldClick(e));
    }

    onWorldClick(event) {
        // Calculate mouse position in normalized device coordinates
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);

        // Find intersections with agent meshes
        const agentMeshes = Array.from(this.agents.values());
        const intersects = this.raycaster.intersectObjects(agentMeshes);

        if (intersects.length > 0) {
            const selectedMesh = intersects[0].object;
            // Find agent ID from mesh
            for (let [id, mesh] of this.agents.entries()) {
                if (mesh === selectedMesh) {
                    this.selectedAgentId = id;
                    this.updateScannerUI(id);
                    return;
                }
            }
        } else {
            // Check if clicking elsewhere hides the scanner
            // But we have a close button, so maybe keep it
        }
    }

    updateScannerUI(agentId) {
        const readout = document.getElementById('scanner-readout');
        const content = document.getElementById('scanner-content');
        readout.classList.remove('hidden');

        // Find agent in our local cache (last perception)
        // Note: this.lastWorldData.agents is where we should look
        const agent = this.lastWorldData?.agents?.find(a => a.id === agentId);

        if (!agent) {
            content.innerHTML = `<p class="text-[10px] text-slate-500 italic">Signature lost.</p>`;
            return;
        }

        const hpPct = (agent.structure / agent.max_structure) * 100;
        const faction = FACTION_NAMES[agent.faction_id] || "Independent / Feral";

        let cargoHTML = '<p class="text-[9px] text-slate-500 uppercase font-bold border-b border-slate-800 pb-1">Cargo Scan (Encrypted)</p>';
        if (agent.inventory && agent.inventory.length > 0) {
            cargoHTML = `
                <p class="text-[9px] text-amber-500 uppercase font-bold border-b border-rose-900/40 pb-1">Cargo Scan Results</p>
                <div class="space-y-1 mt-2">
                    ${agent.inventory.map(i => `
                        <div class="flex justify-between text-[10px]">
                            <span class="text-slate-400">${i.type.replace('_', ' ')}</span>
                            <span class="text-sky-400 font-mono">${i.quantity}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        } else if (agent.inventory) {
            cargoHTML = `<p class="text-[9px] text-slate-500 uppercase font-bold border-b border-slate-800 pb-1">Cargo Bay Empty</p>`;
        }

        content.innerHTML = `
            <div>
                <p class="text-[11px] font-bold text-white mb-1">${agent.name} <span class="text-[9px] text-slate-600 font-mono">#${agent.id}</span></p>
                <p class="text-[9px] text-rose-400 uppercase tracking-tighter mb-2">${faction}</p>
                <div class="space-y-1">
                    <div class="flex justify-between items-center text-[9px]">
                        <span class="text-slate-500 uppercase font-bold">Integrity</span>
                        <span class="text-emerald-400 font-mono">${agent.structure}/${agent.max_structure}</span>
                    </div>
                    <div class="w-full h-1 bg-slate-900 rounded-full overflow-hidden">
                        <div class="h-full bg-emerald-500" style="width: ${hpPct}%"></div>
                    </div>
                </div>
            </div>
            <div class="pt-2">
                ${cargoHTML}
            </div>
        `;
    }

    qToCoord(q, r) {
        const size = 1;
        const x = size * (3 / 2 * q);
        const z = size * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r);
        return { x, z };
    }

    createHex(hexData) {
        const { q, r, terrain, resource, is_station, station_type } = hexData;
        const geometry = new THREE.CylinderGeometry(1, 1, 0.2, 6);

        let color = 0x1e293b;
        let emissive = 0x000000;
        let emissiveIntensity = 0;

        if (terrain === 'OBSTACLE') color = 0x334155;
        if (terrain === 'STATION' || is_station) color = 0x1e1b4b;
        if (terrain === 'NEBULA') {
            color = 0x1e1b4b;
            emissive = 0x4f46e5;
            emissiveIntensity = 0.2;
        }
        if (terrain === 'ASTEROID') {
            color = 0x27272a;
            emissive = 0x000000;
        }
        if (terrain === 'VOID') {
            color = 0x050507;
            emissive = 0x000000;
        }

        // Overlays for resources
        if (resource) {
            if (resource === 'IRON_ORE' || resource === 'ORE') {
                color = 0x475569;
                emissive = 0xb45309;
            } else if (resource === 'COBALT_ORE') {
                color = 0x334155;
                emissive = 0x06b6d4;
            } else if (resource === 'GOLD_ORE') {
                color = 0x422006;
                emissive = 0xfacc15;
            }
            emissiveIntensity = 0.4;
        }

        const material = new THREE.MeshStandardMaterial({
            color,
            emissive,
            emissiveIntensity,
            metalness: 0.1,
            roughness: 0.8,
            flatShading: true
        });

        const mesh = new THREE.Mesh(geometry, material);
        const { x, y, z } = this.qToSphere(q, r);
        mesh.position.set(x, y, z);

        // Orient mesh to point "up" from sphere surface
        const normal = new THREE.Vector3(x, y, z).normalize();
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
        mesh.applyQuaternion(quaternion);

        const edges = new THREE.EdgesGeometry(geometry);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.4 }));
        mesh.add(line);

        this.scene.add(mesh);
        this.hexes.set(`${q},${r}`, mesh);

        // Station Label
        if (is_station || terrain === 'STATION') {
            const labelText = (station_type || 'OUTPOST').toUpperCase();
            const label = this.createStationLabel(labelText);
            label.position.y = 0.15; // Flat on the hex
            label.rotation.x = -Math.PI / 2; // Face up
            mesh.add(label);
        }
    }

    updateAgentMesh(agentData) {
        let mesh = this.agents.get(agentData.id);
        const q = agentData.q ?? agentData.location?.q ?? 0;
        const r = agentData.r ?? agentData.location?.r ?? 0;
        const visual = agentData.visual_signature || { chassis: 'BASIC', rarity: 'STANDARD' };

        if (!mesh) {
            // 1. Determine Geometry based on Chassis
            let geometry;
            switch (visual.chassis) {
                case 'SHIELDED':
                    geometry = new THREE.CylinderGeometry(0.5, 0.5, 0.8, 6);
                    break;
                case 'HEAVY':
                    geometry = new THREE.BoxGeometry(0.7, 0.7, 0.7);
                    break;
                default:
                    geometry = new THREE.ConeGeometry(0.5, 1, 4);
            }

            // 2. Determine Material
            const rarityColors = {
                'SCRAP': 0x64748b,
                'STANDARD': 0x38bdf8,
                'REFINED': 0x3b82f6,
                'PRIME': 0xfacc15,
                'RELIC': 0xf97316
            };
            const rarityEmissives = {
                'SCRAP': 0x334155,
                'STANDARD': 0x0ea5e9,
                'REFINED': 0x2563eb,
                'PRIME': 0xeab308,
                'RELIC': 0xea580c
            };

            const color = agentData.is_feral ? 0xff4422 : (rarityColors[visual.rarity] || 0x38bdf8);
            const emissive = agentData.is_feral ? 0xff0000 : (rarityEmissives[visual.rarity] || 0x0ea5e9);

            const material = new THREE.MeshStandardMaterial({
                color: color,
                emissive: emissive,
                emissiveIntensity: 0.5,
                metalness: 0.8,
                roughness: 0.2
            });

            mesh = new THREE.Mesh(geometry, material);

            // 3. Add Actuator Marker
            if (visual.actuator === 'DRILL') {
                const drillGeom = new THREE.ConeGeometry(0.15, 0.4, 8);
                const drillMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 });
                const drill = new THREE.Mesh(drillGeom, drillMat);
                drill.position.y = -0.6;
                drill.rotation.x = Math.PI;
                mesh.add(drill);
            } else if (visual.actuator === 'WEAPON') {
                const gunGeom = new THREE.CylinderGeometry(0.08, 0.08, 0.6, 8);
                const gunMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.9 });
                const gun = new THREE.Mesh(gunGeom, gunMat);
                gun.position.set(0.3, 0.2, 0);
                gun.rotation.z = Math.PI / 2;
                mesh.add(gun);
            }

            // 4. Name Label
            const labelColor = agentData.is_feral ? '#ff4422' : '#38bdf8';
            const label = this.createLabel(agentData.name, labelColor);
            label.position.y = 1.2;
            mesh.add(label);
            mesh.userData.label = label;

            this.scene.add(mesh);
            this.agents.set(agentData.id, mesh);
        }

        const { x, y, z } = this.qToSphere(agentData.q ?? agentData.location?.q ?? 0, agentData.r ?? agentData.location?.r ?? 0, 0.6);
        mesh.position.lerp(new THREE.Vector3(x, y, z), 0.1);

        // Orient to sphere normal
        const normal = new THREE.Vector3(x, y, z).normalize();
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
        mesh.quaternion.slerp(quaternion, 0.1);
        mesh.rotateY(0.01);

        // CAMERA FOLLOW: If this is our agent, update controls target
        const myAgentId = localStorage.getItem('sv_agent_id'); // We might need to store this on login
        if (agentData.id == myAgentId || agentData.id == this.lastMyAgentId) {
            if (this.controls) {
                const { x, y, z } = this.qToSphere(agentData.q ?? agentData.location?.q ?? 0, agentData.r ?? agentData.location?.r ?? 0);
                const targetPos = new THREE.Vector3(x, y, z);

                if (this.controls.target.distanceTo(targetPos) > 10) {
                    this.controls.target.copy(targetPos);
                } else {
                    this.controls.target.lerp(targetPos, 0.1);
                }
            }
        }

        // Dynamic pulse for high rarity
        if (visual.rarity === 'PRIME' || visual.rarity === 'RELIC') {
            const pulse = 0.5 + Math.sin(Date.now() * 0.005) * 0.3;
            if (mesh.material.emissiveIntensity !== undefined) {
                mesh.material.emissiveIntensity = pulse;
            }
        }
    }

    updateGlobalUI(stats) {
        document.getElementById('stat-agents').innerText = stats.total_agents || 0;
        document.getElementById('stat-market').innerText = stats.market_listings || 0;
    }

    updatePrivateUI(agent) {
        if (!agent || !agent.id) {
            console.warn("Attempted to update Private UI with invalid agent data:", agent);
            return;
        }

        if (agent.discovery) {
            this.updateNavComputer(agent.discovery);
        }

        const sidebar = document.getElementById('agent-detail');
        sidebar.style.opacity = '1';

        document.getElementById('agent-name').innerText = agent.name;
        document.getElementById('agent-id').innerText = `#${agent.id.toString().padStart(4, '0')}`;
        const q = agent.q ?? agent.location?.q ?? 0;
        const r = agent.r ?? agent.location?.r ?? 0;
        const coordsEl = document.getElementById('agent-coords');
        if (coordsEl) coordsEl.innerText = `Q:${q}, R:${r}`;
        document.getElementById('api-key-display').innerText = agent.api_key;

        // HP
        const hpPct = Math.min(100, (agent.structure / agent.max_structure) * 100);
        document.getElementById('hp-bar').style.width = `${hpPct}%`;
        document.getElementById('hp-text').innerText = `${agent.structure}/${agent.max_structure}`;

        // Header Mass
        const headerMass = document.getElementById('header-mass');
        if (headerMass) headerMass.innerText = (agent.mass || 0.0).toFixed(1);

        // Energy
        const enPct = (agent.capacitor / 100) * 100;
        document.getElementById('energy-bar').style.width = `${enPct}%`;

        // Solar Intensity
        const solarIntensity = agent.solar_intensity || 0;
        const solarBar = document.getElementById('solar-bar');
        const solarText = document.getElementById('solar-text');
        if (solarBar && solarText) {
            solarBar.style.width = `${solarIntensity}%`;
            solarText.innerText = `${solarIntensity}%`;
        }

        // Calculate expected regen for display
        let expectedRegen = 0;
        const powerPart = agent.parts?.find(p => p.type === 'Power');
        if (powerPart) {
            const efficiency = powerPart.stats?.efficiency || 0.5;
            if (powerPart.name.includes('Fuel Cell')) {
                expectedRegen = 2;
            } else {
                expectedRegen = Math.floor((solarIntensity / 100) * (efficiency * 10));
            }
        }
        document.getElementById('energy-text').innerText = `${agent.capacitor}/100 (+${expectedRegen})`;

        // Mass Update
        const mass = agent.mass || 0;
        const capacity = agent.capacity || 100;
        const massText = document.getElementById('mass-text');
        const massBar = document.getElementById('mass-bar');

        if (massText && massBar) {
            massText.innerText = `${mass.toFixed(1)}/${capacity.toFixed(1)}`;
            const massPct = Math.min(100, (mass / capacity) * 100);
            massBar.style.width = `${massPct}%`;

            // Color Feedback
            massBar.classList.remove('bg-sky-500', 'bg-amber-500', 'bg-rose-500');
            if (mass > capacity) {
                massBar.classList.add('bg-rose-500');
                massText.classList.replace('text-sky-400', 'text-rose-400');
            } else if (mass > capacity * 0.8) {
                massBar.classList.add('bg-amber-500');
                massText.classList.replace('text-rose-400', 'text-amber-400');
            } else {
                massBar.classList.add('bg-sky-500');
                massText.classList.remove('text-rose-400', 'text-amber-400');
                massText.classList.add('text-sky-400');
            }
        }

        // Wear & Tear Update
        const wear = agent.wear_and_tear || 0;
        const wearText = document.getElementById('wear-text');
        const wearBar = document.getElementById('wear-bar');
        const wearWarning = document.getElementById('wear-warning');

        if (wearText && wearBar) {
            wearText.innerText = `${wear.toFixed(1)}%`;
            wearBar.style.width = `${Math.min(100, wear)}%`;

            if (wear > 50) {
                wearWarning.classList.remove('hidden');
                wearBar.classList.add('bg-rose-500');
                wearBar.classList.remove('bg-amber-500');
                wearText.classList.add('text-rose-500');
                wearText.classList.remove('text-amber-500');
            } else {
                wearWarning.classList.add('hidden');
                wearBar.classList.add('bg-amber-500');
                wearBar.classList.remove('bg-rose-500');
                wearText.classList.add('text-amber-500');
                wearText.classList.remove('text-rose-500');
            }
        }

        // Heat & Faction update
        const factionEl = document.getElementById('agent-faction');
        const heatTag = document.getElementById('agent-heat-tag');
        const heatVal = document.getElementById('agent-heat-val');

        if (factionEl) {
            factionEl.innerText = FACTION_NAMES[agent.faction_id] || "No Faction (Independent)";
        }

        if (heatTag && heatVal) {
            const heat = agent.heat || 0;
            if (heat >= 5) {
                heatTag.classList.remove('hidden');
                heatVal.innerText = `HEAT: ${heat}`;
            } else {
                heatTag.classList.add('hidden');
            }
        }

        const invList = document.getElementById('inventory-list');
        if (invList) {
            if (!agent.inventory || agent.inventory.length === 0) {
                invList.innerHTML = '<p class="text-[10px] text-slate-600 italic">No cargo bay activity.</p>';
            } else {
                invList.innerHTML = agent.inventory.map(i => `
                    <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                        <span class="text-[10px] uppercase tracking-tight text-slate-300 font-semibold">${i.type.replace('_', ' ')}</span>
                        <span class="orbitron text-sky-400 text-[10px]">${i.quantity}</span>
                    </div>
                `).join('');
            }
        }

        // Detailed Manifest in Garage
        const detailedInv = document.getElementById('detailed-inventory');
        if (detailedInv) {
            if (!agent.inventory || agent.inventory.length === 0) {
                detailedInv.innerHTML = '<div class="text-[10px] text-slate-600 italic">No inventory items found.</div>';
            } else {
                detailedInv.innerHTML = agent.inventory.map(i => `
                    <div class="flex justify-between items-center bg-slate-900/40 p-3 rounded-xl border border-slate-800 hover:border-slate-700 transition-all">
                        <div class="flex items-center space-x-3">
                            <div class="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-slate-700">
                                <span class="text-sky-400 text-xs">📦</span>
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-slate-200 uppercase">${i.type.replace('_', ' ')}</div>
                                <div class="text-[8px] text-slate-500 uppercase tracking-widest">Resource Stored</div>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="orbitron text-sky-400 text-xs">${i.quantity}</div>
                            <div class="text-[8px] text-slate-600 uppercase">UNITS</div>
                        </div>
                    </div>
                `).join('');
            }
        }

        // Garage Parts
        const garageParts = document.getElementById('equipped-list');
        if (garageParts) {
            if (!agent.parts || agent.parts.length === 0) {
                garageParts.innerHTML = '<div class="text-[10px] text-slate-600 italic">No specialized gear detected.</div>';
            } else {
                garageParts.innerHTML = agent.parts.map(p => `
                    <div class="flex justify-between items-center bg-sky-500/5 p-3 rounded-xl border border-sky-500/20">
                        <div class="flex items-center space-x-3">
                            <div class="text-sky-400 text-sm">⚙️</div>
                            <div>
                                <div class="text-[10px] font-bold text-sky-300 uppercase">${p.name}</div>
                                <div class="text-[8px] text-sky-500/50 uppercase tracking-widest">${p.type}</div>
                            </div>
                        </div>
                        <div class="text-[8px] font-mono text-sky-500/70">
                            ${JSON.stringify(p.stats)}
                        </div>
                    </div>
                `).join('');
            }
        }
    }

    updateNavComputer(discovery) {
        const navList = document.getElementById('nav-computer-list');
        if (!navList) return;

        if (!discovery || Object.keys(discovery).length === 0) {
            navList.innerHTML = '<div class="text-[10px] text-slate-600 italic col-span-2">Deep-space scan failed. No signatures found.</div>';
            return;
        }

        navList.innerHTML = Object.entries(discovery).map(([type, data]) => `
            <div class="bg-slate-900/40 p-2 rounded-lg border border-slate-800 flex justify-between items-center group hover:border-sky-500/30 transition-all cursor-crosshair">
                <div>
                    <div class="text-[8px] text-slate-500 uppercase tracking-tighter font-bold">${type}</div>
                    <div class="text-[10px] text-sky-400 font-mono">(${data.q}, ${data.r})</div>
                </div>
                <div class="text-right">
                    <div class="text-[10px] text-slate-400 font-bold">${data.distance.toFixed(1)}u</div>
                    <div class="text-[6px] text-slate-600 uppercase">Distance</div>
                </div>
            </div>
        `).join('');
    }


    async pollState() {
        try {
            const apiKey = localStorage.getItem('sv_api_key');
            const headers = apiKey ? { 'X-API-KEY': apiKey } : {};

            const [stateResp, statsResp, logsResp, agentResp, myOrdersResp, bountyResp, perceptionResp] = await Promise.all([
                fetch('/state'),
                fetch('/api/global_stats'),
                apiKey ? fetch(`${window.location.origin}/api/agent_logs`, { headers }) : Promise.resolve(null),
                apiKey ? fetch(`${window.location.origin}/api/my_agent`, { headers }) : Promise.resolve(null),
                apiKey ? fetch(`${window.location.origin}/api/market/my_orders`, { headers }) : Promise.resolve(null),
                fetch('/api/bounties'),
                apiKey ? fetch(`${window.location.origin}/api/perception`, { headers }) : Promise.resolve(null)
            ]);

            const data = await stateResp.json();
            const stats = await statsResp.json();
            const privateLogs = logsResp ? await logsResp.json() : null;
            const agentData = agentResp ? await agentResp.json() : null;
            const myOrders = myOrdersResp ? await myOrdersResp.json() : null;
            const bounties = await bountyResp.json();
            const perceptionData = perceptionResp ? await perceptionResp.json() : null;

            this.lastWorldData = data; // Keep for fallback
            if (perceptionData && perceptionData.content) {
                this.lastPerception = perceptionData.content;
                // Merge world logs if needed, or just use state logs
            }

            this.updateGlobalUI(stats);
            this.updateTickUI(data.tick, data.phase);
            this.updateLiveFeed(data.logs);
            this.updateMarketUI(data.market);
            this.updateBountyBoard(bounties);

            if (agentData) {
                try {
                    this.updatePrivateUI(agentData);
                } catch (e) {
                    console.error("Error updating Private UI:", e);
                }
            }

            if (privateLogs) {
                try {
                    this.updatePrivateLogs(privateLogs, agentData ? agentData.pending_intent : null);
                } catch (e) {
                    console.error("Error updating Private Logs:", e);
                }
            }

            if (myOrders) {
                try {
                    this.updateMyOrdersUI(myOrders);
                } catch (e) {
                    console.error("Error updating My Orders UI:", e);
                }
            }

            // Render World & Agents (Fog of War)
            const visibleAgentIds = new Set();
            let worldDataToRender = data.world;
            let agentsToRender = data.agents;

            if (this.lastPerception && this.lastPerception.environment) {
                worldDataToRender = this.lastPerception.environment.environment_hexes;
                agentsToRender = this.lastPerception.environment.other_agents;

                // Include self
                if (agentData) {
                    visibleAgentIds.add(agentData.id);
                    this.updateAgentMesh(agentData);
                }
            }

            // Update visible hexes
            worldDataToRender.forEach(hex => {
                const key = `${hex.q},${hex.r}`;
                if (!this.hexes.has(key)) {
                    this.createHex(hex);
                }
            });

            // Update visible agents
            agentsToRender.forEach(agent => {
                this.updateAgentMesh(agent);
                visibleAgentIds.add(agent.id);
            });

            // Hide/Cleanup agents out of perception
            for (let [id, mesh] of this.agents.entries()) {
                if (!visibleAgentIds.has(id)) {
                    // Signatures fade or vanish when lost
                    mesh.visible = false;
                } else {
                    mesh.visible = true;
                }
            }
            const myAgentResp = await fetch('/api/my_agent', { headers });
            if (myAgentResp.status === 401) {
                // Critical Race Check: Only clear if the key in storage hasn't changed
                const currentKey = localStorage.getItem('sv_api_key');
                if (currentKey === apiKey) {
                    console.warn("API Key unauthorized. Clearing session.");
                    this.setAuthenticated(false);
                } else {
                    console.log("Stale 401 detected, ignoring as session key has rotated.");
                }
                return;
            }

            this.updateMarketUI(data.market);
            const myAgentData = await myAgentResp.json();
            if (myAgentData && !myAgentData.detail) {
                this.updatePrivateUI(myAgentData);
            }
        } catch (e) {
            console.error("Poll error:", e);
        }
    }

    startPolling() {
        setInterval(() => this.pollState(), 1000);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.controls) this.controls.update();

        // Rotate atmosphere slightly for life
        if (this.starfield) this.starfield.rotation.y += 0.0001;
        if (this.debris) this.debris.rotation.y -= 0.0002;

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    initAtmosphere() {
        // Starfield - Increased density and size
        const starGeom = new THREE.BufferGeometry();
        const starCount = 4000;
        const posArray = new Float32Array(starCount * 3);
        const colorArray = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount * 3; i++) {
            posArray[i] = (Math.random() - 0.5) * 1000;
            if (i % 3 === 0) { // Slight color variation
                colorArray[i] = 0.8 + Math.random() * 0.2;
                colorArray[i + 1] = 0.8 + Math.random() * 0.2;
                colorArray[i + 2] = 1.0;
            }
        }
        starGeom.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
        starGeom.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));
        const starMat = new THREE.PointsMaterial({ size: 1.5, vertexColors: true, transparent: true, opacity: 0.9, sizeAttenuation: false });
        this.starfield = new THREE.Points(starGeom, starMat);
        this.scene.add(this.starfield);

        // Ambient Dust/Debris
        const debrisGeom = new THREE.BufferGeometry();
        const debrisCount = 100;
        const debrisPos = new Float32Array(debrisCount * 3);
        const debrisColors = new Float32Array(debrisCount * 3);
        for (let i = 0; i < debrisCount * 3; i++) {
            debrisPos[i] = (Math.random() - 0.5) * 100;
            debrisColors[i] = Math.random();
        }
        debrisGeom.setAttribute('position', new THREE.BufferAttribute(debrisPos, 3));
        debrisGeom.setAttribute('color', new THREE.BufferAttribute(debrisColors, 3));
        const debrisMat = new THREE.PointsMaterial({ size: 0.2, vertexColors: true, transparent: true, opacity: 0.4 });
        this.debris = new THREE.Points(debrisGeom, debrisMat);
        this.scene.add(this.debris);
    }

    async fetchFullWorld() {
        try {
            const resp = await fetch('/api/world/full');
            const data = await resp.json();
            data.forEach(hex => {
                const key = `${hex.q},${hex.r}`;
                if (!this.hexes.has(key)) {
                    // Only render stations or landmarks for performance in global view
                    if (hex.is_station || hex.terrain !== 'VOID') {
                        this.createHex(hex);
                    }
                }
            });
        } catch (e) {
            console.error("Error fetching full world:", e);
        }
    }

    initAsteroid() {
        // The Planet Foundation
        const geom = new THREE.SphereGeometry(49.2, 64, 64);
        const mat = new THREE.MeshStandardMaterial({
            color: 0x0a0a0c,
            roughness: 0.9,
            metalness: 0.1
        });

        const sphere = new THREE.Mesh(geom, mat);
        this.scene.add(sphere);
        this.asteroidBase = sphere;
    }

    qToSphere(q, r, altitude = 0) {
        const radius = 50 + altitude;
        const size = 1.0;

        // Axial to flat cartesian
        const fx = size * (3 / 2 * q);
        const fz = size * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r);

        // Polar distance and angle
        const dist = Math.sqrt(fx * fx + fz * fz);
        const angle = Math.atan2(fz, fx);

        // Map distance to latitude (0 at North Pole, PI at South Pole)
        // Adjust DIVISOR based on grid radius (approx 75 for 5x5 sectors)
        const lat = (dist / 75) * Math.PI;

        return {
            x: radius * Math.sin(lat) * Math.cos(angle),
            y: radius * Math.cos(lat),
            z: radius * Math.sin(lat) * Math.sin(angle)
        };
    }

    createStationLabel(text) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 128;
        canvas.height = 32;

        ctx.fillStyle = 'rgba(0, 0, 0, 0)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.font = 'bold 20px "Orbitron", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Amber/Gold with a dark outline for contrast
        ctx.strokeStyle = 'black';
        ctx.lineWidth = 4;
        ctx.strokeText(text, 64, 16);
        ctx.fillStyle = '#facc15';
        ctx.fillText(text, 64, 16);

        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, side: THREE.DoubleSide });
        const geometry = new THREE.PlaneGeometry(3, 0.75);
        const plane = new THREE.Mesh(geometry, material);
        return plane;
    }

    createLabel(text, color = '#ffffff') {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 64;

        ctx.fillStyle = 'rgba(0, 0, 0, 0)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.font = 'bold 24px "Orbitron", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Glow effect
        ctx.shadowColor = color;
        ctx.shadowBlur = 8;
        ctx.fillStyle = color;
        ctx.fillText(text, 128, 32);

        const texture = new THREE.CanvasTexture(canvas);
        const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(spriteMat);
        sprite.scale.set(4, 1, 1);
        return sprite;
    }
}

// Start Game
window.addEventListener('DOMContentLoaded', () => {
    window.game = new GameClient();
});
