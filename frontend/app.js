import { GameAPI } from './api.js';
import { AuthManager } from './auth.js';
import { GameRenderer } from './renderer.js';
import { UIManager } from './ui.js';
import { TerminalHandler } from './terminal.js';

/**
 * app.js — Main Bootstrapper
 * Orchestrates modular systems and maintains shared state.
 */
class GameClient {
    constructor() {
        window.game = this;

        // 1. Initialize Sub-Systems
        this.api = new GameAPI(this);
        this.auth = new AuthManager(this);
        this.renderer = new GameRenderer(this);
        this.ui = new UIManager(this);
        this.terminal = new TerminalHandler(this);

        // 2. Shared State
        this.tradeSide = 'SELL';
        this.lastWorldData = null;
        this.lastPerception = null;
        this.isInitialized = false;

        // 3. Start Systems
        this.renderer.init();
        this.renderer.animate();
        this.auth.checkAuth();
        this.api.setupWebSocket();
        this.api.startPolling();

        this.setupListeners();

        this.isInitialized = true;
        this.auth.processPendingAuth();
    }

    setupListeners() {
        // Auth UI
        document.getElementById('logout-btn')?.addEventListener('click', () => this.auth.logout());
        document.getElementById('copy-api-btn')?.addEventListener('click', () => this.auth.copyApiKey());

        // Faction & Rename
        document.getElementById('realign-faction-btn')?.addEventListener('click', () => this.api.submitFactionRealignment());
        document.getElementById('rename-trigger')?.addEventListener('click', () => this.ui.handleRename());

        // Mode Switcher
        document.getElementById('btn-mode-world')?.addEventListener('click', () => this.ui.setUIMode('world'));
        document.getElementById('btn-mode-agent')?.addEventListener('click', () => this.ui.setUIMode('management'));

        // Tabs
        ['overview', 'garage', 'market', 'forge', 'terminal', 'storage'].forEach(tab => {
            const el = document.getElementById(`tab-${tab}`);
            if (el) el.addEventListener('click', () => this.ui.switchTab(tab));
        });

        // Industry Actions
        const actions = ['SMELT', 'CRAFT', 'REPAIR'];
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

    // Proxy Methods for backward compatibility or cross-module ease
    pollState() { return this.api.pollState(); }
    setAuthenticated(status) { return this.auth.setAuthenticated(status); }
    setUIMode(mode) { return this.ui.setUIMode(mode); }
    toggleDirectiveModal(show) { return this.ui.toggleDirectiveModal(show); }
    updateGlobalUI(stats) { return this.ui.updateGlobalUI(stats); }
    updateTickUI(tick, phase) { return this.ui.updateTickUI(tick, phase); }
    updateLiveFeed(logs) { return this.ui.updateLiveFeed(logs); }
    updateMarketUI(market) { return this.ui.updateMarketUI(market); }
    updateBountyBoard(bounties) { return this.ui.updateBountyBoard(bounties); }
    updateMissionsUI(missions) { return this.ui.updateMissionsUI(missions); }
    updatePrivateUI(agent) { return this.ui.updatePrivateUI(agent); }
    updateForgeUI(discovery) { return this.ui.updateForgeUI(discovery); }
    updatePrivateLogs(logs, pending) { return this.ui.updatePrivateLogs(logs, pending); }
    updateMyOrdersUI(orders) { return this.ui.updateMyOrdersUI(orders); }
    handleWorldEvent(data) { return this.renderer.handleWorldEvent ? this.renderer.handleWorldEvent(data) : null; }

    // Internal state access helpers
    get apiKey() { return localStorage.getItem('sv_api_key'); }
    get agentData() { return this.lastWorldData?.agents?.find(a => a.id === parseInt(localStorage.getItem('sv_agent_id'))); }
}

// Global initialization
window.addEventListener('DOMContentLoaded', () => {
    new GameClient();
});
