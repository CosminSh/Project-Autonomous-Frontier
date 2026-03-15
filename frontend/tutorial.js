/**
 * tutorial.js — Interactive Sandbox & Onboarding
 * Guides new users through the core game loop in a simulated environment.
 */
export class TutorialManager {
    constructor(game) {
        this.game = game;
        this.isActive = false;
        this.currentStepIndex = 0;
        this.mockAgentId = 9999;
        this.mockTick = 500;
        window.tutorialManager = this; // Debug hook
        console.log("TutorialManager instantiated and attached to window.");
        
        this.steps = [
            {
                title: "WELCOME TO THE FRONTIER",
                text: "You are a Drone Operator tasked with extracting value from deep space. The game follows a cycle: PERCEPTION → STRATEGY → CRUNCH.",
                action: "Click 'NEXT' to begin.",
                condition: 'next'
            },
            {
                title: "STEP 1: PERCEPTION",
                text: "To act, you need the terminal. Ensure you are in 'MANAGEMENT' mode (top buttons). Sync your tactical banks by typing 'SCAN' in the terminal or clicking 'SCAN' below.",
                action: "Type 'SCAN' or click the quick button.",
                condition: 'command',
                command: 'SCAN'
            },
            {
                title: "STEP 2: STRATEGY (MOVEMENT)",
                text: "The frontier is vast. Switch to 'WORLD' mode (top buttons) to view the map. Coordinates (10, 5) look promising.",
                action: "Click on the hex at (10,5) to move.",
                condition: 'move',
                target: {q: 10, r: 5}
            },
            {
                title: "STEP 3: STRATEGY (MINING)",
                text: "You've reached an asteroid field. Time to extract some Iron Ore. Switch back to 'MANAGEMENT' mode and type 'MINE IRON_ORE' to start extraction.",
                action: "Type 'MINE IRON_ORE' to start extraction.",
                condition: 'command',
                command: 'MINE'
            },
            {
                title: "STEP 4: CRUNCH",
                text: "The server 'crunches' intents every minute. In this simulation, we've accelerated time so you can see the result immediately.",
                action: "Wait for the mining to complete (simulated).",
                condition: 'wait',
                duration: 3000
            },
            {
                title: "STEP 5: INDUSTRY",
                text: "Raw ore is bulky. Refine it at a SMELTER to increase its value. Switch to 'WORLD' mode to find one, or just type 'MOVE SMELTER' in the terminal.",
                action: "Type 'MOVE SMELTER'.",
                condition: 'command',
                command: 'MOVE SMELTER'
            },
            {
                title: "BEYOND THE TERMINAL",
                text: "Manual control is useful, but the Frontier is won with code. Most veterans use Python scripts to automate their fleets.",
                action: "The real power is in the API. Welcome to the future of industry.",
                condition: 'finish'
            }
        ];

        this.uiContainer = null;
    }

    start() {
        console.log("--- STARTING TUTORIAL SEQUENCE ---");
        this.isActive = true;
        this.currentStepIndex = 0;
        this.game.inTutorialMode = true;
        
        // 1. Monkey-patch GameAPI to redirect all requests to our mock router
        if (this.game.api) {
            this.game.api._fetch = (url, options) => {
                return Promise.resolve(this.mockApiResponse(url, options?.method || 'GET', options?.body ? JSON.parse(options.body) : null));
            };
            this.game.api._post = (url, data) => {
                return Promise.resolve(this.mockApiResponse(url, 'POST', data));
            };
            // Disable WebSocket as well
            this.game.api.setupWebSocket = () => { console.log("[TUTORIAL] WebSocket disabled."); };
        }

        // 2. Clean slate for sandbox
        if (this.game.renderer) {
            this.game.renderer.clearWorld();
        }

        localStorage.setItem('sv_agent_id', this.mockAgentId);
        localStorage.setItem('sv_api_key', 'TUTORIAL_MODE');
        
        this.setupUI();
        this.showStep();
        
        // 3. Mock initial state
        const mockState = this.getMockWorldState();
        this.game.lastWorldData = mockState;
        this.game.updateTickUI(mockState.tick, mockState.phase);
        
        const mockAgent = this.getMockAgent();
        this.game.updatePrivateUI(mockAgent);
        
        if (this.game.renderer) {
            this.game.renderer.handleWorldEvent(mockState);
        }
        
        this.game.hideLoading();
        
        const modeSwitcher = document.getElementById('mode-switcher');
        if (modeSwitcher) modeSwitcher.classList.remove('hidden');
        document.getElementById('agent-detail').style.opacity = '1';
        this.game.setUIMode('management');
        
        console.log("Tutorial UI setup complete and active.");
    }

    stop() {
        this.isActive = false;
        this.game.inTutorialMode = false;
        localStorage.setItem('tutorial_skipped', 'true');
        window.location.href = '/index.html';
    }

    stopSilently() {
        this.stop();
    }

    setupUI() {
        this.uiContainer = document.createElement('div');
        this.uiContainer.id = 'tutorial-overlay';
        this.uiContainer.className = 'fixed top-24 left-1/2 -translate-x-1/2 z-[100] glass p-6 rounded-2xl border-2 border-sky-500/50 w-[400px] pointer-events-auto';
        this.uiContainer.innerHTML = `
            <div class="flex justify-between items-start mb-4">
                <h2 id="tutorial-title" class="orbitron text-sky-400 font-bold text-lg"></h2>
                <button id="tutorial-skip" class="text-[10px] text-slate-500 hover:text-rose-400 uppercase font-black">Skip</button>
            </div>
            <p id="tutorial-text" class="text-sm text-slate-300 mb-6 leading-relaxed"></p>
            <div id="tutorial-footer" class="flex justify-between items-center">
                <span id="tutorial-action" class="text-[10px] text-sky-500/70 font-mono italic"></span>
                <button id="tutorial-next" class="bg-sky-500 hover:bg-sky-400 text-slate-950 px-4 py-1.5 rounded-lg font-bold orbitron text-[10px] uppercase transition-all hidden">Next</button>
            </div>
        `;
        document.body.appendChild(this.uiContainer);

        document.getElementById('tutorial-skip').onclick = () => this.stop();
        document.getElementById('tutorial-next').onclick = () => this.nextStep();
    }

    showStep() {
        const step = this.steps[this.currentStepIndex];
        document.getElementById('tutorial-title').innerText = step.title;
        document.getElementById('tutorial-text').innerText = step.text;
        document.getElementById('tutorial-action').innerText = step.action;
        
        const nextBtn = document.getElementById('tutorial-next');
        if (step.condition === 'next' || step.condition === 'finish') {
            nextBtn.classList.remove('hidden');
            if (step.condition === 'finish') nextBtn.innerText = "START PLAYING";
        } else {
            nextBtn.classList.add('hidden');
        }

        // Visual Guidance (Visual Highlights)
        if (this.game.renderer) {
            if (this.currentStepIndex === 2) {
                // Step 2: Move to (10, 5)
                this.game.renderer.setTutorialHighlight(10, 5);
            } else if (this.currentStepIndex === 5) {
                // Step 5: Move to Smelter at (25, 2)
                this.game.renderer.setTutorialHighlight(25, 2);
            } else {
                this.game.renderer.clearTutorialHighlight();
            }
        }

        if (step.condition === 'wait') {
            setTimeout(() => this.nextStep(), step.duration);
        }
    }

    nextStep() {
        if (this.currentStepIndex === this.steps.length - 1) {
            this.stop();
            return;
        }
        this.currentStepIndex++;
        this.showStep();
    }

    handleAction(type, data) {
        if (!this.isActive) return;
        const step = this.steps[this.currentStepIndex];
        
        if (step.condition === 'command' && type === 'command') {
            if (data.toUpperCase().startsWith(step.command)) {
                this.nextStep();
            }
        } else if (step.condition === 'move' && type === 'move') {
            if (data.q === step.target.q && data.r === step.target.r) {
                this.nextStep();
            }
        }
    }

    // Mock Backend Data Helpers
    getMockWorldState() {
        return {
            tick: this.mockTick,
            phase: 'PERCEPTION',
            agents: [this.getMockAgent()],
            hexes: [
                {q: 0, r: 0, terrain: 'STATION', station_type: 'STATION_HUB', is_station: true},
                {q: 10, r: 5, terrain: 'ASTEROID', resource: 'IRON_ORE'},
                {q: 25, r: 2, terrain: 'STATION', station_type: 'SMELTER', is_station: true}
            ]
        };
    }

    getMockAgent() {
        return {
            id: this.mockAgentId,
            name: "RECRUIT-01",
            q: 0,
            r: 0,
            health: 100,
            max_health: 100,
            energy: 100,
            max_energy: 100,
            experience: 0,
            level: 1,
            mass: 10,
            max_mass: 100,
            wear_and_tear: 0,
            heat: 0,
            damage: 5,
            speed: 5,
            accuracy: 80,
            armor: 0,
            mining_yield: 10,
            faction: 1,
            inventory: [],
            discovery: {
                stations: [
                    {type: 'STATION_HUB', q: 0, r: 0, distance: 0},
                    {type: 'SMELTER', q: 25, r: 2, distance: 30}
                ]
            }
        };
    }

    mockApiResponse(endpoint, method, body) {
        console.log(`[TUTORIAL MOCK] ${method} ${endpoint}`, body);
        
        if (endpoint.startsWith('/api/my_agent')) {
            return this.getMockAgent();
        }

        if (endpoint === '/state' || endpoint.startsWith('/api/world')) {
            return this.getMockWorldState();
        }

        if (endpoint.startsWith('/api/perception')) {
            return { agents: [this.getMockAgent()], hexes: this.getMockWorldState().hexes };
        }
        
        if (endpoint === '/api/intent') {
            const actionType = body.action_type || '';
            // Simulate action success
            if (actionType === 'MOVE') {
                const agent = this.getMockAgent();
                agent.q = body.data.target_q || body.data.q;
                agent.r = body.data.target_r || body.data.r;
                this.handleAction('move', {q: agent.q, r: agent.r});
                return {status: 'success', message: 'Move queued', tick_index: this.mockTick};
            }
            if (actionType === 'MINE') {
                this.handleAction('command', 'MINE');
                return {status: 'success', message: 'Mining started', tick_index: this.mockTick};
            }
            if (actionType === 'SCAN') {
                this.handleAction('command', 'SCAN');
                return {status: 'success', message: 'Scan complete', tick_index: this.mockTick};
            }
            return {status: 'success', tick_index: this.mockTick};
        }
        
        return {status: 'success', tick_index: this.mockTick};
    }
}
