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
        
        this.steps = [
            {
                title: "WELCOME TO THE FRONTIER",
                text: "You are a Drone Operator tasked with extracting value from deep space. The game follows a cycle: PERCEPTION → STRATEGY → CRUNCH.",
                action: "Click 'NEXT' to begin.",
                condition: 'next'
            },
            {
                title: "STEP 1: PERCEPTION",
                text: "Your sensors provide a holographic view of the world. Before acting, you must sync your local tactical banks with the network.",
                action: "Type 'SCAN' in the terminal or click 'SCAN' below.",
                condition: 'command',
                command: 'SCAN'
            },
            {
                title: "STEP 2: STRATEGY (MOVEMENT)",
                text: "The frontier is vast. You need to move your drone to a resource-rich area. Coordinates (10, 5) look promising.",
                action: "Type 'MOVE 10 5' or click on the hex at (10,5).",
                condition: 'move',
                target: {q: 10, r: 5}
            },
            {
                title: "STEP 3: STRATEGY (MINING)",
                text: "You've reached an asteroid field. Time to extract some Iron Ore. This will build your initial wealth.",
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
                text: "Raw ore is bulky. Refine it at a SMELTER to increase its value and reduce mass.",
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
        console.log("--- STARTING TUTORIAL ---");
        this.isActive = true;
        this.currentStepIndex = 0;
        this.game.inTutorialMode = true;
        this.setupUI();
        this.showStep();
        
        // Mock initial state
        this.game.lastWorldData = this.getMockWorldState();
        this.game.updatePrivateUI(this.getMockAgent());
        this.game.renderer.handleWorldEvent(this.game.lastWorldData);
        
        // Hide regular UI elements
        document.getElementById('auth-panel')?.classList.add('hidden');
    }

    stop() {
        this.isActive = false;
        this.game.inTutorialMode = false;
        if (this.uiContainer) {
            this.uiContainer.remove();
        }
        // Force refresh back to landing state
        window.location.reload();
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
        
        if (endpoint === '/api/my_agent') {
            return this.getMockAgent();
        }
        
        if (endpoint === '/api/intent') {
            // Simulate action success
            if (body.action === 'MOVE') {
                const agent = this.getMockAgent();
                agent.q = body.data.q;
                agent.r = body.data.r;
                this.handleAction('move', body.data);
                return {status: 'success', message: 'Move queued'};
            }
            if (body.action === 'MINE') {
                this.handleAction('command', 'MINE');
                return {status: 'success', message: 'Mining started'};
            }
            if (body.action === 'SCAN') {
                this.handleAction('command', 'SCAN');
                return {status: 'success', message: 'Scan complete'};
            }
        }
        
        return {status: 'success'};
    }
}
