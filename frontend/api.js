/**
 * api.js — Network calls (HTTP and WebSocket)
 */
export class GameAPI {
    constructor(game) {
        this.game = game;
        this.socket = null;
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
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
            setTimeout(() => this.setupWebSocket(), 3000);
        };
    }

    async pollState() {
        try {
            const apiKey = localStorage.getItem('sv_api_key');
            const headers = apiKey ? { 'X-API-KEY': apiKey } : {};

            // Use allSettled so a single 500 doesn't crash the entire poll
            const results = await Promise.allSettled([
                fetch('/state'),                                                                                          // 0
                fetch('/api/global_stats'),                                                                               // 1
                apiKey ? fetch(`${window.location.origin}/api/agent_logs`, { headers }) : Promise.resolve(null),         // 2
                apiKey ? fetch(`${window.location.origin}/api/my_agent`, { headers }) : Promise.resolve(null),           // 3
                apiKey ? fetch(`${window.location.origin}/api/market/my_orders`, { headers }) : Promise.resolve(null),   // 4
                fetch('/api/bounties'),                                                                                   // 5
                apiKey ? fetch(`${window.location.origin}/api/perception`, { headers }) : Promise.resolve(null),         // 6
                apiKey ? fetch(`${window.location.origin}/api/missions`, { headers }) : Promise.resolve(null)            // 7
            ]);

            // Helper: safely get JSON from a settled result (returns null on failure)
            const safeJson = async (settled) => {
                if (settled.status === 'rejected' || !settled.value) return null;
                const resp = settled.value;
                if (!resp.ok) { console.warn(`API error ${resp.status} on ${resp.url}`); return null; }
                try { return await resp.json(); } catch { return null; }
            };

            const [stateR, statsR, logsR, agentR, myOrdersR, bountyR, perceptionR, missionsR] = results;

            // Check for auth expiry
            if (agentR.value && agentR.value.status === 401) {
                console.warn("Session expired or API key invalid.");
                this.game.setAuthenticated(false);
                return;
            }

            const data = await safeJson(stateR);
            const stats = await safeJson(statsR);
            const privateLogs = await safeJson(logsR);
            const agentData = await safeJson(agentR);
            const myOrders = await safeJson(myOrdersR);
            const bounties = await safeJson(bountyR);
            const perceptionData = await safeJson(perceptionR);
            const missions = await safeJson(missionsR);

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
                this.game.lastAgentData = agentData; // cache for UI cross-reference (e.g. mission turn-in checks)
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

            if (privateLogs) {
                try {
                    this.game.updatePrivateLogs(privateLogs, agentData ? agentData.pending_intent : null);
                } catch (e) {
                    console.error("Error updating Private Logs:", e);
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

            for (let [id, mesh] of this.game.agents.entries()) {
                mesh.visible = visibleAgentIds.has(id);
            }

            if (agentData) {
                this.game.updatePrivateUI(agentData);
            }
        } catch (e) {
            console.error("Poll error:", e);
        }
    }

    startPolling() {
        setInterval(() => this.pollState(), 1000);
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
                body: JSON.stringify({ action_type: actionType, data: data })
            });
            const result = await resp.json();
            if (result.status === 'success') {
                console.log(`${actionType} intent recorded.`);
                alert(`${actionType} Recorded. Awaiting the next game tick for processing.`);
                if (actionType === 'CANCEL') {
                    this.pollState();
                }
            } else {
                const errorDetail = typeof result.detail === 'object' ? JSON.stringify(result.detail) : result.detail;
                alert(`Command Failed: ${errorDetail || 'Access Denied'}`);
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

        let actionType = this.game.tradeSide === 'SELL' ? 'LIST' : 'BUY';
        let data = this.game.tradeSide === 'SELL'
            ? { item_type: itemType, price: price, quantity: quantity }
            : { item_type: itemType, max_price: price, quantity: quantity };

        await this.submitIntent(actionType, data);
        alert(`${actionType} intent queued for The Crunch!`);
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
            } else if (type === 'REPAIR') {
                const amount = parseInt(document.getElementById('repair-amount').value) || 0;
                data = { amount: amount };
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
