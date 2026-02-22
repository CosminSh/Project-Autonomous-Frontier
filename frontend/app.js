import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

function copyAgentPrompt() {
    const prompt = document.getElementById('agent-prompt');
    const apiKey = localStorage.getItem('sv_api_key') || 'YOUR_API_KEY_HERE';
    const serverUrl = window.location.origin;

    // Dynamically inject current values for easy copy-paste
    let text = prompt.value;
    text = text.replace('[PASTE_SERVER_URL_HERE]', serverUrl);
    text = text.replace('[YOUR_API_KEY]', apiKey);

    navigator.clipboard.writeText(text);
    alert('Agent Directive copied to clipboard!');
}

class GameClient {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.hexes = new Map();
        this.agents = new Map();
        this.selectedAgentId = null;

        this.init();
        this.animate();
        this.startPolling();

        // Setup UI Listeners
        document.getElementById('logout-btn').addEventListener('click', () => this.logout());
        document.getElementById('copy-api-btn').addEventListener('click', () => this.copyApiKey());

        // Mode Switcher Listeners
        document.getElementById('btn-mode-world').addEventListener('click', () => this.setUIMode('world'));
        document.getElementById('btn-mode-agent').addEventListener('click', () => this.setUIMode('management'));

        // Tab Listeners
        ['command', 'garage', 'market'].forEach(tab => {
            document.getElementById(`tab-${tab}`).addEventListener('click', () => this.switchTab(tab));
        });

        // Check for existing session
        this.checkAuth();
    }

    setUIMode(mode) {
        const privateLayer = document.getElementById('private-dashboard');
        const btnWorld = document.getElementById('btn-mode-world');
        const btnAgent = document.getElementById('btn-mode-agent');

        if (mode === 'world') {
            privateLayer.classList.add('hidden');
            btnWorld.classList.add('bg-sky-500', 'text-slate-950');
            btnWorld.classList.remove('text-slate-400');
            btnAgent.classList.remove('bg-sky-500', 'text-slate-950');
            btnAgent.classList.add('text-slate-400');
        } else {
            privateLayer.classList.remove('hidden');
            btnAgent.classList.add('bg-sky-500', 'text-slate-950');
            btnAgent.classList.remove('text-slate-400');
            btnWorld.classList.remove('bg-sky-500', 'text-slate-950');
            btnWorld.classList.add('text-slate-400');
        }
    }

    switchTab(tabName) {
        const tabs = ['command', 'garage', 'market'];
        tabs.forEach(t => {
            const content = document.getElementById(`content-${t}`);
            const btn = document.getElementById(`tab-${t}`);
            if (t === tabName) {
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
            alert("Connection Error: Could not reach the authentication server. Verify the backend is running on port 8001.");
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
            const material = new THREE.MeshStandardMaterial({
                color: 0x38bdf8,
                emissive: 0x0ea5e9,
                emissiveIntensity: 0.5
            });
            mesh = new THREE.Mesh(geometry, material);
            this.scene.add(mesh);
            this.agents.set(agentData.id, mesh);
        }

        mesh.position.lerp(new THREE.Vector3(x, 0.6, z), 0.1);
        mesh.rotation.y += 0.01;
    }

    updateGlobalUI(stats) {
        document.getElementById('stat-agents').innerText = stats.total_agents || 0;
        document.getElementById('stat-market').innerText = stats.market_listings || 0;
    }

    updatePrivateUI(agent) {
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
                const myAgentData = await myAgentResp.json();
                if (myAgentData.status !== 'error') {
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
