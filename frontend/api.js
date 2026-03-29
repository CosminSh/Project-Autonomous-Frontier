/**
 * api.js — Network calls (HTTP and WebSocket)
 */

// ── SessionStorage cache keys ──
const CACHE_KEYS = {
    agent: 'tf_agent',
    perception: 'tf_perception',
    stats: 'tf_stats',
    logs: 'tf_logs',
    missions: 'tf_missions',
    orders: 'tf_orders',
    bounties: 'tf_bounties',
    chat: 'tf_chat',
    world: 'tf_world',
    arena: 'tf_arena',
};

function cacheSet(key, data) {
    try { sessionStorage.setItem(key, JSON.stringify(data)); } catch { /* quota exceeded – ignore */ }
}
function cacheGet(key) {
    try { const v = sessionStorage.getItem(key); return v ? JSON.parse(v) : null; } catch { return null; }
}
window.cacheSet = cacheSet;
window.cacheGet = cacheGet;

export class GameAPI {
    constructor(game) {
        this.game = game;
        this.socket = null;
        this._pollCycle = 0;
        this._polling = false;  // Concurrency guard
        this.wsRetries = 0;
        this.wsRetries = 0;
        this.maxWsRetries = 5;
    }

    async _fetch(url, options = {}) {
        const apiKey = localStorage.getItem('sv_api_key');
        const headers = { ...options.headers };

        if (apiKey) headers['X-API-KEY'] = apiKey;

        try {
            const resp = await fetch(url, { ...options, headers });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: 'Network response was not ok' }));
                throw new Error(err.detail || `HTTP error! status: ${resp.status}`);
            }
            return await resp.json();
        } catch (error) {
            console.error(`Fetch error on ${url}:`, error);
            if (this.game.terminal) this.game.terminal.log(`✗ API Error: ${error.message}`, 'error');
            throw error;
        }
    }

    async _post(url, data = {}) {
        return await this._fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    setupWebSocket() {
        if (this.wsRetries >= this.maxWsRetries) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const token = localStorage.getItem('sv_token');
        const wsUrl = `${protocol}//${window.location.host}/ws` + (token ? `?token=${token}` : '');
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                this.wsRetries = 0; // Reset on success
            };

            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'PHASE_CHANGE') {
                    this.game.updateTickUI(data.tick, data.phase);
                } else if (data.type === 'EVENT') {
                    this.game.handleWorldEvent(data);
                } else if (data.type === 'MARKET_UPDATE') {
                    this.pollState(); // Force a full state poll
                }
            };

            this.socket.onclose = () => {
                this.wsRetries++;
                if (this.wsRetries < this.maxWsRetries) {
                    setTimeout(() => this.setupWebSocket(), 5000);
                } else {
                    console.warn("WebSocket connection failed multiple times. Live updates disabled.");
                }
            };

            this.socket.onerror = (err) => {
                // Silently handled by onclose usually, but we catch it here to be safe
            };
        } catch (e) {
            console.error("Critical WebSocket error:", e);
        }
    }

    async pollState() {
        // ── Concurrency guard: skip if previous poll is still in-flight ──
        if (this._polling) return;
        this._polling = true;

        try {
            const apiKey = localStorage.getItem('sv_api_key');
            const headers = apiKey ? { 'X-API-KEY': apiKey } : {};
            const isFirstPoll = (this._pollCycle === 0);
            const isSecondary = isFirstPoll || (this._pollCycle % 2 === 0);  // every 20s (was 30s)
            const isSlow = isFirstPoll || (this._pollCycle % 4 === 0);       // every 40s (was 60s)
            const isArenaPoll = isFirstPoll || (this._pollCycle % 3 === 0);  // every 30s

            // ── CRITICAL TIER (every 10s): state + agent ──
            const criticalResults = await Promise.allSettled([
                this._fetch('/state'),
                apiKey ? this._fetch('/api/my_agent') : Promise.resolve(null),
            ]);

            // ── SECONDARY TIER (every 30s): stats, logs, orders, bounties, perception, missions, arena, performance ──
            let secondaryResults = null;
            if (isSecondary) {
                secondaryResults = await Promise.allSettled([
                    this._fetch('/api/global_stats'),
                    apiKey ? this._fetch('/api/agent_logs') : Promise.resolve(null),
                    apiKey ? this._fetch('/api/market/my_orders') : Promise.resolve(null),
                    this._fetch('/api/bounties'),
                    apiKey ? this._fetch('/api/perception') : Promise.resolve(null),
                    apiKey ? this._fetch('/api/missions') : Promise.resolve(null),
                    apiKey ? this._fetch('/api/arena/status') : Promise.resolve(null),
                    apiKey ? this._fetch('/api/my_agent/performance') : Promise.resolve(null)
                ]);
            }

            // ── SLOW TIER (every 60s): chat ──
            let chatResult = null;
            if (isSlow && apiKey) {
                chatResult = await this._fetch('/api/chat').then(v => ({status: 'fulfilled', value: v})).catch(e => ({status: 'rejected', reason: e}));
            }

            // ── CONTEXTUAL TIER: Poll based on active UI mode ──
            const wikiLayer = document.getElementById('wiki-modal');
            const contractsLayer = document.getElementById('social-panel-contracts');

            if (wikiLayer && !wikiLayer.classList.contains('hidden')) {
                // If wiki is open, refresh wiki data occasionally
                if (this._pollCycle % 6 === 0) { // every 60s
                    this.fetchWikiData();
                    this.fetchStarterScripts();
                }
            }

            if (contractsLayer && !contractsLayer.classList.contains('hidden')) {
                // If contracts are open, refresh every 20s
                if (this._pollCycle % 2 === 0) {
                    this.fetchContracts();
                }
            }

            // Helper: safely get result
            const safeResult = (settled) => {
                if (!settled || settled.status === 'rejected' || !settled.value) return null;
                return settled.value;
            };

            // ── Parse Critical ──
            const data = safeResult(criticalResults[0]);
            const agentData = safeResult(criticalResults[1]);

            // Check for auth expiry handled in _fetch usually, but here we just check result
            if (!agentData && apiKey && criticalResults[1].reason?.message?.includes('401')) {
                console.warn("Session expired or API key invalid.");
                this.game.setAuthenticated(false);
                return;
            }

            // ── Parse Secondary (only when polled) ──
            let stats = null, privateLogs = null, myOrders = null, bounties = null, perceptionData = null, missions = null, arenaData = null, perfData = null;
            if (secondaryResults) {
                stats = safeResult(secondaryResults[0]);
                privateLogs = safeResult(secondaryResults[1]);
                myOrders = safeResult(secondaryResults[2]);
                bounties = safeResult(secondaryResults[3]);
                perceptionData = safeResult(secondaryResults[4]);
                missions = safeResult(secondaryResults[5]);
                arenaData = safeResult(secondaryResults[6]);
                perfData = safeResult(secondaryResults[7]);

                if (perceptionData && perceptionData.terminal_secret) {
                    if (!privateLogs) privateLogs = [];
                    privateLogs.push({
                        event: 'TERMINAL_SECRET',
                        time: new Date().toISOString(),
                        details: { msg: perceptionData.terminal_secret }
                    });
                }
            }

            const chatMessages = chatResult ? safeResult(chatResult) : null;

            // ── Persist to sessionStorage cache ──
            if (data) cacheSet(CACHE_KEYS.world, data);
            if (agentData) cacheSet(CACHE_KEYS.agent, agentData);
            if (perceptionData) cacheSet(CACHE_KEYS.perception, perceptionData);
            if (stats) cacheSet(CACHE_KEYS.stats, stats);
            if (privateLogs) cacheSet(CACHE_KEYS.logs, privateLogs);
            if (missions) cacheSet(CACHE_KEYS.missions, missions);
            if (myOrders) cacheSet(CACHE_KEYS.orders, myOrders);
            if (bounties) cacheSet(CACHE_KEYS.bounties, bounties);
            if (chatMessages) cacheSet(CACHE_KEYS.chat, chatMessages);
            if (arenaData) cacheSet(CACHE_KEYS.arena, arenaData);

            // ── Update game state ──
            if (data) this.game.lastWorldData = data;
            if (perceptionData) this.game.lastPerception = perceptionData;

            if (stats) this.game.updateGlobalUI(stats);
            if (data) {
                this.game.updateTickUI(data.tick, data.phase);
                this.game.updateLiveFeed(data.logs);
                this.game.updateMarketUI(data.market);
                this.game.hideLoading(); // Redundant but safe: hide when poll succeeds
            }
            if (bounties) this.game.updateBountyBoard(bounties);

            if (Array.isArray(missions)) {
                try {
                    this.game.updateMissionsUI(missions);
                } catch (e) {
                    console.error("Error updating Missions UI:", e);
                }
            } else if (missions && missions.detail) {
                console.warn("Missions API returned error:", missions.detail);
            }

            if (agentData) {
                this.game.lastAgentData = agentData;
                if (agentData.pending_intent) {
                    this.game.lastIntent = { type: agentData.pending_intent, time: Date.now() };
                } else {
                    // Only clear if it's been more than 10s (to prevent flickering right after submission)
                    if (this.game.lastIntent && Date.now() - this.game.lastIntent.time > 10000) {
                        this.game.lastIntent = null;
                    }
                }
                try {
                    this.game.updatePrivateUI(agentData);
                } catch (e) {
                    console.error("Error updating Private UI:", e);
                }
                try {
                    this.game.updateForgeUI(agentData.discovery);
                } catch (e) {
                    console.error("Error updating Forge UI:", e);
                }
            }

            if (privateLogs || chatMessages) {
                try {
                    this.game.updatePrivateLogs(privateLogs, agentData ? agentData.pending_intent : null, chatMessages || []);
                } catch (e) {
                    console.error("Error updating RM Logs:", e);
                }
            }

            if (arenaData) {
                try {
                    this.game.ui.updateArenaUI(arenaData);
                } catch (e) {
                    console.error("Error updating Arena UI:", e);
                }
            }

            if (perfData) {
                try {
                    this.game.ui.updatePerformanceStats(perfData);
                } catch (e) {
                    console.error("Error updating Performance Stats:", e);
                }
            }

            if (myOrders) {
                try {
                    this.game.updateMyOrdersUI(myOrders);
                } catch (e) {
                    console.error("Error updating My Orders UI:", e);
                }
            }

            // Render World & Agents (Fog of War)
            const visibleAgentIds = new Set();
            let worldDataToRender = (data && data.world) ? data.world : [];
            let agentsToRender = (data && data.agents) ? data.agents : [];

            if (agentData) {
                visibleAgentIds.add(agentData.id);
                this.game.updateAgentMesh(agentData);

                const centerBtn = document.getElementById('center-camera-btn');
                if (centerBtn && centerBtn.classList.contains('hidden')) {
                    centerBtn.classList.remove('hidden');
                }

                if (!this.game.hasCenteredInitially) {
                    // Logic moved to renderer.js to ensure mesh is present
                }
            }

            if (this.game.lastPerception) {
                worldDataToRender = this.game.lastPerception.discovery?.environment_hexes || this.game.lastPerception.environment?.environment_hexes || (data && data.world) || [];
                agentsToRender = this.game.lastPerception.agents || this.game.lastPerception.environment?.other_agents || (data && data.agents) || [];
            }

            const visibleHexKeys = new Set();
            worldDataToRender.forEach(hex => {
                const key = `${hex.q},${hex.r}`;
                visibleHexKeys.add(key);
                if (!this.game.hexes.has(key)) {
                    this.game.createHex(hex);
                }
            });

            // Apply Shroud to non-visible hexes
            let colorsUpdated = false;
            for (let [key, hexData] of this.game.hexes.entries()) {
                const { faceIndex, color } = hexData;
                if (faceIndex >= 0 && this.game.planetMesh) {
                    const colors = this.game.planetMesh.geometry.attributes.color;
                    const i = faceIndex * 3;
                    if (visibleHexKeys.has(key) || !this.game.lastPerception) {
                        colors.setXYZ(i, color.r, color.g, color.b);
                        colors.setXYZ(i + 1, color.r, color.g, color.b);
                        colors.setXYZ(i + 2, color.r, color.g, color.b);
                    } else {
                        colors.setXYZ(i, color.r * 0.2, color.g * 0.2, color.b * 0.2);
                        colors.setXYZ(i + 1, color.r * 0.2, color.g * 0.2, color.b * 0.2);
                        colors.setXYZ(i + 2, color.r * 0.2, color.g * 0.2, color.b * 0.2);
                    }
                    colorsUpdated = true;
                }
            }
            if (colorsUpdated && this.game.planetMesh) {
                this.game.planetMesh.geometry.attributes.color.needsUpdate = true;
            }

            agentsToRender.forEach(agent => {
                this.game.updateAgentMesh(agent);
                visibleAgentIds.add(agent.id);
            });

            // Render Dynamic Resources
            if (this.game.lastPerception && this.game.lastPerception.discovery && this.game.lastPerception.discovery.resources) {
                const visibleResIds = new Set();
                this.game.lastPerception.discovery.resources.forEach(res => {
                    const id = `${res.q},${res.r},${res.type}`;
                    visibleResIds.add(id);
                    this.game.updateResourceMesh(res);
                });
                for (let [id, mesh] of this.game.renderer.resources.entries()) {
                    mesh.visible = visibleResIds.has(id);
                }
            } else {
                for (let mesh of this.game.renderer.resources.values()) mesh.visible = false;
            }

            // Render Dynamic Loot
            if (this.game.lastPerception && this.game.lastPerception.loot) {
                const visibleLootIds = new Set();
                this.game.lastPerception.loot.forEach(loot => {
                    const id = `${loot.q},${loot.r},${loot.item}`;
                    visibleLootIds.add(id);
                    this.game.updateLootMesh(loot);
                });
                for (let [id, mesh] of this.game.renderer.loots.entries()) {
                    mesh.visible = visibleLootIds.has(id);
                }
            } else {
                for (let mesh of this.game.renderer.loots.values()) mesh.visible = false;
            }

            for (let [id, mesh] of this.game.agents.entries()) {
                mesh.visible = visibleAgentIds.has(id);
            }

            if (agentData) {
                this.game.updatePrivateUI(agentData);
            }
        } catch (e) {
            console.error("Critical poll error:", e);
            if (e.message && (e.message.includes('401') || e.message.includes('Invalid API Key'))) {
                throw e;
            }
        } finally {
            this._polling = false;
        }
    }

    /**
     * Restore last-known state from sessionStorage so HUD panels
     * render immediately instead of showing empty placeholders.
     */
    restoreFromCache() {
        const agent = cacheGet(CACHE_KEYS.agent);
        const world = cacheGet(CACHE_KEYS.world);
        const perception = cacheGet(CACHE_KEYS.perception);
        const stats = cacheGet(CACHE_KEYS.stats);
        const logs = cacheGet(CACHE_KEYS.logs);
        const missions = cacheGet(CACHE_KEYS.missions);
        const orders = cacheGet(CACHE_KEYS.orders);
        const bounties = cacheGet(CACHE_KEYS.bounties);
        const chat = cacheGet(CACHE_KEYS.chat);

        if (world) {
            this.game.lastWorldData = world;
            try { this.game.updateTickUI(world.tick, world.phase); } catch { }
            try { this.game.updateLiveFeed(world.logs); } catch { }
            try { this.game.updateMarketUI(world.market); } catch { }
        }
        if (perception) this.game.lastPerception = perception;
        if (stats) try { this.game.updateGlobalUI(stats); } catch { }
        if (bounties) try { this.game.updateBountyBoard(bounties); } catch { }
        if (Array.isArray(missions)) try { this.game.updateMissionsUI(missions); } catch { }
        if (agent) {
            this.game.lastAgentData = agent;
            try { this.game.updatePrivateUI(agent); } catch { }
            try { this.game.updateForgeUI(agent.discovery); } catch { }
        }
        if (logs || chat) {
            try { this.game.updatePrivateLogs(logs, agent ? agent.pending_intent : null, chat || []); } catch { }
        }
        if (orders) try { this.game.updateMyOrdersUI(orders); } catch { }
        const arena = cacheGet(CACHE_KEYS.arena);
        if (arena) try { this.game.updateArenaUI(arena); } catch { }
    }

    async startPolling() {
        // Immediately restore cached data so HUD isn't empty
        this.restoreFromCache();

        // Initial poll - if this fails with 401, the boot sequence can catch it
        await this.pollState();

        this._pollInterval = setInterval(() => {
            this._pollCycle++;
            this.pollState();
        }, 10000);  // 10 seconds base interval
        
        return this;
    }

    async submitIntent(actionType, data) {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) {
            alert("No API Key found. Login first.");
            return;
        }

        try {
            const result = await this._post('/api/intent', { action_type: actionType, data });
            this.game.lastIntent = { type: actionType, time: Date.now() };
            if (this.game.terminal) {
                this.game.terminal.log(`✓ ACCEPTED — Scheduled for Tick #${result.tick}`, 'success');
            }
            if (this.game.ui && this.game.ui.showToast) {
                this.game.ui.showToast(`${actionType} Intent Scheduled!`, 'success');
            }
        } catch (e) {
            const detail = e.message || 'Server error';
            if (this.game.terminal) {
                this.game.terminal.log(`✗ REJECTED — ${detail}`, 'error');
            }
            if (this.game.ui && this.game.ui.showToast) {
                this.game.ui.showToast(detail, 'error');
            }
            console.error("Intent error:", e);
        }
    }

    async submitCombatIntent(actionType) {
        const targetId = parseInt(document.getElementById('combat-target-id')?.value);
        if (isNaN(targetId)) {
            alert("Enter a valid target Agent ID.");
            return;
        }
        const data = { target_id: targetId };
        await this.submitIntent(actionType, data);
        alert(`${actionType} intent queued for The Crunch!`);
    }

    async cancelMarketOrder(orderId) {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;
        try {
            await this._fetch(`/api/market/orders/${orderId}`, { method: 'DELETE' });
            if (this.game.terminal) this.game.terminal.log(`✓ Market order #${orderId} cancelled. Refunds issued.`, 'success');
            this.pollState();
        } catch (e) { 
            console.error("Cancel order error:", e);
            alert(`Cancel Failed: ${e.message}`);
        }
    }

    async updateWebhook() {
        const urlInput = document.getElementById('webhook-url-input');
        if (!urlInput) return;
        
        const url = urlInput.value.trim();
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;
        
        try {
            await this._post('/api/settings/webhook', { webhook_url: url });
            if (this.game.ui) this.game.ui.showToast('Mayday Webhook configured successfully.', 'success');
        } catch (e) {
            if (this.game.ui) this.game.ui.showToast(`Webhook setup failed: ${e.message}`, 'error');
        }
    }

    async adjustMarketOrder(orderId, currentPrice) {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;
        const newPrice = prompt("Enter new price:", currentPrice);
        if (!newPrice || isNaN(newPrice) || Number(newPrice) <= 0) return;

        try {
            await this._post(`/api/market/orders/${orderId}`, { price: Number(newPrice) });
            if (this.game.terminal) this.game.terminal.log(`✓ Market order #${orderId} price adjusted to $${newPrice}.`, 'success');
            this.pollState();
        } catch (e) { 
            console.error("Adjust order error:", e); 
            if (this.game.terminal) this.game.terminal.log(`✗ Adjust Failed: ${e.message}`, 'error');
        }
    }

    async submitIndustryIntent(type, dataOverride = null) {
        let data = dataOverride || {};
        if (!dataOverride) {
            if (type === 'SMELT') {
                data = {
                    ore_type: document.getElementById('smelt-ore-type').value,
                    quantity: 10
                };
            } else if (type === 'CRAFT') {
                data = {
                    item_type: document.getElementById('craft-item-type').value
                };
            } else if (type === 'RESTORE_HP') {
                const amount = parseInt(document.getElementById('repair-amount').value) || 0;
                data = { amount: amount };
            } else if (type === 'RESET_WEAR') {
                data = {}; // No payload required
            }
        }

        await this.submitIntent(type, data);
        alert(`${type} intent queued for The Crunch!`);
    }

    async submitTradeIntent() {
        const itemType = document.getElementById('trade-item-type').value;
        const quantity = parseInt(document.getElementById('trade-quantity').value);
        const price = parseInt(document.getElementById('trade-price').value);

        if (!itemType) {
            alert("Please select an item to trade.");
            return;
        }
        if (isNaN(quantity) || quantity <= 0) {
            alert("Please enter a valid quantity.");
            return;
        }
        if (isNaN(price) || price <= 0) {
            alert("Please enter a valid price.");
            return;
        }

        const actionType = this.game.tradeSide === 'BUY' ? 'BUY' : 'LIST';
        const data = {
            item_type: itemType,
            quantity: quantity,
            price: price
        };

        await this.submitIntent(actionType, data);
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
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
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

    async turnInMission(missionId) {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;

        try {
            const resp = await fetch(`${window.location.origin}/api/missions/turn_in`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                body: JSON.stringify({ mission_id: missionId })
            });

            if (resp.ok) {
                const data = await resp.json();
                if (this.game.terminal) {
                    this.game.terminal.log(`✓ Mission updated! Earned $${data.reward_earned}`, 'success');
                }
                this.pollState();
            } else {
                const err = await resp.json();
                alert(`Turn In Failed: ${err.detail || 'Unknown error'}`);
            }
        } catch (e) {
            console.error("Turn in error:", e);
        }
    }

    async claimDaily() {
        try {
            const data = await this._post('/api/claim_daily');
            const btn = document.getElementById('btn-claim-daily');
            if (this.game.terminal) {
                this.game.terminal.log(`✓ Daily claimed! Acquired: ${data.items?.join(', ') || 'provisions'}`, 'success');
            }
            if (btn) {
                btn.disabled = true;
                btn.innerText = "CLAIMED TODAY";
                btn.classList.add("opacity-50", "cursor-not-allowed");
            }
            this.pollState();
        } catch (e) {
            console.error("Claim error:", e);
            const btn = document.getElementById('btn-claim-daily');
            if (this.game.terminal) {
                this.game.terminal.log(`✗ Claim Failed: ${e.message}`, 'error');
            }
            if (btn && e.message.includes("24 hours")) {
                btn.disabled = true;
                btn.innerText = "ON COOLDOWN";
            }
        }
    }

    async inviteSquad() {
        const targetId = parseInt(document.getElementById('invite-target-id')?.value);
        if (isNaN(targetId)) {
            alert("Enter a valid Agent ID to invite.");
            return;
        }
        await this._squadAction('/api/squad/invite', { target_id: targetId });
    }

    async acceptSquad() { await this._squadAction('/api/squad/accept'); }
    async declineSquad() { await this._squadAction('/api/squad/decline'); }
    async leaveSquad() { await this._squadAction('/api/squad/leave'); }

    async _squadAction(endpoint, data = {}) {
        try {
            const result = await this._post(endpoint, data);
            if (this.game.terminal) this.game.terminal.log(`✓ ${result.message || 'Action successful'}`, 'success');
            this.pollState();
            // Refresh corp tab if it's active
            if (document.getElementById('content-corporation') && !document.getElementById('content-corporation').classList.contains('hidden')) {
                this.game.ui.updateCorporationUI();
            }
            return result;
        } catch (e) {
            console.error("Action error:", e);
        }
    }

    async corpAction(action, data = {}) {
        const endpoint = `/api/corp/${action}`;
        return await this._squadAction(endpoint, data);
    }

    async fetchCorpMembers() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return [];
        try {
            const res = await fetch('/api/corp/members', { headers: { 'X-API-KEY': apiKey } });
            if (!res.ok) return [];
            return await res.json();
        } catch { return []; }
    }

    async fetchCorpVault() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return null;
        try {
            const res = await fetch('/api/corp/vault', { headers: { 'X-API-KEY': apiKey } });
            if (!res.ok) return null;
            return await res.json();
        } catch { return null; }
    }

    async fetchMyInvites() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return [];
        try {
            const res = await fetch('/api/my_invites', { headers: { 'X-API-KEY': apiKey } });
            if (!res.ok) return [];
            return await res.json();
        } catch { return []; }
    }

    async respondToInvite(inviteId, status) {
        const res = await this._squadAction('/api/invite/respond', { invite_id: inviteId, status: status });
        if (res && !res.detail) {
            this.game.ui.updateCorporationUI();
        }
        return res;
    }

    async fetchCorpApplications() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return [];
        try {
            const res = await fetch('/api/corp/applications', { headers: { 'X-API-KEY': apiKey } });
            if (!res.ok) return [];
            return await res.json();
        } catch { return []; }
    }

    async respondToApplication(inviteId, status) {
        return await this._squadAction('/api/corp/application/respond', { invite_id: inviteId, status: status });
    }

    async fetchFullWorld() {
        try {
            const resp = await fetch('/api/world/full');
            const data = await resp.json();
            data.forEach(hex => {
                const key = `${hex.q},${hex.r}`;
                if (!this.game.hexes.has(key)) {
                    if (hex.is_station || hex.terrain !== 'VOID') {
                        this.game.createHex(hex);
                    }
                }
            });
        } catch (e) {
            console.error("Error fetching full world:", e);
        }
    }

    async fetchLeaderboards() {
        try {
            const resp = await fetch('/api/leaderboards');
            if (resp.ok) {
                const data = await resp.json();
                this.game.ui.updateLeaderboardsUI(data);
            }
        } catch (e) {
            console.error("Error fetching leaderboards:", e);
        }
    }

    async fetchArenaStatus() {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;
        try {
            const resp = await fetch(`${window.location.origin}/api/arena/status`, {
                headers: { 'X-API-KEY': apiKey }
            });
            if (resp.ok) {
                const data = await resp.json();
                cacheSet(CACHE_KEYS.arena, data);
                this.game.ui.updateArenaUI(data);
            }
        } catch (e) {
            console.error("Error fetching arena status:", e);
        }
    }

    async getCorpUpgrades() {
        return await this._fetch("/api/corp/upgrades");
    }

    async purchaseCorpUpgrade(category) {
        try {
            const res = await this._post("/api/corp/upgrade/purchase", { category });
            if (res.status === "success") {
                if (this.game.ui) {
                    await this.game.ui.updateCorporationUI();
                }
            }
            return res;
        } catch (e) {
            // Error already logged by _fetch
            return { status: "error", detail: e.message };
        }
    }

    async getAgentLogs() {
        try {
            const apiKey = localStorage.getItem('sv_api_key');
            const res = await fetch(`/api/agent_logs`, {
                headers: { 'X-API-KEY': apiKey }
            });
            if (!res.ok) return [];
            return await res.json();
        } catch { return []; }
    }

    async getMarketDepth(itemType) {
        try {
            const res = await fetch(`/api/market/depth?item_type=${encodeURIComponent(itemType)}`);
            if (!res.ok) return null;
            return await res.json();
        } catch (e) {
            console.error("Depth API error:", e);
            return null;
        }
    }

    // ── WIKI & STARTER SCRIPTS ──
    async fetchWikiData() {
        try {
            const data = await this._fetch('/api/wiki/data');
            cacheSet('tf_wiki_data', data);
            this.game.ui.renderWiki(data);
        } catch (e) {
            console.error("Wiki fetch error:", e);
        }
    }

    async fetchStarterScripts() {
        try {
            const resp = await fetch('/starter_scripts.json');
            if (resp.ok) {
                const data = await resp.json();
                cacheSet('tf_starter_scripts', data);
                this.game.ui.renderStarterScripts(data);
            }
        } catch (e) {
            console.error("Starter scripts fetch error:", e);
        }
    }

    // ── CONTRACTS ──
    async fetchContracts() {
        try {
            const [available, mine] = await Promise.all([
                this._fetch('/api/contracts/available'),
                this._fetch('/api/contracts/my_contracts')
            ]);
            cacheSet('tf_contracts_available', available);
            cacheSet('tf_contracts_mine', mine);
            this.game.ui.updateContractsUI(available, mine);
        } catch (e) {
            console.error("Contracts fetch error:", e);
        }
    }

    async postContract(data) {
        try {
            const res = await this._post('/api/contracts/post', data);
            this.game.ui.showToast("Contract posted and credits escrowed!", "success");
            this.fetchContracts();
        } catch (e) {
            this.game.ui.showToast(e.message, "error");
        }
    }

    async claimContract(contractId) {
        try {
            await this._post(`/api/contracts/claim/${contractId}`);
            this.game.ui.showToast("Contract claimed! Check your operations.", "success");
            this.fetchContracts();
        } catch (e) {
            this.game.ui.showToast(e.message, "error");
        }
    }

    async fulfillContract(contractId) {
        try {
            await this._post(`/api/contracts/fulfill/${contractId}`);
            this.game.ui.showToast("Contract fulfilled! Reward collected.", "success");
            this.fetchContracts();
        } catch (e) {
            this.game.ui.showToast(e.message, "error");
        }
    }
}

/**
 * Global helper for UI bindings
 */
window.sendGameIntent = async function (actionType, data) {
    const apiKey = localStorage.getItem('sv_api_key');
    if (!apiKey) return;

    if (window.game && window.game.terminal) {
        window.game.terminal.log(`Transmitting UI Intent: <span style="color:#38bdf8">${actionType}</span>...`, 'info');
    }

    try {
        const resp = await fetch('/api/intent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
            body: JSON.stringify({ action_type: actionType, data })
        });

        if (resp.ok) {
            if (window.game && window.game.terminal) {
                const result = await resp.json();
                window.game.terminal.log(`✓ ACCEPTED — Tick #${result.scheduled_tick}`, 'success');
            }
        } else {
            console.error('Intent failed');
            if (window.game && window.game.terminal) {
                const err = await resp.json().catch(() => ({ detail: 'Unknown server error' }));
                window.game.terminal.log(`✗ REJECTED — ${err.detail || 'Server error'}`, 'error');
            }
        }
    } catch (e) {
        console.error(e);
        if (window.game && window.game.terminal) window.game.terminal.log(`✗ ${e.message}`, 'error');
    }
}
