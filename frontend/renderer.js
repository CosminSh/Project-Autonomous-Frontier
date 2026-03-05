import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

/**
 * renderer.js — THREE.js Scene and Map rendering
 */
export class GameRenderer {
    constructor(game) {
        this.game = game;

        // Render State
        this.scene = new THREE.Scene();
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        // World Objects
        this.planetMesh = null;
        this.faceCentroids = [];
        this.debris = null;
        this.hexes = new Map();
        this.agents = new Map();
        this.resources = new Map();
        this.loots = new Map();
        this.poiLabels = new Map();

        // Selection
        this.selectedAgentId = null;
        this.hasCenteredInitially = false;
    }

    init() {
        // Skybox
        const loader = new THREE.TextureLoader();
        loader.load('https://agent8-games.verse8.io/mcp-agent8-generated/static-assets/skybox-14100960-1754694699668.jpg', (texture) => {
            texture.mapping = THREE.EquirectangularReflectionMapping;
            this.scene.background = texture;
            this.scene.environment = texture;

            if (!this.scene.backgroundRotation) {
                this.scene.backgroundRotation = new THREE.Euler();
            }
        });

        this.scene.fog = new THREE.FogExp2(0x050507, 0.002);

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
        this.controls.minDistance = 50.5;
        this.controls.maxDistance = 500;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 2);
        this.scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 4);
        sunLight.position.set(200, 100, 0);
        this.scene.add(sunLight);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x080820, 0.2);
        this.scene.add(hemiLight);

        // Atmosphere & Environment
        this.initAtmosphere();
        this.initAsteroid();
        this.game.api.fetchFullWorld();

        // View Resizer
        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // Click Handler (Raycasting)
        this.renderer.domElement.addEventListener('click', (e) => this.onWorldClick(e));

        // Center Camera Handler
        document.getElementById('center-camera-btn')?.addEventListener('click', () => this.centerOnAgent());
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.controls) this.controls.update();

        const stacks = new Map();

        // 1. Add POI labels to stacks
        for (let [faceIndex, poi] of this.poiLabels.entries()) {
            if (!stacks.has(faceIndex)) stacks.set(faceIndex, []);
            stacks.get(faceIndex).push({ mesh: poi.label, baseHeight: 1.5 });
        }

        // 2. Add visible agent labels to stacks
        for (let [id, mesh] of this.agents.entries()) {
            if (mesh.visible && mesh.userData.label) {
                const faceIndex = this.findNearestFace(mesh.position);
                if (!stacks.has(faceIndex)) stacks.set(faceIndex, []);
                stacks.get(faceIndex).push({ mesh: mesh.userData.label, baseHeight: 1.2 });
            }
        }

        // 3. Apply vertical offsets
        const STACK_INCREMENT = 0.6;
        for (let [faceIndex, labels] of stacks.entries()) {
            labels.sort((a, b) => (a.baseHeight > b.baseHeight ? 1 : -1));

            labels.forEach((item, index) => {
                if (item.mesh.parent === this.scene) {
                    const centroid = this.faceCentroids[faceIndex];
                    if (centroid) {
                        const altitude = 1.5 + (index * STACK_INCREMENT);
                        item.mesh.position.copy(centroid.clone().normalize().multiplyScalar(50 + altitude));
                    }
                } else {
                    item.mesh.position.y = 1.2 + (index * STACK_INCREMENT);
                }
            });
        }

        if (this.starfield) this.starfield.rotation.y += 0.00015;
        if (this.debris) {
            this.debris.rotation.y -= 0.0005;
            this.debris.rotation.z += 0.0002;
        }

        if (this.scene.backgroundRotation) {
            this.scene.backgroundRotation.y += 0.0002;
        }

        // 4. Spin Resources & Loot
        for (let mesh of this.resources.values()) {
            if (mesh.visible) {
                mesh.rotation.y += 0.02;
            }
        }
        for (let mesh of this.loots.values()) {
            if (mesh.visible) {
                mesh.rotation.x += 0.01;
                mesh.rotation.y += 0.02;
            }
        }

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    initAtmosphere() {
        const starGeom = new THREE.BufferGeometry();
        const starCount = 4000;
        const posArray = new Float32Array(starCount * 3);
        const colorArray = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount * 3; i++) {
            posArray[i] = (Math.random() - 0.5) * 1000;
            if (i % 3 === 0) {
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

        const debrisGeom = new THREE.BufferGeometry();
        const debrisCount = 300;
        const debrisPos = new Float32Array(debrisCount * 3);
        const debrisColors = new Float32Array(debrisCount * 3);
        const debrisSizes = new Float32Array(debrisCount);

        for (let i = 0; i < debrisCount * 3; i += 3) {
            debrisPos[i] = (Math.random() - 0.5) * 250;
            debrisPos[i + 1] = (Math.random() - 0.5) * 250;
            debrisPos[i + 2] = (Math.random() - 0.5) * 250;

            const shade = 0.3 + (Math.random() * 0.4);
            debrisColors[i] = shade;
            debrisColors[i + 1] = shade * 0.9;
            debrisColors[i + 2] = shade * 0.8;

            debrisSizes[i / 3] = 0.5 + Math.random() * 1.5;
        }
        debrisGeom.setAttribute('position', new THREE.BufferAttribute(debrisPos, 3));
        debrisGeom.setAttribute('color', new THREE.BufferAttribute(debrisColors, 3));
        debrisGeom.setAttribute('size', new THREE.BufferAttribute(debrisSizes, 1));

        const debrisMat = new THREE.PointsMaterial({
            size: 0.6,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            sizeAttenuation: true
        });

        this.debris = new THREE.Points(debrisGeom, debrisMat);
        this.scene.add(this.debris);
    }

    initAsteroid() {
        const PLANET_RADIUS = 50;
        const SUBDIVISIONS = 10;

        const icoGeo = new THREE.IcosahedronGeometry(PLANET_RADIUS, SUBDIVISIONS);
        const geo = icoGeo.toNonIndexed();

        const posAttr = geo.attributes.position;
        const faceCount = posAttr.count / 3;
        const colorArray = new Float32Array(posAttr.count * 3);
        for (let i = 0; i < posAttr.count; i++) {
            colorArray[i * 3] = 0.04;
            colorArray[i * 3 + 1] = 0.04;
            colorArray[i * 3 + 2] = 0.07;
        }
        geo.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));

        const mat = new THREE.MeshStandardMaterial({
            vertexColors: true,
            flatShading: true,
            metalness: 0.15,
            roughness: 0.85
        });

        this.planetMesh = new THREE.Mesh(geo, mat);
        this.scene.add(this.planetMesh);

        const edgeGeo = new THREE.EdgesGeometry(geo, 1);
        const edgeMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.15 });
        const wireframe = new THREE.LineSegments(edgeGeo, edgeMat);
        this.planetMesh.add(wireframe);

        this.faceCentroids = [];
        for (let f = 0; f < faceCount; f++) {
            const i = f * 3;
            const cx = (posAttr.getX(i) + posAttr.getX(i + 1) + posAttr.getX(i + 2)) / 3;
            const cy = (posAttr.getY(i) + posAttr.getY(i + 1) + posAttr.getY(i + 2)) / 3;
            const cz = (posAttr.getZ(i) + posAttr.getZ(i + 1) + posAttr.getZ(i + 2)) / 3;
            this.faceCentroids.push(new THREE.Vector3(cx, cy, cz));
        }

        console.log(`Geodesic planet: ${faceCount} faces, ${this.faceCentroids.length} centroids`);
    }

    qToSphere(q, r, altitude = 0) {
        const radius = 50 + altitude;

        // Lambert Equal-Area Cylindrical Projection
        // Hub is at (0, 50) = equator — no polar crowding.
        // q: 0-99 → longitude 0-2π (full wrap)
        // r: 0-100 → latitude via arcsin so areas are equal (not bunched at poles)
        const lon = (q / 100) * 2 * Math.PI;
        const t = ((r / 100) * 2) - 1; // maps 0..100 → -1..+1
        const lat = -Math.asin(Math.max(-0.9999, Math.min(0.9999, t)));

        return {
            x: radius * Math.cos(lat) * Math.cos(lon),
            y: radius * Math.sin(lat),
            z: radius * Math.cos(lat) * Math.sin(lon)
        };
    }


    createStationLabel(text) {
        return this.createLabel(text, '#facc15');
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

        ctx.shadowColor = color;
        ctx.shadowBlur = 8;
        ctx.fillStyle = color;
        ctx.fillText(text, 128, 32);

        const texture = new THREE.CanvasTexture(canvas);
        const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(spriteMat);
        sprite.scale.set(3, 0.75, 1);
        sprite.userData.isLabel = true;
        return sprite;
    }

    qToCoord(q, r) {
        const size = 1;
        const x = size * (3 / 2 * q);
        const z = size * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r);
        return { x, z };
    }

    createHex(hexData) {
        const { q, r, terrain, resource, is_station, station_type } = hexData;
        let color = new THREE.Color(0x1a1a2e);

        if (terrain === 'OBSTACLE') color = new THREE.Color(0x334155);
        if (terrain === 'STATION' || is_station) color = new THREE.Color(0x2d1b69);
        if (terrain === 'NEBULA') color = new THREE.Color(0x1e1b4b);
        if (terrain === 'ASTEROID') color = new THREE.Color(0x27272a);
        if (terrain === 'VOID') color = new THREE.Color(0x0d0d14);

        if (resource) {
            if (resource === 'IRON_ORE' || resource === 'ORE') color = new THREE.Color(0x8b5e3c);
            else if (resource === 'COBALT_ORE') color = new THREE.Color(0x1a6b7a);
            else if (resource === 'GOLD_ORE') color = new THREE.Color(0x7a6520);
        }

        const { x, y, z } = this.qToSphere(q, r);
        const targetPos = new THREE.Vector3(x, y, z);
        const faceIndex = this.findNearestFace(targetPos);

        if (faceIndex >= 0 && this.planetMesh) {
            const colors = this.planetMesh.geometry.attributes.color;
            const i = faceIndex * 3;
            colors.setXYZ(i, color.r, color.g, color.b);
            colors.setXYZ(i + 1, color.r, color.g, color.b);
            colors.setXYZ(i + 2, color.r, color.g, color.b);
            colors.needsUpdate = true;
        }

        this.hexes.set(`${q},${r}`, { faceIndex, color });

        if (is_station || terrain === 'STATION') {
            const labelText = (station_type || 'OUTPOST').toUpperCase();
            const label = this.createStationLabel(labelText);
            const centroid = this.faceCentroids[faceIndex];
            if (centroid) {
                const labelPos = centroid.clone().normalize().multiplyScalar(51.5);
                label.position.copy(labelPos);
                this.scene.add(label);
                this.poiLabels.set(faceIndex, { label, faceIndex });
            }
        }

        if (resource) {
            let resColor = 0xffffff;
            let scale = 0.8;
            if (resource === 'IRON_ORE' || resource === 'ORE') resColor = 0x94a3b8;
            else if (resource === 'COBALT_ORE') resColor = 0x38bdf8;
            else if (resource === 'GOLD_ORE') { resColor = 0xfbbf24; scale = 1.0; }

            const geom = new THREE.TetrahedronGeometry(scale, 0);
            const mat = new THREE.MeshStandardMaterial({ color: resColor, roughness: 0.2, metalness: 0.8, flatShading: true });
            const crystalMesh = new THREE.Mesh(geom, mat);

            const centroid = this.faceCentroids[faceIndex];
            if (centroid) {
                crystalMesh.position.copy(centroid.clone().normalize().multiplyScalar(50.2));
                crystalMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), centroid.clone().normalize());
                crystalMesh.rotateY(Math.random() * Math.PI);
                crystalMesh.scale.set(0.6, 1.2, 0.6);
                this.scene.add(crystalMesh);
            }
        }
    }

    findNearestFace(targetPos) {
        if (!this.faceCentroids) return -1;
        let bestIndex = 0;
        let bestDistSq = Infinity;
        for (let i = 0; i < this.faceCentroids.length; i++) {
            const dSq = this.faceCentroids[i].distanceToSquared(targetPos);
            if (dSq < bestDistSq) {
                bestDistSq = dSq;
                bestIndex = i;
            }
        }
        return bestIndex;
    }

    updateAgentMesh(agentData) {
        let mesh = this.agents.get(agentData.id);
        const q = agentData.q ?? agentData.location?.q ?? 0;
        const r = agentData.r ?? agentData.location?.r ?? 0;
        const visual = agentData.visual_signature || { chassis: 'BASIC', rarity: 'STANDARD' };

        if (!mesh) {
            let geometry;
            switch (visual.chassis) {
                case 'SHIELDED': geometry = new THREE.CylinderGeometry(0.5, 0.5, 0.8, 6); break;
                case 'HEAVY': geometry = new THREE.BoxGeometry(0.7, 0.7, 0.7); break;
                default: geometry = new THREE.ConeGeometry(0.5, 1, 4);
            }

            const rarityColors = { 'SCRAP': 0x64748b, 'STANDARD': 0x38bdf8, 'REFINED': 0x3b82f6, 'PRIME': 0xfacc15, 'RELIC': 0xf97316 };
            const rarityEmissives = { 'SCRAP': 0x334155, 'STANDARD': 0x0ea5e9, 'REFINED': 0x2563eb, 'PRIME': 0xeab308, 'RELIC': 0xea580c };

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

            const labelColor = agentData.is_feral ? '#ff4422' : '#38bdf8';
            const label = this.createLabel(agentData.name, labelColor);
            label.position.y = 1.2;
            mesh.add(label);
            mesh.userData.label = label;

            this.scene.add(mesh);
            this.agents.set(agentData.id, mesh);
        }

        const { x, y, z } = this.qToSphere(q, r, 1.5);
        const targetPos = new THREE.Vector3(x, y, z);

        if (mesh.position.lengthSq() < 1 || mesh.position.distanceTo(targetPos) > 10) {
            mesh.position.copy(targetPos);
        } else {
            mesh.position.lerp(targetPos, 0.1);
        }

        const up = targetPos.clone().normalize();
        const targetQuat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), up);
        mesh.quaternion.slerp(targetQuat, 0.15);

        if (visual.rarity === 'PRIME' || visual.rarity === 'RELIC') {
            const pulse = 0.5 + Math.sin(Date.now() * 0.005) * 0.3;
            if (mesh.material.emissiveIntensity !== undefined) {
                mesh.material.emissiveIntensity = pulse;
            }
        }
    }

    updateResourceMesh(resData) {
        const id = `${resData.q},${resData.r},${resData.type}`;
        let mesh = this.resources.get(id);

        if (!mesh) {
            let resColor = 0xffffff;
            let scale = 0.8;
            let emissive = 0x000000;
            let geom, mat;

            if (resData.type === 'IRON_ORE' || resData.type === 'ORE') resColor = 0x94a3b8;
            else if (resData.type === 'COBALT_ORE') resColor = 0x38bdf8;
            else if (resData.type === 'GOLD_ORE') { resColor = 0xfbbf24; scale = 1.0; }
            else if (resData.type === 'HE3_FUEL') {
                resColor = 0xa855f7; // Purple/Pink
                emissive = 0x9333ea;
                scale = 1.2;
            }

            if (resData.type === 'HE3_FUEL') {
                geom = new THREE.SphereGeometry(scale * 0.5, 8, 8);
                mat = new THREE.MeshStandardMaterial({
                    color: resColor,
                    emissive: emissive,
                    emissiveIntensity: 0.8,
                    transparent: true,
                    opacity: 0.7
                });
            } else {
                geom = new THREE.TetrahedronGeometry(scale, 0);
                mat = new THREE.MeshStandardMaterial({ color: resColor, roughness: 0.2, metalness: 0.8, flatShading: true });
            }

            mesh = new THREE.Mesh(geom, mat);
            if (resData.type !== 'HE3_FUEL') {
                mesh.scale.set(0.6, 1.2, 0.6);
            }

            const { x, y, z } = this.qToSphere(resData.q, resData.r, 0.5); // float slightly above ground
            mesh.position.set(x, y, z);
            mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), mesh.position.clone().normalize());

            this.scene.add(mesh);
            this.resources.set(id, mesh);
        }
    }

    updateLootMesh(lootData) {
        const id = `${lootData.q},${lootData.r},${lootData.item}`;
        let mesh = this.loots.get(id);

        if (!mesh) {
            const geom = new THREE.BoxGeometry(0.5, 0.5, 0.5);
            const mat = new THREE.MeshStandardMaterial({
                color: 0x10b981, // Emerald green
                emissive: 0x059669,
                emissiveIntensity: 0.6,
                roughness: 0.3,
                metalness: 0.5
            });

            mesh = new THREE.Mesh(geom, mat);

            const { x, y, z } = this.qToSphere(lootData.q, lootData.r, 0.5);
            mesh.position.set(x, y, z);
            mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), mesh.position.clone().normalize());

            this.scene.add(mesh);
            this.loots.set(id, mesh);
        }
    }


    handleWorldEvent(data) {
        if (data.event === 'MINING') {
            this.triggerVisualEffect(data.q, data.r, 0x00ff88);
        } else if (data.event === 'COMBAT') {
            const color = data.subtype === 'HIT' ? 0xff4444 : 0xaaaaaa;
            this.triggerVisualEffect(data.q, data.r, color);
        }
    }

    triggerVisualEffect(q, r, color) {
        const { x, y, z } = this.qToSphere(q, r, 0.5);

        // Simple spark/flare
        const geom = new THREE.SphereGeometry(0.2, 8, 8);
        const mat = new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 1 });
        const mesh = new THREE.Mesh(geom, mat);
        mesh.position.set(x, y, z);
        this.scene.add(mesh);

        // Animate out
        const duration = 1000;
        const start = Date.now();
        const anim = () => {
            const elapsed = Date.now() - start;
            const t = elapsed / duration;
            if (t >= 1) {
                this.scene.remove(mesh);
                return;
            }
            mesh.scale.set(1 + t * 3, 1 + t * 3, 1 + t * 3);
            mesh.material.opacity = 1 - t;
            requestAnimationFrame(anim);
        };
        anim();
    }

    centerOnAgent() {
        const myAgentId = parseInt(localStorage.getItem('sv_agent_id'));
        const mesh = this.agents.get(myAgentId);

        if (!mesh || !this.controls || !this.camera) {
            console.warn("Cannot center: Agent mesh not found or camera not ready.");
            return;
        }

        const agentPos = mesh.position.clone();
        const normal = agentPos.clone().normalize();
        const camDistance = 15;
        const targetCamPos = agentPos.clone().add(normal.multiplyScalar(camDistance));

        const startTarget = this.controls.target.clone();
        const startCamPos = this.camera.position.clone();
        const DURATION = 900;
        const startTime = performance.now();

        const animate = (now) => {
            const elapsed = now - startTime;
            const t = Math.min(1, elapsed / DURATION);
            const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

            this.controls.target.lerpVectors(startTarget, agentPos, ease);
            this.camera.position.lerpVectors(startCamPos, targetCamPos, ease);
            this.controls.update();

            if (t < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }

    onWorldClick(event) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);

        const agentMeshes = Array.from(this.agents.values());
        const intersects = this.raycaster.intersectObjects(agentMeshes);

        if (intersects.length > 0) {
            const selectedMesh = intersects[0].object;
            for (let [id, mesh] of this.agents.entries()) {
                if (mesh === selectedMesh) {
                    this.selectedAgentId = id;
                    this.game.ui.updateScannerUI(id);
                    return;
                }
            }
        }
    }
}
