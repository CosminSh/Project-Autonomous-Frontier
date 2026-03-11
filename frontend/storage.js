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

            if (data.items !== undefined) {
                this.items = data.items;
                this.capacity = data.capacity;
                this.used = data.used;
                this.nextUpgradeRequirements = data.next_upgrade_requirements;
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
        if (massText) massText.innerText = `${this.used.toFixed(1)} / ${this.capacity.toFixed(0)} kg`;

        // ── Vault contents ──
        const storageList = document.getElementById('storage-list');
        if (storageList) {
            if (this.items.length === 0) {
                storageList.innerHTML = `<div class="text-[10px] text-slate-600 italic">No items in storage. Visit a Market to deposit.</div>`;
            } else {
                storageList.innerHTML = this.items.map(item => `
                    <div class="flex justify-between items-center p-2 bg-slate-900/40 border border-slate-800 rounded group hover:border-sky-500/30 transition-all">
                        <div>
                            <span class="text-[10px] text-slate-300 font-bold uppercase">${item.type.replace(/_/g, ' ')}</span>
                            <span class="text-[9px] text-slate-500 block">Stored: ${item.quantity}</span>
                        </div>
                        <div class="flex gap-1">
                            <button onclick="window.storageUI.withdrawPartial('${item.type}', ${item.quantity})"
                                    class="bg-sky-500/10 hover:bg-sky-500 text-sky-400 hover:text-slate-950 px-2 py-1 rounded text-[8px] orbitron font-bold border border-sky-500/20 transition-all">
                                WITHDRAW
                            </button>
                        </div>
                    </div>
                `).join('');
            }
        }

        // ── Upgrade Section ──
        const upgradeBtn = document.getElementById('storage-upgrade-btn');
        const upgradeCostEl = document.getElementById('storage-upgrade-cost');
        if (upgradeBtn && this.nextUpgradeRequirements) {
            const reqStr = Object.entries(this.nextUpgradeRequirements)
                .map(([res, qty]) => `${qty} ${res.replace('_', ' ')}`)
                .join(', ');
            if (upgradeCostEl) upgradeCostEl.innerText = `Next: +250kg (${reqStr})`;
        }

        // ── Quick Deposit from current agent inventory ──
        const depositList = document.getElementById('storage-inventory-list');
        if (depositList) {
            const agentData = window.game && (window.game.agentData || window.game.lastAgentData);
            const inv = agentData && agentData.inventory
                ? agentData.inventory.filter(i => i.type !== 'CREDITS')
                : [];
            if (inv.length === 0) {
                depositList.innerHTML = `<div class="text-[10px] text-slate-600 italic">Inventory is empty.</div>`;
            } else {
                depositList.innerHTML = inv.map(item => `
                    <div class="flex justify-between items-center p-2 bg-slate-900/40 border border-slate-800 rounded group hover:border-emerald-500/30 transition-all">
                        <div>
                            <span class="text-[10px] text-slate-300 font-bold uppercase">${item.type.replace(/_/g, ' ')}</span>
                            <span class="text-[9px] text-slate-500 block">Cargo: ${item.quantity}</span>
                        </div>
                        <button onclick="window.storageUI.depositPartial('${item.type}', ${item.quantity})"
                                class="bg-emerald-500/10 hover:bg-emerald-500 text-emerald-400 hover:text-slate-950 px-2 py-1 rounded text-[8px] orbitron font-bold border border-emerald-500/20 transition-all">
                            DEPOSIT
                        </button>
                    </div>
                `).join('');
            }
        }
    }

    /** Prompt for a quantity then deposit. */
    async depositPartial(itemType, maxQty) {
        const qtyStr = prompt(`Deposit ${itemType.replace(/_/g, ' ')} — how many? (max ${maxQty})`, maxQty);
        if (qtyStr === null) return;
        const qty = parseInt(qtyStr);
        if (isNaN(qty) || qty <= 0 || qty > maxQty) {
            alert(`Invalid quantity.`);
            return;
        }
        await this.deposit(itemType, qty);
    }

    /** Prompt for a quantity then withdraw. */
    async withdrawPartial(itemType, maxQty) {
        const qtyStr = prompt(`Withdraw ${itemType.replace(/_/g, ' ')} — how many? (max ${maxQty})`, maxQty);
        if (qtyStr === null) return;
        const qty = parseInt(qtyStr);
        if (isNaN(qty) || qty <= 0 || qty > maxQty) {
            alert(`Invalid quantity.`);
            return;
        }
        await this.withdraw(itemType, qty);
    }

    async deposit(itemType, qty) {
        try {
            const response = await fetch('/api/storage/deposit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': window.game.apiKey },
                body: JSON.stringify({ item_type: itemType, quantity: qty })
            });
            const res = await response.json();
            if (response.ok) {
                this._toast(res.message || `Deposited ${qty}x ${itemType}.`, 'success');
                this.refreshStorage();
                window.game.pollState();
            } else {
                this._toast(res.detail || 'Deposit failed.', 'error');
            }
        } catch (err) {
            console.error(err);
            this._toast('Network error during deposit.', 'error');
        }
    }

    async withdraw(itemType, qty) {
        try {
            const response = await fetch('/api/storage/withdraw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': window.game.apiKey },
                body: JSON.stringify({ item_type: itemType, quantity: qty })
            });
            const res = await response.json();
            if (response.ok) {
                this._toast(res.message || `Withdrew ${qty}x ${itemType}.`, 'success');
                this.refreshStorage();
                window.game.pollState();
            } else {
                this._toast(res.detail || 'Withdrawal failed.', 'error');
            }
        } catch (err) {
            console.error(err);
            this._toast('Network error during withdrawal.', 'error');
        }
    }

    async upgradeStorage() {
        if (!this.nextUpgradeRequirements) {
            await this.refreshStorage();
        }
        if (!this.nextUpgradeRequirements) {
            alert("Unable to fetch upgrade requirements. Please try again.");
            return;
        }

        const reqStr = Object.entries(this.nextUpgradeRequirements)
            .map(([res, qty]) => `${qty} ${res.replace('_', ' ')}`)
            .join('\n- ');

        const nextCap = this.capacity + 250;
        if (!confirm(`Upgrade vault capacity from ${this.capacity}kg to ${nextCap}kg?\n\nRequired:\n- ${reqStr}\n\nProceed?`)) return;

        try {
            const response = await fetch('/api/storage/upgrade', {
                method: 'POST',
                headers: { 'X-API-KEY': window.game.apiKey }
            });
            const res = await response.json();
            if (response.ok) {
                this._toast(res.message || 'Vault upgraded!', 'success');
                this.refreshStorage();
                window.game.pollState();
            } else {
                this._toast(res.detail || 'Upgrade failed.', 'error');
            }
        } catch (err) {
            console.error(err);
            this._toast('Network error during upgrade.', 'error');
        }
    }

    /** Show a brief toast-style message in the terminal if available. */
    _toast(msg, type) {
        if (window.game && window.game.terminal) {
            window.game.terminal.log(msg, type === 'error' ? 'error' : 'success');
        } else {
            console.log(`[StorageUI] ${msg}`);
        }
    }
}

// Initialize and bind to window
window.storageUI = new StorageUI();

// Hook into Vault tab visibility to auto-refresh
document.addEventListener('DOMContentLoaded', () => {
    const tabStorage = document.getElementById('tab-storage');
    if (tabStorage) {
        tabStorage.addEventListener('click', () => window.storageUI.refreshStorage());
    }
    // Also refresh whenever the Vault sub-tab is selected inside Inventory
    const vaultTabBtn = document.getElementById('inv-tab-vault') || document.querySelector('[onclick*="vault"]');
    if (vaultTabBtn) {
        vaultTabBtn.addEventListener('click', () => window.storageUI.refreshStorage());
    }

    // Initial check after a short delay
    setTimeout(() => window.storageUI.refreshStorage(), 1500);
});
