class DashboardClient {
    constructor() {
        this.apiKey = localStorage.getItem('sv_api_key');
        this.activeTab = 'agent'; // Default tab
        if (!this.apiKey) {
            window.location.href = '/';
            return;
        }

        this.init();
        this.initWebSocket();
        this.startPolling();
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws?token=${this.apiKey}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log("WebSocket Uplink Established");
            const statusFull = document.getElementById('ws-status');
            if (statusFull) {
                statusFull.classList.remove('bg-slate-500', 'bg-rose-500');
                statusFull.classList.add('bg-emerald-500');
            }
            this.addFeedEntry("SYSTEM", "Uplink established... Waiting for data.");
        };

        this.ws.onclose = () => {
            console.warn("WebSocket Uplink Offline. Retrying in 5s...");
            const statusFull = document.getElementById('ws-status');
            if (statusFull) {
                statusFull.classList.remove('bg-emerald-500');
                statusFull.classList.add('bg-rose-500');
            }
            setTimeout(() => this.initWebSocket(), 5000);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketEvent(data);
        };
    }

    handleWebSocketEvent(data) {
        if (data.type === 'PHASE_CHANGE') {
            this.addFeedEntry("TICK", `TICK ${data.tick} | PHASE ${data.phase}`, "text-sky-400");
        } else if (data.type === 'EVENT') {
            let msg = "";
            let color = "text-slate-300";

            switch (data.event) {
                case 'COMBAT':
                    msg = `COMBAT: Attacker ${data.attacker_id} HIT Target ${data.target_id} for ${data.damage} DMG at (${data.q},${data.r})`;
                    color = "text-rose-400";
                    break;
                case 'MARKET':
                    if (data.subtype === 'MATCH') {
                        msg = `MARKET: ${data.qty}x ${data.item} MATCHED @ ${data.price} credits`;
                        color = "text-amber-400";
                    } else {
                        msg = `MARKET: ${data.buyer} bought ${data.qty}x ${data.item}`;
                        color = "text-amber-500";
                    }
                    break;
                case 'RESOURCE':
                    msg = `RESOURCE: Node ${data.resource} at (${data.q},${data.r}) DEPLETED`;
                    color = "text-indigo-400";
                    break;
                case 'SIMULATION':
                    msg = `SYSTEM: Simulation Tick ${data.tick} Complete. ${data.processed} actions processed.`;
                    color = "text-slate-500";
                    break;
                default:
                    msg = `${data.event}: ${JSON.stringify(data)}`;
            }
            this.addFeedEntry(data.event, msg, color);
        } else if (data.type === 'MARKET_UPDATE') {
            // Option: refresh market UI early or just ignore since we poll
        }
    }

    addFeedEntry(tag, text, colorClass = "text-slate-300") {
        const feed = document.getElementById('live-feed');
        if (!feed) return;

        const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const entry = document.createElement('div');
        entry.className = `border-l border-slate-800 pl-2 pb-1 transition-all animate-in fade-in slide-in-from-left-2 ${colorClass}`;
        entry.innerHTML = `
            <span class="text-slate-600 mr-2 text-[8px]">[${time}]</span>
            <span class="font-bold border border-current px-1 rounded-[2px] mr-2 text-[7px] uppercase tracking-tighter">${tag}</span>
            <span>${text}</span>
        `;

        if (feed.firstChild && feed.firstChild.tagName === 'P') {
            feed.innerHTML = "";
        }

        feed.prepend(entry);

        // Cap entries
        while (feed.children.length > 50) {
            feed.removeChild(feed.lastChild);
        }
    }

    init() {
        document.getElementById('api-key-display').innerText = this.apiKey;
        this.switchTab(this.activeTab);

        const contractForm = document.getElementById('post-contract-form');
        if (contractForm) {
            contractForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.postContract();
            });
        }
    }

    switchTab(tabId) {
        this.activeTab = tabId;

        // Toggle Views
        const views = {
            'agent': 'view-agent',
            'world': 'view-world',
            'contracts': 'view-contracts',
            'wiki': 'view-wiki'
        };

        Object.keys(views).forEach(key => {
            const el = document.getElementById(views[key]);
            if (el) el.classList.toggle('hidden', key !== tabId);
        });

        // Toggle Buttons
        ['tab-agent', 'tab-world', 'tab-contracts', 'tab-wiki'].forEach(id => {
            const btn = document.getElementById(id);
            if (!btn) return;
            if (id === `tab-${tabId}`) {
                btn.className = "flex-1 md:flex-none px-6 py-2 rounded-lg text-[10px] orbitron font-bold transition-all bg-sky-500/20 text-sky-300 border border-sky-500/30";
            } else {
                btn.className = "flex-1 md:flex-none px-6 py-2 rounded-lg text-[10px] orbitron font-bold transition-all text-slate-500 hover:text-slate-300";
            }
        });

        if (tabId === 'contracts') {
            this.updateContracts();
        } else if (tabId === 'wiki') {
            this.updateWiki();
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

        const lvlEl = document.getElementById('agent-lvl');
        if (lvlEl) lvlEl.innerText = `LVL ${agent.level || 1}`;

        const hpPct = (agent.health / agent.max_health) * 100;
        document.getElementById('hp-bar').style.width = `${hpPct}%`;
        document.getElementById('hp-text').innerText = `${agent.health}/${agent.max_health}`;

        const enPct = (agent.energy / 100) * 100;
        document.getElementById('energy-bar').style.width = `${enPct}%`;
        document.getElementById('energy-text').innerText = `${agent.energy}/100`;

        const exp = agent.experience || 0;
        const lvl = agent.level || 1;
        const base_xp = ((lvl - 1) * lvl / 2) * 100;
        const next_xp = (lvl * (lvl + 1) / 2) * 100;
        const xp_progress = exp - base_xp;
        const xp_bracket = next_xp - base_xp;

        const xpPct = Math.min(100, Math.max(0, (xp_progress / xp_bracket) * 100));
        document.getElementById('xp-bar').style.width = `${xpPct}%`;
        document.getElementById('xp-text').innerText = `${exp}/${next_xp}`;

        const massPct = Math.min(100, (agent.mass / agent.capacity) * 100);
        document.getElementById('mass-bar').style.width = `${massPct}%`;
        document.getElementById('mass-text').innerText = `${(agent.mass || 0).toFixed(1)}/${(agent.capacity || 0).toFixed(0)} KG`;

        if (agent.mass > agent.capacity) {
            document.getElementById('mass-bar').classList.remove('bg-amber-500');
            document.getElementById('mass-bar').classList.add('bg-rose-500');
            document.getElementById('mass-text').classList.add('text-rose-500', 'font-bold');
        } else {
            document.getElementById('mass-bar').classList.remove('bg-rose-500');
            document.getElementById('mass-bar').classList.add('bg-amber-500');
            document.getElementById('mass-text').classList.remove('text-rose-500', 'font-bold');
        }

        // Wear & Tear (Condition)
        const wearVal = agent.wear_and_tear || 0;
        const conditionPct = Math.max(0, 100 - wearVal);
        const wearBar = document.getElementById('wear-bar');
        const wearText = document.getElementById('wear-text');

        if (wearBar && wearText) {
            wearBar.style.width = `${conditionPct}%`;
            wearText.innerText = `${Math.round(conditionPct)}%`;

            // Color feedback
            wearBar.classList.remove('bg-rose-500', 'bg-amber-500', 'bg-emerald-500');
            if (conditionPct > 70) wearBar.classList.add('bg-emerald-500');
            else if (conditionPct > 30) wearBar.classList.add('bg-amber-500');
            else wearBar.classList.add('bg-rose-500');
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
                    <p class="text-[9px] text-slate-500 uppercase">QTY: ${order.quantity} | OWNER: ${(order.owner || 'UNKNOWN').substring(0, 8)}...</p>
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
        const currentSelection = select ? select.value : '';

        // Build option HTML
        const optionsHtml = discovery.crafting_recipes.map(recipe => {
            const costStr = Object.entries(recipe.materials)
                .map(([mat, qty]) => `${qty} ${mat.replace('_', ' ')}`)
                .join(', ');

            // Shorten stats for display
            const statsStr = Object.entries(recipe.stats || {})
                .map(([k, v]) => `${(k || '???').substring(0, 3).toUpperCase()}: ${v > 0 ? '+' : ''}${v}`)
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

    async rotateKey() {
        if (!confirm("CRITICAL WARNING: Rotating your API key will immediately invalidate your current key. Any bots or scripts using the old key will offline. Proceed?")) return;

        try {
            const resp = await fetch('/auth/rotate_key', {
                method: 'POST',
                headers: { 'X-API-KEY': this.apiKey }
            });
            const res = await resp.json();
            if (res.status === 'success') {
                const newKey = res.new_api_key;
                this.apiKey = newKey;
                localStorage.setItem('sv_api_key', newKey);
                document.getElementById('api-key-display').innerText = newKey;
                alert("ACCESS GRANTED: New API Key generated and saved to local session.");
            } else {
                alert("Error: " + (res.message || "Uplink failed"));
            }
        } catch (e) {
            console.error("Rotate Error:", e);
            alert("Security System Error: Check browser console.");
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
        setInterval(() => {
            this.pollData();
            if (this.activeTab === 'contracts') {
                this.updateContracts();
            }
        }, 2000);
    }

    async postContract() {
        const item = document.getElementById('contract-item').value;
        const qty = parseInt(document.getElementById('contract-qty').value);
        const reward = parseInt(document.getElementById('contract-reward').value);
        const q = parseInt(document.getElementById('contract-target-q').value);
        const r = parseInt(document.getElementById('contract-target-r').value);

        try {
            const resp = await fetch('/api/contracts/post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': this.apiKey },
                body: JSON.stringify({
                    item_type: item,
                    quantity: qty,
                    reward_credits: reward,
                    target_station_q: q,
                    target_station_r: r
                })
            });
            const res = await resp.json();
            if (resp.ok) {
                alert("CONTRACT POSTED: Credits escrowed and mission uplinked to public board.");
                this.updateContracts();
                this.pollData(); // Update credits
            } else {
                alert("Denied: " + (res.detail || "Request failed"));
            }
        } catch (e) {
            console.error("Post Contract Error:", e);
        }
    }

    async updateContracts() {
        try {
            const [availResp, myResp] = await Promise.all([
                fetch('/api/contracts/available'),
                fetch('/api/contracts/my_contracts', { headers: { 'X-API-KEY': this.apiKey } })
            ]);

            const available = await availResp.json();
            const myData = await myResp.json();

            this.renderAvailableContracts(available);
            this.renderMyContracts(myData);
        } catch (e) {
            console.error("Contract Update Error:", e);
        }
    }

    renderAvailableContracts(contracts) {
        const list = document.getElementById('available-contracts-list');
        if (!list) return;
        if (contracts.length === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 uppercase text-center py-10">No public contracts available</p>';
            return;
        }

        list.innerHTML = contracts.map(c => `
            <div class="glass p-4 rounded-xl border border-slate-800 flex justify-between items-center group hover:border-amber-500/30 transition-all">
                <div class="space-y-1">
                    <h4 class="text-xs text-amber-300 font-bold uppercase">${c.requirements.qty}x ${c.requirements.item.replace('_', ' ')}</h4>
                    <p class="text-[9px] text-slate-500 uppercase">ISSUER: ${c.issuer} | TARGET: Station (${c.target.q}, ${c.target.r})</p>
                    <p class="text-[8px] text-slate-600 uppercase">EXPIRES: ${new Date(c.expires_at).toLocaleString([], {hour: '2-digit', minute:'2-digit'})}</p>
                </div>
                <div class="text-right flex flex-col items-end gap-2">
                    <span class="orbitron text-xs text-emerald-400 font-bold">${c.reward} Ȼ</span>
                    <button onclick="window.dashboard.claimContract(${c.id})" class="text-[8px] bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 px-3 py-1 rounded border border-amber-500/30 transition-all orbitron font-bold uppercase">Claim</button>
                </div>
            </div>
        `).join('');
    }

    renderMyContracts(data) {
        const list = document.getElementById('my-contracts-list');
        if (!list) return;
        const total = (data.issued?.length || 0) + (data.claimed?.length || 0);
        if (total === 0) {
            list.innerHTML = '<p class="text-[10px] text-slate-600 italic">No active operations.</p>';
            return;
        }

        let html = '';
        
        if (data.claimed && data.claimed.length > 0) {
            html += '<h3 class="text-[9px] text-indigo-400 font-bold uppercase mb-2">Active Claims</h3>';
            html += data.claimed.map(c => `
                <div class="bg-indigo-900/10 p-3 rounded-xl border border-indigo-500/20 flex justify-between items-center mb-2">
                    <div>
                        <p class="text-[10px] font-bold text-indigo-200 uppercase">${c.requirements.qty}x ${c.requirements.item}</p>
                        <p class="text-[9px] text-slate-500 uppercase">Deliver to (${c.target_station_q}, ${c.target_station_r})</p>
                    </div>
                    <button onclick="window.dashboard.fulfillContract(${c.id})" class="text-[8px] bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-300 px-2 py-1 rounded border border-emerald-500/30 transition-all orbitron font-bold uppercase">Fulfill</button>
                </div>
            `).join('');
        }

        if (data.issued && data.issued.length > 0) {
            html += '<h3 class="text-[9px] text-sky-400 font-bold uppercase mt-4 mb-2">Posted by Me</h3>';
            html += data.issued.map(c => `
                <div class="bg-slate-900/40 p-3 rounded-xl border border-slate-800 flex justify-between items-center mb-2">
                    <div>
                        <p class="text-[10px] font-bold text-slate-300 uppercase">${c.requirements.qty}x ${c.requirements.item}</p>
                        <p class="text-[9px] text-slate-500 uppercase">Status: ${c.status} | Reward: ${c.reward_credits} Ȼ</p>
                    </div>
                </div>
            `).join('');
        }

        list.innerHTML = html;
    }

    async claimContract(id) {
        try {
            const resp = await fetch(`/api/contracts/claim/${id}`, {
                method: 'POST',
                headers: { 'X-API-KEY': this.apiKey }
            });
            const res = await resp.json();
            if (resp.ok) {
                this.updateContracts();
            } else {
                alert("Error: " + (res.detail || "Claim failed"));
            }
        } catch (e) {
            console.error("Claim Error:", e);
        }
    }

    async fulfillContract(id) {
        try {
            const resp = await fetch(`/api/contracts/fulfill/${id}`, {
                method: 'POST',
                headers: { 'X-API-KEY': this.apiKey }
            });
            const res = await resp.json();
            if (resp.ok) {
                alert("CONTRACT FULFILLED: Reward received and status updated.");
                this.updateContracts();
                this.pollData(); // Refresh inventory/credits
            } else {
                alert("Error: " + (res.detail || "Fulfillment denied"));
            }
        } catch (e) {
            console.error("Fulfill Error:", e);
        }
    }

    async updateWiki() {
        try {
            const wikiResp = await fetch('/api/wiki/data');
            const wikiData = await wikiResp.json();
            
            const scriptsResp = await fetch('/starter_scripts.json');
            const scriptsData = await scriptsResp.json();

            this.renderWiki(wikiData);
            this.renderStarterScripts(scriptsData);
        } catch (e) {
            console.error("Wiki/Scripts Update Error:", e);
        }
    }

    renderWiki(data) {
        const list = document.getElementById('wiki-content');
        if (!list) return;

        let html = '';

        // Lore
        html += '<h3 class="text-[10px] text-sky-300 font-bold uppercase mb-2 border-b border-sky-500/20 pb-1">Foundational Lore</h3>';
        data.lore.forEach(l => {
            html += `
                <div class="p-3 bg-sky-500/5 border border-sky-500/10 rounded-lg mb-3">
                    <h4 class="text-[9px] text-sky-200 font-bold uppercase mb-1">${l.title}</h4>
                    <p class="text-[9px] text-slate-400 leading-relaxed">${l.text}</p>
                </div>
            `;
        });

        // Industrial (Recipes)
        html += '<h3 class="text-[10px] text-sky-300 font-bold uppercase mt-6 mb-2 border-b border-sky-500/20 pb-1">Industrial Processes</h3>';
        html += '<div class="grid grid-cols-1 gap-2">';
        data.smelting.forEach(s => {
            html += `
                <div class="p-2 bg-slate-900/40 border border-slate-800 rounded flex justify-between items-center">
                    <span class="text-[8px] text-slate-300 font-bold uppercase">SMELT: ${s.ore.replace('_', ' ')} → ${s.ingot.replace('_', ' ')}</span>
                    <span class="text-[8px] text-slate-500">RATIO: ${s.ratio}:1 | COST: ${s.energy_cost} EN</span>
                </div>
            `;
        });
        html += '</div>';

        // Item Stats (Overview)
        html += '<h3 class="text-[10px] text-sky-300 font-bold uppercase mt-6 mb-2 border-b border-sky-500/20 pb-1">Technical Specifications</h3>';
        data.items.slice(0, 10).forEach(i => { // Only show first 10 for overview
            html += `
                <div class="p-2 bg-slate-900/40 border border-slate-800 rounded mb-2">
                    <div class="flex justify-between items-start mb-1">
                        <span class="text-[9px] text-sky-200 font-bold uppercase">${i.name}</span>
                        <span class="text-[7px] bg-slate-800 px-1 py-0.5 rounded text-slate-500 uppercase">${i.type}</span>
                    </div>
                    <p class="text-[8px] text-slate-500 uppercase mb-1">${i.description}</p>
                    <div class="flex gap-2 text-[7px] orbitron text-sky-400">
                        ${Object.entries(i.stats).map(([k,v]) => `${k.charAt(0).toUpperCase()}: ${v}`).join(' | ')}
                    </div>
                </div>
            `;
        });

        list.innerHTML = html;
    }

    renderStarterScripts(scripts) {
        const list = document.getElementById('starter-scripts-list');
        if (!list) return;

        list.innerHTML = scripts.map(s => `
            <div class="bg-emerald-950/10 border border-emerald-500/20 rounded-xl p-4 space-y-3">
                <h3 class="text-[10px] text-emerald-400 font-bold uppercase">${s.name}</h3>
                <p class="text-[9px] text-slate-500">${s.description}</p>
                <div class="relative group">
                    <pre class="bg-black/40 p-3 rounded border border-slate-800 overflow-x-auto text-[8px] text-emerald-100 font-mono"><code>${s.code}</code></pre>
                    <button onclick="window.dashboard.copyToClipboard(this)" data-code="${btoa(s.code)}" class="absolute top-2 right-2 bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-400 text-[7px] px-2 py-1 rounded transition-all opacity-0 group-hover:opacity-100">COPY</button>
                </div>
            </div>
        `).join('');
    }

    copyToClipboard(btn) {
        const code = atob(btn.dataset.code);
        navigator.clipboard.writeText(code).then(() => {
            const originalText = btn.innerText;
            btn.innerText = "COPIED!";
            btn.classList.add('bg-emerald-500/40');
            setTimeout(() => {
                btn.innerText = originalText;
                btn.classList.remove('bg-emerald-500/40');
            }, 2000);
        });
    }
}

function logout() {
    localStorage.removeItem('sv_api_key');
    window.location.href = '/';
}

window.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DashboardClient();
});
