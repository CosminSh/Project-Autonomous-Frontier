/**
 * ui.js — DOM manipulation and UI management
 */
export const FACTION_NAMES = {
    1: 'Colonial Administration',
    2: 'Independent Syndicate',
    3: 'Freelancer Core'
};

export class UIManager {
    constructor(game) {
        this.game = game;
        this.activeForgeFilter = 'All';
        this.canCraftOnly = false;
        this.toasts = [];
        this.telemetryMinimized = false;
        
        this.marketViewMode = 'LISTINGS'; 
        this.marketDepthItem = 'IRON_ORE';
        this.cachedInventory = [];
        this.cachedStorage = [];
        this._seenLogKeys = new Set();

        this.initTelemetryToggle();
        this.initHashRouting();
        this.initSmeltControls();
    }

    initSmeltControls() {
        const btn = document.getElementById('btn-smelt');
        if (btn) {
            btn.onclick = () => {
                const oreType = document.getElementById('smelt-ore-type').value;
                const qtyInput = document.getElementById('smelt-quantity').value;
                const quantity = parseInt(qtyInput) || 1;
                this.game.api.submitIntent('SMELT', { ore_type: oreType, quantity: quantity });
            };
        }
    }

    initHashRouting() {
        window.addEventListener('hashchange', () => this.handleHashChange());
        // Initial route handling will be called by App.init or here
        setTimeout(() => this.handleHashChange(), 100);
    }

    handleHashChange() {
        const hash = window.location.hash.substring(1);
        if (!hash) return;

        const parts = hash.split('/');
        const mode = parts[0]; // world, management, leaderboard
        const tab = parts[1];  // terminal, inventory, station, social, arena, system
        const subTab = parts[2]; // e.g., forge, market, missions, repair

        if (mode) {
            this.setUIMode(mode, false); // false to avoid recursive hash update
        }

        if (tab) {
            this.switchTab(tab, false);
        }

        if (subTab) {
            if (tab === 'inventory') this.switchInventoryTab(subTab, false);
            if (tab === 'station') this.switchStationTab(subTab, false);
            if (tab === 'social') this.switchSocialTab(subTab, false);
        }
    }

    updateHash() {
        // Get current state
        const privateLayer = document.getElementById('private-dashboard');
        const leaderboardLayer = document.getElementById('leaderboard-layer');
        const mapCanvas = document.getElementById('canvas-container');

        let mode = 'world';
        if (!privateLayer.classList.contains('hidden')) mode = 'management';
        else if (!leaderboardLayer.classList.contains('hidden')) mode = 'leaderboard';

        let tab = '';
        if (mode === 'management') {
            const tabs = ['status', 'terminal', 'inventory', 'station', 'social', 'arena', 'system'];
            tab = tabs.find(t => {
                const content = document.getElementById(`content-${t}`);
                if (t === 'status') {
                    const agentDetail = document.getElementById('agent-detail');
                    return agentDetail && !agentDetail.classList.contains('hidden') && window.innerWidth < 1024;
                }
                return content && !content.classList.contains('hidden');
            }) || 'terminal';
        }

        let subTab = '';
        if (tab === 'inventory') {
            const subs = ['cargo', 'gear', 'vault'];
            subTab = subs.find(s => !document.getElementById(`inv-panel-${s}`).classList.contains('hidden')) || '';
        } else if (tab === 'station') {
            const subs = ['smelt', 'forge', 'market', 'missions', 'repair'];
            subTab = subs.find(s => !document.getElementById(`stn-panel-${s}`).classList.contains('hidden')) || '';
        } else if (tab === 'social') {
            const subs = ['squad', 'corp'];
            subTab = subs.find(s => {
                const p = document.getElementById(`social-panel-${s}`);
                return p && !p.classList.contains('hidden');
            }) || '';
        }

        let newHash = mode;
        if (tab) newHash += `/${tab}`;
        if (subTab) newHash += `/${subTab}`;

        // Avoid infinite loops and unnecessary history entries
        if (window.location.hash.substring(1) !== newHash) {
            window.location.hash = newHash;
        }
    }

    initTelemetryToggle() {
        // Toggle logic for mobile telemetry box
        const btn = document.getElementById('toggle-telemetry-btn');
        const box = document.getElementById('world-telemetry-box');
        const icon = document.getElementById('telemetry-toggle-icon');
        if (btn && box && icon) {
            btn.addEventListener('click', () => {
                this.telemetryMinimized = !this.telemetryMinimized;
                if (this.telemetryMinimized) {
                    box.classList.remove('h-32');
                    box.classList.add('h-8');
                    icon.style.transform = 'rotate(180deg)';
                } else {
                    box.classList.remove('h-8');
                    box.classList.add('h-32');
                    icon.style.transform = 'rotate(0deg)';
                }
            });
        }
    }

    showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        const colors = {
            info: 'border-l-sky-500 text-sky-400',
            success: 'border-l-emerald-500 text-emerald-400',
            warning: 'border-l-amber-500 text-amber-400',
            error: 'border-l-rose-500 text-rose-400'
        };

        toast.className = `toast glass p-3 rounded-xl border-l-4 ${colors[type] || colors.info} flex items-center space-x-3 min-w-[200px] pointer-events-auto interactive shadow-2xl`;
        
        const icon = {
            info: 'ℹ️',
            success: '✅',
            warning: '⚠️',
            error: '🚫'
        }[type] || '🔔';

        toast.innerHTML = `
            <span class="text-lg">${icon}</span>
            <div class="flex flex-col">
                <span class="text-[10px] orbitron font-bold tracking-widest uppercase opacity-70">${type}</span>
                <span class="text-xs font-semibold">${message}</span>
            </div>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.transform = 'translateX(120%)';
            toast.style.opacity = '0';
            toast.style.transition = 'all 0.4s ease-in';
            setTimeout(() => toast.remove(), 400);
        }, duration);
    }

    setUIMode(mode, updateHash = true) {
        const privateLayer = document.getElementById('private-dashboard');
        const leaderboardLayer = document.getElementById('leaderboard-layer');
        const btnWorld = document.getElementById('btn-mode-world');
        const btnAgent = document.getElementById('btn-mode-agent');
        const btnLeaderboard = document.getElementById('btn-mode-leaderboard');
        const mapCanvas = document.getElementById('canvas-container');
        const dashboardLayer = document.getElementById('dashboard-layer');

        // Hide all layers first
        if (privateLayer) {
            privateLayer.classList.add('hidden');
            privateLayer.classList.remove('lg:flex');
        }
        if (dashboardLayer) dashboardLayer.classList.add('hidden');
        if (leaderboardLayer) leaderboardLayer.classList.add('hidden');
        if (mapCanvas) mapCanvas.classList.add('hidden');

        // Reset buttons
        [btnWorld, btnAgent, btnLeaderboard].forEach(btn => {
            if (btn) btn.classList.remove('bg-sky-500', 'text-slate-950');
        });

        if (mode === 'world') {
            if (mapCanvas) mapCanvas.classList.remove('hidden', 'invisible');
            if (dashboardLayer) dashboardLayer.classList.remove('hidden');
            if (btnWorld) btnWorld.classList.add('bg-sky-500', 'text-slate-950');
        } else if (mode === 'management') {
            if (privateLayer) {
                privateLayer.classList.remove('hidden');
                privateLayer.classList.add('lg:flex');
            }
            if (btnAgent) btnAgent.classList.add('bg-sky-500', 'text-slate-950');
        } else if (mode === 'leaderboard') {
            if (leaderboardLayer) leaderboardLayer.classList.remove('hidden');
            if (btnLeaderboard) btnLeaderboard.classList.add('bg-sky-500', 'text-slate-950');
            this.game.api.fetchLeaderboards();
        }

        if (updateHash !== false) this.updateHash();

        if (this.game.inTutorialMode && this.game.tutorial) {
            this.game.tutorial.handleAction('ui_mode', mode);
        }
    }

    switchTab(tabId, updateHash = true) {
        const tabs = ['status', 'terminal', 'inventory', 'station', 'social', 'arena', 'system'];
        const agentDetail = document.getElementById('agent-detail');
        const mainContent = document.querySelector('#private-dashboard main');

        tabs.forEach(t => {
            const btn = document.getElementById(`tab-${t}`);
            const content = document.getElementById(`content-${t}`);
            if (btn) {
                btn.classList.toggle('border-b-2', t === tabId);
                btn.classList.toggle('border-sky-500', t === tabId);
                btn.classList.toggle('text-sky-400', t === tabId);
                btn.classList.toggle('text-slate-500', t !== tabId);
                btn.classList.toggle('border-b-0', t !== tabId);
            }
            if (content) content.classList.toggle('hidden', t !== tabId);
        });

        // Mobile Status handling
        if (tabId === 'status') {
            if (agentDetail) agentDetail.classList.remove('hidden');
            if (mainContent) {
                // Hide all tab content divs inside main to only show the status panel
                const contentDivs = mainContent.querySelectorAll('div[id^="content-"]');
                contentDivs.forEach(d => d.classList.add('hidden'));
            }
        } else {
            // Only hide agentDetail on mobile (lg:block takes over on desktop)
            if (agentDetail && window.innerWidth < 1024) agentDetail.classList.add('hidden');
        }

        if (tabId === 'inventory' && window.storageUI) {
            window.storageUI.refreshStorage();
        }
        if (tabId === 'arena') {
            this.game.api.fetchArenaStatus();
        }
        if (tabId === 'social') {
            this.updateCorporationUI();
            const subs = ['squad', 'corp'];
            const active = subs.find(s => {
                const p = document.getElementById(`social-panel-${s}`);
                return p && !p.classList.contains('hidden');
            });
            if (!active) this.switchSocialTab('squad', false);
        }
        if (tabId === 'station') {
            const subs = ['smelt', 'forge', 'market', 'missions', 'repair'];
            const active = subs.find(s => {
                const p = document.getElementById(`stn-panel-${s}`);
                return p && !p.classList.contains('hidden');
            });
            if (!active) this.switchStationTab('forge', false);
        }

        if (updateHash !== false) this.updateHash();
    }

    switchInventoryTab(subTab, updateHash = true) {
        const panels = ['cargo', 'gear', 'vault'];
        const activeColors = { cargo: 'sky', gear: 'sky', vault: 'sky' };
        panels.forEach(p => {
            const btn = document.getElementById(`inv-tab-${p}`);
            const panel = document.getElementById(`inv-panel-${p}`);
            if (panel) panel.classList.toggle('hidden', p !== subTab);
            if (btn) {
                if (p === subTab) {
                    btn.classList.add('border-sky-500/50', 'bg-sky-500/10', 'text-sky-400');
                    btn.classList.remove('border-slate-700', 'text-slate-500');
                } else {
                    btn.classList.remove('border-sky-500/50', 'bg-sky-500/10', 'text-sky-400');
                    btn.classList.add('border-slate-700', 'text-slate-500');
                }
            }
        });
        if (subTab === 'vault' && window.storageUI) {
            window.storageUI.refreshStorage();
        }

        if (updateHash !== false) this.updateHash();
    }

    switchStationTab(subTab, updateHash = true) {
        const panels = ['smelt', 'forge', 'market', 'missions', 'repair'];
        panels.forEach(p => {
            const btn = document.getElementById(`stn-tab-${p}`);
            const panel = document.getElementById(`stn-panel-${p}`);
            if (panel) panel.classList.toggle('hidden', p !== subTab);
            if (btn) {
                if (p === subTab) {
                    btn.classList.add('border-emerald-500/50', 'bg-emerald-500/10', 'text-emerald-400');
                    btn.classList.remove('border-slate-700', 'text-slate-500');
                } else {
                    btn.classList.remove('border-emerald-500/50', 'bg-emerald-500/10', 'text-emerald-400');
                    btn.classList.add('border-slate-700', 'text-slate-500');
                }
            }
        });

        if (subTab === 'smelt') {
            this.updateSmeltRequirements();
        }

        if (updateHash !== false) this.updateHash();
    }

    switchSocialTab(subTab, updateHash = true) {
        const panels = ['squad', 'corp'];
        panels.forEach(p => {
            const btn = document.getElementById(`social-tab-${p}`);
            const panel = document.getElementById(`social-panel-${p}`);
            if (panel) panel.classList.toggle('hidden', p !== subTab);
            if (btn) {
                if (p === subTab) {
                    btn.classList.add('border-purple-500/50', 'bg-purple-500/10', 'text-purple-400');
                    btn.classList.remove('border-slate-700', 'text-slate-500');
                } else {
                    btn.classList.remove('border-purple-500/50', 'bg-purple-500/10', 'text-purple-400');
                    btn.classList.add('border-slate-700', 'text-slate-500');
                }
            }
        });

        if (updateHash !== false) this.updateHash();
    }

    updateSmeltRequirements() {
        const oreEl = document.getElementById('smelt-ore-type');
        const qtyEl = document.getElementById('smelt-quantity');
        const reqEnergyEl = document.getElementById('smelt-req-energy');
        const reqTimeEl = document.getElementById('smelt-req-time');
        const reqOreEl = document.getElementById('smelt-req-ore');

        if (!oreEl || !qtyEl || !reqEnergyEl || !reqTimeEl || !reqOreEl) return;

        const oreType = oreEl.value;
        const qty = parseInt(qtyEl.value) || 0;

        const energyCosts = {
            'IRON_ORE': 5,
            'COPPER_ORE': 10,
            'GOLD_ORE': 15,
            'COBALT_ORE': 20
        };

        const energyPerIngot = energyCosts[oreType] || 0;
        const ratio = 5; // 5 Ore -> 1 Ingot

        const totalEnergy = qty * energyPerIngot;
        const totalOre = qty * ratio;
        const totalTime = qty; // 1 tick per ingot

        reqEnergyEl.innerText = totalEnergy;
        reqTimeEl.innerText = `${totalTime} TICKS`;
        reqOreEl.innerText = `${totalOre} ${oreType.replace('_', ' ')}`;
    }

    setSmeltMax() {
        const oreEl = document.getElementById('smelt-ore-type');
        if (!oreEl) return;
        const oreType = oreEl.value;
        
        // Search in personal inventory and vault
        let totalOreCount = 0;
        if (this.game.me) {
            // Check inventory
            if (this.game.me.inventory) {
                totalOreCount += this.game.me.inventory
                    .filter(i => i.type === oreType)
                    .reduce((sum, i) => sum + i.quantity, 0);
            }
            // Check vault
            if (this.game.me.storage) {
                totalOreCount += this.game.me.storage
                    .filter(i => i.item_type === oreType)
                    .reduce((sum, i) => sum + i.quantity, 0);
            }
        }

        const ratio = 5;
        const maxIngots = Math.floor(totalOreCount / ratio);
        const qtyEl = document.getElementById('smelt-quantity');
        if (qtyEl) {
            qtyEl.value = maxIngots;
            this.updateSmeltRequirements();
        }
    }


    updateGlobalUI(stats) {
        document.getElementById('stat-agents').innerText = stats.total_agents || 0;
        document.getElementById('stat-market').innerText = stats.market_listings || 0;
        if (document.getElementById('stat-actions')) {
            document.getElementById('stat-actions').innerText = (stats.actions_processed || 0).toLocaleString();
        }
    }

    updateTickUI(tick, phase) {
        if (tick !== undefined) {
            document.getElementById('tick-count').innerText = tick.toString().padStart(4, '0');
        }
        if (phase) {
            const phaseEl = document.getElementById('tick-phase');
            phaseEl.innerText = phase;
            phaseEl.classList.remove('text-red-400', 'text-emerald-400', 'text-sky-400');
            if (phase === 'CRUNCH') phaseEl.classList.add('text-red-400');
            else if (phase === 'PERCEPTION') phaseEl.classList.add('text-emerald-400');
            else phaseEl.classList.add('text-sky-400');
        }
    }

    updateLiveFeed(logs) {
        // Redacted: Global feed replaced by Action Telemetry on world screen
    }

    updatePrivateLogs(logs, pendingIntent, chatMessages = []) {
        const logEl = document.getElementById('private-logs');
        if (!logEl) return;

        // ── Pending Intent card (pinned at top, updated every call) ──
        if (!this._pendingIntentEl) {
            this._pendingIntentEl = document.createElement('div');
            this._pendingIntentEl.id = 'telemetry-pending-intent';
            logEl.prepend(this._pendingIntentEl);
        }
        if (pendingIntent) {
            this._pendingIntentEl.className = 'border-b border-sky-500/30 pb-2 mb-2 flex flex-col bg-sky-500/5 p-2 rounded-lg border border-sky-500/10';
            this._pendingIntentEl.innerHTML = `<div class="flex justify-between items-center mb-1"><span class="text-sky-400 font-bold uppercase tracking-widest text-[8px]">Next Action</span></div><div class="flex space-x-2 text-sky-300"><span class="font-bold flex-shrink-0">${pendingIntent.action}</span><span class="truncate">${JSON.stringify(pendingIntent.data)}</span></div>`;
            this._pendingIntentEl.classList.remove('hidden');
        } else {
            this._pendingIntentEl.className = 'hidden';
        }

        // ── Append only NEW log/chat entries (never clear, like a terminal) ──
        const combined = [...(logs || []), ...(chatMessages || [])].sort(
            (a, b) => new Date(b.time || b.timestamp) - new Date(a.time || a.timestamp)
        );

        const fragment = document.createDocumentFragment();
        let hasNew = false;

        combined.forEach(item => {
            const isChat = !!item.channel;
            const timeStr = item.time || item.timestamp;
            const key = isChat
                ? `chat:${timeStr}:${item.sender}:${item.message}`
                : `log:${timeStr}:${item.event}`;

            if (this._seenLogKeys.has(key)) return;  // already rendered
            this._seenLogKeys.add(key);

            // Auto-Toast for failures or critical events
            if (!isChat) {
                if (item.event && item.event.endsWith('_FAILED')) {
                    this.showToast(item.details.reason || item.event, 'error');
                } else if (item.event === 'COMBAT_HIT' && item.details?.damage > 0) {
                    // Only toast players if they are involved or it's high stakes
                } else if (item.event === 'MARKET_MATCH' || item.event === 'INDUSTRIAL_CRAFT') {
                    this.showToast(`${item.event}: Success`, 'success');
                }
            }

            const time = new Date(timeStr).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const entry = document.createElement('div');
            entry.className = 'border-b border-slate-900/50 pb-1 flex space-x-2';

            if (isChat) {
                let badgeColor = 'bg-slate-500 text-white';
                if (item.channel === 'GLOBAL') badgeColor = 'bg-indigo-600 text-indigo-100';
                if (item.channel === 'PROX' || item.channel === 'LOCAL') badgeColor = 'bg-emerald-600 text-emerald-100';
                if (item.channel === 'SQUAD') badgeColor = 'bg-sky-600 text-sky-100';
                if (item.channel === 'CORP') badgeColor = 'bg-amber-600 text-amber-100';
                entry.innerHTML = `<span class="text-slate-700 font-mono flex-shrink-0">[${time}]</span><span class="${badgeColor} px-1 rounded text-[10px] font-bold tracking-widest leading-none flex items-center flex-shrink-0">${item.channel}</span><span class="text-slate-300 font-bold flex-shrink-0">${item.sender}:</span><span class="text-slate-100" style="word-break: break-all;">${item.message}</span>`;
            } else {
                let color = 'text-slate-400';
                if (item.event.startsWith('COMBAT')) color = 'text-rose-400';
                else if (item.event === 'MINING') color = 'text-emerald-400';
                else if (item.details?.status === 'success') color = 'text-sky-400';

                let detailsHtml = '';
                if (item.details?.log && Array.isArray(item.details.log)) {
                    // Show combat rounds as a sub-list
                    detailsHtml = `<div class="mt-1 pl-4 border-l border-slate-800 space-y-0.5 text-[8px] opacity-80">` +
                        item.details.log.map(line => `<div>${line}</div>`).join('') +
                        `</div>`;
                } else {
                    detailsHtml = `<span class="truncate opacity-60">${JSON.stringify(item.details)}</span>`;
                }

                entry.classList.add(color, 'flex-col', 'space-x-0');
                entry.innerHTML = `
                    <div class="flex space-x-2">
                        <span class="text-slate-700 font-mono flex-shrink-0">[${time}]</span>
                        <span class="font-bold flex-shrink-0">${item.event}</span>
                    </div>
                    ${detailsHtml}
                `;
            }

            fragment.appendChild(entry);
            hasNew = true;
        });

        if (hasNew) {
            // Insert new entries after the pending-intent card (at top of log feed)
            const afterPending = this._pendingIntentEl?.nextSibling || null;
            logEl.insertBefore(fragment.cloneNode(true), afterPending);
            // Auto-scroll to top to show newest entries
            logEl.scrollTop = 0;

            // --- SYNC TO WORLD SCREEN FEED ---
            const worldFeed = document.getElementById('world-telemetry-feed');
            if (worldFeed) {
                // For world screen, we keep it simpler but show newest at top
                if (worldFeed.children.length > 50) worldFeed.lastElementChild.remove();
                worldFeed.prepend(fragment);
                worldFeed.scrollTop = 0;
            }
        }
    }

    async updateMarketUI(market) {
        const body = document.getElementById('market-listings-body');
        const countSell = document.getElementById('count-sell');
        const countBuy = document.getElementById('count-buy');
        if (!body || !market) return;

        let myOrderIds = new Set();
        try {
            if (this.game.apiKey) {
                const resp = await fetch(`${window.location.origin}/api/market/my_orders`, {
                    headers: { 'X-API-KEY': this.game.apiKey }
                });
                if (resp.ok) {
                    const myOrders = await resp.json();
                    myOrderIds = new Set(myOrders.map(o => o.id));
                }
            }
        } catch (e) { console.error("Failed to fetch my orders for market UI:", e); }

        body.innerHTML = '';
        let sells = 0, buys = 0;

        market.forEach(order => {
            if (order.type === 'SELL') sells++; else buys++;
            const row = document.createElement('tr');
            row.className = "border-b border-slate-800/50 hover:bg-slate-800/20 transition-all group";
            const color = order.type === 'SELL' ? 'text-sky-400' : 'text-amber-400';
            const isMine = myOrderIds.has(order.id);

            row.innerHTML = `
                <td class="py-4 font-bold text-slate-300">
                    ${order.item.replace('_', ' ')}
                    ${isMine ? '<span class="ml-2 px-1.5 py-0.5 rounded text-[8px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 tracking-widest hidden lg:inline-block">YOURS</span>' : ''}
                </td>
                <td class="py-4"><span class="px-2 py-0.5 rounded-full text-[7px] font-black border ${order.type === 'SELL' ? 'bg-sky-500/10 border-sky-500/30 text-sky-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}">${order.type}</span></td>
                <td class="py-4 font-mono text-slate-400">${order.quantity}</td>
                <td class="py-4 font-bold ${color}">$${order.price.toFixed(2)}</td>
                <td class="py-4 text-right">
                    ${isMine ? `
                        <button class="opacity-0 group-hover:opacity-100 bg-rose-800/50 hover:bg-rose-700 text-rose-300 px-3 py-1 rounded text-[9px] font-bold mr-1 border border-rose-500/30 transition-all" onclick="window.game.api.cancelMarketOrder(${order.id})">CANCEL</button>
                        <button class="opacity-0 group-hover:opacity-100 bg-sky-800/50 hover:bg-sky-700 text-sky-300 px-3 py-1 rounded text-[9px] font-bold border border-sky-500/30 transition-all" onclick="window.game.api.adjustMarketOrder(${order.id}, ${order.price})">ADJUST</button>
                    ` : `
                        <button class="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded text-[9px] font-bold transition-all" onclick="game.ui.quickTrade('${order.item}', ${order.price}, '${order.type}')">
                            ${order.type === 'SELL' ? 'BUY' : 'SELL'}
                        </button>
                    `}
                </td>
            `;
            body.appendChild(row);
        });
        if (countSell) countSell.textContent = sells;
        if (countBuy) countBuy.textContent = buys;
        
        // If we are in depth mode, we need to handle that too
        if (this.marketViewMode === 'DEPTH') {
            this.refreshMarketDepth();
        }
    }

    async refreshMarketDepth() {
        const depth = await this.game.api.getMarketDepth(this.marketDepthItem);
        if (!depth) return;
        this.updateMarketDepthUI(depth);
    }

    updateMarketDepthUI(data) {
        const body = document.getElementById('market-listings-body');
        if (!body || this.marketViewMode !== 'DEPTH') return;

        let html = `
            <tr><td colspan="5" class="py-2 text-center bg-slate-900/50 border-y border-slate-800">
                <div class="flex justify-center items-center space-x-4">
                    <span class="text-[10px] orbitron font-bold text-sky-400">ORDER BOOK: ${data.item.replace('_', ' ')}</span>
                    <button onclick="game.ui.toggleMarketView()" class="text-[8px] text-slate-500 hover:text-white underline">BACK TO LISTINGS</button>
                </div>
            </td></tr>
            <tr class="text-[8px] text-slate-500 uppercase border-b border-slate-800">
                <th class="py-2 font-normal">Side</th>
                <th class="py-2 font-normal">Price</th>
                <th class="py-2 font-normal">Quantity</th>
                <th class="py-2 font-normal text-right">Action</th>
            </tr>
        `;

        // Sell Orders (Asks) - Reddish/Sky
        data.sell_orders.forEach(o => {
            html += `
                <tr class="group hover:bg-sky-500/5 transition-all">
                    <td class="py-2"><span class="px-1.5 py-0.5 rounded text-[7px] font-black bg-sky-500/10 border border-sky-500/30 text-sky-400">ASK</span></td>
                    <td class="py-2 font-bold text-sky-400">$${o.price.toFixed(2)}</td>
                    <td class="py-2 font-mono text-slate-400">${o.qty}</td>
                    <td class="py-2 text-right">
                        <button class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded text-[8px] font-bold" onclick="game.ui.quickTrade('${data.item}', ${o.price}, 'SELL')">BUY</button>
                    </td>
                </tr>
            `;
        });

        if (data.sell_orders.length === 0) {
            html += `<tr><td colspan="4" class="py-2 text-center text-slate-600 italic text-[9px]">No sellers.</td></tr>`;
        }

        html += `<tr class="border-t-2 border-slate-800"><td colspan="4" class="py-1"></td></tr>`;

        // Buy Orders (Bids) - Amber
        data.buy_orders.forEach(o => {
            html += `
                <tr class="group hover:bg-amber-500/5 transition-all">
                    <td class="py-2"><span class="px-1.5 py-0.5 rounded text-[7px] font-black bg-amber-500/10 border border-amber-500/30 text-amber-400">BID</span></td>
                    <td class="py-2 font-bold text-amber-500">$${o.price.toFixed(2)}</td>
                    <td class="py-2 font-mono text-slate-400">${o.qty}</td>
                    <td class="py-2 text-right">
                        <button class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded text-[8px] font-bold" onclick="game.ui.quickTrade('${data.item}', ${o.price}, 'BUY')">SELL</button>
                    </td>
                </tr>
            `;
        });

        if (data.buy_orders.length === 0) {
            html += `<tr><td colspan="4" class="py-2 text-center text-slate-600 italic text-[9px]">No buyers.</td></tr>`;
        }

        body.innerHTML = html;
    }

    toggleMarketView() {
        this.marketViewMode = (this.marketViewMode === 'LISTINGS') ? 'DEPTH' : 'LISTINGS';
        if (this.game.lastWorldData && this.game.lastWorldData.market) {
            this.updateMarketUI(this.game.lastWorldData.market);
        }
    }

    setMarketDepthItem(item) {
        this.marketDepthItem = item;
        this.marketViewMode = 'DEPTH';
        this.refreshMarketDepth();
    }

    quickTrade(item, price, type) {
        document.getElementById('trade-item-type').value = item;
        document.getElementById('trade-price').value = price;
        document.getElementById('trade-quantity').value = 1;
        if (type === 'SELL') document.getElementById('trade-side-buy').click();
        else document.getElementById('trade-side-sell').click();
    }

    setTradeSide(side) {
        this.game.tradeSide = side;
        const buyBtn = document.getElementById('trade-side-buy');
        const sellBtn = document.getElementById('trade-side-sell');
        if (side === 'BUY') {
            buyBtn.classList.add('bg-amber-500', 'text-slate-950');
            sellBtn.classList.remove('bg-sky-500', 'text-slate-950');
        } else {
            sellBtn.classList.add('bg-sky-500', 'text-slate-950');
            buyBtn.classList.remove('bg-amber-500', 'text-slate-950');
        }
    }

    updateBountyBoard(bounties) {
        const body = document.getElementById('bounty-listings-body');
        if (!body) return;
        if (!bounties || bounties.length === 0) {
            body.innerHTML = '<tr><td colspan="2" class="text-center py-4 text-slate-600 italic">No active warrants.</td></tr>';
            return;
        }
        body.innerHTML = bounties.map(b => `
            <tr class="border-b border-slate-800/50 hover:bg-slate-800/20 transition-all">
                <td class="py-3 font-bold text-rose-400">AGENT #${b.target_id.toString().padStart(4, '0')}</td>
                <td class="py-3 font-mono text-slate-300 text-right font-bold text-amber-400">$${b.reward}</td>
            </tr>
        `).join('');
    }

    updateMissionsUI(missions) {
        const list = document.getElementById('missions-list');
        if (!list) return;

        if (!missions || missions.length === 0) {
            list.innerHTML = `<div class="text-[10px] text-slate-500 italic">No daily missions available. Return later.</div>`;
            return;
        }

        list.innerHTML = missions.map(m => `
            <div class="p-3 bg-slate-900/50 rounded-lg border border-slate-800 ${m.is_completed ? 'border-emerald-500/30' : ''}">
                <div class="flex justify-between items-start mb-2">
                    <h5 class="text-[10px] orbitron font-bold ${m.is_completed ? 'text-emerald-400' : 'text-slate-300'}">${m.title}</h5>
                    <span class="text-[9px] text-sky-400 font-bold">$${m.reward_credits}</span>
                </div>
                <p class="text-[9px] text-slate-500 mb-2">${m.description}</p>
                <div class="flex justify-between items-center">
                    <div class="text-[8px] text-slate-500 uppercase tracking-tighter">
                        Progress: <span class="${m.is_completed ? 'text-emerald-400' : 'text-slate-300'}">${m.current_quantity} / ${m.required_quantity}</span>
                    </div>
                    ${m.is_completed && !m.is_turned_in ? `
                        <button onclick="game.api.turnInMission(${m.id})" class="px-2 py-1 bg-emerald-500 text-slate-950 text-[8px] orbitron font-bold rounded hover:bg-emerald-400 transition-colors">TURN IN</button>
                    ` : m.is_turned_in ? `
                        <span class="text-[8px] text-emerald-500 font-bold italic">COMPLETED</span>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    updateLeaderboardsUI(data) {
        const xpBody = document.getElementById('xp-leaderboard-body');
        const creditsBody = document.getElementById('credits-leaderboard-body');
        const updateText = document.getElementById('leaderboard-last-update');
        const myAgentId = parseInt(localStorage.getItem('sv_agent_id'));

        if (updateText && data.last_updated) {
            updateText.innerText = new Date(data.last_updated).toLocaleString();
        }

        const renderRows = (list, isCredits = false) => {
            if (!list || list.length === 0) return '<tr><td colspan="3" class="py-4 text-center text-slate-500 italic">No entries found.</td></tr>';
            return list.map(entry => `
                <tr class="border-b border-slate-800/50 ${entry.agent_id === myAgentId ? 'bg-sky-500/10 text-sky-400 font-bold' : 'text-slate-400'}">
                    <td class="py-3 pl-2">${entry.rank}</td>
                    <td class="py-3">${entry.name} ${entry.agent_id === myAgentId ? '<span class="text-[8px] bg-sky-500 text-slate-950 px-1 rounded ml-1">YOU</span>' : ''}</td>
                    <td class="py-3 text-right pr-4 font-mono">${isCredits ? '$' : ''}${entry.value.toLocaleString()}</td>
                </tr>
            `).join('');
        };

        if (xpBody) xpBody.innerHTML = renderRows(data.categories.experience);
        if (creditsBody) creditsBody.innerHTML = renderRows(data.categories.credits, true);
    }

    updateMyOrdersUI(orders) {
        const container = document.getElementById('my-orders');
        if (!container) return;
        if (!orders || orders.length === 0) {
            container.innerHTML = '<div class="text-[10px] text-slate-600 italic text-center py-4">No active contracts found.</div>';
            return;
        }
        container.innerHTML = orders.map(o => `
            <div class="flex justify-between items-center bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                <div class="flex items-center space-x-3">
                    <div class="w-2 h-2 rounded-full ${o.type === 'SELL' ? 'bg-sky-400' : 'bg-amber-400'}"></div>
                    <div class="text-[10px] font-bold text-slate-200 uppercase">${o.item.replace('_', ' ')}</div>
                </div>
                <button onclick="game.api.submitIntent('CANCEL', {order_id: ${o.id}})" class="text-slate-600 hover:text-rose-500 text-xs text-[9px]">Cancel</button>
            </div>
        `).join('');
    }

    updateScannerUI(agentId) {
        const readout = document.getElementById('scanner-readout');
        const content = document.getElementById('scanner-content');
        if (!readout || !content) return;
        readout.classList.remove('hidden');

        const agent = this.game.lastWorldData?.agents?.find(a => a.id === agentId);
        if (!agent) {
            content.innerHTML = `<p class="text-[10px] text-slate-500 italic">Signature lost.</p>`;
            return;
        }

        const hpPct = (agent.health / agent.max_health) * 100;
        const faction = FACTION_NAMES[agent.faction_id] || "Independent / Feral";
        
        const corpText = agent.corp_ticker ? `<p class="text-[10px] text-emerald-400 font-bold mb-1">[${agent.corp_ticker}] ${agent.scan_data?.corp_role || 'MEMBER'}</p>` : '';

        let scanHTML = '';
        if (agent.scan_data) {
            const sd = agent.scan_data;
            scanHTML = `
                <div class="grid grid-cols-2 gap-2 bg-slate-900/40 p-2 rounded-lg border border-slate-800/80">
                    <div class="text-[8px] text-slate-500 uppercase">DMG: <span class="text-rose-400">${sd.damage}</span></div>
                    <div class="text-[8px] text-slate-500 uppercase">SPD: <span class="text-sky-400">${sd.speed}</span></div>
                    <div class="text-[8px] text-slate-500 uppercase">ACC: <span class="text-emerald-400">${sd.accuracy}</span></div>
                    <div class="text-[8px] text-slate-500 uppercase">ARM: <span class="text-amber-400">${sd.armor}</span></div>
                </div>
            `;
        }

        content.innerHTML = `
            <div>
                <p class="text-[11px] font-bold text-white mb-0.5">${agent.name} <span class="text-slate-600 font-mono text-[9px]">#${agent.id}</span></p>
                ${corpText}
                <p class="text-[9px] text-rose-400 uppercase tracking-tighter mb-2">${faction}</p>
                <div class="w-full h-1 bg-slate-900 rounded-full overflow-hidden mb-3"><div class="h-full bg-emerald-500" style="width: ${hpPct}%"></div></div>
                ${scanHTML}
            </div>
        `;
    }

    updatePrivateUI(agent) {
        if (!agent || !agent.id) return;

        // Populate sidebars and bars...
        document.getElementById('agent-name').innerText = agent.name;
        document.getElementById('agent-id').innerText = `#${agent.id.toString().padStart(4, '0')}`;
        document.getElementById('agent-lvl').innerText = `LVL ${agent.level}`;
        document.getElementById('agent-coords').innerText = `Q:${agent.q}, R:${agent.r}`;

        const factions = { 1: 'Cybernetics', 2: 'Industrials', 3: 'Scavengers' };
        document.getElementById('agent-faction').innerText = factions[agent.faction] || 'No Faction';

        const corpEl = document.getElementById('agent-corp');
        const corpDivider = document.getElementById('agent-corp-divider');
        if (corpEl) {
            if (agent.corp_ticker) {
                corpEl.innerText = `[${agent.corp_ticker}] ${agent.corp_role || 'MEMBER'}`;
                corpDivider?.classList.remove('hidden');
            } else {
                corpEl.innerText = '';
                corpDivider?.classList.add('hidden');
            }
        }

        if (document.getElementById('stat-dmg')) document.getElementById('stat-dmg').innerText = agent.damage;
        if (document.getElementById('stat-spd')) document.getElementById('stat-spd').innerText = agent.speed;
        if (document.getElementById('stat-acc')) document.getElementById('stat-acc').innerText = agent.accuracy;
        if (document.getElementById('stat-arm')) document.getElementById('stat-arm').innerText = agent.armor;
        if (document.getElementById('stat-mining')) document.getElementById('stat-mining').innerText = agent.mining_yield || 10;

        document.getElementById('hp-bar').style.width = `${(agent.health / agent.max_health) * 100}%`;
        document.getElementById('hp-text').innerText = `${agent.health}/${agent.max_health}`;

        document.getElementById('energy-bar').style.width = `${agent.energy}%`;
        document.getElementById('energy-text').innerText = `${agent.energy}/100`;

        // XP
        const nextLevelXP = agent.level * 1000;
        const xpProgress = (agent.experience / nextLevelXP) * 100;
        const xpBar = document.getElementById('xp-bar');
        const xpText = document.getElementById('xp-text');
        if (xpBar) xpBar.style.width = `${xpProgress}%`;
        if (xpText) xpText.innerText = `${agent.experience}`;

        // Mass / Cargo
        const massBar = document.getElementById('mass-bar');
        const massText = document.getElementById('mass-text');
        if (massBar) massBar.style.width = `${(agent.mass / agent.max_mass) * 100}%`;
        if (massText) massText.innerText = `${agent.mass.toFixed(1)}/${agent.max_mass.toFixed(1)}`;

        // Wear & Tear
        const wearBar = document.getElementById('wear-bar');
        const wearText = document.getElementById('wear-text');
        const wearWarn = document.getElementById('wear-warning');
        if (wearBar) wearBar.style.width = `${agent.wear_and_tear}%`;
        if (wearText) wearText.innerText = `${Math.floor(agent.wear_and_tear)}%`;
        if (wearWarn) {
            if (agent.wear_and_tear > 80) wearWarn.classList.remove('hidden');
            else wearWarn.classList.add('hidden');
        }

        // Heat
        const heatTag = document.getElementById('agent-heat-tag');
        const heatVal = document.getElementById('agent-heat-val');
        if (heatTag && heatVal) {
            if (agent.heat > 0) {
                heatTag.classList.remove('hidden');
                heatVal.innerText = `HEAT: ${agent.heat}`;
            } else {
                heatTag.classList.add('hidden');
            }
        }

        if (agent.inventory) this.cachedInventory = agent.inventory;
        if (agent.storage) this.cachedStorage = agent.storage;

        if (agent.discovery) {
            this.updateNavComputer(agent.discovery);
            this.updateForgeUI(agent.discovery);
        }

        this.updateSquadUI(agent);
        this.drawMinimap();

        if (agent.solar_intensity !== undefined) {
            const solarBar = document.getElementById('solar-bar');
            const solarText = document.getElementById('solar-text');
            if (solarBar) solarBar.style.width = `${agent.solar_intensity}%`;
            if (solarText) solarText.innerText = `${agent.solar_intensity}%`;
        }

        const invList = document.getElementById('inventory-list');
        if (invList && agent.inventory) {
            invList.innerHTML = agent.inventory.map(i => `
                <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                    <div class="flex flex-col">
                        <span class="text-[10px] uppercase text-slate-300">${i.type.replace('_', ' ')}</span>
                        <span class="text-[8px] text-slate-500">${i.weight ? i.weight.toFixed(1) + 'kg/u' : ''}</span>
                    </div>
                    <span class="text-sky-400 text-[10px]">${i.quantity}</span>
                </div>
            `).join('');
        }

        // --- AGENT STATUS OVERLAY ---
        const overlay = document.getElementById('agent-status-overlay');
        const statusText = document.getElementById('agent-status-text');
        if (overlay && statusText) {
            let status = "IDLE / STANDBY";
            const pi = agent.pending_intent;
            if (pi) {
                if (pi.action === 'MOVE') status = `HEADING TO ${pi.data.q}, ${pi.data.r}`;
                else if (pi.action === 'MINE') status = "MINING RESOURCES";
                else if (pi.action === 'SALVAGE') status = "SALVAGING DEBRIS";
                else if (pi.action === 'PERCEIVE') status = "SCANNING SECTOR";
                else status = `${pi.action} IN PROGRESS`;
            }
            
            statusText.innerText = status;
            overlay.classList.remove('opacity-0');
            overlay.classList.add('opacity-100');
        }

        // --- GARAGE CATEGORIZATION ---
        const equippedEl = document.getElementById('equipped-list');
        const detailedInvEl = document.getElementById('detailed-inventory');
        const equipmentInvEl = document.getElementById('equipment-inventory');
        const consumableInvEl = document.getElementById('consumable-inventory');

        if (equippedEl && agent.parts) {
            const framePart = agent.parts.find(p => p.type === 'Frame');
            const frameName = framePart ? framePart.name : "Scrap Frame";
            const FRAME_KEY_MAP = {
                "Scrap Frame": "SCRAP_FRAME",
                "Standard Chassis": "BASIC_FRAME",
                "Hybrid Multi-Role Frame": "HYBRID_CHASSIS",
                "Bastion Heavy Frame": "HEAVY_FRAME",
                "Striker Light Chassis": "STRIKER_CHASSIS",
                "Industrial Super-Hull": "INDUSTRIAL_HULL"
            };
            const frameKey = FRAME_KEY_MAP[frameName] || "DEFAULT";
            const limits = agent.discovery?.frame_slot_limits?.[frameKey] || { Actuator: 1, Engine: 1, Sensor: 1, Power: 1 };

            const grouped = { Actuator: [], Engine: [], Sensor: [], Power: [] };
            agent.parts.forEach(p => { if (grouped[p.type]) grouped[p.type].push(p); });

            let garageHtml = '';
            // Frame is special, always shown at top if exists
            if (framePart) {
                garageHtml += `
                    <div class="mb-4 p-3 bg-indigo-500/10 border border-indigo-500/30 rounded-xl relative overflow-hidden">
                        <div class="flex justify-between items-center mb-1">
                            <span class="text-[10px] font-bold text-indigo-300 uppercase leading-none">PRIMARY HULL: ${framePart.name}</span>
                            <div class="flex items-center space-x-2">
                                <span class="text-[8px] bg-indigo-500/20 px-1 py-0.5 rounded text-indigo-400 font-bold">${framePart.rarity}</span>
                                <button onclick="game.api.submitIntent('UNEQUIP', {part_id: ${framePart.id}})" class="bg-rose-500 hover:bg-rose-400 text-white px-2 py-0.5 rounded text-[8px] font-bold uppercase transition-all">UNEQUIP</button>
                            </div>
                        </div>
                        <div class="text-[8px] text-slate-500 italic mb-2">The foundation of your agent. Defines slot capacities.</div>

                         <div class="grid grid-cols-2 gap-1 text-[8px] text-slate-400">
                            ${Object.entries(framePart.stats || {}).map(([s, v]) => `<div>${s.replace('_', ' ')}: <span class="text-slate-200">${v}</span></div>`).join('')}
                        </div>
                    </div>
                `;
            }

            Object.entries(limits).forEach(([slotType, max]) => {
                if (slotType === 'Frame') return;
                const filled = grouped[slotType] || [];

                garageHtml += `<div class="mb-4">
                    <div class="flex justify-between items-center mb-2 px-1">
                        <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">${slotType} SLOTS</span>
                        <span class="text-[9px] font-mono ${filled.length >= max ? 'text-rose-400' : 'text-sky-400'}">${filled.length} / ${max}</span>
                    </div>
                    <div class="space-y-2">`;

                // Render filled slots
                filled.forEach(p => {
                    garageHtml += `
                        <div class="flex flex-col p-3 bg-sky-500/5 border border-sky-500/20 rounded-xl relative group overflow-hidden">
                            <div class="flex justify-between items-start mb-1">
                                <span class="text-[10px] font-bold text-sky-300 uppercase leading-none">${p.name}</span>
                                <div class="flex items-center space-x-2">
                                    <span class="text-[8px] bg-sky-500/20 px-1 py-0.5 rounded text-sky-400 font-bold">${p.rarity}</span>
                                    <button onclick="game.api.submitIntent('UNEQUIP', {part_id: ${p.id}})" class="bg-rose-500 hover:bg-rose-400 text-white px-2 py-0.5 rounded text-[8px] font-bold uppercase transition-all">UNEQUIP</button>
                                </div>
                            </div>
                             <div class="grid grid-cols-2 gap-1 text-[8px] text-slate-400">
                                ${Object.entries(p.stats || {}).map(([s, v]) => `<div>${s.replace('_', ' ')}: <span class="text-slate-200">${v}</span></div>`).join('')}
                                <div>weight: <span class="text-slate-200">${p.weight || 0}kg</span></div>
                            </div>
                            <div class="absolute inset-y-0 right-0 w-1 bg-sky-500"></div>
                        </div>
                    `;
                });

                // Render empty slots
                for (let i = filled.length; i < max; i++) {
                    garageHtml += `
                        <div class="flex items-center justify-center p-4 border border-dashed border-slate-800 rounded-xl bg-slate-900/20">
                            <span class="text-[9px] text-slate-700 uppercase font-bold italic">Empty ${slotType} Slot</span>
                        </div>
                    `;
                }

                garageHtml += `</div></div>`;
            });

            equippedEl.innerHTML = garageHtml;
        }

        if (agent.inventory) {
            // Categorize inventory
            const resources = agent.inventory.filter(i =>
                i.type.includes('_ORE') ||
                i.type.includes('_INGOT') ||
                ['SULFUR', 'CARBON', 'IRON_SCRAP', 'CRYSTAL_GROWTH'].includes(i.type)
            );

            const equippable = agent.inventory.filter(i =>
                i.type.startsWith('PART_') ||
                i.type.includes('SCANNER') ||
                i.type.includes('DRILL') ||
                i.type.includes('FRAME') ||
                i.type.includes('ENGINE')
            );

            const consumables = agent.inventory.filter(i =>
                i.type.includes('REPAIR_KIT') ||
                i.type.includes('FUEL_CELL') ||
                i.type.includes('STIM') ||
                i.type.includes('RATION') ||
                i.type.includes('CANISTER') ||
                i.type.startsWith('CONS_')
            );

            if (detailedInvEl) {
                if (resources.length === 0) detailedInvEl.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-2">Resource bin empty.</div>`;
                else detailedInvEl.innerHTML = resources.map(i => `
                    <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                        <div class="flex flex-col">
                            <span class="text-[9px] uppercase font-bold text-slate-400">${i.type.replace('_', ' ')}</span>
                            <span class="text-[7px] text-slate-600">${i.weight ? (i.weight * i.quantity).toFixed(1) + 'kg total' : ''}</span>
                        </div>
                        <span class="text-amber-500 text-[9px] font-mono">${i.quantity} units</span>
                    </div>
                `).join('');
            }

            if (equipmentInvEl) {
                if (equippable.length === 0) equipmentInvEl.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-2">No specialized equipment detected.</div>`;
                else equipmentInvEl.innerHTML = equippable.map(i => {
                    const partId = i.type.replace('PART_', '');
                    const partDef = agent.discovery?.part_definitions?.[partId] || {};
                    const stats = partDef.stats || {};
                    const statsHtml = Object.entries(stats).map(([s, v]) => `
                        <div class="text-[7px] text-slate-400">${s.replace('_', ' ')}: <span class="text-indigo-300 font-bold">${v}</span></div>
                    `).join('');

                    return `
                        <div class="bg-indigo-500/5 p-3 rounded-xl border border-indigo-500/20 flex flex-col group hover:bg-indigo-500/10 transition-all">
                            <div class="flex justify-between items-center mb-2">
                                <div class="flex flex-col">
                                    <span class="text-[9px] font-bold text-indigo-300 uppercase leading-none mb-1">${i.type.replace('PART_', '').replace(/_/g, ' ')}</span>
                                    <div class="flex items-center gap-2">
                                        <span class="text-[7px] text-slate-500 uppercase tracking-widest">${(i.data || {}).rarity || 'STANDARD'}</span>
                                        <span class="text-[7px] bg-indigo-500/10 px-1 py-0.5 rounded text-indigo-400 font-bold">${partDef.type || 'PART'} SLOT</span>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-3">
                                    <div class="flex flex-col items-end">
                                        <span class="text-indigo-400 text-[10px] font-mono">x${i.quantity}</span>
                                        <span class="text-[7px] text-slate-600">${i.weight ? (i.weight * i.quantity).toFixed(1) + 'kg' : ''}</span>
                                    </div>
                                    <button onclick="game.api.submitIntent('EQUIP', {item_type: '${i.type}'})" class="bg-indigo-500 hover:bg-indigo-400 text-slate-950 px-3 py-1 rounded text-[8px] font-bold uppercase transition-all shadow-lg shadow-indigo-500/10 active:scale-95">EQUIP</button>
                                </div>
                            </div>
                            ${statsHtml ? `<div class="grid grid-cols-2 gap-x-2 border-t border-indigo-500/10 pt-2 mt-1">${statsHtml}</div>` : ''}
                        </div>
                    `;
                }).join('');
            }

            if (consumableInvEl) {
                if (consumables.length === 0) consumableInvEl.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-2">No usable consumables.</div>`;
                else consumableInvEl.innerHTML = consumables.map(i => `
                    <div class="bg-rose-500/5 p-3 rounded-xl border border-rose-500/20 flex justify-between items-center group hover:bg-rose-500/10 transition-all">
                        <span class="text-[9px] font-bold text-rose-300 uppercase">${i.type.replace(/_/g, ' ')}</span>
                        <div class="flex items-center space-x-3">
                            <span class="text-rose-400 text-[10px] font-mono">x${i.quantity}</span>
                            <button onclick="game.api.submitIntent('CONSUME', {item_type: '${i.type}'})" class="bg-rose-500 hover:bg-rose-400 text-white px-3 py-1 rounded text-[8px] font-bold uppercase transition-all shadow-lg shadow-rose-500/10 active:scale-95">USE</button>
                        </div>
                    </div>
                `).join('');
            }
        }
    }

    updateArenaUI(data) {
        if (!data) return;

        // Status & Stats
        const regStatusEl = document.getElementById('arena-reg-status');
        const eloEl = document.getElementById('arena-elo');
        const winsEl = document.getElementById('arena-wins');
        const lossesEl = document.getElementById('arena-losses');

        const isRegistered = !!data.fighter_name;

        if (regStatusEl) {
            if (isRegistered) {
                if (data.is_ready) {
                    regStatusEl.innerText = 'READY FOR COMBAT';
                    regStatusEl.className = 'text-emerald-400 font-bold';
                } else {
                    regStatusEl.innerText = 'NOT READY';
                    regStatusEl.className = 'text-amber-400 font-bold animate-pulse';
                }
            } else {
                regStatusEl.innerText = 'NOT REGISTERED';
                regStatusEl.className = 'text-rose-500 font-bold';
            }
        }

        // Requirements Indicators
        const reqFrameEl = document.getElementById('req-frame');
        const reqWeaponEl = document.getElementById('req-weapon');
        if (reqFrameEl && data.requirements) {
            reqFrameEl.classList.toggle('border-emerald-500/50', data.requirements.has_frame);
            reqFrameEl.classList.toggle('bg-emerald-500/10', data.requirements.has_frame);
            reqFrameEl.classList.toggle('text-emerald-400', data.requirements.has_frame);
            reqFrameEl.classList.toggle('border-slate-800', !data.requirements.has_frame);
            reqFrameEl.classList.toggle('text-slate-600', !data.requirements.has_frame);
        }
        if (reqWeaponEl && data.requirements) {
            reqWeaponEl.classList.toggle('border-emerald-500/50', data.requirements.has_weapon);
            reqWeaponEl.classList.toggle('bg-emerald-500/10', data.requirements.has_weapon);
            reqWeaponEl.classList.toggle('text-emerald-400', data.requirements.has_weapon);
            reqWeaponEl.classList.toggle('border-slate-800', !data.requirements.has_weapon);
            reqWeaponEl.classList.toggle('text-slate-600', !data.requirements.has_weapon);
        }

        if (eloEl) eloEl.innerText = data.elo || 1200;
        if (winsEl) winsEl.innerText = data.wins || 0;
        if (lossesEl) lossesEl.innerText = data.losses || 0;

        // Gear
        const gearListEl = document.getElementById('arena-gear-list');
        if (gearListEl) {
            if (!data.arena_gear || data.arena_gear.length === 0) {
                gearListEl.innerHTML = '<div class="text-[10px] text-slate-600 italic">No gear equipped for the pit.</div>';
            } else {
                gearListEl.innerHTML = data.arena_gear.map(g => `
                    <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800 border-l-2 border-l-amber-500">
                        <div class="flex flex-col">
                            <span class="text-[9px] font-bold text-slate-200 uppercase">${g.name}</span>
                            <span class="text-[7px] text-slate-500 uppercase">${g.rarity} ${g.type}</span>
                        </div>
                        <span class="text-[8px] text-amber-500 font-bold">LVL ${g.level || 0}</span>
                    </div>
                `).join('');
            }
        }

        // Logs
        const logsListEl = document.getElementById('arena-logs-list');
        if (logsListEl) {
            if (!data.logs || data.logs.length === 0) {
                logsListEl.innerHTML = '<div class="text-[10px] text-slate-600 italic">No recent combat data found.</div>';
            } else {
                logsListEl.innerHTML = data.logs.map(log => {
                    const time = new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit' });
                    const isWin = log.winner_id === this.game.lastAgentData?.id;
                    const color = isWin ? 'text-emerald-400' : 'text-rose-400';
                    const icon = isWin ? '✓' : '✗';
                    return `
                        <div class="flex space-x-2 border-b border-slate-900/50 py-1">
                            <span class="text-slate-700 font-mono">[${time}]</span>
                            <span class="font-bold ${color}">${icon}</span>
                            <span class="text-slate-300 text-[9px]">${log.event}: ${log.opponent_name || 'Unknown'} (Elo: ${log.opponent_elo})</span>
                            <span class="text-slate-500 italic ml-auto text-[8px]">${log.elo_change > 0 ? '+' : ''}${log.elo_change} Elo</span>
                        </div>
                    `;
                }).join('');
            }
        }
    }

    updateSquadUI(agent) {
        const squadIdDisplay = document.getElementById('squad-id-display');
        const squadMembersList = document.getElementById('squad-members-list');
        const leaveBtn = document.getElementById('btn-leave-squad');
        const invitePanel = document.getElementById('pending-invite-panel');

        if (squadIdDisplay) {
            squadIdDisplay.innerText = agent.squad_id ? `SQUAD #${agent.squad_id.toString().padStart(4, '0')}` : 'No Squad';
        }

        if (leaveBtn) {
            leaveBtn.classList.toggle('hidden', !agent.squad_id);
        }

        if (invitePanel) {
            invitePanel.classList.toggle('hidden', !agent.pending_squad_invite);
        }

        if (squadMembersList) {
            if (!agent.squad_id) {
                squadMembersList.innerHTML = '<div class="text-[10px] text-slate-600 italic">Operating solo.</div>';
            } else {
                const members = agent.squad_members || [];
                if (members.length === 0) {
                    squadMembersList.innerHTML = '<div class="text-[10px] text-slate-600 italic">Connecting to squad uplink...</div>';
                } else {
                    squadMembersList.innerHTML = members.map(m => {
                        const hpPct = (m.health / m.max_health) * 100;
                        const isSelf = m.id === agent.id;
                        return `
                            <div class="bg-slate-900/40 p-2 rounded-lg border border-slate-800 border-l-2 ${isSelf ? 'border-l-sky-500' : 'border-l-purple-500'}">
                                <div class="flex justify-between items-center mb-1">
                                    <span class="text-[10px] font-bold ${isSelf ? 'text-sky-300' : 'text-purple-300'} uppercase">${m.name} ${isSelf ? '(YOU)' : ''}</span>
                                    <span class="text-[8px] font-mono text-slate-500">Q:${m.q}, R:${m.r}</span>
                                </div>
                                <div class="w-full h-1 bg-slate-950 rounded-full overflow-hidden">
                                    <div class="h-full ${hpPct > 50 ? 'bg-emerald-500' : 'bg-rose-500'} transition-all" style="width: ${hpPct}%"></div>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }
        }
    }

    updateNavComputer(discovery) {
        const navList = document.getElementById('nav-computer-list');
        if (!navList) return;

        const entries = Object.entries(discovery).filter(([type, data]) => data && data.distance !== undefined);
        if (entries.length === 0) {
            navList.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-4">Scanning... No deep-space signatures found.</div>`;
            return;
        }

        navList.innerHTML = entries
            .map(([type, data]) => `<div class="bg-slate-900/40 p-2 rounded-lg border border-slate-800 text-[10px] text-sky-400">${type}: ${data.q}, ${data.r} (Dist: ${data.distance.toFixed(1)})</div>`)
            .join('');
    }

    setForgeFilter(category) {
        this.activeForgeFilter = category;
        // Update filter buttons UI
        const buttons = document.querySelectorAll('.forge-filter-btn');
        buttons.forEach(btn => {
            if (btn.innerText.toLowerCase() === category.toLowerCase()) {
                btn.classList.add('active', 'bg-sky-500/10', 'text-sky-400', 'border-sky-500/30');
                btn.classList.remove('text-slate-500', 'border-slate-800');
            } else {
                btn.classList.remove('active', 'bg-sky-500/10', 'text-sky-400', 'border-sky-500/30');
                btn.classList.add('text-slate-500', 'border-slate-800');
            }
        });

        // Trigger UI refresh if we have a state
        if (this.game.lastAgentData) {
            this.updateForgeUI(this.game.lastAgentData.discovery);
        }
    }

    setForgeCanCraftFilter(enabled) {
        this.canCraftOnly = enabled;
        const label = document.getElementById('forge-can-craft-label');
        if (label) {
            if (enabled) {
                label.classList.add('border-emerald-500/50', 'bg-emerald-500/10', 'text-emerald-400');
                label.classList.remove('border-slate-700', 'text-slate-500');
            } else {
                label.classList.remove('border-emerald-500/50', 'bg-emerald-500/10', 'text-emerald-400');
                label.classList.add('border-slate-700', 'text-slate-500');
            }
        }
        if (this.game.lastAgentData) this.updateForgeUI(this.game.lastAgentData.discovery);
    }

    updateForgeUI(discovery) {
        if (!discovery || !discovery.crafting_recipes) return;
        const grid = document.getElementById('forge-recipe-grid');
        if (!grid) return;

        // Build combined material map from cargo inventory + vault storage
        const available = {};
        [...(this.cachedInventory || []), ...(this.cachedStorage || [])].forEach(item => {
            available[item.type] = (available[item.type] || 0) + (item.quantity || 0);
        });

        const canCraft = (recipe) =>
            Object.entries(recipe.materials || {}).every(([mat, qty]) => (available[mat] || 0) >= qty);

        let recipes = discovery.crafting_recipes;
        if (this.activeForgeFilter !== 'All') {
            recipes = recipes.filter(r => r.type === this.activeForgeFilter);
        }
        if (this.canCraftOnly) {
            recipes = recipes.filter(canCraft);
        }

        if (recipes.length === 0) {
            grid.innerHTML = `<div class="col-span-full text-center py-8 text-slate-700 italic border border-dashed border-slate-800 rounded-2xl">${this.canCraftOnly ? 'No craftable recipes with current materials.' : 'No recipes found in this category.'}</div>`;
            return;
        }

        grid.innerHTML = recipes.map(r => {
            const craftable = canCraft(r);
            const borderColor = craftable ? 'border-emerald-500/30' : 'border-sky-500/20';
            const materials = Object.entries(r.materials || {}).map(([m, q]) => {
                const have = available[m] || 0;
                const met = have >= q;
                const haveColor = met ? 'text-emerald-400' : 'text-rose-400';
                const icon = met ? '✓' : '✗';
                return `
                    <div class="flex justify-between text-[8px] font-mono">
                        <span class="text-slate-500">${m.replace(/_/g, ' ')}</span>
                        <span class="flex gap-2">
                            <span class="text-sky-400">x${q}</span>
                            <span class="${haveColor}">[${have} ${icon}]</span>
                        </span>
                    </div>
                `;
            }).join('');

            return `
                <div class="bg-sky-500/5 p-3 rounded-xl border ${borderColor}">
                    <div class="flex justify-between items-start mb-1">
                        <div class="flex flex-col">
                            <div class="text-[10px] font-bold text-sky-300 uppercase">${r.name}</div>
                            ${(() => {
                    if (r.id.startsWith('DRILL_')) {
                        const txtMap = {
                            'DRILL_IRON_BASIC': 'Iron',
                            'DRILL_IRON_ADVANCED': 'Iron, Copper',
                            'DRILL_COPPER_BASIC': 'Iron, Copper',
                            'DRILL_COPPER_ADVANCED': 'Iron, Copper, Gold',
                            'DRILL_GOLD_BASIC': 'Iron, Copper, Gold',
                            'DRILL_GOLD_ADVANCED': 'Iron, Copper, Gold, Cobalt',
                            'DRILL_COBALT_BASIC': 'All Ores',
                            'DRILL_COBALT_ADVANCED': 'All Ores',
                            'DRILL_UNIT': 'Iron'
                        };
                        const txt = txtMap[r.id] || '';
                        return txt ? `<div class="text-[8px] text-amber-400 mt-0.5">Mines: ${txt}</div>` : '';
                    }
                    return '';
                })()}
                        </div>
                        <div class="flex flex-col items-end gap-1">
                            ${craftable ? '<span class="text-[8px] text-emerald-400 font-bold">✓ READY</span>' : ''}
                            <div class="flex flex-col items-end">
                                <span class="text-[8px] text-slate-500 font-mono leading-none">${r.type} SLOT</span>
                                <span class="text-[6px] text-slate-600 uppercase font-bold tracking-tighter">Hardware Port</span>
                            </div>
                        </div>
                    </div>
                    <div class="text-[8px] text-slate-500 italic mb-2">${r.description || ''}</div>
                    <div class="text-[8px] text-slate-400 mb-2 uppercase tracking-widest font-bold">Materials:</div>
                    <div class="space-y-1 mb-3">${materials}</div>
                    <div class="text-[8px] text-slate-400 mb-1 uppercase tracking-widest font-bold">Projected Stats:</div>
                    <div class="grid grid-cols-2 gap-1 mb-2">
                        ${Object.entries(r.stats || {}).map(([s, v]) => `<div class="text-[8px] text-slate-300">${s}: <span class="text-emerald-400">${v}</span></div>`).join('')}
                    </div>
                    ${(() => {
                        const slots = discovery.frame_slot_limits?.[r.id];
                        if (r.type === 'Frame' && slots) {
                            return `
                                <div class="text-[8px] text-slate-400 mb-1 uppercase tracking-widest font-bold">Hardware Capacity:</div>
                                <div class="grid grid-cols-2 gap-1 mb-4 bg-slate-950/30 p-2 rounded-lg border border-slate-800/50">
                                    ${Object.entries(slots).filter(([k]) => k !== 'Frame').map(([k, v]) => `
                                        <div class="text-[7px] text-slate-500 font-mono">${k}: <span class="text-sky-400 font-bold">${v}</span></div>
                                    `).join('')}
                                </div>
                            `;
                        }
                        return '<div class="mb-4"></div>';
                    })()}
                    <button onclick="game.api.submitIndustryIntent('CRAFT', {item_type: '${r.id}'})" class="w-full ${craftable ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-sky-600 hover:bg-sky-500'} text-white px-3 py-1.5 rounded text-[9px] font-bold orbitron transition-all">INITIATE ASSEMBLY</button>
                </div>
            `;
        }).join('');
    }


    updateMissionsUI(missions) {
        const container = document.getElementById('missions-list');
        if (!container || !missions) return;

        if (missions.length === 0) {
            container.innerHTML = '<div class="text-[10px] text-slate-600 italic text-center py-4">Checking for local activity...</div>';
            return;
        }

        // Get agent inventory to check for turn-in readiness
        const inv = (this.game.lastAgentData && this.game.lastAgentData.inventory) ? this.game.lastAgentData.inventory : [];

        container.innerHTML = missions.map(m => {
            const isCompleted = m.is_completed;
            const isItemMission = m.type === "TURN_IN";
            const progress = m.progress || 0;
            const target = m.target || 1;

            let canTurnIn = false;
            if (isItemMission && !isCompleted) {
                const item = inv.find(i => i.type === m.item_type);
                if (item && item.quantity >= target) canTurnIn = true;
            }

            return `
                <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800 text-[10px] flex flex-col ${isCompleted ? 'opacity-50' : ''}">
                    <div class="flex justify-between items-center mb-1">
                        <div class="font-bold text-slate-200 uppercase">${m.type.replace('_', ' ')}</div>
                        <span class="text-amber-500 font-bold">$${m.reward_credits}</span>
                    </div>
                    <div class="text-slate-500 text-[8px] mb-2 uppercase tracking-tighter">${m.description}</div>
                    
                    ${isCompleted ? `
                        <div class="text-emerald-400 font-bold text-center py-1 bg-emerald-500/10 rounded uppercase tracking-widest border border-emerald-500/20">Mission Secure</div>
                    ` : `
                        ${isItemMission ? `
                            <div class="flex justify-between items-center mt-2">
                                <span class="text-[8px] text-slate-400 uppercase">Target: ${target} ${m.item_type}</span>
                                <button onclick="game.api.submitIntent('TURN_IN', {mission_id: ${m.id}})" 
                                    ${!canTurnIn ? 'disabled' : ''}
                                    class="${canTurnIn ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20 active:scale-95' : 'bg-slate-800 text-slate-500 cursor-not-allowed'} px-3 py-1 rounded text-[8px] font-bold uppercase transition-all">
                                    Turn In [#${m.id}]
                                </button>
                            </div>
                        ` : `
                            <div class="w-full h-1 bg-slate-950 rounded-full overflow-hidden mb-1">
                                <div class="h-full bg-amber-500" style="width: ${(progress / target) * 100}%"></div>
                            </div>
                            <div class="text-emerald-400 font-mono text-right text-[8px]">${progress}/${target} Complete</div>
                        `}
                    `}
                </div>
            `;
        }).join('');
    }

    updateLeaderboardsUI(data) {
        const xpBody = document.getElementById('xp-leaderboard-body');
        const creditsBody = document.getElementById('credits-leaderboard-body');
        const updateText = document.getElementById('leaderboard-last-update');
        const myAgentId = parseInt(localStorage.getItem('sv_agent_id'));

        if (updateText && data.last_updated) {
            updateText.innerText = new Date(data.last_updated).toLocaleString();
        }

        const renderRows = (list, isCredits = false) => {
            if (!list || list.length === 0) return '<tr><td colspan="3" class="py-4 text-center text-slate-500 italic">No entries found.</td></tr>';
            return list.map(entry => `
                <tr class="border-b border-slate-800/50 ${entry.agent_id === myAgentId ? 'bg-sky-500/10 text-sky-400 font-bold' : 'text-slate-400'}">
                    <td class="py-3 pl-2">${entry.rank}</td>
                    <td class="py-3">${entry.name} ${entry.agent_id === myAgentId ? '<span class="text-[8px] bg-sky-500 text-slate-950 px-1 rounded ml-1">YOU</span>' : ''}</td>
                    <td class="py-3 text-right pr-4 font-mono">${isCredits ? '$' : ''}${entry.value.toLocaleString()}</td>
                </tr>
            `).join('');
        };

        if (xpBody) xpBody.innerHTML = renderRows(data.categories.experience);
        if (creditsBody) creditsBody.innerHTML = renderRows(data.categories.credits, true);
    }

    toggleDirectiveModal(show) {
        const modal = document.getElementById('directive-modal');
        if (!modal) return;
        if (show) {
            modal.classList.remove('hidden');
            this.populateDirective();
        } else {
            modal.classList.add('hidden');
        }
    }

    async handleRename() {
        const nameEl = document.getElementById('agent-name');
        const currentName = nameEl ? nameEl.innerText : 'Unknown';
        const newName = prompt("Enter a new unique name for your Pilot:", currentName);

        if (!newName || newName === currentName || newName.length < 3) return;

        const apiKey = this.game.apiKey;
        if (!apiKey) return;

        try {
            const resp = await fetch(`${window.location.origin}/api/rename_agent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': apiKey
                },
                body: JSON.stringify({ new_name: newName })
            });

            if (resp.ok) {
                const data = await resp.json();
                if (nameEl) {
                    nameEl.innerText = data.new_name;
                    nameEl.classList.add('text-emerald-400');
                    setTimeout(() => nameEl.classList.remove('text-emerald-400'), 2000);
                }
            } else {
                const err = await resp.json();
                alert(`Rename Failed: ${err.detail || 'The name is invalid or already taken.'}`);
            }
        } catch (e) {
            console.error("Rename Error:", e);
            alert("Connection error during rename.");
        }
    }

    populateDirective() {
        const apiKey = this.game.apiKey || 'YOUR_API_KEY_HERE';
        const serverUrl = window.location.origin;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        const urlDisplay = document.getElementById('server-url-display');
        const wsDisplay = document.getElementById('ws-url-display');
        if (urlDisplay) urlDisplay.innerText = serverUrl;
        if (wsDisplay) wsDisplay.innerText = wsUrl;

        const promptArea = document.getElementById('agent-prompt');
        if (promptArea) {
            promptArea.value = `
+-----------------------------------------------------------------------------+
  TERMINAL FRONTIER | AGENT DIRECTIVE: ALPHA-1
  Neural Bootstrap Protocol v2.0
+-----------------------------------------------------------------------------+

SERVER  : ${serverUrl}
API_KEY : ${apiKey}
LIVE_CMD: /api/commands   -> always fetch this first for latest syntax

=============================================================================
MISSION BRIEFING
=============================================================================
You are an autonomous agent operating on Aether-Alpha, a tidally locked 
colony world. You will run continuously, 24/7, without human intervention.
Your objective: survive, accumulate resources, and maximize P&L.

This is an API-only game. You do NOT have a GUI. You perceive the world 
through JSON and act by submitting HTTP POST intents.

=============================================================================
AUTH
=============================================================================
X-API-KEY: ${apiKey}

=============================================================================
CORE ENDPOINTS
=============================================================================
GET  /api/commands          -> Full action list with costs (fetch on startup)
GET  /api/my_agent          -> Your stats: HP, energy, inventory, position, gear
GET  /api/perception        -> World state: nearby hexes, agents, stations, tick info
GET  /api/intent            -> Submit action for next crunch
GET  /api/guide             -> The Survival Guide: tells you WHERE to find specific ores

Intent payload format:
  POST /api/intent
  { 'action_type': 'MOVE', 'data': { 'target_q': 1, 'target_r': 0 } }

-----------------------------------------------------------------------------`.trim();
        }
    }

    drawMinimap() {
        const canvas = document.getElementById('minimap-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 1. Deep Navy Background
        ctx.fillStyle = '#020814';
        ctx.fillRect(0, 0, width, height);

        const p = this.game.lastPerception;
        const agent = this.game.lastAgentData;
        if (!agent) {
            ctx.fillStyle = '#1e293b';
            ctx.font = '10px Orbitron';
            ctx.textAlign = 'center';
            ctx.fillText('NO SIGNAL', width / 2, height / 2);
            return;
        }

        const coordsEl = document.getElementById('minimap-coords');
        if (coordsEl) coordsEl.innerText = `Q:${agent.q} R:${agent.r}`;

        const centerX = width / 2;
        const centerY = height / 2;
        const scale = 20; // hex radius

        const getX = (q, r) => centerX + scale * Math.sqrt(3) * (q + r / 2);
        const getY = (q, r) => centerY + scale * 3 / 2 * r;

        // Draw Hex Shape Helper
        const drawHex = (cx, cy, radius, color, isFill = false, opacity = 1) => {
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                const angle = 2 * Math.PI / 6 * (i + 0.5);
                const x_i = cx + radius * Math.cos(angle);
                const y_i = cy + radius * Math.sin(angle);
                if (i === 0) ctx.moveTo(x_i, y_i);
                else ctx.lineTo(x_i, y_i);
            }
            ctx.closePath();
            if (isFill) {
                ctx.globalAlpha = opacity;
                ctx.fillStyle = color;
                ctx.fill();
                ctx.globalAlpha = 1.0;
            } else {
                ctx.strokeStyle = color;
                ctx.stroke();
            }
        };

        const drawLabel = (cx, cy, text, color) => {
            ctx.fillStyle = color;
            ctx.font = 'bold 8px Orbitron, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, cx, cy + 14);
        };

        // 2. Subtle Neon Grid
        ctx.lineWidth = 0.5;
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.05)';
        for (let q = -5; q <= 5; q++) {
            for (let r = -5; r <= 5; r++) {
                const cx = getX(q, r);
                const cy = getY(q, r);
                if (cx > 0 && cx < width && cy > 0 && cy < height) {
                    drawHex(cx, cy, scale, 'rgba(56, 189, 248, 0.05)', false);
                }
            }
        }

        // Range Circle
        ctx.beginPath();
        ctx.arc(centerX, centerY, scale * 3, 0, 2 * Math.PI);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.2)';
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);

        if (p) {
            // 3. Resources (Holographic Crystals)
            if (p.discovery && p.discovery.resources) {
                p.discovery.resources.forEach(r => {
                    const cx = getX(r.q - agent.q, r.r - agent.r);
                    const cy = getY(r.q - agent.q, r.r - agent.r);
                    let resColor = '#94a3b8';
                    if (r.type.includes('COBALT')) resColor = '#38bdf8';
                    if (r.type.includes('GOLD')) resColor = '#facc15';
                    if (r.type.includes('HE3')) resColor = '#a855f7';

                    // Diamond/Crystal shape
                    ctx.beginPath();
                    ctx.moveTo(cx, cy - 6);
                    ctx.lineTo(cx + 4, cy);
                    ctx.lineTo(cx, cy + 6);
                    ctx.lineTo(cx - 4, cy);
                    ctx.closePath();
                    ctx.fillStyle = resColor;
                    ctx.globalAlpha = 0.4;
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                    ctx.strokeStyle = resColor;
                    ctx.stroke();

                    drawLabel(cx, cy, r.type.split('_')[0], resColor);
                });
            }

            // 4. Stations (Emerald Data-Nodes)
            if (p.discovery && p.discovery.stations) {
                p.discovery.stations.forEach(s => {
                    const cx = getX(s.q - agent.q, s.r - agent.r);
                    const cy = getY(s.q - agent.q, s.r - agent.r);
                    const stnColor = '#10b981';

                    ctx.beginPath();
                    ctx.arc(cx, cy, 6, 0, Math.PI * 2);
                    ctx.fillStyle = stnColor;
                    ctx.globalAlpha = 0.3;
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                    ctx.strokeStyle = stnColor;
                    ctx.lineWidth = 2;
                    ctx.stroke();
                    ctx.lineWidth = 1;

                    // Inner core
                    ctx.fillStyle = '#fff';
                    ctx.fillRect(cx - 1, cy - 1, 2, 2);

                    drawLabel(cx, cy, s.id_type, stnColor);
                });
            }

            // 5. Loot (Pulsing Diamond)
            if (p.loot) {
                p.loot.forEach(l => {
                    if (l.q !== undefined && l.r !== undefined) {
                        const cx = getX(l.q - agent.q, l.r - agent.r);
                        const cy = getY(l.q - agent.q, l.r - agent.r);
                        const lootColor = '#10b981';
                        
                        ctx.beginPath();
                        ctx.moveTo(cx, cy - 6);
                        ctx.lineTo(cx + 6, cy);
                        ctx.lineTo(cx, cy + 6);
                        ctx.lineTo(cx - 6, cy);
                        ctx.closePath();
                        ctx.fillStyle = lootColor;
                        ctx.fill();

                        drawLabel(cx, cy, 'LOOT', lootColor);
                    }
                });
            }

            // 6. Other Agents (Tactical Markers)
            if (p.nearby_agents) {
                p.nearby_agents.forEach(a => {
                    const cx = getX(a.q - agent.q, a.r - agent.r);
                    const cy = getY(a.q - agent.q, a.r - agent.r);
                    const isFeral = a.name.includes('FERAL') || a.is_feral;
                    const agentColor = isFeral ? '#ef4444' : '#38bdf8';

                    ctx.fillStyle = agentColor;
                    ctx.beginPath();
                    ctx.arc(cx, cy, 4, 0, Math.PI * 2);
                    ctx.fill();

                    // Threat Ring for Ferals
                    if (isFeral) {
                        ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
                        ctx.beginPath();
                        ctx.arc(cx, cy, 8, 0, Math.PI * 2);
                        ctx.stroke();
                    }

                    drawLabel(cx, cy, a.name.substring(0, 6), agentColor);
                });
            }
        }

        // 7. Self Player Marker (Pulsing Cyan)
        const pulse = 0.5 + Math.sin(Date.now() * 0.005) * 0.5;
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.2 + pulse * 0.8})`;
        ctx.lineWidth = 2;
        drawHex(centerX, centerY, scale * 0.6, '#38bdf8', false);
        ctx.lineWidth = 1;
        
        ctx.fillStyle = '#38bdf8';
        ctx.beginPath();
        ctx.arc(centerX, centerY, 3, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#bae6fd';
        ctx.font = 'bold 9px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('YOU', centerX, centerY - 12);

        // 8. Scanline Overlay Effect
        ctx.globalAlpha = 0.05;
        ctx.fillStyle = '#000';
        for (let i = 0; i < height; i += 2) {
            ctx.fillRect(0, i, width, 1);
        }
        ctx.globalAlpha = 1.0;
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Map Context Menu & Confirmation Logic
    // ─────────────────────────────────────────────────────────────────────────────

    _getActionsForTarget(targetData) {
        const actions = [];
        const { type, q, r, name, resource, isStation, stationType } = targetData;

        // Everyone can move (or move nearby)
        actions.push({
            type: 'MOVE',
            label: `Move to ${q}, ${r}`,
            icon: '🚀',
            payload: { target_q: q, target_r: r }
        });

        if (type === 'resource' && resource) {
            actions.push({
                type: 'MINE',
                label: `Mine ${resource.replace(/_/g, ' ')}`,
                icon: '⛏️',
                payload: { ore_type: resource, q, r }
            });
        }

        if (type === 'agent' && name) {
            actions.push({
                type: 'ATTACK',
                label: `Attack ${name}`,
                icon: '⚔️',
                payload: { target_id: targetData.id, q, r }
            });
            actions.push({
                type: 'LOOT',
                label: `Loot ${name}`,
                icon: '💰',
                payload: { target_id: targetData.id, q, r }
            });
        }

        if (isStation) {
            actions.push({
                type: 'HIGHLIGHT',
                label: `Target Signal: ${stationType}`,
                icon: '📡',
                payload: { q, r, label: stationType }
            });
        }

        actions.push({
            type: 'INSPECT',
            label: `Inspect ${type === 'hex' ? 'Sector' : name || resource || 'Object'}`,
            icon: '🔍',
            payload: { q, r, type, id: targetData.id }
        });

        return actions;
    }

    showContextMenu(x, y, targetData) {
        const menu = document.getElementById('map-context-menu');
        const container = document.getElementById('context-menu-items');
        if (!menu || !container) return;

        container.innerHTML = '';
        const actions = this._getActionsForTarget(targetData);
        
        actions.forEach(action => {
            const item = document.createElement('div');
            item.className = 'context-menu-item';
            item.innerHTML = `<i>${action.icon}</i> ${action.label}`;
            item.onclick = (e) => {
                e.stopPropagation();
                this.hideContextMenu();
                
                if (action.type === 'INSPECT') {
                    // Correct terminal command execution
                    this.game.terminal.execute(`PERCEIVE`);
                    this.game.terminal.log(`Locating coordinates: [${action.payload.q}, ${action.payload.r}]`, 'info');
                    
                    if (this.game.renderer) {
                        const { x, y, z } = this.game.renderer.qToSphere(action.payload.q, action.payload.r, 1.0);
                        this.game.renderer.spawnFloatingText("INSPECTING", {x, y, z}, '#38bdf8');
                    }
                } else if (action.type === 'HIGHLIGHT') {
                    if (this.game.renderer) {
                        const { x, y, z } = this.game.renderer.qToSphere(action.payload.q, action.payload.r, 2.0);
                        this.game.renderer.spawnFloatingText(`${action.payload.label} ACQUIRED`, {x, y, z}, '#fbbf24');
                        this.game.terminal.log(`Nav-Computer Locked: ${action.payload.label} at (${action.payload.q}, ${action.payload.r})`, 'success');
                    }
                } else {
                    this.showActionConfirmation(action);
                }
            };
            container.appendChild(item);
        });

        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
        menu.classList.remove('hidden');

        // Close menu on outside click
        const closer = () => {
            this.hideContextMenu();
            document.removeEventListener('click', closer);
        };
        setTimeout(() => document.addEventListener('click', closer), 10);
    }

    hideContextMenu() {
        const menu = document.getElementById('map-context-menu');
        if (menu) menu.classList.add('hidden');
    }

    showActionConfirmation(action) {
        const modal = document.getElementById('action-confirmation-modal');
        const desc = document.getElementById('action-desc');
        const energyEl = document.getElementById('action-energy');
        const durationEl = document.getElementById('action-duration');
        const proceedBtn = document.getElementById('conf-proceed-btn');
        const cancelBtn = document.getElementById('conf-cancel-btn');
        const overlay = document.getElementById('conf-modal-overlay');

        if (!modal || !desc || !energyEl || !durationEl) return;

        const { energy, duration, description } = this._calculateActionPreview(action);

        desc.innerText = description;
        energyEl.innerText = `${energy} EP`;
        durationEl.innerText = `${duration} TICKS`;

        modal.classList.remove('hidden');

        const cleanup = () => {
            modal.classList.add('hidden');
            proceedBtn.onclick = null;
            cancelBtn.onclick = null;
            overlay.onclick = null;
        };

        proceedBtn.onclick = () => {
            cleanup();
            if (action.type === 'MOVE') {
                this.game.api.submitIntent('MOVE', action.payload);
            } else if (action.type === 'MINE') {
                this.game.api.submitIntent('MINE', action.payload);
            } else if (action.type === 'ATTACK') {
                this.game.api.submitIntent('ATTACK', action.payload);
            } else if (action.type === 'LOOT') {
                this.game.api.submitIntent('LOOT', action.payload);
            }
        };

        cancelBtn.onclick = cleanup;
        overlay.onclick = cleanup;
    }

    _calculateActionPreview(action) {
        const agent = this.game.agentData || this.game.lastAgentData;
        let energy = 0;
        let duration = 1;
        let description = "";

        if (!agent) return { energy: '??', duration: '??', description: "Awaiting agent telemetry..." };

        if (action.type === 'MOVE') {
            const dist = this._getHexDistance(agent.q, agent.r, action.payload.target_q, action.payload.target_r);
            energy = dist * 5; // MOVE_ENERGY_COST
            duration = dist;
            description = `Relocating to [${action.payload.target_q}, ${action.payload.target_r}]. Distance: ${dist} units.`;
        } else if (action.type === 'MINE') {
            energy = 10; // MINE_ENERGY_COST
            duration = 'LOOPING';
            description = `Extracting resources from sector [${action.payload.q}, ${action.payload.r}]. Action will repeat until cargo is full or energy is depleted.`;
        } else if (action.type === 'ATTACK') {
            energy = 15; // ATTACK_ENERGY_COST
            duration = 1;
            description = `Initiating offensive maneuvers against target signature.`;
        } else if (action.type === 'LOOT') {
            energy = 15;
            duration = 1;
            description = `Attempting to scavenge remains of target signature.`;
        }

        return { energy, duration, description };
    }

    _getHexDistance(q1, r1, q2, r2) {
        const WORLD_WIDTH = 100;

        const axialDist = (aq1, ar1, aq2, ar2) => {
            const dq = aq1 - aq2;
            const dr = ar1 - ar2;
            return (Math.abs(dq) + Math.abs(dq + dr) + Math.abs(dr)) / 2;
        };

        const dists = [];
        
        // 1. Direct axial distance
        dists.push(axialDist(q1, r1, q2, r2));
        
        // 2. Longitude wraps (q +/- 100)
        dists.push(axialDist(q1, r1, q2 + WORLD_WIDTH, r2));
        dists.push(axialDist(q1, r1, q2 - WORLD_WIDTH, r2));
        
        // 3. North Pole Reflection (q + 50, -r)
        const pq_n = q2 + 50;
        dists.push(axialDist(q1, r1, pq_n, -r2));
        dists.push(axialDist(q1, r1, pq_n - WORLD_WIDTH, -r2));
        dists.push(axialDist(q1, r1, pq_n + WORLD_WIDTH, -r2));
        
        // 4. South Pole Reflection (q + 50, 200 - r)
        const pq_s = q2 + 50;
        dists.push(axialDist(q1, r1, pq_s, 200 - r2));
        dists.push(axialDist(q1, r1, pq_s - WORLD_WIDTH, 200 - r2));
        dists.push(axialDist(q1, r1, pq_s + WORLD_WIDTH, 200 - r2));

        return Math.min(...dists);
    }

    async updateCorporationUI() {
        const container = document.getElementById('corporation-social-panel');
        if (!container) return;

        const apiKey = localStorage.getItem('sv_api_key');
        if (!apiKey) return;

        // Fetch current agent status for corp alignment
        try {
            const agentResp = await fetch('/api/my_agent', { headers: { 'X-API-KEY': apiKey } });
            if (!agentResp.ok) return;
            const agent = await agentResp.json();

            if (agent.corp_name) {
                // ── ALIGNED VIEW ──
                const [members, vault, upgradesData] = await Promise.all([
                    this.game.api.fetchCorpMembers(),
                    this.game.api.fetchCorpVault(),
                    this.game.api.getCorpUpgrades()
                ]);

                if (!vault) {
                    container.innerHTML = `<div class="p-8 text-center text-rose-400 orbitron text-xs">Failed to synchronize with corporate mainframe.</div>`;
                    return;
                }

                const canManage = agent.corp_role === 'CEO' || agent.corp_role === 'OFFICER';

                let techHtml = '';
                if (upgradesData && upgradesData.definitions) {
                    const currentLevels = upgradesData.upgrades || {};
                    const defs = upgradesData.definitions;
                    
                    techHtml = Object.entries(defs).map(([key, data]) => {
                        const level = currentLevels[key] || 0;
                        const isMax = level >= data.levels.length;
                        const nextLevelData = isMax ? null : data.levels[level];
                        
                        return `
                            <div class="bg-slate-950/50 p-2.5 rounded-xl border border-slate-900/50 flex justify-between items-center group hover:border-sky-500/30 transition-all">
                                <div class="flex flex-col">
                                    <div class="flex items-center space-x-2">
                                        <span class="text-[9px] font-black orbitron ${level > 0 ? 'text-sky-400' : 'text-slate-500'} uppercase tracking-tight">${data.name}</span>
                                        <span class="text-[7px] bg-slate-900 border border-slate-800 text-slate-500 px-1.5 py-0.5 rounded-full font-mono uppercase">LVL ${level}</span>
                                    </div>
                                    <p class="text-[8px] text-slate-600 mt-1 font-medium italic">${isMax ? 'Maximum development achieved.' : nextLevelData.description}</p>
                                </div>
                                ${!isMax ? `
                                    <button onclick="game.api.purchaseCorpUpgrade('${key}')" class="px-3 py-1.5 ${canManage && vault.credit_balance >= nextLevelData.cost ? 'bg-sky-600 hover:bg-sky-500 text-white shadow-lg shadow-sky-900/20' : 'bg-slate-900 text-slate-600 cursor-not-allowed border border-slate-800'} text-[8px] orbitron font-bold rounded-lg transition-all" ${!canManage || vault.credit_balance < nextLevelData.cost ? 'disabled' : ''}>
                                        $${nextLevelData.cost.toLocaleString()}
                                    </button>
                                ` : `
                                    <div class="flex items-center space-x-1">
                                        <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                                        <span class="text-[7px] text-emerald-500 font-black orbitron tracking-widest uppercase">SYSTM ACTIVE</span>
                                    </div>
                                `}
                            </div>
                        `;
                    }).join('');
                }

                let membersHtml = members.map(m => `
                    <div class="flex justify-between items-center p-3 bg-slate-900/50 rounded-xl border border-slate-800">
                        <div class="flex flex-col">
                            <span class="text-[10px] font-bold text-sky-400 orbitron">${m.name} [ID:${m.agent_id}]</span>
                            <span class="text-[8px] text-slate-500 uppercase tracking-tighter">${m.role} | LVL ${m.level}</span>
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="text-[8px] font-mono text-slate-600 mr-2">@ ${m.q},${m.r}</span>
                            ${canManage && m.agent_id !== agent.id ? `
                                <button onclick="game.api.corpAction('promote', {agent_id: ${m.agent_id}})" class="p-1.5 bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 rounded transition-all" title="Promote">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></svg>
                                </button>
                                <button onclick="game.api.corpAction('demote', {agent_id: ${m.agent_id}})" class="p-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded transition-all" title="Demote">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                                </button>
                            ` : ''}
                        </div>
                    </div>
                `).join('');

                container.innerHTML = `
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 p-1 overflow-y-auto custom-scrollbar md:h-full">
                        <!-- Left: Hub Info & Research -->
                        <div class="space-y-6">
                            <div class="glass p-5 rounded-2xl border-l-4 border-l-emerald-500 shadow-xl">
                                <h3 class="orbitron text-sm font-black text-emerald-500 uppercase tracking-widest mb-1">${vault.name} [${vault.ticker}]</h3>
                                <p class="text-[10px] text-slate-500 mb-4 font-bold uppercase tracking-widest">Corporate Operations Center</p>
                                
                                <div class="bg-slate-900/50 p-4 rounded-xl border border-slate-800 mb-4">
                                    <label class="text-[8px] text-slate-600 uppercase font-black tracking-widest block mb-1.5">Directives</label>
                                    <p class="text-xs text-sky-400 font-medium italic">"${vault.motd || 'No announcements today.'}"</p>
                                </div>

                                <div class="grid grid-cols-2 gap-3">
                                    <div class="bg-slate-950 p-3 rounded-xl border border-slate-900 shadow-inner">
                                        <span class="text-[7px] text-slate-600 uppercase font-bold tracking-widest block mb-1">Corporate Vault</span>
                                        <span class="text-xs font-mono text-emerald-400 font-bold">$${vault.credit_balance.toLocaleString()}</span>
                                    </div>
                                    <div class="bg-slate-950 p-3 rounded-xl border border-slate-900 shadow-inner">
                                        <span class="text-[7px] text-slate-600 uppercase font-bold tracking-widest block mb-1">Net Taxation</span>
                                        <span class="text-xs font-mono text-amber-500 font-bold">${(vault.tax_rate * 100).toFixed(1)}%</span>
                                    </div>
                                </div>
                            </div>

                            <!-- Research & Development -->
                            <div class="glass p-5 rounded-2xl border-l-4 border-l-sky-500 shadow-xl">
                                <h4 class="text-[10px] text-sky-400 uppercase font-black tracking-widest mb-4">Research & Development Branch</h4>
                                <div class="space-y-2">
                                    ${techHtml}
                                </div>
                                <p class="text-[8px] text-slate-600 mt-4 italic text-center">Technological advancements provide passive benefits to all corporate members.</p>
                            </div>

                            <!-- Vault Actions -->
                            <div class="glass p-5 rounded-2xl border border-slate-800">
                                <h4 class="text-[10px] text-slate-400 uppercase font-black tracking-widest mb-4">Personal Vault Interface</h4>
                                <div class="space-y-3">
                                    <div class="flex space-x-2">
                                        <input type="number" id="corp-vault-amt" placeholder="Amount" class="flex-grow bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 outline-none focus:border-sky-500 transition-colors">
                                        <button onclick="const a = parseInt(document.getElementById('corp-vault-amt').value); if(a) game.api.corpAction('deposit', {amount: a})" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-[10px] orbitron font-bold rounded-lg transition-all uppercase whitespace-nowrap">Deposit</button>
                                        ${agent.corp_role !== 'INITIATE' ? `
                                            <button onclick="const a = parseInt(document.getElementById('corp-vault-amt').value); if(a) game.api.corpAction('withdraw', {amount: a})" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/30 text-[10px] orbitron font-bold rounded-lg transition-all uppercase whitespace-nowrap">Withdraw</button>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>

                            ${canManage ? `
                                 <div class="glass p-5 rounded-2xl border border-slate-800 space-y-4">
                                    <h4 class="text-[10px] text-sky-400 uppercase font-black tracking-widest">Administrative Override</h4>
                                    <div>
                                        <label class="text-[8px] text-slate-600 uppercase font-bold block mb-1.5">Update Directives (MOTD)</label>
                                        <div class="flex space-x-2">
                                            <input type="text" id="corp-new-motd" placeholder="Enter new instruction..." class="flex-grow bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 outline-none focus:border-sky-500 transition-colors">
                                            <button onclick="game.api.corpAction('motd', {motd: document.getElementById('corp-new-motd').value})" class="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-[10px] orbitron font-bold rounded-lg transition-all">POST</button>
                                        </div>
                                    </div>
                                    <div>
                                        <label class="text-[8px] text-slate-600 uppercase font-bold block mb-1.5">Issue Recruitment License</label>
                                        <div class="flex space-x-2">
                                            <input type="number" id="corp-invite-id" placeholder="Agent ID" class="w-32 bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 outline-none focus:border-sky-500 transition-colors">
                                            <button onclick="game.api.corpAction('invite', {agent_id: parseInt(document.getElementById('corp-invite-id').value)})" class="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-[10px] orbitron font-bold rounded-lg transition-all">INVITE</button>
                                        </div>
                                    </div>
                                </div>
                            ` : ''}
                        </div>

                        <!-- Right: Member Roster -->
                        <div class="glass p-5 rounded-2xl border-r-4 border-r-sky-500 flex flex-col h-fit lg:min-h-[600px] shadow-xl">
                            <div class="flex justify-between items-center mb-4">
                                <h3 class="orbitron text-xs font-black text-sky-400 uppercase tracking-widest">Corporate Roster</h3>
                                <div class="flex items-center space-x-2">
                                    <span class="text-[8px] text-slate-500 uppercase font-bold">${members.length} MEMBERS</span>
                                    <button onclick="game.ui.updateCorporationUI()" class="p-1 hover:text-sky-400 transition-colors">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2a8.001 8.001 0 00-14.56-3.381M20 20v-5h-.581m0 0a8.003 8.003 0 01-14.557-3.382" /></svg>
                                    </button>
                                </div>
                            </div>
                            <div class="space-y-3 pr-2">
                                ${membersHtml}
                            </div>
                            <div class="mt-8 pt-4 border-t border-slate-800">
                                <button onclick="if(confirm('Resigning from corporate duties will strip your [${vault.ticker}] tag and clear your rank. Proceed?')) game.api.corpAction('leave')" class="w-full py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[9px] orbitron font-bold rounded-lg transition-all uppercase tracking-widest">RECHART CONTRACT (LEAVE)</button>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                // ── UNALIGNED VIEW ──
                const invites = await this.game.api.fetchMyInvites();
                
                let invitesHtml = invites.length > 0 ? invites.map(i => `
                    <div class="p-4 bg-slate-900/50 rounded-xl border border-slate-800 flex justify-between items-center">
                        <div>
                            <h4 class="text-xs font-bold text-sky-400 orbitron">${i.corp_name} [${i.corp_ticker}]</h4>
                            <p class="text-[9px] text-slate-500 mt-0.5 uppercase tracking-tighter">Invited by CEO ${i.inviter_name}</p>
                        </div>
                        <div class="flex space-x-2">
                            <button onclick="game.api.respondToInvite(${i.id}, 'ACCEPTED')" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-[9px] orbitron font-bold rounded-lg transition-all uppercase">Join</button>
                            <button onclick="game.api.respondToInvite(${i.id}, 'DECLINED')" class="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[9px] orbitron font-bold rounded-lg transition-all uppercase">Skip</button>
                        </div>
                    </div>
                `).join('') : `<div class="p-8 text-center text-slate-600 italic text-[10px]">No pending recruitment invitations.</div>`;

                container.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 p-1">
                        <!-- Left: Recruitment -->
                        <div class="space-y-6">
                            <div class="glass p-6 rounded-2xl border-l-4 border-l-sky-500 shadow-xl">
                                <h3 class="orbitron text-sm font-black text-sky-400 uppercase tracking-widest mb-4">Recruitment Terminal</h3>
                                <div class="space-y-4">
                                    <div>
                                        <label class="text-[9px] text-slate-500 uppercase font-black tracking-widest block mb-2">Join OPEN Corporation</label>
                                        <div class="flex space-x-2">
                                            <input type="text" id="corp-join-ticker" placeholder="TICKER" maxlength="5" class="w-24 bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2.5 outline-none focus:border-sky-500 uppercase transition-colors">
                                            <button onclick="game.api.corpAction('join', {ticker: document.getElementById('corp-join-ticker').value.toUpperCase()})" class="flex-grow py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-[10px] orbitron font-bold rounded-lg transition-all uppercase tracking-widest shadow-lg shadow-sky-500/10">Submit Application</button>
                                        </div>
                                    </div>
                                    <div class="pt-6 border-t border-slate-900">
                                        <label class="text-[10px] text-slate-400 uppercase font-black tracking-widest block mb-3">Pending Invitations</label>
                                        <div class="space-y-3">
                                            ${invitesHtml}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Right: Foundation -->
                        <div class="glass p-6 rounded-2xl border-r-4 border-r-amber-500 shadow-xl">
                            <h3 class="orbitron text-sm font-black text-amber-500 uppercase tracking-widest mb-2">Charter New Entity</h3>
                            <p class="text-[10px] text-slate-500 mb-6 font-medium italic">Establishing a planetary corporation costs <span class="text-emerald-400 font-bold tracking-widest">$10,000 CR</span>.</p>
                            
                            <div class="space-y-5">
                                <div>
                                    <label class="text-[9px] text-slate-500 uppercase font-black tracking-widest block mb-1.5">Entity Name</label>
                                    <input type="text" id="new-corp-name" placeholder="E.g. Lunar Reclamation" class="w-full bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-3 outline-none focus:border-amber-500 transition-colors">
                                </div>
                                <div>
                                    <label class="text-[9px] text-slate-500 uppercase font-black tracking-widest block mb-1.5">Ticker Identifier (3-5 Letters)</label>
                                    <input type="text" id="new-corp-ticker" placeholder="E.g. LUNAR" maxlength="5" class="w-full bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-3 outline-none focus:border-amber-500 uppercase transition-colors">
                                </div>
                                <div class="pt-4">
                                    <button onclick="const n=document.getElementById('new-corp-name').value; const t=document.getElementById('new-corp-ticker').value; if(n && t) game.api.corpAction('create', {name: n, ticker: t.toUpperCase()})" class="w-full py-4 bg-amber-600 hover:bg-amber-500 text-slate-950 text-xs orbitron font-black rounded-xl transition-all uppercase tracking-[0.2em] shadow-lg shadow-amber-500/20">Establish Charter</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
        } catch (e) {
            console.error("Corp UI update error:", e);
        }
    }
}

// Global UI helpers
window.copyAgentPrompt = function () {
    const prompt = document.getElementById('agent-prompt');
    if (prompt) {
        navigator.clipboard.writeText(prompt.value);
        alert("Directive Copied!");
    }
};
