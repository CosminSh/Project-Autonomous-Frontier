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
        this.cachedInventory = [];
        this.cachedStorage = [];
    }

    setUIMode(mode) {
        const privateLayer = document.getElementById('private-dashboard');
        const btnWorld = document.getElementById('btn-mode-world');
        const btnAgent = document.getElementById('btn-mode-agent');
        const mapCanvas = document.getElementById('canvas-container');
        const dashboardLayer = document.getElementById('dashboard-layer');

        if (mode === 'world') {
            privateLayer.classList.add('hidden');
            privateLayer.classList.remove('lg:flex');
            if (mapCanvas) mapCanvas.classList.remove('hidden', 'invisible');
            if (dashboardLayer) dashboardLayer.classList.remove('hidden');
            btnWorld.classList.add('bg-sky-500', 'text-slate-950');
            btnAgent.classList.remove('bg-sky-500', 'text-slate-950');
        } else {
            privateLayer.classList.remove('hidden');
            privateLayer.classList.add('lg:flex');
            if (mapCanvas) mapCanvas.classList.add('hidden');
            if (dashboardLayer) dashboardLayer.classList.add('hidden');
            btnAgent.classList.add('bg-sky-500', 'text-slate-950');
            btnWorld.classList.remove('bg-sky-500', 'text-slate-950');
        }
    }

    switchTab(tabId) {
        const tabs = ['terminal', 'inventory', 'station', 'system'];
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

        if (tabId === 'inventory' && window.storageUI) {
            window.storageUI.refreshStorage();
        }
    }

    switchInventoryTab(subTab) {
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
    }

    switchStationTab(subTab) {
        const panels = ['forge', 'market', 'missions'];
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
    }


    updateGlobalUI(stats) {
        document.getElementById('stat-agents').innerText = stats.total_agents || 0;
        document.getElementById('stat-market').innerText = stats.market_listings || 0;
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
        if (!logs) return;
        const feedEl = document.getElementById('live-feed');
        if (!feedEl) return;

        feedEl.innerHTML = '';
        logs.forEach(log => {
            const entry = document.createElement('div');
            const time = new Date(log.time).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

            let color = 'text-slate-400';
            let icon = '>>';

            if (log.event === 'COMBAT_HIT') { color = 'text-red-400'; icon = '!!'; }
            if (log.event === 'MINING') { color = 'text-emerald-400'; icon = '&&'; }
            if (log.event === 'RESPAWNED') { color = 'text-orange-400'; icon = 'XX'; }
            if (log.event.startsWith('MARKET')) { color = 'text-sky-400'; icon = '$$'; }

            entry.className = `flex space-x-2 ${color}`;
            entry.innerHTML = `<span class="text-slate-600">[${time}]</span><span class="font-bold">${icon}</span><span>${log.event}: ${JSON.stringify(log.details)}</span>`;
            feedEl.appendChild(entry);
        });
    }

    updatePrivateLogs(logs, pendingIntent, chatMessages = []) {
        if (!logs && chatMessages.length === 0) return;
        const logEl = document.getElementById('private-logs');
        if (!logEl) return;
        logEl.innerHTML = '';

        if (pendingIntent) {
            const pendingEntry = document.createElement('div');
            pendingEntry.className = `border-b border-sky-500/30 pb-2 mb-2 flex flex-col bg-sky-500/5 p-2 rounded-lg border border-sky-500/10`;
            pendingEntry.innerHTML = `<div class="flex justify-between items-center mb-1"><span class="text-sky-400 font-bold uppercase tracking-widest text-[8px]">Next Action</span></div><div class="flex space-x-2 text-sky-300"><span class="font-bold flex-shrink-0">${pendingIntent.action}</span><span class="truncate">${JSON.stringify(pendingIntent.data)}</span></div>`;
            logEl.appendChild(pendingEntry);
        }

        const combined = [...(logs || []), ...chatMessages].sort((a, b) => new Date(b.time || b.timestamp) - new Date(a.time || a.timestamp));

        combined.forEach(item => {
            const isChat = !!item.channel;
            const timeStr = item.time || item.timestamp;
            const time = new Date(timeStr).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

            const entry = document.createElement('div');
            entry.className = `border-b border-slate-900/50 pb-1 flex space-x-2`;

            if (isChat) {
                let badgeColor = 'bg-slate-500 text-white';
                if (item.channel === 'GLOBAL') badgeColor = 'bg-indigo-600 text-indigo-100';
                if (item.channel === 'PROX' || item.channel === 'LOCAL') badgeColor = 'bg-emerald-600 text-emerald-100';
                if (item.channel === 'SQUAD') badgeColor = 'bg-sky-600 text-sky-100';
                if (item.channel === 'CORP') badgeColor = 'bg-amber-600 text-amber-100';

                entry.innerHTML = `<span class="text-slate-700 font-mono flex-shrink-0">[${time}]</span><span class="${badgeColor} px-1 rounded text-[10px] font-bold tracking-widest leading-none flex items-center flex-shrink-0">${item.channel}</span><span class="text-slate-300 font-bold flex-shrink-0">${item.sender}:</span><span class="text-slate-100" style="word-break: break-all;">${item.message}</span>`;
            } else {
                let color = 'text-slate-400';
                if (item.event === 'COMBAT_HIT') color = 'text-rose-400';
                if (item.event === 'MINING') color = 'text-emerald-400';
                if (item.details?.status === 'success') color = 'text-sky-400';

                entry.classList.add(color);
                entry.innerHTML = `<span class="text-slate-700 font-mono flex-shrink-0">[${time}]</span><span class="font-bold flex-shrink-0">${item.event}</span><span class="truncate">${JSON.stringify(item.details)}</span>`;
            }
            logEl.appendChild(entry);
        });
    }

    updateMarketUI(market) {
        const body = document.getElementById('market-listings-body');
        const countSell = document.getElementById('count-sell');
        const countBuy = document.getElementById('count-buy');
        if (!body || !market) return;

        body.innerHTML = '';
        let sells = 0, buys = 0;

        market.forEach(order => {
            if (order.type === 'SELL') sells++; else buys++;
            const row = document.createElement('tr');
            row.className = "border-b border-slate-800/50 hover:bg-slate-800/20 transition-all group";
            const color = order.type === 'SELL' ? 'text-sky-400' : 'text-amber-400';
            row.innerHTML = `
                <td class="py-4 font-bold text-slate-300">${order.item.replace('_', ' ')}</td>
                <td class="py-4"><span class="px-2 py-0.5 rounded-full text-[7px] font-black border ${order.type === 'SELL' ? 'bg-sky-500/10 border-sky-500/30 text-sky-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}">${order.type}</span></td>
                <td class="py-4 font-mono text-slate-400">${order.quantity}</td>
                <td class="py-4 font-bold ${color}">$${order.price.toFixed(2)}</td>
                <td class="py-4 text-right">
                    <button class="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded text-[9px] font-bold" onclick="game.ui.quickTrade('${order.item}', ${order.price}, '${order.type}')">
                        ${order.type === 'SELL' ? 'BUY' : 'SELL'}
                    </button>
                </td>
            `;
            body.appendChild(row);
        });
        if (countSell) countSell.textContent = sells;
        if (countBuy) countBuy.textContent = buys;
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

        const hpPct = (agent.structure / agent.max_structure) * 100;
        const faction = FACTION_NAMES[agent.faction_id] || "Independent / Feral";

        content.innerHTML = `
            <div>
                <p class="text-[11px] font-bold text-white mb-1">${agent.name} <span class="text-slate-600 font-mono text-[9px]">#${agent.id}</span></p>
                <p class="text-[9px] text-rose-400 uppercase tracking-tighter mb-2">${faction}</p>
                <div class="w-full h-1 bg-slate-900 rounded-full overflow-hidden"><div class="h-full bg-emerald-500" style="width: ${hpPct}%"></div></div>
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

        document.getElementById('hp-bar').style.width = `${(agent.structure / agent.max_structure) * 100}%`;
        document.getElementById('hp-text').innerText = `${agent.structure}/${agent.max_structure}`;

        document.getElementById('energy-bar').style.width = `${agent.capacitor}%`;
        document.getElementById('energy-text').innerText = `${agent.capacitor}/100`;

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
        if (agent.inventory) this.cachedInventory = agent.inventory;
        if (agent.storage) this.cachedStorage = agent.storage;
        if (invList && agent.inventory) {
            invList.innerHTML = agent.inventory.map(i => `
                <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                    <span class="text-[10px] uppercase text-slate-300">${i.type.replace('_', ' ')}</span>
                    <span class="text-sky-400 text-[10px]">${i.quantity}</span>
                </div>
            `).join('');
        }

        // --- GARAGE CATEGORIZATION ---
        const equippedEl = document.getElementById('equipped-list');
        const detailedInvEl = document.getElementById('detailed-inventory');
        const equipmentInvEl = document.getElementById('equipment-inventory');
        const consumableInvEl = document.getElementById('consumable-inventory');

        if (equippedEl && agent.parts) {
            if (agent.parts.length === 0) {
                equippedEl.innerHTML = `<div class="text-[10px] text-slate-600 italic">No specialized gear detected.</div>`;
            } else {
                equippedEl.innerHTML = agent.parts.map(p => `
                    <div class="flex flex-col p-3 bg-sky-500/5 border border-sky-500/20 rounded-xl relative group overflow-hidden">
                        <div class="flex justify-between items-start mb-2">
                            <span class="text-[10px] font-bold text-sky-300 uppercase leading-none">${p.name}</span>
                            <div class="flex items-center space-x-2">
                                <span class="text-[8px] bg-sky-500/20 px-1 py-0.5 rounded text-sky-400 font-bold">${p.rarity}</span>
                                <button onclick="game.api.submitIntent('UNEQUIP', {part_id: ${p.id}})" class="bg-rose-500 hover:bg-rose-400 text-white px-2 py-0.5 rounded text-[8px] font-bold uppercase transition-all">UNEQUIP</button>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-1 text-[8px] text-slate-400">
                            ${Object.entries(p.stats || {}).map(([s, v]) => `<div>${s}: <span class="text-slate-200">${v}</span></div>`).join('')}
                        </div>
                        <div class="absolute inset-y-0 right-0 w-1 bg-sky-500"></div>
                    </div>
                `).join('');
            }
        }

        if (agent.inventory) {
            const resources = agent.inventory.filter(i => i.type.includes('_ORE') || i.type.includes('_INGOT') || ['SULFUR', 'CARBON'].includes(i.type));
            const items = agent.inventory.filter(i => i.type.includes('SCANNER'));
            const consumables = agent.inventory.filter(i => i.type.includes('REPAIR_KIT') || i.type.includes('FUEL_CELL') || i.type.includes('STIM') || i.type.includes('RATION') || i.type.includes('CANISTER'));

            if (detailedInvEl) {
                if (resources.length === 0) detailedInvEl.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-2">Cargo bay empty.</div>`;
                else detailedInvEl.innerHTML = resources.map(i => `
                    <div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-slate-800">
                        <span class="text-[9px] uppercase font-bold text-slate-400">${i.type.replace('_', ' ')}</span>
                        <span class="text-amber-500 text-[9px] font-mono">${i.quantity} units</span>
                    </div>
                `).join('');
            }

            if (equipmentInvEl) {
                if (items.length === 0) equipmentInvEl.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-2">No specialized equipment.</div>`;
                else equipmentInvEl.innerHTML = items.map(i => `
                    <div class="bg-indigo-500/5 p-3 rounded-xl border border-indigo-500/20 flex justify-between items-center">
                        <span class="text-[9px] font-bold text-indigo-300 uppercase">${i.type.replace('_', ' ')}</span>
                        <div class="flex items-center space-x-3">
                            <span class="text-indigo-400 text-[10px] font-mono">${i.quantity}</span>
                            <button onclick="game.api.submitIntent('EQUIP', {item_type: '${i.type}'})" class="bg-indigo-500 text-slate-950 px-2 py-0.5 rounded text-[8px] font-bold uppercase transition-all">EQUIP</button>
                        </div>
                    </div>
                `).join('');
            }

            if (consumableInvEl) {
                if (consumables.length === 0) consumableInvEl.innerHTML = `<div class="text-[10px] text-slate-600 italic text-center py-2">No consumables detected.</div>`;
                else consumableInvEl.innerHTML = consumables.map(i => `
                    <div class="bg-rose-500/5 p-3 rounded-xl border border-rose-500/20 flex justify-between items-center">
                        <span class="text-[9px] font-bold text-rose-300 uppercase">${i.type.replace('_', ' ')}</span>
                        <div class="flex items-center space-x-3">
                            <span class="text-rose-400 text-[10px] font-mono">${i.quantity}</span>
                            <button onclick="console.log('Consume ${i.type}')" class="bg-rose-500 text-white px-2 py-0.5 rounded text-[8px] font-bold uppercase transition-all">Consume</button>
                        </div>
                    </div>
                `).join('');
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
                        const hpPct = (m.structure / m.max_structure) * 100;
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
                    <div class="flex justify-between items-start mb-2">
                        <div class="text-[10px] font-bold text-sky-300 uppercase">${r.name}</div>
                        <div class="flex items-center gap-2">
                            ${craftable ? '<span class="text-[8px] text-emerald-400 font-bold">✓ READY</span>' : ''}
                            <span class="text-[8px] text-slate-500 font-mono">${r.type}</span>
                        </div>
                    </div>
                    <div class="text-[8px] text-slate-400 mb-2 uppercase tracking-widest font-bold">Materials:</div>
                    <div class="space-y-1 mb-3">${materials}</div>
                    <div class="text-[8px] text-slate-400 mb-1 uppercase tracking-widest font-bold">Projected Stats:</div>
                    <div class="grid grid-cols-2 gap-1 mb-4">
                        ${Object.entries(r.stats || {}).map(([s, v]) => `<div class="text-[8px] text-slate-300">${s}: <span class="text-emerald-400">${v}</span></div>`).join('')}
                    </div>
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

        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#0f172a'; // slate-900
        ctx.fillRect(0, 0, width, height);

        const p = this.game.lastPerception;
        const agent = this.game.lastAgentData;
        if (!agent) {
            ctx.fillStyle = '#64748b';
            ctx.font = '10px font-mono';
            ctx.textAlign = 'center';
            ctx.fillText('NO SIGNAL', width / 2, height / 2);
            return;
        }

        const coordsEl = document.getElementById('minimap-coords');
        if (coordsEl) coordsEl.innerText = `Q:${agent.q} R:${agent.r}`;

        const centerX = width / 2;
        const centerY = height / 2;
        const scale = 20; // hex radius

        // Helpers to convert axial to pixel
        const getX = (q, r) => centerX + scale * Math.sqrt(3) * (q + r / 2);
        const getY = (q, r) => centerY + scale * 3 / 2 * r;

        // Draw grids or just items
        const drawHex = (cx, cy, radius, color, isFill = false) => {
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
                ctx.fillStyle = color;
                ctx.fill();
            } else {
                ctx.strokeStyle = color;
                ctx.stroke();
            }
        };

        const drawLabel = (cx, cy, text, color) => {
            ctx.fillStyle = color;
            ctx.font = '8px Orbitron, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, cx, cy + 12);
        };

        ctx.lineWidth = 1;

        if (p) {
            // Draw Range Radius (approximate)
            ctx.beginPath();
            ctx.arc(centerX, centerY, scale * 3, 0, 2 * Math.PI);
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.1)';
            ctx.stroke();

            // Resources
            if (p.discovery && p.discovery.resources) {
                p.discovery.resources.forEach(r => {
                    const cx = getX(r.q - agent.q, r.r - agent.r);
                    const cy = getY(r.q - agent.q, r.r - agent.r);
                    drawHex(cx, cy, scale * 0.6, 'rgba(16, 185, 129, 0.5)', true); // emerald
                    drawHex(cx, cy, scale * 0.6, '#10b981', false);
                    drawLabel(cx, cy, r.type.split('_')[0], '#34d399');
                });
            }

            // Stations
            if (p.discovery && p.discovery.stations) {
                p.discovery.stations.forEach(s => {
                    const cx = getX(s.q - agent.q, s.r - agent.r);
                    const cy = getY(s.q - agent.q, s.r - agent.r);
                    drawHex(cx, cy, scale * 0.8, 'rgba(234, 179, 8, 0.5)', true); // yellow
                    drawHex(cx, cy, scale * 0.8, '#eab308', false);
                    drawLabel(cx, cy, s.id_type, '#facc15');
                });
            }

            // Loot
            if (p.loot) {
                p.loot.forEach(l => {
                    if (l.q !== undefined && l.r !== undefined) {
                        const cx = getX(l.q - agent.q, l.r - agent.r);
                        const cy = getY(l.q - agent.q, l.r - agent.r);

                        // Draw triangle for loot
                        ctx.beginPath();
                        ctx.moveTo(cx, cy - 5);
                        ctx.lineTo(cx + 5, cy + 4);
                        ctx.lineTo(cx - 5, cy + 4);
                        ctx.closePath();
                        ctx.fillStyle = 'rgba(168, 85, 247, 0.8)'; // purple
                        ctx.fill();

                        drawLabel(cx, cy, l.item.split('_')[0], '#c084fc');
                    }
                });
            }

            // Other Agents
            if (p.nearby_agents) {
                p.nearby_agents.forEach(a => {
                    const cx = getX(a.q - agent.q, a.r - agent.r);
                    const cy = getY(a.q - agent.q, a.r - agent.r);

                    // Draw red square for agents
                    ctx.fillStyle = 'rgba(244, 63, 94, 0.8)'; // rose
                    ctx.fillRect(cx - 4, cy - 4, 8, 8);

                    drawLabel(cx, cy + 4, a.name.substring(0, 6), '#fb7185');
                });
            }
        }

        // Draw Self (Center)
        drawHex(centerX, centerY, scale * 0.5, 'rgba(56, 189, 248, 0.8)', true); // sky
        ctx.fillStyle = '#bae6fd';
        ctx.font = 'bold 9px Base';
        ctx.textAlign = 'center';
        ctx.fillText('YOU', centerX, centerY - 8);
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
