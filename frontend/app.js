import { GameAPI } from './api.js?v=0.6.2';
import { AuthManager } from './auth.js?v=0.6.2';
import { GameRenderer } from './renderer.js?v=0.6.2';
import { UIManager } from './ui.js?v=0.6.2';
import { TerminalHandler } from './terminal.js?v=0.6.2';

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
        this._loadingHidden = false; // Flag for hiding loading panel once

        // 3. Start Systems
        this.renderer.init();
        this.renderer.animate();
        this.api.setupWebSocket();
        this.setupListeners();
        this.isInitialized = true;

        // 4. Startup flow based on auth state
        const apiKey = localStorage.getItem('sv_api_key');
        if (apiKey) {
            console.log('[BOOT] Returning user detected. Loading live world.');
            this.auth.checkAuth();
            this.api.startPolling().catch(err => {
                if (err.message && err.message.includes('401')) {
                    console.warn('[BOOT] Token expired. Switching to guest flow.');
                    this.logout(); 
                }
            });
        } else {
            console.log('[BOOT] Guest detected. Showing greeting overlay.');
            const greeting = document.getElementById('guest-greeting-overlay');
            if (greeting) greeting.style.display = 'block';
            this.hideLoading();
        }

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
        document.getElementById('btn-mode-leaderboard')?.addEventListener('click', () => this.ui.setUIMode('leaderboard'));

        // Tabs
        ['terminal', 'inventory', 'station', 'system', 'arena', 'corporation'].forEach(tab => {
            const el = document.getElementById(`tab-${tab}`);
            if (el) el.addEventListener('click', () => this.ui.switchTab(tab));
        });
        // Default to Command Center tab
        this.ui.switchTab('terminal');

        // Industry Actions
        const camDistance = 15; // Closer default view
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

    // Proxy Methods for backward compatibility or cross-module ease
    pollState() { return this.api.pollState(); }
    handleLogin(response) { return this.auth.handleLogin(response); }
    handleGuestLogin() { return this.auth.handleGuestLogin(); }
    logout() { return this.auth.logout(); }
    claimDaily() { return this.api.claimDaily(); }
    acceptSquad() { return this.api.acceptSquad(); }
    declineSquad() { return this.api.declineSquad(); }
    inviteSquad() { return this.api.inviteSquad(); }
    leaveSquad() { return this.api.leaveSquad(); }
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
    updatePrivateLogs(logs, pending, chat) { return this.ui.updatePrivateLogs(logs, pending, chat); }
    updateMyOrdersUI(orders) { return this.ui.updateMyOrdersUI(orders); }
    hideLoading() {
        if (this._loadingHidden) return;
        const screen = document.getElementById('loading-screen');
        if (screen) {
            console.log("--- SYNC COMPLETE: HIDING LOADING PANEL ---");
            screen.style.display = 'none';
            this._loadingHidden = true;
        }
    }

    handleWorldEvent(data) {
        this.hideLoading();
        return this.renderer.handleWorldEvent(data);
    }
    updateAgentMesh(data) { return this.renderer.updateAgentMesh(data); }
    updateResourceMesh(data) { return this.renderer.updateResourceMesh(data); }
    updateLootMesh(data) { return this.renderer.updateLootMesh(data); }
    createHex(data) { return this.renderer.createHex(data); }
    centerOnAgent() { return this.renderer.centerOnAgent(); }

    // Internal state access helpers
    get apiKey() { return localStorage.getItem('sv_api_key'); }
    get agentData() { return this.lastWorldData?.agents?.find(a => a.id === parseInt(localStorage.getItem('sv_agent_id'))); }
    get hexes() { return this.renderer.hexes; }
    get agents() { return this.renderer.agents; }
    get planetMesh() { return this.renderer.planetMesh; }
    get hasCenteredInitially() { return this.renderer.hasCenteredInitially; }
    set hasCenteredInitially(v) { this.renderer.hasCenteredInitially = v; }
}

// Global initialization
window.addEventListener('DOMContentLoaded', () => {
    new GameClient();
});
