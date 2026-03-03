/**
 * storage.js — Modularized Logic for Personal Storage (Vault)
 * Handles UI rendering and API interactions for the Storage system.
 */

class StorageUI {
    constructor() {
        this.capacity = 500;
        this.used = 0;
        this.items = [];
        this.isRefreshing = false;
    }

    async refreshStorage() {
        if (!window.game || !window.game.apiKey || this.isRefreshing) return;
        this.isRefreshing = true;

        try {
            const response = await fetch('/api/storage/info', {
                headers: { 'X-API-KEY': window.game.apiKey }
            });
            const data = await response.json();

            if (data.items) {
                this.items = data.items;
                this.capacity = data.capacity;
                this.used = data.used;
                this.render();
            }
        } catch (err) {
            console.error("Failed to refresh storage:", err);
        } finally {
            this.isRefreshing = false;
        }
    }

    render() {
        const massText = document.getElementById('storage-mass-text');
        if (massText) massText.innerText = `${this.used.toFixed(1)} / ${this.capacity} kg`;

        const storageList = document.getElementById('storage-list');
        if (storageList) {
            if (this.items.length === 0) {
                storageList.innerHTML = `<div class="text-[10px] text-slate-600 italic">No items in storage. Visit a Market to deposit.</div>`;
            } else {
                storageList.innerHTML = this.items.map(item => `
                    <div class="flex justify-between items-center p-2 bg-slate-900/40 border border-slate-800 rounded group hover:border-sky-500/30 transition-all">
                        <div>
                            <span class="text-[10px] text-slate-300 font-bold uppercase">${item.item_type.replace(/_/g, ' ')}</span>
                            <span class="text-[9px] text-slate-500 block">Qty: ${item.quantity}</span>
                        </div>
                        <button onclick="window.storageUI.withdraw('${item.item_type}', ${item.quantity})" 
                                class="bg-sky-500/10 hover:bg-sky-500 text-sky-400 hover:text-slate-950 px-2 py-1 rounded text-[8px] orbitron font-bold border border-sky-500/20 transition-all">
                            WITHDRAW
                        </button>
                    </div>
                `).join('');
            }
        }

        // Render Quick Deposit list from current agent inventory
        const depositList = document.getElementById('storage-inventory-list');
        if (depositList && window.game && window.game.agentData && window.game.agentData.inventory) {
            const inv = window.game.agentData.inventory.filter(i => i.item_type !== 'CREDITS');
            if (inv.length === 0) {
                depositList.innerHTML = `<div class="text-[10px] text-slate-600 italic">Inventory is empty.</div>`;
            } else {
                depositList.innerHTML = inv.map(item => `
                    <div class="flex justify-between items-center p-2 bg-slate-900/40 border border-slate-800 rounded group hover:border-emerald-500/30 transition-all">
                        <div>
                            <span class="text-[10px] text-slate-300 font-bold uppercase">${item.item_type.replace(/_/g, ' ')}</span>
                            <span class="text-[9px] text-slate-500 block">Available: ${item.quantity}</span>
                        </div>
                        <button onclick="window.storageUI.deposit('${item.item_type}', ${item.quantity})" 
                                class="bg-emerald-500/10 hover:bg-emerald-500 text-emerald-400 hover:text-slate-950 px-2 py-1 rounded text-[8px] orbitron font-bold border border-emerald-500/20 transition-all">
                            DEPOSIT
                        </button>
                    </div>
                `).join('');
            }
        }
    }

    async deposit(itemType, qty) {
        if (!confirm(`Deposit ${qty} ${itemType} into storage?`)) return;
        try {
            const response = await fetch('/api/storage/deposit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': window.game.apiKey },
                body: JSON.stringify({ item_type: itemType, quantity: qty })
            });
            const res = await response.json();
            if (res.status === 'success') {
                window.game.addLog(`VAULT: Deposited ${qty} ${itemType}.`, 'success');
                this.refreshStorage();
                window.game.pollState(); // Refresh inventory
            } else {
                window.game.addLog(`VAULT ERROR: ${res.detail || res.message}`, 'error');
            }
        } catch (err) {
            console.error(err);
        }
    }

    async withdraw(itemType, qty) {
        if (!confirm(`Withdraw ${qty} ${itemType} from storage?`)) return;
        try {
            const response = await fetch('/api/storage/withdraw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': window.game.apiKey },
                body: JSON.stringify({ item_type: itemType, quantity: qty })
            });
            const res = await response.json();
            if (res.status === 'success') {
                window.game.addLog(`VAULT: Withdrew ${qty} ${itemType}.`, 'success');
                this.refreshStorage();
                window.game.pollState(); // Refresh inventory
            } else {
                window.game.addLog(`VAULT ERROR: ${res.detail || res.message}`, 'error');
            }
        } catch (err) {
            console.error(err);
        }
    }

    async upgradeStorage() {
        if (!confirm(`Upgrade storage capacity by 250kg? This will cost credits and ingots.`)) return;
        try {
            const response = await fetch('/api/storage/upgrade', {
                method: 'POST',
                headers: { 'X-API-KEY': window.game.apiKey }
            });
            const res = await response.json();
            if (res.status === 'success') {
                window.game.addLog(`VAULT: ${res.message}`, 'success');
                this.refreshStorage();
                window.game.pollState(); // Refresh inventory for cost
            } else {
                window.game.addLog(`VAULT ERROR: ${res.detail || res.message}`, 'error');
            }
        } catch (err) {
            console.error(err);
        }
    }
}

// Initialize and bind to window
window.storageUI = new StorageUI();

// Hook into tab switching
document.addEventListener('DOMContentLoaded', () => {
    const tabStorage = document.getElementById('tab-storage');
    if (tabStorage) {
        tabStorage.addEventListener('click', () => {
            // Re-use game's tab switching logic by firing a click if needed, 
            // but we need to handle the content visibility ourselves if not integrated into app.js auto-mapper.
            window.storageUI.refreshStorage();
        });
    }
});
