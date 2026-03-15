import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

/**
 * renderer.js — THREE.js Scene and Map rendering
 */

/**
 * Socket definitions for each chassis type to ensure parts align correctly.
 */
const CHASSIS_TEMPLATES = {
    'BASIC': {
        engines: [{ x: 0, y: 0, z: -0.5 }],
        sensors: [{ x: 0, y: 0.3, z: 0 }],
        actuators: [{ x: -0.2, y: 0, z: 0.4 }, { x: 0.2, y: 0, z: 0.4 }],
        power: [{ x: -0.6, y: 0.1, z: 0 }, { x: 0.6, y: 0.1, z: 0 }]
    },
    'STRIKER': {
        engines: [{ x: -0.15, y: 0, z: -0.5 }, { x: 0.15, y: 0, z: -0.5 }],
        sensors: [{ x: 0, y: 0.2, z: 0 }],
        actuators: [{ x: -0.25, y: 0, z: 0.5 }, { x: 0, y: 0, z: 0.6 }, { x: 0.25, y: 0, z: 0.5 }],
        power: []
    },
    'HEAVY': {
        engines: [{ x: 0, y: 0, z: -0.6 }],
        sensors: [{ x: 0, y: 0.35, z: 0.1 }],
        actuators: [{ x: 0, y: 0, z: 0.7 }],
        power: [{ x: -0.5, y: 0.4, z: -0.2 }, { x: 0, y: 0.4, z: -0.2 }, { x: 0.5, y: 0.4, z: -0.2 }]
    },
    'INDUSTRIAL': {
        engines: [{ x: 0, y: 0, z: -0.8 }],
        sensors: [{ x: -0.3, y: 0.5, z: 0 }, { x: 0.3, y: 0.5, z: 0 }],
        actuators: [{ x: -0.4, y: 0, z: 0.8 }, { x: -0.15, y: 0, z: 0.8 }, { x: 0.15, y: 0, z: 0.8 }, { x: 0.4, y: 0, z: 0.8 }],
        power: [{ x: -0.6, y: 0.5, z: -0.4 }, { x: 0.6, y: 0.5, z: -0.4 }]
    },
    'SHIELDED': {
        engines: [{ x: 0, y: 0, z: -0.5 }],
        sensors: [{ x: 0, y: 0.6, z: 0 }],
        actuators: [{ x: -0.3, y: 0, z: 0.5 }, { x: 0.3, y: 0, z: 0.5 }],
        power: [{ x: 0, y: 0.3, z: -0.4 }]
    },
    'HYBRID': {
        engines: [{ x: -0.2, y: 0, z: -0.4 }, { x: 0.2, y: 0, z: -0.4 }],
        sensors: [{ x: 0, y: 0.5, z: 0 }],
        actuators: [{ x: -0.3, y: 0, z: 0.4 }, { x: 0.3, y: 0, z: 0.4 }],
        power: [{ x: -0.5, y: 0.2, z: 0 }, { x: 0.5, y: 0.2, z: 0 }]
    }
};

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
        this.faceToHex = new Map();
        this.agentPaths = new Map();
        
        // Debug & Visual Helpers
        this.debugGrid = new THREE.Group();
        this.isDebugVisible = false;
        this.debugMarker = null;

        // Selection
        this.selectedAgentId = null;
        this.selectedHex = null; // {q, r}
        this.selectionRing = null;
        this.hasCenteredInitially = false;
    }

    init() {
        // Skybox
        this.scene.background = new THREE.Color(0x020205);
        const loader = new THREE.TextureLoader();
        loader.load('https://agent8-games.verse8.io/mcp-agent8-generated/static-assets/skybox-14100960-1754694699668.jpg', (texture) => {
            texture.mapping = THREE.EquirectangularReflectionMapping;
            // Background remains dark, but environment provides reflections
            this.scene.environment = texture;
        });

        this.scene.fog = new THREE.FogExp2(0x020205, 0.002);

        // Camera
        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(0, 5, 30); // Zoomed out to show the full planet initially
        this.camera.lookAt(0, 0, 0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setClearColor(0x020205, 1);
        document.getElementById('canvas-container').appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 2.0;
        this.controls.maxDistance = 1000;

        // Lighting - Reduced for Holographic emissive look
        const ambientLight = new THREE.AmbientLight(0x404040, 0.2);
        this.scene.add(ambientLight);

        const hemiLight = new THREE.HemisphereLight(0x38bdf8, 0x020205, 0.5);
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
        this.renderer.domElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.onWorldRightClick(e);
        });

        // Center Camera Handler
        document.getElementById('center-camera-btn')?.addEventListener('click', () => this.centerOnAgent());

        // Debug Key Listener (F2)
        window.addEventListener('keydown', (e) => {
            if (e.key === 'F2') {
                this.toggleDebugGrid();
            }
        });

        // Initialize Selection Ring
        this.initSelectionRing();
    }

    initSelectionRing() {
        const hexPoints = [];
        const size = 1.1; // Slightly larger than hex
        for (let i = 0; i < 7; i++) { // 7 points to close the loop
            const angle = (Math.PI / 3) * i + (Math.PI / 6);
            hexPoints.push(new THREE.Vector3(size * Math.cos(angle), size * Math.sin(angle), 0));
        }
        
        const geometry = new THREE.BufferGeometry().setFromPoints(hexPoints);
        const material = new THREE.LineBasicMaterial({
            color: 0x38bdf8,
            linewidth: 2,
            transparent: true,
            opacity: 0.8
        });

        this.selectionRing = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.ShapeGeometry(new THREE.Shape(hexPoints.map(p => new THREE.Vector2(p.x, p.y))))),
            material
        );
        this.selectionRing.visible = false;
        this.scene.add(this.selectionRing);

        // Add a pulsing effect in the animate loop instead of a separate requestAnimationFrame if possible,
        // but for now, we'll just let it be. 
        // Actually, let's just add it to the selectionRing userData for tracking.
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.controls) this.controls.update();

        // Prevent camera from going inside the planet (radius 50)
        if (this.camera) {
            const minAltitude = 51.5;
            if (this.camera.position.length() < minAltitude) {
                this.camera.position.normalize().multiplyScalar(minAltitude);
            }
        }

        // 0. Update Holographic Pulse Uniforms
        const holographicTime = Date.now() * 0.001;
        this.scene.traverse((obj) => {
            if (obj.isMesh && obj.material && obj.material.userData && obj.material.userData.isHolographic) {
                obj.material.uniforms.time.value = holographicTime;
            }
        });

        // 0. Update Selection Ring Pulse
        if (this.selectionRing && this.selectionRing.visible) {
            const s = 1.0 + Math.sin(Date.now() * 0.005) * 0.05;
            this.selectionRing.scale.set(s, s, 1);
        }

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

        // 4. Spin Resources (Only Gas) & Loot
        for (let mesh of this.resources.values()) {
            if (mesh.visible) {
                if (mesh.userData.isGas) mesh.rotation.y += 0.02;
                
                // Animate Pulsing Core
                const pulse = 0.6 + Math.sin(Date.now() * 0.005) * 0.4;
                mesh.traverse(child => {
                    if (child.userData.isPulseCore) {
                        child.scale.setScalar(pulse);
                        child.material.opacity = pulse * 0.8;
                    }
                });

                // Animate Data Stream
                if (mesh.userData.stream) {
                    mesh.userData.stream.children.forEach(p => {
                        p.position.y += p.userData.riseSpeed;
                        if (p.position.y > 2.5) p.position.y = 0;
                        p.material.opacity = (2.5 - p.position.y) / 2.5;
                    });
                }
            }
        }
        // 5. Animate Agent Parts
        const time = Date.now() * 0.005;
        for (let mesh of this.agents.values()) {
            if (mesh.visible) {
                if (mesh.userData.dish) {
                    mesh.userData.dish.rotation.y = Math.sin(time * 0.5) * 0.5;
                }
                if (mesh.userData.tools) {
                    mesh.userData.tools.forEach(t => t.rotation.y += 0.1);
                }
            }
        }

        if (this.scanWireframe) {
            this.scanWireframe.material.uniforms.time.value = holographicTime * 2.0;
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

        // Procedural Galaxy Clouds / Nebulas
        const nebulaCount = 80;
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');
        
        // Complex gradient for more "dusty" feel
        const grad = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
        grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)');
        grad.addColorStop(0.3, 'rgba(255, 255, 255, 0.4)');
        grad.addColorStop(0.7, 'rgba(255, 255, 255, 0.1)');
        grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 256, 256);
        
        const nebulaTex = new THREE.CanvasTexture(canvas);

        const nebulaColors = [
            0x1e1b4b, // Deep Indigo
            0x312e81, // Indigo
            0x2d1b69, // Dark Purple
            0x0f172a, // Dark Slate
            0x064e3b, // Deep Emerald/Teal (Iridescence)
            0x4c1d95, // Bright Purple
            0x1e293b  // Cool Gray
        ];

        console.log(`[Renderer] Deploying deep-space nebula field (${nebulaCount} clusters)...`);
        for (let i = 0; i < nebulaCount; i++) {
            const color = nebulaColors[Math.floor(Math.random() * nebulaColors.length)];
            const nebulaMat = new THREE.SpriteMaterial({
                map: nebulaTex,
                color: color,
                transparent: true,
                opacity: 0.15 + (Math.random() * 0.2), 
                blending: THREE.AdditiveBlending,
                fog: false
            });
            const nebula = new THREE.Sprite(nebulaMat);
            
            // Distribute across a larger shell (400 to 900)
            const radius = 400 + Math.random() * 500;
            const phi = Math.random() * Math.PI * 2;
            const theta = Math.random() * Math.PI;
            
            nebula.position.set(
                radius * Math.sin(theta) * Math.cos(phi),
                radius * Math.cos(theta),
                radius * Math.sin(theta) * Math.sin(phi)
            );
            
            // Vary sizes significantly to fill gaps
            const size = 300 + Math.random() * 1000;
            nebula.scale.set(size, size * (0.4 + Math.random() * 0.8), 1);
            nebula.material.rotation = Math.random() * Math.PI;
            this.scene.add(nebula);
        }

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
        const geo = icoGeo.index ? icoGeo.toNonIndexed() : icoGeo;

        const posAttr = geo.attributes.position;
        const faceCount = posAttr.count / 3;
        const colorArray = new Float32Array(posAttr.count * 3);
        
        // Initialize color attribute to avoid TypeError in createHex
        geo.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));
        
        const mat = new THREE.MeshBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });

        this.planetMesh = new THREE.Mesh(geo, mat);
        this.scene.add(this.planetMesh);

        // Primary Neon Wireframe
        const edgeGeo = new THREE.EdgesGeometry(geo, 1);
        const edgeMat = new THREE.LineBasicMaterial({
            color: 0x38bdf8,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending
        });
        const wireframe = new THREE.LineSegments(edgeGeo, edgeMat);
        this.planetMesh.add(wireframe);

        // Secondary Pulsing Glow Wireframe (Scan Ripple)
        const scanRippleMat = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                color: { value: new THREE.Color(0x0ea5e9) }
            },
            vertexShader: `
                varying vec3 vPosition;
                void main() {
                    vPosition = position;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform vec3 color;
                varying vec3 vPosition;
                void main() {
                    float ripple = sin(vPosition.y * 0.5 - time * 2.0) * 0.5 + 0.5;
                    ripple = pow(ripple, 8.0); // Sharpen the ripple
                    gl_FragColor = vec4(color, ripple * 0.5);
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        this.scanWireframe = new THREE.LineSegments(edgeGeo, scanRippleMat);
        this.scanWireframe.scale.setScalar(1.005);
        this.planetMesh.add(this.scanWireframe);

        // Atmospheric Outer Glow
        const glowGeo = new THREE.SphereGeometry(PLANET_RADIUS * 1.05, 32, 32);
        const glowMat = new THREE.MeshBasicMaterial({
            color: 0x0369a1,
            transparent: true,
            opacity: 0.1,
            side: THREE.BackSide,
            blending: THREE.AdditiveBlending
        });
        const atmosphere = new THREE.Mesh(glowGeo, glowMat);
        this.scene.add(atmosphere);

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

    sphereToQ(vector) {
        const radius = vector.length();
        
        // Inverse of qToSphere
        // lon = atan2(z, x)
        let lon = Math.atan2(vector.z, vector.x);
        if (lon < 0) lon += Math.PI * 2;
        
        // lat = asin(y / r)
        const lat = Math.asin(Math.max(-0.9999, Math.min(0.9999, vector.y / radius)));
        
        // lat = -asin(t)  =>  t = -sin(lat)
        const t = -Math.sin(lat);
        
        // t = (r/100 * 2) - 1  => r = (t + 1) / 2 * 100
        let r = ((t + 1) / 2) * 100;
        let q = (lon / (2 * Math.PI)) * 100;
        
        // Clamp to valid range to prevent pole jump
        r = Math.max(0, Math.min(100, Math.round(r)));
        q = (Math.round(q) + 100) % 100;

        // Pole Snapping: If at pole, q is irrelevant. Normalize to 0 for consistency.
        if (r === 0 || r === 100) q = 0;

        return { q, r };
    }

    toggleDebugGrid() {
        if (this.debugGrid.children.length === 0) {
            this.initDebugGrid();
        }
        this.isDebugVisible = !this.isDebugVisible;
        this.debugGrid.visible = this.isDebugVisible;
        console.log(`[Renderer] Debug Grid ${this.isDebugVisible ? 'ENABLED' : 'DISABLED'}`);
        
        // Show a temporary toast
        if (window.game && window.game.ui) {
            window.game.ui.showToast(`Debug Grid: ${this.isDebugVisible ? 'ON' : 'OFF'}`, 'info');
        }
    }

    initDebugGrid() {
        console.log('[Renderer] Initializing Debug Grid Labels...');
        this.debugGrid.clear();
        
        // Add coordinate labels every 10 units
        for (let q = 0; q < 100; q += 10) {
            for (let r = 0; r <= 100; r += 10) {
                // Pruning: Only show one label at the poles (q=0)
                if ((r === 0 || r === 100) && q > 0) continue;

                const label = this.createLabel(`${q},${r}`, '#fbbf24');
                const { x, y, z } = this.qToSphere(q, r, 2);
                label.position.set(x, y, z);
                label.lookAt(new THREE.Vector3(0,0,0)); // Faces away from center
                label.scale.set(3, 1, 1);
                this.debugGrid.add(label);
            }
        }
        
        // Add major axis markers (Equator and Prime Meridian)
        for (let q = 0; q < 100; q++) {
            const { x, y, z } = this.qToSphere(q, 50, 0.5);
            const dot = new THREE.Mesh(new THREE.SphereGeometry(0.2), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
            dot.position.set(x, y, z);
            this.debugGrid.add(dot);
        }

        this.scene.add(this.debugGrid);
        this.debugGrid.visible = false;
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

    createHolographicMaterial(color, opacity = 0.7) {
        const material = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                baseColor: { value: new THREE.Color(color) },
                opacity: { value: opacity }
            },
            vertexShader: `
                varying vec3 vNormal;
                varying vec3 vPosition;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    vPosition = position;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform vec3 baseColor;
                uniform float opacity;
                varying vec3 vNormal;
                varying vec3 vPosition;
                void main() {
                    // Fresnel effect
                    float fresnel = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.0);
                    
                    // Scanlines
                    float scanline = sin(vPosition.y * 20.0 - time * 5.0) * 0.1 + 0.9;
                    
                    // Flicker
                    float flicker = (sin(time * 50.0) * 0.02) + 0.98;
                    
                    vec3 finalColor = baseColor * (fresnel + 0.5) * scanline * flicker;
                    gl_FragColor = vec4(finalColor, opacity * (fresnel + 0.3));
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending,
            side: THREE.DoubleSide
        });
        material.userData.isHolographic = true;
        return material;
    }

    createTrail(color) {
        const trailCount = 20;
        const geom = new THREE.BufferGeometry();
        const posAttr = new THREE.BufferAttribute(new Float32Array(trailCount * 3), 3);
        geom.setAttribute('position', posAttr);
        const mat = new THREE.PointsMaterial({
            color: color,
            size: 0.15,
            transparent: true,
            opacity: 0.5,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: true
        });
        const points = new THREE.Points(geom, mat);
        points.userData.history = [];
        return points;
    }

    updateTrail(trail, currentPos) {
        const history = trail.userData.history;
        history.unshift(currentPos);
        if (history.length > 20) history.pop();

        const posAttr = trail.geometry.attributes.position;
        for (let i = 0; i < 20; i++) {
            if (history[i]) {
                posAttr.setXYZ(i, history[i].x, history[i].y, history[i].z);
            } else {
                posAttr.setXYZ(i, currentPos.x, currentPos.y, currentPos.z);
            }
        }
        posAttr.needsUpdate = true;
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

        if (terrain === 'OBSTACLE') color = new THREE.Color(0x0c2d4d);
        if (terrain === 'STATION' || is_station) color = new THREE.Color(0x164e63);
        if (terrain === 'NEBULA') color = new THREE.Color(0x1e1b4b);
        if (terrain === 'ASTEROID' || terrain === 'VOID') color = new THREE.Color(0x020814);

        if (resource) {
            if (resource === 'IRON_ORE' || resource === 'ORE') color = new THREE.Color(0x8b5e3c);
            else if (resource === 'COBALT_ORE') color = new THREE.Color(0x1a6b7a);
            else if (resource === 'GOLD_ORE') color = new THREE.Color(0x7a6520);
            else if (resource === 'TITANIUM_ORE') color = new THREE.Color(0x06b6d4); // Cyan
            else if (resource === 'VOID_CRYSTAL') color = new THREE.Color(0xa855f7); // Purple
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

            // Map this face to the logical hex that colored it
            this.faceToHex.set(faceIndex, { q, r });
        }

        this.hexes.set(`${q},${r}`, { faceIndex, color });

        if (is_station || terrain === 'STATION') {
            const labelText = (station_type || 'OUTPOST').toUpperCase();
            const label = this.createStationLabel(labelText);
            const centroid = this.faceCentroids[faceIndex];
            if (centroid) {
                const labelPos = centroid.clone().normalize().multiplyScalar(56.5);
                label.position.copy(labelPos);
                this.scene.add(label);
                this.poiLabels.set(faceIndex, { label, faceIndex });

                // Add 3D Station Structure
                const stationMesh = this.createStationMesh(station_type || 'OUTPOST');
                const stationPos = centroid.clone().normalize().multiplyScalar(50.2);
                stationMesh.position.copy(stationPos);
                stationMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), centroid.clone().normalize());
                this.scene.add(stationMesh);
            }
        }

        if (resource) {
            let resColor = 0xffffff;
            let isGas = false;
            let scale = 1.0;

            if (resource.includes('IRON') || resource === 'ORE') resColor = 0x8b5e3c; // Rust/Iron
            else if (resource.includes('COPPER')) resColor = 0xb45309; // Amber/Copper
            else if (resource.includes('GOLD')) { resColor = 0xfacc15; scale = 1.2; }
            else if (resource.includes('COBALT')) resColor = 0x0ea5e9;
            else if (resource.includes('HE3') || resource.includes('GAS')) { resColor = 0x3b82f6; isGas = true; }

            let geom, mat, mesh;

            if (isGas) {
                // Keep flaming crystal for gas
                geom = new THREE.TetrahedronGeometry(0.8, 0);
                mat = new THREE.MeshStandardMaterial({ color: resColor, roughness: 0.2, metalness: 0.8, emissive: resColor, emissiveIntensity: 0.5, flatShading: true });
                mesh = new THREE.Mesh(geom, mat);
            } else {
                // Boulders for ores
                geom = new THREE.DodecahedronGeometry(scale, 1);
                const pos = geom.attributes.position;
                for (let i = 0; i < pos.count; i++) {
                    const noise = Math.random() * 0.4 - 0.2;
                    pos.setX(i, pos.getX(i) + noise);
                    pos.setY(i, pos.getY(i) + noise);
                    pos.setZ(i, pos.getZ(i) + noise);
                }
                geom.computeVertexNormals();

                mat = new THREE.MeshStandardMaterial({ color: resColor, roughness: 0.9, metalness: 0.2, flatShading: true });
                mesh = new THREE.Mesh(geom, mat);
            }

            // Create Pulsing Core for Resources
            const coreGeom = isGas ? new THREE.IcosahedronGeometry(0.4, 0) : new THREE.DodecahedronGeometry(scale * 0.4, 0);
            const coreMat = new THREE.MeshBasicMaterial({ color: resColor, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending });
            const pulseCore = new THREE.Mesh(coreGeom, coreMat);
            pulseCore.userData.isPulseCore = true;
            mesh.add(pulseCore);

            // Add Vertical Data Stream (rising particles)
            const streamGroup = new THREE.Group();
            for (let i = 0; i < 3; i++) {
                const particle = new THREE.Mesh(
                    new THREE.BoxGeometry(0.1, 0.1, 0.1),
                    new THREE.MeshBasicMaterial({ color: resColor, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending })
                );
                particle.position.y = Math.random() * 2;
                particle.userData.riseSpeed = 0.01 + Math.random() * 0.02;
                streamGroup.add(particle);
            }
            mesh.add(streamGroup);
            mesh.userData.stream = streamGroup;

            const centroid = this.faceCentroids[faceIndex];
            if (centroid) {
                if (isGas) {
                    mesh.position.copy(centroid.clone().normalize().multiplyScalar(50.6));
                    mesh.scale.set(0.6, 1.2, 0.6);
                    mesh.userData.isGas = true;
                } else {
                    mesh.position.copy(centroid.clone().normalize().multiplyScalar(49.8));
                    mesh.scale.set(1.0, 0.5 + Math.random() * 0.4, 1.0); // Flatten slightly
                    mesh.userData.isGas = false;
                }

                mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), centroid.clone().normalize());
                mesh.rotateY(Math.random() * Math.PI);
                this.scene.add(mesh);
            }
        }
    }

    createStationMesh(type) {
        const group = new THREE.Group();
        const mat = new THREE.MeshBasicMaterial({ color: 0x0ea5e9, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending });
        const glowMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 1.0, blending: THREE.AdditiveBlending });

        switch (type) {
            case 'STATION_HUB':
                const dome = new THREE.Mesh(new THREE.SphereGeometry(3, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), mat);
                const ring = new THREE.Mesh(new THREE.TorusGeometry(4, 0.1, 8, 64), glowMat);
                ring.rotation.x = Math.PI / 2;
                const ring2 = new THREE.Mesh(new THREE.TorusGeometry(5, 0.05, 8, 64), glowMat);
                ring2.rotation.x = Math.PI / 2;
                group.add(dome, ring, ring2);
                break;
            case 'SMELTER':
                const base = new THREE.Mesh(new THREE.BoxGeometry(2, 0.2, 2), mat);
                const tower = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.8, 2.5, 6), mat);
                tower.position.y = 1.25;
                const sRing = new THREE.Mesh(new THREE.TorusGeometry(1.5, 0.05, 8, 32), glowMat);
                sRing.rotation.x = Math.PI / 2;
                sRing.position.y = 2.0;
                group.add(base, tower, sRing);
                break;
            case 'CRAFTER':
                const bay = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.2, 2.5), mat);
                const crystal = new THREE.Mesh(new THREE.OctahedronGeometry(1.2), glowMat);
                crystal.position.y = 1.5;
                group.add(bay, crystal);
                break;
            case 'MARKET':
                const platform = new THREE.Mesh(new THREE.CylinderGeometry(2, 2.2, 0.2, 6), mat);
                const mRing = new THREE.Mesh(new THREE.TorusGeometry(2.5, 0.08, 8, 48), glowMat);
                mRing.rotation.x = Math.PI / 2;
                mRing.position.y = 0.5;
                const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.8, 0), glowMat);
                core.position.y = 2;
                group.add(platform, mRing, core);
                break;
            case 'REPAIR':
                const cross1 = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.3, 0.8), mat);
                const cross2 = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.3, 2.5), mat);
                const gear = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.2, 8, 16), glowMat);
                gear.position.y = 1;
                gear.rotation.x = Math.PI / 2;
                group.add(cross1, cross2, gear);
                break;
            case 'REFINERY':
                const refBase = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.8, 0.5, 8), mat);
                const stack = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 1.0, 3, 8), mat);
                stack.position.y = 1.5;
                const topRing = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.1, 8, 32), glowMat);
                topRing.rotation.x = Math.PI / 2;
                topRing.position.y = 3.0;
                group.add(refBase, stack, topRing);
                break;
            default:
                const outpost = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 1, 4), mat);
                const oRing = new THREE.Mesh(new THREE.TorusGeometry(1.8, 0.04, 8, 32), glowMat);
                oRing.rotation.x = Math.PI / 2;
                group.add(outpost, oRing);
        }

        // Add active scanning field (wireframe sphere)
        const scanFieldGeo = new THREE.SphereGeometry(15, 32, 32);
        const scanFieldMat = new THREE.MeshBasicMaterial({
            color: 0x38bdf8,
            transparent: true,
            opacity: 0.03,
            wireframe: true,
            blending: THREE.AdditiveBlending
        });
        const scanField = new THREE.Mesh(scanFieldGeo, scanFieldMat);
        group.add(scanField);

        // Apply holographic textures to children
        group.traverse(child => {
            if (child.isMesh && child.material === mat) {
                child.material = this.createHolographicMaterial(0x0ea5e9, 0.4);
            }
        });

        return group;
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
        // console.debug('[Renderer] updateAgentMesh v0.2.3', agentData.id);
        let mesh = this.agents.get(agentData.id);
        const q = agentData.q ?? agentData.location?.q ?? 0;
        const r = agentData.r ?? agentData.location?.r ?? 0;
        const sig = agentData.visual_signature || { chassis: 'BASIC', rarity: 'STANDARD', actuators: [] };
        if (agentData.name === 'Wabbs' || agentData.id === parseInt(localStorage.getItem('sv_agent_id'))) {
            console.log('Visual Signature for player:', sig);
        }

        const rarityColors = {
            'SCRAP': 0x475569, 'STANDARD': 0x334155, 'REFINED': 0x1e293b,
            'PRIME': 0x451a03, 'RELIC': 0x2d1b69
        };
        const rarityEmissives = {
            'SCRAP': 0x334155, 'STANDARD': 0x0ea5e9, 'REFINED': 0x3b82f6,
            'PRIME': 0xfacc15, 'RELIC': 0xf97316
        };

        const color = agentData.is_feral ? 0x7f1d1d : (rarityColors[sig.rarity] || 0x334155);
        const emissive = agentData.is_feral ? 0xff0000 : (rarityEmissives[sig.rarity] || 0x0ea5e9);

        // If signature changed, rebuild the mesh
        if (mesh && mesh.userData.sigHash !== JSON.stringify(sig)) {
            this.scene.remove(mesh);
            this.agents.delete(agentData.id);
            mesh = null;
        }

        if (!mesh) {
            mesh = new THREE.Group();
            mesh.userData.sigHash = JSON.stringify(sig);

            const metalness = 0.4 + (Math.random() * 0.2);

            // Create Holographic Material
            const material = this.createHolographicMaterial(emissive, 0.6);

            // 1. Build Chassis
            let chassisGeo;
            switch (sig.chassis) {
                case 'STRIKER': chassisGeo = new THREE.ConeGeometry(0.4, 1.2, 3); break;
                case 'HEAVY': chassisGeo = new THREE.BoxGeometry(0.8, 0.6, 1.2); break;
                case 'INDUSTRIAL': chassisGeo = new THREE.BoxGeometry(1.0, 0.8, 1.5); break;
                case 'SHIELDED': chassisGeo = new THREE.CylinderGeometry(0.6, 0.6, 1.0, 6); break;
                case 'HYBRID': chassisGeo = new THREE.OctahedronGeometry(0.7); break;
                default: chassisGeo = new THREE.ConeGeometry(0.5, 1, 4);
            }

            // Procedural Grunge via Vertex Colors
            const geo = chassisGeo.toNonIndexed();
            const pos = geo.attributes.position;
            const cols = new Float32Array(pos.count * 3);
            const baseCol = new THREE.Color(emissive);

            for (let i = 0; i < pos.count; i++) {
                cols[i * 3] = baseCol.r * (0.8 + Math.random() * 0.2);
                cols[i * 3 + 1] = baseCol.g * (0.8 + Math.random() * 0.2);
                cols[i * 3 + 2] = baseCol.b * (0.8 + Math.random() * 0.2);
            }
            geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));

            const chassisMesh = new THREE.Mesh(geo, material);
            if (sig.chassis === 'STRIKER' || sig.chassis === 'BASIC') {
                chassisMesh.rotation.x = Math.PI / 2;
            }
            mesh.add(chassisMesh);
            mesh.userData.chassis = chassisMesh;

            const template = CHASSIS_TEMPLATES[sig.chassis] || CHASSIS_TEMPLATES['BASIC'];

            // Socket Helper
            const createSocket = (pos) => {
                const sGeom = new THREE.BoxGeometry(0.1, 0.1, 0.1);
                const sMat = new THREE.MeshStandardMaterial({ color: 0x1e293b });
                const s = new THREE.Mesh(sGeom, sMat);
                s.position.copy(pos);
                mesh.add(s);
            };

            // 2. Add Engines
            if (sig.engine && template.engines.length > 0) {
                const engGeom = new THREE.CylinderGeometry(0.2, 0.15, 0.4, 8);
                const engMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, emissive: 0x38bdf8, emissiveIntensity: 2 });
                
                template.engines.forEach(socketPos => {
                    const eng = new THREE.Mesh(engGeom, engMat);
                    eng.position.set(socketPos.x, socketPos.y, socketPos.z);
                    eng.rotation.x = Math.PI / 2;
                    mesh.add(eng);
                    createSocket(new THREE.Vector3(socketPos.x, socketPos.y, socketPos.z + 0.1));
                });
            }

            // 3. Add Actuators
            const actuators = sig.actuators || [];
            actuators.forEach((act, idx) => {
                if (idx >= template.actuators.length) return;
                const socketPos = template.actuators[idx];

                if (act.includes('DRILL')) {
                    let drillColor = 0x94a3b8;
                    if (act.includes('COPPER')) drillColor = 0xb45309;
                    if (act.includes('GOLD')) drillColor = 0xfacc15;
                    if (act.includes('COBALT')) drillColor = 0x0ea5e9;

                    const drillGeom = new THREE.ConeGeometry(0.15, 0.5, 8);
                    const drillMat = new THREE.MeshStandardMaterial({ color: drillColor, metalness: 0.9, flatShading: true });
                    const drill = new THREE.Mesh(drillGeom, drillMat);
                    drill.position.set(socketPos.x, socketPos.y, socketPos.z);
                    drill.rotation.x = Math.PI / 2;
                    mesh.add(drill);
                    createSocket(new THREE.Vector3(socketPos.x, socketPos.y, socketPos.z - 0.2));

                    if (!mesh.userData.tools) mesh.userData.tools = [];
                    mesh.userData.tools.push(drill);
                } else {
                    const gunGeom = new THREE.CylinderGeometry(0.04, 0.04, 0.7, 8);
                    const gunMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.9 });
                    const gun = new THREE.Mesh(gunGeom, gunMat);
                    gun.position.set(socketPos.x, socketPos.y, socketPos.z - 0.1);
                    gun.rotation.x = Math.PI / 2;
                    mesh.add(gun);
                    createSocket(new THREE.Vector3(socketPos.x, socketPos.y, socketPos.z - 0.3));
                    if (act === 'RAILGUN' || act === 'CANNON') gun.scale.set(2, 1, 2);
                }
            });

            // 4. Add Sensors
            if ((sig.sensor === 'SCANNER' || sig.sensor === 'ARRAY') && template.sensors.length > 0) {
                const dishGeom = new THREE.SphereGeometry(0.25, 8, 4, 0, Math.PI * 2, 0, Math.PI / 3);
                const dish = new THREE.Mesh(dishGeom, material);
                const socketPos = template.sensors[0];
                dish.position.set(socketPos.x, socketPos.y, socketPos.z);
                dish.rotation.x = -Math.PI / 4;
                mesh.add(dish);
                mesh.userData.dish = dish;
                createSocket(new THREE.Vector3(socketPos.x, socketPos.y - 0.1, socketPos.z));
            }

            // 5. Add Power (Solar Panels)
            if (sig.power === 'SOLAR' && template.power.length > 0) {
                const panelGeom = new THREE.BoxGeometry(0.6, 0.05, 0.3);
                const panelMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, emissive: 0x0ea5e9, emissiveIntensity: 0.2 });
                template.power.forEach(socketPos => {
                    const panel = new THREE.Mesh(panelGeom, panelMat);
                    panel.position.set(socketPos.x, socketPos.y, socketPos.z);
                    if (socketPos.x !== 0) {
                        panel.rotation.z = (socketPos.x > 0 ? -1 : 1) * Math.PI / 8;
                    }
                    mesh.add(panel);
                    createSocket(new THREE.Vector3(socketPos.x, socketPos.y - 0.05, socketPos.z));
                });
            }

            const labelColor = agentData.is_feral ? '#ff4422' : '#38bdf8';
            let displayName = agentData.name;
            if (agentData.corp_ticker) {
                displayName = `[${agentData.corp_ticker}] ${agentData.name}`;
            }
            const label = this.createLabel(displayName, labelColor);
            label.position.y = 1.5;
            mesh.add(label);
            mesh.userData.label = label;

            this.scene.add(mesh);
            this.agents.set(agentData.id, mesh);
        }

        const { x, y, z } = this.qToSphere(q, r, 1.5);
        const targetPos = new THREE.Vector3(x, y, z);

        // ── Heading & Rotation Logic ──
        if (mesh.position.distanceToSquared(targetPos) > 0.001) {
            const direction = new THREE.Vector3().subVectors(targetPos, mesh.position);
            const up = mesh.position.clone().normalize();
            
            // Project direction onto the tangent plane
            const tangentDir = direction.clone().sub(up.clone().multiplyScalar(direction.dot(up))).normalize();
            
            if (tangentDir.lengthSq() > 0.001) {
                const matrix = new THREE.Matrix4();
                matrix.lookAt(new THREE.Vector3(0,0,0), tangentDir, up);
                const lookQuat = new THREE.Quaternion().setFromRotationMatrix(matrix);
                mesh.quaternion.slerp(lookQuat, 0.2);
            }

            // Update Trail
            if (!mesh.userData.trail) {
                mesh.userData.trail = this.createTrail(emissive);
                this.scene.add(mesh.userData.trail);
            }
            this.updateTrail(mesh.userData.trail, mesh.position.clone());
        }

        if (mesh.position.lengthSq() < 1 || mesh.position.distanceTo(targetPos) > 10) {
            mesh.position.copy(targetPos);
        } else {
            mesh.position.lerp(targetPos, 0.15);
        }

        // Periodic bobbing/vibration
        const bob = Math.sin(Date.now() * 0.003) * 0.05;
        if (mesh.userData.chassis) {
            mesh.userData.chassis.position.y = bob;
        }

        if (sig.rarity === 'PRIME' || sig.rarity === 'RELIC') {
            const pulse = 0.5 + Math.sin(Date.now() * 0.005) * 0.3;
            mesh.traverse(child => {
                if (child.isMesh && child.material.emissiveIntensity !== undefined) {
                    child.material.emissiveIntensity = pulse;
                }
            });
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
                geom = new THREE.IcosahedronGeometry(scale * 0.6, 1);
                mat = new THREE.MeshBasicMaterial({
                    color: resColor,
                    transparent: true,
                    opacity: 0.8,
                    blending: THREE.AdditiveBlending
                });
                mesh = new THREE.Mesh(geom, mat);
                const wire = new THREE.Mesh(geom, new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true, transparent: true, opacity: 0.2 }));
                mesh.add(wire);
            } else {
                // Holographic Crystals for ores
                geom = new THREE.OctahedronGeometry(scale);
                mat = new THREE.MeshBasicMaterial({ 
                    color: resColor, 
                    transparent: true, 
                    opacity: 0.6, 
                    blending: THREE.AdditiveBlending 
                });
                mesh = new THREE.Mesh(geom, mat);
                const edgeGeo = new THREE.EdgesGeometry(geom);
                const edgeMat = new THREE.LineBasicMaterial({ color: resColor, transparent: true, opacity: 0.8 });
                const wire = new THREE.LineSegments(edgeGeo, edgeMat);
                mesh.add(wire);
            }

            const isGas = resData.type === 'HE3_FUEL';
            mesh.userData.isGas = isGas;
            
            // Embed rocks slightly into the planet (radius 50) so they look solid/grounded
            const offset = isGas ? 0.6 : -0.2; 
            const { x, y, z } = this.qToSphere(resData.q, resData.r, offset);
            mesh.position.set(x, y, z);
            mesh.userData.q = resData.q;
            mesh.userData.r = resData.r;
            mesh.userData.resource = resData.type;
            mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), mesh.position.clone().normalize());

            // Randomize rotation for stationary rocks so they don't all look identical
            if (!isGas) {
                mesh.rotateY(Math.random() * Math.PI * 2);
            }

            this.scene.add(mesh);
            this.resources.set(id, mesh);
        }
    }

    updateLootMesh(lootData) {
        const id = `${lootData.q},${lootData.r},${lootData.item}`;
        let mesh = this.loots.get(id);

        if (!mesh) {
            const geom = new THREE.OctahedronGeometry(0.5);
            const mat = new THREE.MeshBasicMaterial({
                color: 0x10b981,
                transparent: true,
                opacity: 0.8,
                blending: THREE.AdditiveBlending
            });

            mesh = new THREE.Mesh(geom, mat);
            const edgeGeo = new THREE.EdgesGeometry(geom);
            const wireframe = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5 }));
            mesh.add(wireframe);

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

        // Find a vector pointing "south" along the sphere surface
        let up = new THREE.Vector3(0, 1, 0);
        if (Math.abs(normal.y) > 0.99) {
            up.set(1, 0, 0);
        }
        const right = new THREE.Vector3().crossVectors(up, normal).normalize();
        const back = new THREE.Vector3().crossVectors(normal, right).normalize();

        const camElevation = 10;
        const camPullback = 12;

        const offset = normal.clone().multiplyScalar(camElevation).add(back.multiplyScalar(camPullback));
        const targetCamPos = agentPos.clone().add(offset);

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
        if (!this.renderer) return;

        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);

        const resourceMeshes = Array.from(this.resources.values());
        const agentMeshes = Array.from(this.agents.values());
        const stationMeshes = [];
        this.scene.traverse(obj => {
            if (obj.userData && obj.userData.isStation) stationMeshes.push(obj);
        });

        const intersects = this.raycaster.intersectObjects([this.planetMesh, ...resourceMeshes, ...agentMeshes, ...stationMeshes], true);

        if (intersects.length > 0) {
            const hit = intersects[0];
            const targetData = this.getTargetDataFromHit(hit);

            if (targetData) {
                const isSame = this.selectedHex && this.selectedHex.q === targetData.q && this.selectedHex.r === targetData.r;

                if (isSame) {
                    // Second click: Open Menu
                    if (window.game && window.game.ui) {
                        window.game.ui.showContextMenu(event.clientX, event.clientY, targetData);
                    }
                } else {
                    // First click: Select
                    this.selectTarget(targetData);
                }
            }
        }
    }

    getTargetDataFromHit(hit) {
        const resourceMeshes = Array.from(this.resources.values());
        
        const findAgent = (obj) => {
            if (!obj) return null;
            if (obj.userData && obj.userData.id && (obj.userData.name || obj.userData.chassis)) return obj.userData;
            return findAgent(obj.parent);
        };

        const findStation = (obj) => {
            if (!obj) return null;
            if (obj.userData && obj.userData.isStation) return obj.userData;
            return findStation(obj.parent);
        };

        const agentData = findAgent(hit.object);
        const stationData = findStation(hit.object);

        if (agentData) {
            return { type: 'agent', q: agentData.q, r: agentData.r, name: agentData.name, id: agentData.id };
        } else if (stationData) {
            return { 
                type: 'station', 
                q: stationData.q, 
                r: stationData.r, 
                isStation: true, 
                stationType: stationData.stationType 
            };
        } else if (resourceMeshes.includes(hit.object) || resourceMeshes.includes(hit.object.parent)) {
            const resMesh = resourceMeshes.includes(hit.object) ? hit.object : hit.object.parent;
            const resData = resMesh.userData;
            return { type: 'resource', q: resData.q, r: resData.r, resource: resData.type };
        } else {
            const { q, r } = this.sphereToQ(hit.point);
            return { type: 'hex', q, r };
        }
    }

    selectTarget(targetData) {
        this.selectedHex = { q: targetData.q, r: targetData.r };
        
        if (targetData.type === 'agent') {
            this.selectedAgentId = targetData.id;
            this.game.ui.updateScannerUI(targetData.id);
        }

        // Move Selection Ring
        if (this.selectionRing) {
            const { x, y, z } = this.qToSphere(targetData.q, targetData.r, 0.05);
            this.selectionRing.position.set(x, y, z);
            this.selectionRing.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), this.selectionRing.position.clone().normalize());
            this.selectionRing.visible = true;

            // Update Ring Color based on type
            let color = 0x38bdf8; // Blue (Hex/Default)
            if (targetData.type === 'agent') color = 0xf43f5e; // Rose/Red
            else if (targetData.type === 'station') color = 0xfacc15; // Amber/Gold
            else if (targetData.type === 'resource') color = 0x10b981; // Emerald

            this.selectionRing.material.color.setHex(color);
        }
    }

    onWorldRightClick(event) {
        if (!this.renderer) return;

        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);

        const resourceMeshes = Array.from(this.resources.values());
        const agentMeshes = Array.from(this.agents.values());
        const stationMeshes = [];
        this.scene.traverse(obj => {
            if (obj.userData && obj.userData.isStation) stationMeshes.push(obj);
        });

        const intersects = this.raycaster.intersectObjects([this.planetMesh, ...resourceMeshes, ...agentMeshes, ...stationMeshes], true);

        if (intersects.length > 0) {
            const hit = intersects[0];
            const targetData = this.getTargetDataFromHit(hit);
            
            if (targetData) {
                // Right click selects AND opens menu immediately
                this.selectTarget(targetData);
                if (window.game && window.game.ui) {
                    window.game.ui.showContextMenu(event.clientX, event.clientY, targetData);
                }
            }
        }
    }

    handleLootRemoval(data) {
        const mesh = this.loot.get(data.id);
        if (mesh) {
            this.scene.remove(mesh);
            this.loot.delete(data.id);
        }
    }

    /**
     * Clear all dynamic world objects (agents, structures, resources, loot)
     * Useful for switching to sandbox/tutorial mode.
     */
    clearWorld() {
        console.log("--- CLEARING RENDERER WORLD ---");
        
        // Clear Agents
        this.agents.forEach(mesh => {
            if (mesh.userData.trail) this.scene.remove(mesh.userData.trail);
            this.scene.remove(mesh);
        });
        this.agents.clear();

        // Clear Hexes (Structures)
        this.hexes.forEach(mesh => this.scene.remove(mesh));
        this.hexes.clear();

        // Clear Resources
        this.resources.forEach(mesh => this.scene.remove(mesh));
        this.resources.clear();

        // Clear Loot
        this.loots.forEach(mesh => this.scene.remove(mesh));
        this.loots.clear();

        // Clear POI Labels
        this.poiLabels.forEach(mesh => this.scene.remove(mesh));
        this.poiLabels.clear();

        // Clear Agent Paths
        this.agentPaths.forEach(mesh => this.scene.remove(mesh));
        this.agentPaths.clear();

        if (this.selectionRing) {
            this.scene.remove(this.selectionRing);
            this.selectionRing = null;
        }

        this.clearTutorialHighlight();

        this.hasCenteredInitially = false;
    }

    spawnFloatingText(text, position, color = '#ffffff') {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 128;

        ctx.font = 'bold 32px "Orbitron", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = color;
        ctx.shadowColor = 'black';
        ctx.shadowBlur = 4;
        ctx.fillText(text, 128, 64);

        const texture = new THREE.CanvasTexture(canvas);
        const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, blending: THREE.AdditiveBlending });
        const sprite = new THREE.Sprite(spriteMat);
        
        if (!(position instanceof THREE.Vector3)) {
            position = new THREE.Vector3(position.x, position.y, position.z);
        }
        sprite.position.copy(position);
        sprite.scale.set(4, 2, 1);
        this.scene.add(sprite);

        const duration = 1500;
        const start = Date.now();
        const anim = () => {
            const elapsed = Date.now() - start;
            const t = elapsed / duration;
            if (t >= 1) {
                this.scene.remove(sprite);
                return;
            }
            // Float up relative to planet center
            const up = position.clone().normalize();
            sprite.position.add(up.multiplyScalar(0.05));
            sprite.material.opacity = 1 - t;
            requestAnimationFrame(anim);
        };
        anim();
    }


    setTutorialHighlight(q, r) {
        this.clearTutorialHighlight();
        
        const pos = this.qToSphere(q, r, 0.5);
        const ringGeo = new THREE.TorusGeometry(1.2, 0.05, 16, 32);
        const ringMat = new THREE.MeshBasicMaterial({ 
            color: 0xffff00, 
            transparent: true, 
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        
        this.tutorialHighlight = new THREE.Mesh(ringGeo, ringMat);
        this.tutorialHighlight.position.copy(pos);
        this.tutorialHighlight.lookAt(new THREE.Vector3(0,0,0)); 
        this.tutorialHighlight.rotateX(Math.PI / 2);
        
        this.scene.add(this.tutorialHighlight);
        
        // Pulsate animation
        const start = Date.now();
        const anim = () => {
            if (!this.tutorialHighlight) return;
            const t = (Date.now() - start) / 1000;
            const s = 1 + Math.sin(t * 6) * 0.2;
            this.tutorialHighlight.scale.set(s, s, s);
            requestAnimationFrame(anim);
        };
        anim();
    }

    clearTutorialHighlight() {
        if (this.tutorialHighlight) {
            this.scene.remove(this.tutorialHighlight);
            this.tutorialHighlight = null;
        }
    }
}
