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
        
        // Centralized State for persistence (MINE adds cargo, MOVE updates pose)
        this.agentState = {
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
            mass: 0,
            max_mass: 100,
            wear_and_tear: 0,
            heat: 0,
            damage: 5,
            speed: 5,
            accuracy: 80,
            armor: 0,
            mining_yield: 25,
            faction: 1,
            inventory: [],
            logs: [
                { time: new Date().toLocaleTimeString(), event: "SYSTEM_INIT", details: { message: "System Initialized" } },
                { time: new Date().toLocaleTimeString(), event: "TUTORIAL_ACTIVE", details: { message: "TUTORIAL_MODE Active" } }
            ],
            discovery: {
                'HUB-01': { q: 0, r: 0, distance: 0 },
                'SMELTER-A': { q: 25, r: 2, distance: 30 },
                'IRON-FIELD-1': { q: 10, r: 5, distance: 15 }
            }
        };

        this.worldState = {
            tick: this.mockTick,
            phase: 'PERCEPTION',
            agents: [this.agentState],
            hexes: [
                {q: 0, r: 0, terrain: 'STATION', station_type: 'STATION_HUB', is_station: true},
                {q: 10, r: 5, terrain: 'ASTEROID', resource: 'IRON_ORE'},
                {q: 25, r: 2, terrain: 'STATION', station_type: 'SMELTER', is_station: true}
            ]
        };

        window.tutorialManager = this; // Debug hook
        console.log("TutorialManager instantiated and attached to window.");
        
        this.steps = [
            {
                title: "WELCOME TO THE FRONTIER",
                text: "You are a Drone Operator tasked with extracting value from deep space. The game follows a cycle: SCAN → DECIDE → EXECUTE. (Previously Perception/Strategy/Crunch)",
                action: "Click 'NEXT' to begin.",
                condition: 'next',
                highlightId: 'tutorial-next'
            },
            {
                title: "STEP 1: PROTOCOLS (HELP)",
                text: "Before we deploy, you should know how to access your command protocols. Knowledge is power in the Frontier.",
                action: "Type 'HELP' in the terminal or click the shortcut.",
                condition: 'command',
                command: 'HELP',
                highlightId: 'terminal-input',
                buttonAction: 'HELP',
                buttonLabel: 'RUN HELP'
            },
            {
                title: "STEP 2: SCANNING",
                text: "The first step is always to SCAN your surroundings. In the terminal below, type 'SCAN' to see what's nearby.",
                action: "Type 'SCAN' in the terminal or use the button.",
                condition: 'command',
                command: 'SCAN',
                highlightId: 'terminal-input',
                buttonAction: 'SCAN',
                buttonLabel: 'RUN SCAN'
            },
            {
                title: "STEP 3: DECISION (MINING)",
                text: "Your sensors detected Iron Ore at coordinates (10, 5). Let's extract it. Decisions are sent as intense commands.",
                action: "Type 'MINE IRON_ORE 10 5' or click 'MINE' shortcut.",
                condition: 'command',
                command: 'MINE IRON_ORE 10 5',
                highlightId: 'terminal-input',
                buttonAction: 'MINE IRON_ORE 10 5',
                buttonLabel: 'MINE IRON (10,5)'
            },
            {
                title: "STEP 4: VISUALIZATION",
                text: "Your hardware has received the command! Switch to 'WORLD' mode (top buttons) to see your agent in the 3D environment.",
                action: "Click 'WORLD' in the top bar.",
                condition: 'ui_mode',
                mode: 'world',
                highlightId: 'btn-mode-world'
            },
            {
                title: "STEP 5: THE EXECUTION (TICKS)",
                text: "The Frontier doesn't run in real-time. Every minute, the server 'executes' all player intents simultaneously. This is called a TICK.",
                action: "Observe the phase indicator and click 'NEXT'.",
                condition: 'next',
                highlightId: 'phase-indicator'
            },
            {
                title: "STEP 6: NAVIGATION",
                text: "Raw ore is bulky. We need a SMELTER. You can move there by clicking on a Smelter in the map or using a command.",
                action: "Type 'MOVE 25 2' or click 'GO' shortcut.",
                condition: 'move',
                target: { q: 25, r: 2 },
                highlightId: 'terminal-input',
                buttonAction: 'MOVE 25 2',
                buttonLabel: 'GO TO SMELTER'
            },
            {
                title: "STEP 7: TRANSIT",
                text: "Your agent is now in transit. In the live game, this might take several ticks depending on your engine speed.",
                action: "Wait for deployment (simulated).",
                condition: 'wait',
                duration: 4000
            },
            {
                title: "STEP 8: REFINING",
                text: "You've reached the SMELTER. Time to maximize your profit by refining that ore into Iron Bars.",
                action: "Type 'SMELT IRON_ORE MAX' in the terminal.",
                condition: 'command',
                command: 'SMELT IRON_ORE MAX',
                highlightId: 'terminal-input',
                buttonAction: 'SMELT IRON_ORE MAX',
                buttonLabel: 'REFINE ORE'
            },
            {
                title: "MISSION COMPLETE",
                text: "You've mastered the basics. The real Frontier is vast, competitive, and waiting for your code.",
                action: "Click 'NEXT' to learn about automation.",
                condition: 'next'
            },
            {
                title: "AUTOMATION & THE FUTURE",
                text: "The true power of the Autonomous Frontier lies in automation. While you can command drones manually, the most successful corporations use scripts to manage entire fleets 24/7. Use the API endpoints you've seen here (and many more) to build your own autonomous empire. Check the 'DASHBOARD' and 'ABOUT' pages for detailed technical documentation.",
                action: "Click 'FINISH' to start your journey.",
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
        
        // Hide loading screen and ensure agent is rendered
        if (this.game.hideLoading) this.game.hideLoading();
        
        if (this.game.renderer) {
            this.game.renderer.updateAgentMesh(this.agentState);
        }

        this.showStep();
        
        // 3. Mock initial state
        const mockState = this.getMockWorldState();
        this.game.lastWorldData = mockState;
        this.game.lastAgentData = this.agentState;
        this.game.lastPerception = { 
            self: this.agentState,
            agents: [this.agentState],
            discovery: {
                stations: [
                    {id_type: 'HUB-01', q: 0, r: 0, distance: 0},
                    {id_type: 'SMELTER-A', q: 25, r: 2, distance: 30}
                ],
                resources: [
                    {type: 'IRON_ORE', q: 10, r: 5, distance: 15}
                ]
            },
            loot: []
        };
        
        this.game.updateTickUI(mockState.tick, mockState.phase);
        this.game.updatePrivateLogs(this.agentState.logs, [], []);

        // Setup mock ticker (10s intervals)
        this.mockTick = mockState.tick;
        const phases = ['PERCEPTION', 'STRATEGY', 'CRUNCH'];
        let phaseIdx = 0;
        
        this.tickInterval = setInterval(() => {
            this.mockTick++;
            phaseIdx = (phaseIdx + 1) % phases.length;
            if (this.game.updateTickUI) {
                this.game.updateTickUI(this.mockTick, phases[phaseIdx]);
            }
        }, 10000);

        const mockAgent = this.getMockAgent();
        this.game.renderer.handleWorldEvent({
            type: 'agent_update',
            agents: [mockAgent]
        });
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
        window.location.href = '/';
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
                <button id="tutorial-next" class="bg-sky-500 hover:bg-sky-400 text-slate-950 px-5 py-1.5 rounded-xl font-bold orbitron text-[10px] uppercase transition-all shadow-lg shadow-sky-500/20 active:scale-95 hidden">Next Step</button>
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

        // --- NEW: Visual Pointers & Highlights ---
        if (this.game.ui) {
            this.game.ui.clearHighlights();
            if (step.highlightId) {
                this.game.ui.highlightElement(step.highlightId, "LOOK HERE");
            }
        }

        // --- NEW: Quick Action Button ---
        const footer = document.getElementById('tutorial-footer');
        let quickBtn = document.getElementById('tutorial-quick-action');
        if (quickBtn) quickBtn.remove();

        if (step.buttonAction) {
            quickBtn = document.createElement('button');
            quickBtn.id = 'tutorial-quick-action';
            quickBtn.className = 'ml-4 bg-amber-500 hover:bg-amber-400 text-slate-950 px-4 py-1.5 rounded-xl font-bold orbitron text-[10px] uppercase transition-all shadow-lg shadow-amber-500/20 active:scale-95';
            quickBtn.innerText = step.buttonLabel || 'EXECUTE';
            quickBtn.onclick = () => {
                const terminal = document.getElementById('terminal-input');
                if (terminal) {
                    terminal.value = step.buttonAction;
                    // Trigger enter key
                    const event = new KeyboardEvent('keydown', { key: 'Enter' });
                    terminal.dispatchEvent(event);
                }
            };
            footer.appendChild(quickBtn);
        }

        // Visual Guidance (World Specific Highlights)
        if (this.game.renderer) {
            if (step.title.includes("MINING")) {
                this.game.renderer.setTutorialHighlight(10, 5);
            } else if (step.title.includes("NAVIGATION")) {
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
            const input = data.toUpperCase().trim();
            const target = step.command.toUpperCase().trim();
            if (input === target || input.startsWith(target)) {
                this.nextStep();
            }
        } else if (step.condition === 'move' && type === 'move') {
            if (data.q === step.target.q && data.r === step.target.r) {
                this.nextStep();
            }
        } else if (step.condition === 'ui_mode' && type === 'ui_mode') {
            if (data === step.mode) {
                this.nextStep();
            }
        }
    }

    // Mock Backend Data Helpers
    getMockWorldState() {
        this.worldState.tick = this.mockTick;
        return this.worldState;
    }

    getMockAgent() {
        return this.agentState;
    }

    mockApiResponse(endpoint, method, body) {
        console.log(`[TUTORIAL MOCK] ${method} ${endpoint}`, body);
        
        if (endpoint.startsWith('/api/my_agent')) {
            return this.getMockAgent();
        }

        if (endpoint === '/state' || endpoint.startsWith('/api/world')) {
            return this.getMockWorldState();
        }

        if (endpoint === '/api/storage/info') {
            return {
                items: [],
                capacity: 500,
                used: 0,
                next_upgrade_requirements: { IRON_ORE: 50 }
            };
        }

        if (endpoint.startsWith('/api/perception')) {
            const agent = this.getMockAgent();
            const p = { 
                self: agent,
                agents: [agent], 
                hexes: this.worldState.hexes,
                discovery: {
                    stations: [
                        {id_type: 'HUB-01', q: 0, r: 0, distance: 0},
                        {id_type: 'SMELTER-A', q: 25, r: 2, distance: 30}
                    ],
                    resources: [
                        {type: 'IRON_ORE', q: 10, r: 5, distance: 15}
                    ]
                },
                loot: []
            };
            this.game.lastPerception = p;
            this.game.lastAgentData = agent;
            return p;
        }
        
        if (endpoint === '/api/intent') {
            const actionType = body.action_type || '';
            // Simulate action success
            if (actionType === 'MOVE') {
                this.agentState.q = body.data.target_q ?? body.data.q ?? this.agentState.q;
                this.agentState.r = body.data.target_r ?? body.data.r ?? this.agentState.r;
                this.handleAction('move', {q: this.agentState.q, r: this.agentState.r});
                
                // Sync renderer
                if (this.game.renderer) {
                    this.game.renderer.updateAgentMesh(this.agentState);
                }
                return {status: 'success', message: 'Move queued', tick_index: this.mockTick, tick: this.mockTick};
            }
            if (actionType === 'MINE') {
                this.handleAction('command', 'MINE');
                // Persist cargo
                const existing = this.agentState.inventory.find(i => i.type === 'IRON_ORE');
                if (existing) {
                    existing.qty += 25;
                } else {
                    this.agentState.inventory.push({ type: 'IRON_ORE', qty: 25 });
                }
                this.agentState.mass = this.agentState.inventory.reduce((sum, i) => sum + i.qty, 0);
                
                return {status: 'success', message: 'Mining started', tick_index: this.mockTick, tick: this.mockTick};
            }
            if (actionType === 'SCAN' || actionType === 'PERCEIVE') {
                this.handleAction('command', actionType);
                return {
                    status: 'success', 
                    message: actionType === 'PERCEIVE' ? 'Nearby: IRON_ORE at (10, 5), SMELTER at (25, 2)' : 'Scan complete', 
                    tick_index: this.mockTick,
                    tick: this.mockTick,
                    data: {
                        hexes: this.worldState.hexes,
                        agents: this.worldState.agents
                    }
                };
            }
            if (actionType === 'SMELT') {
                this.handleAction('command', 'SMELT');
                // Simple inventory drain for mock
                this.agentState.inventory = this.agentState.inventory.filter(i => i.type !== 'IRON_ORE');
                this.agentState.mass = 0;
                return {status: 'success', message: 'Smelting started', tick_index: this.mockTick, tick: this.mockTick};
            }
            return {status: 'success', tick_index: this.mockTick, tick: this.mockTick};
        }
        
        return {status: 'success', tick_index: this.mockTick, tick: this.mockTick};
    }
}
