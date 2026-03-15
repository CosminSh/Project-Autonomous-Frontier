import { GameAPI } from './api.js?v=0.6.9';
import { GameRenderer } from './renderer.js?v=0.6.9';
import { UIManager } from './ui.js?v=0.6.9';
import { TerminalHandler } from './terminal.js?v=0.6.9';
import { TutorialManager } from './tutorial.js?v=0.6.9';

/**
 * app-tutorial.js — Standalone Tutorial Bootstrapper
 * Forces sandbox mode and isolates the renderer.
 */
class TutorialClient {
    constructor() {
        window.game = this;
        this.inTutorialMode = true; // Hardcoded for this entry point

        // 1. Initialize Sub-Systems
        this.api = new GameAPI(this);
        this.renderer = new GameRenderer(this);
        this.ui = new UIManager(this);
        this.terminal = new TerminalHandler(this);
        this.tutorial = new TutorialManager(this);

        // 2. Shared State
        this.tradeSide = 'SELL';
        this.lastWorldData = null;
        this.lastPerception = null;
        this.isInitialized = false;
        this._loadingHidden = false;

        // 3. Start Systems
        this.renderer.init();
        this.renderer.animate();
        this.setupListeners();
        this.isInitialized = true;

        // 4. Force Tutorial Start
        console.log('[BOOT] Standing up Tutorial Sandbox...');
        this.tutorial.start();
    }

    setupListeners() {
        // Mode Switcher
        document.getElementById('btn-mode-world')?.addEventListener('click', () => this.ui.setUIMode('world'));
        document.getElementById('btn-mode-agent')?.addEventListener('click', () => this.ui.setUIMode('management'));
        document.getElementById('btn-mode-leaderboard')?.addEventListener('click', () => this.ui.setUIMode('leaderboard'));

        // Tabs
        ['terminal', 'inventory', 'station', 'system', 'arena', 'corporation'].forEach(tab => {
            const el = document.getElementById(`tab-${tab}`);
            if (el) el.addEventListener('click', () => this.ui.switchTab(tab));
        });
        this.ui.switchTab('terminal');

        // Industry Actions
        const actions = ['SMELT', 'CRAFT', 'RESTORE_HP', 'RESET_WEAR'];
        actions.forEach(action => {
            document.getElementById(`btn-${action.toLowerCase()}`)?.addEventListener('click', () => this.api.submitIndustryIntent(action));
        });

        // Market Actions
        document.getElementById('trade-side-buy')?.addEventListener('click', () => this.ui.setTradeSide('BUY'));
        document.getElementById('trade-side-sell')?.addEventListener('click', () => this.ui.setTradeSide('SELL'));
        document.getElementById('btn-submit-order')?.addEventListener('click', () => this.api.submitTradeIntent());

        // Directive Modal
        const modalActions = [
            { id: 'open-directive-btn', show: true },
            { id: 'close-directive-btn', show: false },
            { id: 'close-directive-btn-footer', show: false },
            { id: 'modal-overlay', show: false }
        ];
        modalActions.forEach(a => {
            document.getElementById(a.id)?.addEventListener('click', () => this.ui.toggleDirectiveModal(a.show));
        });
    }

    // Auth Mocking (Tutorial doesn't login)
    handleLogin() { console.warn("Login disabled in tutorial."); }
    handleGuestLogin() { console.warn("Guest login disabled in tutorial."); }
    logout() { this.tutorial.stop(); } // Skip/Logout in tutorial goes back to index

    // Proxy Methods
    pollState() { /* No polling in tutorial */ }
    updateGlobalUI(stats) { return this.ui.updateGlobalUI(stats); }
    updateTickUI(tick, phase) { return this.ui.updateTickUI(tick, phase); }
    updateLiveFeed(logs) { return this.ui.updateLiveFeed(logs); }
    updateMarketUI(market) { return this.ui.updateMarketUI(market); }
    updateBountyBoard(bounties) { return this.ui.updateBountyBoard(bounties); }
    updateMissionsUI(missions) { return this.ui.updateMissionsUI(missions); }
    updatePrivateUI(agent) { return this.ui.updatePrivateUI(agent); }
    updateForgeUI(discovery) { return this.ui.updateForgeUI(discovery); }
    updatePrivateLogs(logs, pending, chat) { return this.ui.updatePrivateLogs(logs, pending, chat); }
    updateMyOrdersUI(orders) { return this.ui.updateMyOrdersUI(orders); }
    hideLoading() {
        const screen = document.getElementById('loading-screen');
        if (screen) screen.style.display = 'none';
        this._loadingHidden = true;
    }

    handleWorldEvent(data) { return this.renderer.handleWorldEvent(data); }
    updateAgentMesh(data) { return this.renderer.updateAgentMesh(data); }
    updateResourceMesh(data) { return this.renderer.updateResourceMesh(data); }
    updateLootMesh(data) { return this.renderer.updateLootMesh(data); }
    createHex(data) { return this.renderer.createHex(data); }
    centerOnAgent() { return this.renderer.centerOnAgent(); }

    setUIMode(mode) { return this.ui.setUIMode(mode); }
    switchTab(tab) { return this.ui.switchTab(tab); }
    toggleDirectiveModal(show) { return this.ui.toggleDirectiveModal(show); }

    get apiKey() { return 'TUTORIAL_MODE'; }
    get agentData() { return this.lastWorldData?.agents?.find(a => a.id === this.tutorial.mockAgentId); }
    get hexes() { return this.renderer.hexes; }
    get agents() { return this.renderer.agents; }
    get planetMesh() { return this.renderer.planetMesh; }
}

window.addEventListener('DOMContentLoaded', () => {
    new TutorialClient();
});
