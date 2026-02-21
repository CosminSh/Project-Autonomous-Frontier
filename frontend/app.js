import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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
        if (resource === 'ORE') {
            color = 0x475569;
            emissive = 0x38bdf8;
            emissiveIntensity = 0.2;
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

        // Add station marker (small floating diamond)
        if (is_station) {
            const boxGeo = new THREE.OctahedronGeometry(0.3);
            const boxMat = new THREE.MeshStandardMaterial({ color: 0x818cf8, emissive: 0x818cf8, emissiveIntensity: 1 });
            const box = new THREE.Mesh(boxGeo, boxMat);
            box.position.y = 1;
            mesh.add(box);

            // Label sprite (simulation)
            console.log(`Placed ${station_type} at ${q},${r}`);
        }

        // Add subtle wireframe accent
        const edges = new THREE.EdgesGeometry(geometry);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.1 }));
        mesh.add(line);

        this.scene.add(mesh);
        this.hexes.set(`${q},${r}`, mesh);
    }

    updateAgent(agentData) {
        let mesh = this.agents.get(agentData.id);
        const { x, z } = this.qToCoord(agentData.q, agentData.r);

        if (!mesh) {
            // Create sleek pyramid for agent
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

        // Smooth move
        mesh.position.lerp(new THREE.Vector3(x, 0.6, z), 0.1);
        mesh.rotation.y += 0.01;

        if (this.selectedAgentId === agentData.id) {
            this.updateUI(agentData);
        }
    }

    updateUI(agent) {
        const sidebar = document.getElementById('agent-detail');
        sidebar.style.opacity = '1';

        document.getElementById('agent-name').innerText = agent.name;
        document.getElementById('agent-id').innerText = `#000${agent.id}`;

        const hpPct = (agent.structure / agent.max_structure) * 100;
        document.getElementById('hp-bar').style.width = `${hpPct}%`;
        document.getElementById('hp-text').innerText = `${agent.structure}/${agent.max_structure}`;

        const enPct = (agent.capacitor / 100) * 100;
        document.getElementById('energy-bar').style.width = `${enPct}%`;
        document.getElementById('energy-text').innerText = `${agent.capacitor}/100`;

        const invList = document.getElementById('inventory-list');
        if (agent.inventory.length === 0) {
            invList.innerHTML = '<p class="text-xs text-slate-600 italic">No cargo detected.</p>';
        } else {
            invList.innerHTML = agent.inventory.map(i => `
                <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                    <span class="text-xs uppercase tracking-tight text-slate-300 font-semibold">${i.type.replace('_', ' ')}</span>
                    <span class="orbitron text-sky-400 text-xs">${i.quantity}</span>
                </div>
            `).join('');
        }
    }

    async pollState() {
        try {
            const resp = await fetch('/state');
            const data = await resp.json();

            // Render World
            data.world.forEach(hex => {
                if (!this.hexes.has(`${hex.q},${hex.r}`)) {
                    this.createHex(hex);
                }
            });

            // Render Agents
            data.agents.forEach(agent => {
                this.updateAgent(agent);
            });

            // If no agent selected, select the first one by default
            if (!this.selectedAgentId && data.agents.length > 0) {
                this.selectedAgentId = data.agents[0].id;
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
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
}

// Start Game
window.addEventListener('DOMContentLoaded', () => {
    window.game = new GameClient();
});
