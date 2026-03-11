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

export class GameAPI {
    constructor(game) {
        this.game = game;
        this.socket = null;
        this._pollCycle = 0;
        this._polling = false;  // Concurrency guard
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const token = localStorage.getItem('sv_token');
        const wsUrl = `${protocol}//${window.location.host}/ws` + (token ? `?token=${token}` : '');
        this.socket = new WebSocket(wsUrl);

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'PHASE_CHANGE') {
                this.game.updateTickUI(data.tick, data.phase);
            } else if (data.type === 'EVENT') {
                this.game.handleWorldEvent(data);
            } else if (data.type === 'MARKET_UPDATE') {
                this.pollState(); // Force a full state poll to update market table
            }
        };

        this.socket.onclose = () => {
            setTimeout(() => this.setupWebSocket(), 5000);
        };
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
                fetch('/state'),
                apiKey ? fetch(`${window.location.origin}/api/my_agent`, { headers }) : Promise.resolve(null),
            ]);

            // ── SECONDARY TIER (every 30s): stats, logs, orders, bounties, perception, missions ──
            let secondaryResults = null;
            if (isSecondary) {
                secondaryResults = await Promise.allSettled([
                    fetch('/api/global_stats'),
                    apiKey ? fetch(`${window.location.origin}/api/agent_logs`, { headers }) : Promise.resolve(null),
                    apiKey ? fetch(`${window.location.origin}/api/market/my_orders`, { headers }) : Promise.resolve(null),
                    fetch('/api/bounties'),
                    apiKey ? fetch(`${window.location.origin}/api/perception`, { headers }) : Promise.resolve(null),
                    apiKey ? fetch(`${window.location.origin}/api/missions`, { headers }) : Promise.resolve(null),
                    apiKey ? fetch(`${window.location.origin}/api/arena/status`, { headers }) : Promise.resolve(null),
                ]);
            }

            // ── SLOW TIER (every 60s): chat ──
            let chatResult = null;
            if (isSlow && apiKey) {
                const [cr] = await Promise.allSettled([
                    fetch(`${window.location.origin}/api/chat`, { headers })
                ]);
                chatResult = cr;
            }

            // Helper: safely get JSON from a settled result
            const safeJson = async (settled) => {
                if (!settled || settled.status === 'rejected' || !settled.value) return null;
                const resp = settled.value;
                if (!resp.ok) { if (resp.status !== 429) console.warn(`API error ${resp.status} on ${resp.url}`); return null; }
                try { return await resp.json(); } catch { return null; }
            };

            // ── Parse Critical ──
            const data = await safeJson(criticalResults[0]);
            const agentData = await safeJson(criticalResults[1]);

            // Check for auth expiry
            if (criticalResults[1].value && criticalResults[1].value.status === 401) {
                console.warn("Session expired or API key invalid.");
                this.game.setAuthenticated(false);
                return;
            }

            // ── Parse Secondary (only when polled) ──
            let stats = null, privateLogs = null, myOrders = null, bounties = null, perceptionData = null, missions = null, arenaData = null;
            if (secondaryResults) {
                stats = await safeJson(secondaryResults[0]);
                privateLogs = await safeJson(secondaryResults[1]);
                myOrders = await safeJson(secondaryResults[2]);
                bounties = await safeJson(secondaryResults[3]);
                perceptionData = await safeJson(secondaryResults[4]);
                missions = await safeJson(secondaryResults[5]);
                arenaData = await safeJson(secondaryResults[6]);
            }

            const chatMessages = await safeJson(chatResult);

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

            if (myOrders) {
                try {
                    this.game.updateMyOrdersUI(myOrders);
                } catch (e) {
                    console.error("Error updating My Orders UI:", e);
                }
            }

            // Render World & Agents (Fog of War)
            const visibleAgentIds = new Set();
            let worldDataToRender = data.world;
            let agentsToRender = data.agents;

            if (agentData) {
                visibleAgentIds.add(agentData.id);
                this.game.updateAgentMesh(agentData);

                const centerBtn = document.getElementById('center-camera-btn');
                if (centerBtn && centerBtn.classList.contains('hidden')) {
                    centerBtn.classList.remove('hidden');
                }

                if (!this.game.hasCenteredInitially) {
                    this.game.centerOnAgent();
                    this.game.hasCenteredInitially = true;
                }
            }

            if (this.game.lastPerception) {
                worldDataToRender = this.game.lastPerception.discovery?.environment_hexes || this.game.lastPerception.environment?.environment_hexes || data.world;
                agentsToRender = this.game.lastPerception.nearby_agents || this.game.lastPerception.environment?.other_agents || data.agents;
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
            console.error("Poll error:", e);
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

    startPolling() {
        // Immediately restore cached data so HUD isn't empty
        this.restoreFromCache();

        setInterval(() => {
            this._pollCycle++;
            this.pollState();
        }, 10000);  // 10 seconds base interval
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
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                body: JSON.stringify({ action_type: actionType, data })
            });

            if (resp.ok) {
                const result = await resp.json();
                if (this.game.terminal) {
                    this.game.terminal.log(`✓ ACCEPTED — Scheduled for Tick #${result.scheduled_tick}`, 'success');
                }
            } else {
                const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                const detail = typeof err.detail === 'object' ? JSON.stringify(err.detail) : err.detail;
                if (this.game.terminal) {
                    this.game.terminal.log(`✗ REJECTED — ${detail || 'Server error'}`, 'error');
                }
            }
        } catch (e) {
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
            const resp = await fetch(`${window.location.origin}/api/market/orders/${orderId}`, {
                method: 'DELETE',
                headers: { 'X-API-KEY': apiKey }
            });
            if (resp.ok) {
                if (this.game.terminal) this.game.terminal.log(`✓ Market order #${orderId} cancelled. Refunds issued.`, 'success');
                this.pollState();
            } else {
                const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                alert(`Cancel Failed: ${err.detail}`);
            }
        } catch (e) { console.error("Cancel order error:", e); }
    }

    async adjustMarketOrder(orderId, currentPrice) {
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;
        const newPrice = prompt("Enter new price:", currentPrice);
        if (!newPrice || isNaN(newPrice) || Number(newPrice) <= 0) return;

        try {
            const resp = await fetch(`${window.location.origin}/api/market/orders/${orderId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                body: JSON.stringify({ price: Number(newPrice) })
            });
            if (resp.ok) {
                if (this.game.terminal) this.game.terminal.log(`✓ Market order #${orderId} price adjusted to $${newPrice}.`, 'success');
                this.pollState();
            } else {
                const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                alert(`Adjust Failed: ${err.detail}`);
            }
        } catch (e) { console.error("Adjust order error:", e); }
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
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;

        try {
            const resp = await fetch(`${window.location.origin}/api/claim_daily`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey }
            });

            const btn = document.getElementById('btn-claim-daily');
            if (resp.ok) {
                const data = await resp.json();
                if (this.game.terminal) {
                    this.game.terminal.log(`✓ Daily claimed! Acquired: ${data.items?.join(', ') || 'provisions'}`, 'success');
                }
                if (btn) {
                    btn.disabled = true;
                    btn.innerText = "CLAIMED TODAY";
                    btn.classList.add("opacity-50", "cursor-not-allowed");
                }
                this.pollState();
            } else {
                const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                if (this.game.terminal) {
                    this.game.terminal.log(`✗ Claim Failed: ${err.detail || 'Unknown error'}`, 'error');
                }
                if (btn && err.detail && err.detail.includes("24 hours")) {
                    btn.disabled = true;
                    btn.innerText = "ON COOLDOWN";
                }
            }
        } catch (e) {
            console.error("Claim error:", e);
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
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;
        try {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                body: Object.keys(data).length ? JSON.stringify(data) : undefined
            });
            const result = await resp.json();
            if (resp.ok) {
                if (this.game.terminal) this.game.terminal.log(`✓ ${result.message}`, 'success');
                this.pollState();
            } else {
                alert(`Squad Error: ${result.detail || 'Access Denied'}`);
            }
        } catch (e) {
            console.error("Squad action error:", e);
        }
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
