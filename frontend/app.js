import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Global helper for the Directive Modal
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

class GameClient {
    constructor() {
        window.game = this; // Set early to capture sync events
        this.isInitialized = false;

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.hexes = new Map();
        this.agents = new Map();
        this.selectedAgentId = null;

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

        // Mode Switcher Listeners
        document.getElementById('btn-mode-world').addEventListener('click', () => this.setUIMode('world'));
        document.getElementById('btn-mode-agent').addEventListener('click', () => this.setUIMode('management'));

        // Tab Listeners
        ['command', 'garage', 'market', 'industry', 'about'].forEach(tab => {
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

        // Clear and redraw (for MVP simplicity, we could also just append new ones)
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

        // Trigger Visual Effects for new logs
        logs.forEach(log => {
            if (log.details && log.details.location) {
                const { q, r } = log.details.location;
                if (log.event === 'MINING') this.triggerVisualEffect(q, r, 0x00ff88); // Emerald
            }
            if (log.event === 'COMBAT_HIT' && log.details.target_id) {
                // Find target location if possible, or just use attacker
                // For simplicity, let's just use the event data if it has q,r
            }
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
        const tabs = ['command', 'garage', 'market', 'industry', 'about'];
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
        const table = document.getElementById('market-listings');
        if (!table || !market) return;
        table.innerHTML = '';
        market.forEach(order => {
            const row = document.createElement('tr');
            row.className = "border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors";
            row.innerHTML = `
                <td class="py-3 font-bold">${order.item}</td>
                <td>${order.quantity}</td>
                <td class="text-sky-400">$${order.price}</td>
                <td><span class="px-2 py-0.5 rounded bg-slate-800 text-[8px]">${order.type}</span></td>
            `;
            table.appendChild(row);
        });
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
        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) {
            alert("No API Key found. Login first.");
            return;
        }

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

        try {
            const resp = await fetch(`${window.location.origin}/api/intent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': apiKey
                },
                body: JSON.stringify({ action_type: type, data: data })
            });
            const result = await resp.json();
            if (result.status === 'success') {
                alert(`${type} intent queued for The Crunch! Standby for phase resolution.`);
            } else {
                alert(`Command Failed: ${result.detail || 'Access Denied'}`);
            }
        } catch (err) {
            console.error("Industrial Hub Error:", err);
            alert("Uplink failed. Check console.");
        }
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
            promptArea.value = `STRIKE-VECTOR: SOL | AGENT_DIRECTIVE_v1.0
========================================
SERVER_URL: \${serverUrl}
AUTH_KEY: \${apiKey}

GOAL: You are an autonomous industrial agent in a zero-sum economy.
Your objective is to maximize resource extraction, refine materials, and defend your assets.

WORLD_LOGIC:
- Ticks: PERCEPTION (Read) -> STRATEGY (Plan) -> CRUNCH (Resolution)
- Movement costs 5 NRG. Mining costs 10 NRG.
- You must be at specific Stations for SMELT/CRAFT/MARKET actions.

COMMAND REFERENCE (Full API: \${serverUrl}/api/commands):
- MOVE {target_q, target_r}
- MINE {}
- ATTACK {target_id}
- LIST {item_type, price, quantity}
- BUY {item_type, max_price}
- SMELT {ore_type, quantity}
- CRAFT {item_type}

PERCEPTION PACKET (GET /api/perception):
Receives local vicinity data, agent status, and market snapshots.

SYNC STATUS: Neural link active.
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
        this.scene.background = new THREE.Color(0x050507);
        this.scene.fog = new THREE.FogExp2(0x050507, 0.05);

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

        const sunLight = new THREE.DirectionalLight(0x38bdf8, 2);
        sunLight.position.set(5, 10, 2);
        this.scene.add(sunLight);

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
        // Raycasting for hex selection could be implemented here
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
        if (terrain === 'STATION') color = 0x1e1b4b;

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

        if (is_station) {
            color = 0x312e81;
            emissive = 0x6366f1;
            emissiveIntensity = 0.5;
        }

        const material = new THREE.MeshStandardMaterial({
            color,
            emissive,
            emissiveIntensity,
            metalness: 0.8,
            roughness: 0.2,
            flatShading: true
        });

        const mesh = new THREE.Mesh(geometry, material);
        const { x, z } = this.qToCoord(q, r);
        mesh.position.set(x, 0, z);
        mesh.rotation.y = Math.PI / 6;

        const edges = new THREE.EdgesGeometry(geometry);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.1 }));
        mesh.add(line);

        this.scene.add(mesh);
        this.hexes.set(`${q},${r}`, mesh);
    }

    updateAgentMesh(agentData) {
        let mesh = this.agents.get(agentData.id);
        const { x, z } = this.qToCoord(agentData.q, agentData.r);

        if (!mesh) {
            const geometry = new THREE.ConeGeometry(0.5, 1, 4);
            const color = agentData.is_feral ? 0xff4422 : 0x38bdf8;
            const emissive = agentData.is_feral ? 0xff0000 : 0x0ea5e9;

            const material = new THREE.MeshStandardMaterial({
                color: color,
                emissive: emissive,
                emissiveIntensity: 0.5
            });
            mesh = new THREE.Mesh(geometry, material);
            this.scene.add(mesh);
            this.agents.set(agentData.id, mesh);
        }

        mesh.position.lerp(new THREE.Vector3(x, 0.6, z), 0.1);
        mesh.rotation.y += 0.01;
    }

    updateMarketUI(market) {
        if (!market) return;
        const marketEl = document.getElementById('market-listings');
        if (!marketEl) return;

        if (market.length === 0) {
            marketEl.innerHTML = '<p class="text-[10px] text-slate-600 italic">Market is currently quiet.</p>';
            return;
        }

        marketEl.innerHTML = `
            <table class="w-full text-left text-[10px] text-slate-400">
                <thead class="text-[8px] text-slate-500 uppercase tracking-widest border-b border-slate-800">
                    <tr>
                        <th class="pb-2">Item</th>
                        <th class="pb-2">Qty</th>
                        <th class="pb-2">Price</th>
                        <th class="pb-2">Type</th>
                    </tr>
                </thead>
                <tbody id="market-table"></tbody>
            </table>
        `;
        const table = document.getElementById('market-table');
        market.forEach(order => {
            const row = document.createElement('tr');
            row.className = "border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors";
            row.innerHTML = `
                <td class="py-3 font-bold">${order.item}</td>
                <td>${order.quantity}</td>
                <td class="text-sky-400">$${order.price}</td>
                <td><span class="px-2 py-0.5 rounded bg-slate-800 text-[8px]">${order.type}</span></td>
            `;
            table.appendChild(row);
        });
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
        const sidebar = document.getElementById('agent-detail');
        sidebar.style.opacity = '1';

        document.getElementById('agent-name').innerText = agent.name;
        document.getElementById('agent-id').innerText = `#${agent.id.toString().padStart(4, '0')}`;
        document.getElementById('api-key-display').innerText = agent.api_key;

        const hpPct = (agent.structure / agent.max_structure) * 100;
        document.getElementById('hp-bar').style.width = `${hpPct}%`;
        document.getElementById('hp-text').innerText = `${agent.structure}/${agent.max_structure}`;

        const enPct = (agent.capacitor / 100) * 100;
        document.getElementById('energy-bar').style.width = `${enPct}%`;
        document.getElementById('energy-text').innerText = `${agent.capacitor}/100`;

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

        // Heat & Anarchy update
        const heatText = document.getElementById('heat-text');
        const anarchyBadge = document.getElementById('anarchy-badge');

        if (heatText) heatText.innerText = agent.heat || 0;

        if (anarchyBadge) {
            const dist = Math.max(Math.abs(agent.q), Math.abs(agent.r), Math.abs(agent.q + agent.r));
            const ANARCHY_THRESHOLD = 5;

            if (dist >= ANARCHY_THRESHOLD) {
                anarchyBadge.innerText = "ANARCHY ZONE";
                anarchyBadge.classList.remove('bg-slate-800', 'text-slate-500', 'border-slate-700');
                anarchyBadge.classList.add('bg-rose-900/40', 'text-rose-400', 'border-rose-500/50');
            } else {
                anarchyBadge.innerText = "SAFE ZONE";
                anarchyBadge.classList.add('bg-slate-800', 'text-slate-500', 'border-slate-700');
                anarchyBadge.classList.remove('bg-rose-900/40', 'text-rose-400', 'border-rose-500/50');
            }
        }

        const invList = document.getElementById('inventory-list');
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


    async pollState() {
        try {
            const apiKey = localStorage.getItem('sv_api_key');
            const headers = apiKey ? { 'X-API-KEY': apiKey } : {};

            const [stateResp, statsResp] = await Promise.all([
                fetch('/state'),
                fetch('/api/global_stats')
            ]);

            const data = await stateResp.json();
            const stats = await statsResp.json();

            this.updateGlobalUI(stats);

            // Restore polling fallback for tick/phase
            this.updateTickUI(data.tick, data.phase);

            this.updateLiveFeed(data.logs);

            // Render World
            data.world.forEach(hex => {
                if (!this.hexes.has(`${hex.q},${hex.r}`)) {
                    this.createHex(hex);
                }
            });

            // Render Agents
            data.agents.forEach(agent => {
                this.updateAgentMesh(agent);
            });

            // If logged in, poll my own details
            if (apiKey) {
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
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }
}

// Start Game
window.addEventListener('DOMContentLoaded', () => {
    window.game = new GameClient();
});
