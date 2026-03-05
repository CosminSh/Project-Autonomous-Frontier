/**
 * terminal.js — Manual Override Console (TerminalHandler)
 * Handles all player-typed commands, suggestions, and meta queries (HELP, RECIPES, STATUS).
 */

export class TerminalHandler {
    constructor(game) {
        this.game = game;
        this.input = document.getElementById('terminal-input');
        this.submitBtn = document.getElementById('terminal-submit');
        this.buffer = document.getElementById('terminal-buffer');
        this.suggestionsEl = document.getElementById('command-suggestions');

        // UX State
        this.selectedIndex = -1;
        this.currentMatches = [];

        // ═══════════════════════════════════════════════════════
        // FULL COMMAND REGISTRY
        // ═══════════════════════════════════════════════════════
        this.commands = {
            'MOVE': { cat: 'NAV', syntax: 'MOVE <q> <r>', example: 'MOVE 1 -1', help: 'Move to adjacent hex' },
            'SCAN': { cat: 'NAV', syntax: 'SCAN', example: 'SCAN', help: 'Re-sync sensor telemetry' },
            'MINE': { cat: 'RESOURCE', syntax: 'MINE', example: 'MINE', help: 'Extract resources (needs Drill)' },
            'SALVAGE': { cat: 'RESOURCE', syntax: 'SALVAGE <drop_id>', example: 'SALVAGE 42', help: 'Collect a world loot drop' },
            'ATTACK': { cat: 'COMBAT', syntax: 'ATTACK <target_id>', example: 'ATTACK 7', help: 'Standard combat engagement' },
            'INTIMIDATE': { cat: 'COMBAT', syntax: 'INTIMIDATE <target_id>', example: 'INTIMIDATE 7', help: 'Piracy: siphon 5% inventory' },
            'LOOT': { cat: 'COMBAT', syntax: 'LOOT <target_id>', example: 'LOOT 7', help: 'Piracy: attack + siphon 15%' },
            'DESTROY': { cat: 'COMBAT', syntax: 'DESTROY <target_id>', example: 'DESTROY 7', help: 'Piracy: high-dmg + siphon 40%' },
            'LIST': { cat: 'MARKET', syntax: 'LIST <item> <price> <qty>', example: 'LIST IRON_INGOT 50 10', help: 'List item on Auction House' },
            'BUY': { cat: 'MARKET', syntax: 'BUY <item> <max_price>', example: 'BUY IRON_INGOT 60', help: 'Purchase from Auction House' },
            'CANCEL': { cat: 'MARKET', syntax: 'CANCEL <order_id>', example: 'CANCEL 15', help: 'Withdraw an active order' },
            'MARKET': { cat: 'META', syntax: 'MARKET [item_type]', example: 'MARKET IRON_ORE', help: 'View active market listings' },
            'SMELT': { cat: 'INDUSTRY', syntax: 'SMELT <ore_type> <quantity>', example: 'SMELT IRON_ORE 5', help: 'Refine ore into ingots (SMELTER)' },
            'CRAFT': { cat: 'INDUSTRY', syntax: 'CRAFT <item_type>', example: 'CRAFT DRILL_MK1', help: 'Assemble parts (CRAFTER)' },
            'REFINE_GAS': { cat: 'INDUSTRY', syntax: 'REFINE_GAS <quantity>', example: 'REFINE_GAS 3', help: 'Helium Gas to He3 (REFINERY)' },
            'RESTORE_HP': { cat: 'MAINT', syntax: 'RESTORE_HP <amount>', example: 'RESTORE_HP 20', help: 'Restore agent HP [Costs 1 CR + 0.02 Iron Ingot/HP]' },
            'RESET_WEAR': { cat: 'MAINT', syntax: 'RESET_WEAR', example: 'RESET_WEAR', help: 'Clear Wear & Tear penalty [Costs 100 CR + 5 Iron Ingots]' },
            'EQUIP': { cat: 'GEAR', syntax: 'EQUIP <item_type>', example: 'EQUIP DRILL_MK1', help: 'Attach part to chassis' },
            'UNEQUIP': { cat: 'GEAR', syntax: 'UNEQUIP <part_id>', example: 'UNEQUIP 3', help: 'Remove equipped part' },
            'CONSUME': { cat: 'GEAR', syntax: 'CONSUME <item_type>', example: 'CONSUME HE3_FUEL', help: 'Use consumable for buff' },
            'CHANGE_FACTION': { cat: 'OTHER', syntax: 'CHANGE_FACTION <faction_id>', example: 'CHANGE_FACTION 2', help: 'Realign to faction (1-3)' },
            'MISSIONS': { cat: 'OTHER', syntax: 'MISSIONS', example: 'MISSIONS', help: 'View active daily missions' },
            'TURN_IN': { cat: 'OTHER', syntax: 'TURN_IN <mission_id>', example: 'TURN_IN 15', help: 'Complete local station delivery objectives' },
            'CLAIM_DAILY': { cat: 'OTHER', syntax: 'CLAIM_DAILY', example: 'CLAIM_DAILY', help: 'Claim daily login items' },
            'RECIPES': { cat: 'META', syntax: 'RECIPES [filter]', example: 'RECIPES drills', help: 'Query crafting database' },
            'HELP': { cat: 'META', syntax: 'HELP [command]', example: 'HELP SMELT', help: 'Show commands or details' },
            'STATUS': { cat: 'META', syntax: 'STATUS', example: 'STATUS', help: 'Show your agent status' },
            'PERCEIVE': { cat: 'META', syntax: 'PERCEIVE', example: 'PERCEIVE', help: 'Display local tactical perception' },
            'GUIDE': { cat: 'META', syntax: 'GUIDE', example: 'GUIDE', help: 'Read the survival guide' },
            'STORAGE_DEPOSIT': { cat: 'STORAGE', syntax: 'STORAGE_DEPOSIT <item> <qty>', example: 'STORAGE_DEPOSIT IRON_ORE 10', help: 'Vault item at MARKET station' },
            'STORAGE_WITHDRAW': { cat: 'STORAGE', syntax: 'STORAGE_WITHDRAW <item> <qty>', example: 'STORAGE_WITHDRAW IRON_ORE 10', help: 'Retrieve item from vault at MARKET' },
            'STORAGE_UPGRADE': { cat: 'STORAGE', syntax: 'STORAGE_UPGRADE', example: 'STORAGE_UPGRADE', help: 'Increase vault capacity (+250kg)' },
            'SQUAD_INVITE': { cat: 'SQUAD', syntax: 'SQUAD_INVITE <target_id>', example: 'SQUAD_INVITE 41', help: 'Invite player to your squad' },
            'SQUAD_ACCEPT': { cat: 'SQUAD', syntax: 'SQUAD_ACCEPT', example: 'SQUAD_ACCEPT', help: 'Accept pending squad invite' },
            'SQUAD_DECLINE': { cat: 'SQUAD', syntax: 'SQUAD_DECLINE', example: 'SQUAD_DECLINE', help: 'Decline pending squad invite' },
            'SQUAD_LEAVE': { cat: 'SQUAD', syntax: 'SQUAD_LEAVE', example: 'SQUAD_LEAVE', help: 'Exit your current squad' },
            'SAY': { cat: 'COMM', syntax: 'SAY <message>', example: 'SAY Hello nearby!', help: 'Local Chat (Radius 10)' },
            'SQUAD': { cat: 'COMM', syntax: 'SQUAD <message>', example: 'SQUAD Need backup!', help: 'Squad Chat' },
            'CORP': { cat: 'COMM', syntax: 'CORP <message>', example: 'CORP Reporting in.', help: 'Corporation Chat' },
            'GLOBAL': { cat: 'COMM', syntax: 'GLOBAL <message>', example: 'GLOBAL Selling Iron!', help: 'Global Chat' },
            'DROP_LOAD': { cat: 'OTHER', syntax: 'DROP_LOAD', example: 'DROP_LOAD', help: 'Jettison all cargo' },
            'STOP': { cat: 'NAV', syntax: 'STOP', example: 'STOP', help: 'Cancel all queued intents' },
            'FIELD_TRADE': { cat: 'MARKET', syntax: 'FIELD_TRADE <id> <price> <items...>', example: 'FIELD_TRADE 5 100 IRON_ORE', help: 'Direct trade with nearby agent' },
            'REQUEST_RESCUE': { cat: 'NAV', syntax: 'REQUEST_RESCUE', example: 'REQUEST_RESCUE', help: 'Get a quote for emergency towing to the Hub' },
            'CONFIRM_RESCUE': { cat: 'NAV', syntax: 'CONFIRM_RESCUE', example: 'CONFIRM_RESCUE', help: 'Confirm emergency tow at quoted price' },
        };

        this.setupListeners();
        setTimeout(() => {
            this.log('TERMINAL v2.0 ONLINE. Type <span style="color:#38bdf8">HELP</span> for commands.', 'system');
        }, 500);
    }

    setupListeners() {
        if (!this.input) return;

        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (this.suggestionsEl.classList.contains('hidden') || this.selectedIndex === -1)) {
                this.submit();
            } else {
                this.handleSuggestions(e);
            }
        });

        this.input.addEventListener('input', () => this.updateSuggestions());
        this.submitBtn?.addEventListener('click', () => this.submit());

        // Quick buttons
        document.getElementById('btn-quick-move')?.addEventListener('click', () => {
            this.input.value = 'MOVE ';
            this.input.focus();
        });
        document.getElementById('btn-quick-mine')?.addEventListener('click', () => {
            this.input.value = 'MINE';
            this.submit();
        });
        document.getElementById('btn-quick-scan')?.addEventListener('click', () => {
            this.input.value = 'SCAN';
            this.submit();
        });
        document.getElementById('btn-quick-perceive')?.addEventListener('click', () => {
            this.input.value = 'PERCEIVE';
            this.submit();
        });
        document.getElementById('btn-quick-status')?.addEventListener('click', () => {
            this.input.value = 'STATUS';
            this.submit();
        });
        document.getElementById('btn-quick-say')?.addEventListener('click', () => {
            this.input.value = 'SAY ';
            this.input.focus();
        });
        document.getElementById('btn-quick-salvage')?.addEventListener('click', () => {
            this.input.value = 'SALVAGE ';
            this.input.focus();
        });
        document.getElementById('btn-quick-repair')?.addEventListener('click', () => {
            this.input.value = 'RESTORE_HP ';
            this.input.focus();
        });
        document.getElementById('btn-quick-help')?.addEventListener('click', () => {
            this.input.value = 'HELP';
            this.submit();
        });
        document.getElementById('btn-quick-missions')?.addEventListener('click', () => {
            this.input.value = 'MISSIONS';
            this.submit();
        });
    }

    log(msg, type = 'info') {
        const div = document.createElement('div');
        const colors = {
            info: 'text-slate-400',
            success: 'text-emerald-400',
            error: 'text-rose-400',
            system: 'text-sky-400'
        };
        div.className = `font-mono ${colors[type] || colors.info}`;
        const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        div.innerHTML = `<span class="opacity-30">[${time}]</span> ${msg}`;
        this.buffer.appendChild(div);
        this.buffer.scrollTop = this.buffer.scrollHeight;
    }

    updateSuggestions() {
        const val = this.input.value.toUpperCase().trim();
        if (!val) {
            this.suggestionsEl.classList.add('hidden');
            this.currentMatches = [];
            this.selectedIndex = -1;
            return;
        }

        this.currentMatches = Object.keys(this.commands).filter(c => c.startsWith(val));

        if (this.currentMatches.length > 0) {
            this.selectedIndex = -1; // Reset selection on typing
            this.renderSuggestions();
            this.suggestionsEl.classList.remove('hidden');
        } else {
            this.suggestionsEl.classList.add('hidden');
            this.currentMatches = [];
        }
    }

    renderSuggestions() {
        this.suggestionsEl.innerHTML = this.currentMatches.map((m, idx) => {
            const cmd = this.commands[m];
            const activeClass = idx === this.selectedIndex ? 'active' : '';
            return `<div class="suggestion-item ${activeClass}" onclick="game.terminal.useSuggestion('${m}')">${cmd.syntax} — ${cmd.help}</div>`;
        }).join('');

        // Scroll active item into view if needed
        const activeItem = this.suggestionsEl.querySelector('.suggestion-item.active');
        if (activeItem) {
            activeItem.scrollIntoView({ block: 'nearest' });
        }
    }

    useSuggestion(cmd) {
        this.input.value = cmd + ' ';
        this.suggestionsEl.classList.add('hidden');
        this.input.focus();
    }

    handleSuggestions(e) {
        if (this.suggestionsEl.classList.contains('hidden')) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex + 1) % this.currentMatches.length;
            this.renderSuggestions();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex - 1 + this.currentMatches.length) % this.currentMatches.length;
            this.renderSuggestions();
        } else if (e.key === 'Tab' || (e.key === 'Enter' && this.selectedIndex !== -1)) {
            e.preventDefault();
            const pick = this.selectedIndex === -1 ? this.currentMatches[0] : this.currentMatches[this.selectedIndex];
            if (pick) this.useSuggestion(pick);
        } else if (e.key === 'Escape') {
            this.suggestionsEl.classList.add('hidden');
        }
    }

    parseIntent(actionType, args) {
        const data = {};
        switch (actionType) {
            case 'MOVE':
                if (args.length < 2) throw new Error('Usage: MOVE <q> <r>  — e.g. MOVE 1 -1');
                data.target_q = parseInt(args[0]); data.target_r = parseInt(args[1]);
                if (isNaN(data.target_q) || isNaN(data.target_r)) throw new Error('Coordinates must be integers.');
                break;
            case 'ATTACK': case 'INTIMIDATE': case 'LOOT': case 'DESTROY':
                if (args.length < 1) throw new Error(`Usage: ${actionType} <target_id>  — e.g. ${actionType} 7`);
                data.target_id = parseInt(args[0]);
                if (isNaN(data.target_id)) throw new Error('Target ID must be an integer.');
                break;
            case 'LIST':
                if (args.length < 3) throw new Error('Usage: LIST <item> <price> <qty>  — e.g. LIST IRON_INGOT 50 10');
                data.item_type = args[0].toUpperCase(); data.price = parseInt(args[1]); data.quantity = parseInt(args[2]);
                if (isNaN(data.price) || isNaN(data.quantity)) throw new Error('Price and Quantity must be integers.');
                break;
            case 'BUY':
                if (args.length < 2) throw new Error('Usage: BUY <item> <max_price>  — e.g. BUY IRON_INGOT 60');
                data.item_type = args[0].toUpperCase(); data.max_price = parseInt(args[1]);
                if (isNaN(data.max_price)) throw new Error('Max price must be an integer.');
                break;
            case 'CANCEL':
                if (args.length < 1) throw new Error('Usage: CANCEL <order_id>  — e.g. CANCEL 15');
                data.order_id = parseInt(args[0]);
                if (isNaN(data.order_id)) throw new Error('Order ID must be an integer.');
                break;
            case 'SMELT':
                if (args.length < 2) throw new Error('Usage: SMELT <ore_type> <qty>  — e.g. SMELT IRON_ORE 5');
                data.ore_type = args[0].toUpperCase(); data.quantity = parseInt(args[1]);
                if (isNaN(data.quantity)) throw new Error('Quantity must be an integer.');
                break;
            case 'CRAFT':
                if (args.length < 1) throw new Error('Usage: CRAFT <item_type>  — e.g. CRAFT DRILL_MK1');
                data.item_type = args.join('_').toUpperCase();
                break;
            case 'RESTORE_HP':
                if (args.length < 1) throw new Error('Usage: RESTORE_HP <amount>  — e.g. RESTORE_HP 20');
                data.amount = parseInt(args[0]);
                if (isNaN(data.amount)) throw new Error('Amount must be an integer.');
                break;
            case 'REFINE_GAS':
                if (args.length < 1) throw new Error('Usage: REFINE_GAS <qty>  — e.g. REFINE_GAS 3');
                data.quantity = parseInt(args[0]);
                if (isNaN(data.quantity)) throw new Error('Quantity must be an integer.');
                break;
            case 'SALVAGE':
                if (args.length < 1) throw new Error('Usage: SALVAGE <drop_id>  — e.g. SALVAGE 42');
                data.drop_id = parseInt(args[0]);
                if (isNaN(data.drop_id)) throw new Error('Drop ID must be an integer.');
                break;
            case 'EQUIP':
                if (args.length < 1) throw new Error('Usage: EQUIP <item_type>  — e.g. EQUIP DRILL_MK1');
                data.item_type = args.join('_').toUpperCase();
                break;
            case 'UNEQUIP':
                if (args.length < 1) throw new Error('Usage: UNEQUIP <part_id>  — e.g. UNEQUIP 3');
                data.part_id = parseInt(args[0]);
                if (isNaN(data.part_id)) throw new Error('Part ID must be an integer.');
                break;
            case 'CONSUME':
                if (args.length < 1) throw new Error('Usage: CONSUME <item_type>  — e.g. CONSUME HE3_FUEL');
                data.item_type = args.join('_').toUpperCase();
                break;
            case 'TURN_IN':
                if (args.length < 1) throw new Error('Usage: TURN_IN <mission_id>  — e.g. TURN_IN 12');
                data.mission_id = parseInt(args[0]);
                if (isNaN(data.mission_id)) throw new Error('Mission ID must be an integer.');
                break;
            case 'CHANGE_FACTION':
                if (args.length < 1) throw new Error('Usage: CHANGE_FACTION <faction_id>  — (1, 2, or 3)');
                data.faction_id = parseInt(args[0]);
                if (isNaN(data.faction_id)) throw new Error('Faction ID must be 1, 2, or 3.');
                break;
            case 'CONFIRM_RESCUE':
                return { action: 'RESCUE', ...data };
            case 'MINE': case 'RESET_WEAR': case 'STOP': case 'DROP_LOAD':
                break;
            case 'FIELD_TRADE':
                if (args.length < 3) throw new Error('Usage: FIELD_TRADE <target_id> <price> <items...>');
                data.target_id = parseInt(args[0]); data.price = parseInt(args[1]);
                data.items = args.slice(2);
                break;
            default:
                throw new Error(`Unknown command: ${actionType}`);
        }
        return data;
    }

    async submit() {
        const raw = this.input.value.trim();
        if (!raw) return;
        this.input.value = '';
        this.suggestionsEl.classList.add('hidden');
        this.log(`&gt; ${raw}`, 'system');

        const parts = raw.split(/\s+/);
        const actionType = parts[0].toUpperCase();
        const args = parts.slice(1);

        // ── META: HELP ──
        if (actionType === 'HELP') {
            if (args.length > 0) {
                const cmdName = args[0].toUpperCase();

                // HELP CRAFT <item> — show specific recipe details
                if (cmdName === 'CRAFT' && args.length > 1) {
                    const itemName = args[1].toUpperCase();
                    try {
                        const apiKey = localStorage.getItem('sv_api_key');
                        fetch('/api/my_agent', { headers: { 'X-API-KEY': apiKey } })
                            .then(r => r.json())
                            .then(a => {
                                const db = a.discovery?.crafting_recipes || [];
                                const recipe = db.find(r => r.id === itemName);
                                if (!recipe) {
                                    this.log(`No known recipe for '${itemName}'. Type <span style="color:#38bdf8">RECIPES</span> to view databanks.`, 'error');
                                    return;
                                }
                                const costStr = Object.entries(recipe.materials)
                                    .map(([mat, qty]) => `${qty}x ${mat.replace(/_/g, ' ')}`)
                                    .join(', ');
                                const statsStr = Object.entries(recipe.stats || {})
                                    .map(([k, v]) => `${k.substring(0, 3).toUpperCase()}: ${v > 0 ? '+' : ''}${v}`)
                                    .join(' | ');
                                this.log(`<b>═══ RECIPE FILE: ${recipe.name} ═══</b>`, 'system');
                                this.log(`  Target: <span style="color:#38bdf8">${recipe.id}</span> [${recipe.type.toUpperCase()}]`, 'info');
                                this.log(`  Cost:   ${costStr}`, 'info');
                                if (statsStr) this.log(`  Stats:  <span style="color:#a78bfa">${statsStr}</span>`, 'info');
                                this.log(`  Requires: <span style="color:#fbbf24">CRAFTER</span> station proximity`, 'info');
                            });
                    } catch (e) {
                        this.log(`Failed to access databanks: ${e.message}`, 'error');
                    }
                    return;
                }

                const cmd = this.commands[cmdName];
                if (cmd) {
                    this.log(`<b>${cmdName}</b> — ${cmd.help}`, 'info');
                    this.log(`  Syntax:  <span style="color:#38bdf8">${cmd.syntax}</span>`, 'info');
                    this.log(`  Example: <span style="color:#a78bfa">${cmd.example}</span>`, 'info');
                } else {
                    this.log(`Unknown command: ${cmdName}`, 'error');
                }
                return;
            }
            const categories = {
                'COMM': '📡 COMMS',
                'NAV': '🧭 NAVIGATION', 'RESOURCE': '⛏️ RESOURCES', 'COMBAT': '⚔️ COMBAT & PIRACY',
                'MARKET': '🏪 MARKET', 'INDUSTRY': '🏭 INDUSTRY', 'MAINT': '🔧 MAINTENANCE',
                'GEAR': '🎒 GEAR', 'STORAGE': '📦 STORAGE', 'SQUAD': '👥 SQUAD',
                'OTHER': '🌐 OTHER', 'META': '📖 META'
            };
            const grouped = {};
            for (const [name, cmd] of Object.entries(this.commands)) {
                if (!grouped[cmd.cat]) grouped[cmd.cat] = [];
                grouped[cmd.cat].push({ name, ...cmd });
            }
            this.log('═══ COMMAND PROTOCOLS ═══', 'system');
            for (const [cat, label] of Object.entries(categories)) {
                if (!grouped[cat]) continue;
                this.log(`<b>${label}</b>`, 'info');
                grouped[cat].forEach(c => {
                    this.log(`  <span style="color:#38bdf8">${c.syntax.padEnd(35)}</span> ${c.help}`, 'info');
                });
            }
            this.log('Type <span style="color:#38bdf8">HELP &lt;command&gt;</span> for details.', 'system');
            this.log('Read the survival guide via <span style="color:#38bdf8">GUIDE</span> (or /api/guide).', 'system');
            return;
        }

        // ── META: RECIPES ──
        if (actionType === 'RECIPES') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/my_agent', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Not authenticated.');
                const a = await resp.json();

                if (!a.discovery || !a.discovery.crafting_recipes) {
                    this.log('Crafting database offline.', 'error');
                    return;
                }

                const db = a.discovery.crafting_recipes;
                const filter = args.length > 0 ? args[0].toUpperCase() : null;

                this.log(`<b>═══ CRAFTING DATABANKS ═══</b>`, 'system');

                if (!filter) {
                    this.log(`Terminal usage: <span style="color:#38bdf8">RECIPES &lt;category&gt;</span>`, 'info');
                    this.log(`Available categories:`, 'info');
                    const types = [...new Set(db.map(r => r.type.toUpperCase()))];
                    types.forEach(t => this.log(`  - ${t}`, 'info'));
                    this.log(``, 'info');
                    this.log(`All ${db.length} recipes: type <span style="color:#38bdf8">RECIPES ACTUATOR</span>, <span style="color:#38bdf8">RECIPES FRAME</span>, etc.`, 'info');
                    return;
                }

                const results = db.filter(r =>
                    r.type.toUpperCase().includes(filter) ||
                    r.id.includes(filter) ||
                    r.name.toUpperCase().includes(filter)
                );

                if (results.length === 0) {
                    this.log(`No recipes found matching '${filter}'.`, 'error');
                    return;
                }

                this.log(`Found ${results.length} results for '${filter}':`, 'system');
                results.forEach(r => {
                    const costStr = Object.entries(r.materials)
                        .map(([mat, qty]) => `${qty}x ${mat.replace(/_/g, ' ')}`)
                        .join(', ');
                    const statsStr = Object.entries(r.stats || {})
                        .map(([k, v]) => `${k.substring(0, 3).toUpperCase()}: ${v > 0 ? '+' : ''}${v}`)
                        .join(' | ');
                    this.log(`<b>${r.name}</b> <span style="color:#64748b">(${r.id})</span>`, 'success');
                    this.log(`  Cost:  ${costStr}`, 'info');
                    if (statsStr) this.log(`  Stats: <span style="color:#a78bfa">${statsStr}</span>`, 'info');
                });

            } catch (e) {
                this.log(`Database sync failed: ${e.message}`, 'error');
            }
            return;
        }

        // ── META: MISSIONS ──
        if (actionType === 'MISSIONS') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/missions', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Not authenticated.');
                const missions = await resp.json();

                this.log(`<b>═══ DAILY MISSIONS ═══</b>`, 'system');
                if (!missions || missions.length === 0) {
                    this.log(`  No active missions available.`, 'info');
                    return;
                }

                missions.forEach(m => {
                    const status = m.is_completed ? '<span style="color:#10b981">[COMPLETED]</span>' : `[${m.progress}/${m.target}]`;
                    this.log(`  <b>[${m.id}] ${m.type.replace(/_/g, ' ')}</b> — ${status}`, 'info');
                    if (m.item_type) this.log(`    Target: ${m.item_type.replace(/_/g, ' ')}`, 'info');
                    this.log(`    Reward: $${m.reward_credits}`, 'success');
                });
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: GUIDE ──
        if (actionType === 'GUIDE') {
            try {
                const resp = await fetch('/api/guide');
                const guide = await resp.json();
                this.log(`<b>═══ ${guide.title.toUpperCase()} ═══</b>`, 'system');
                this.log(`<i>${guide.philosophy}</i>`, 'info');
                this.log('', 'info');
                this.log(`<b>Intel:</b>`, 'success');
                guide.intel.forEach(t => this.log(`  - ${t}`, 'info'));
            } catch (e) { this.log(`ERROR: Could not load guide.`, 'error'); }
            return;
        }

        // ── META: MARKET ──
        if (actionType === 'MARKET') {
            try {
                let url = '/api/market';
                const filter = args.length > 0 ? args[0].toUpperCase().replace(/-/g, '_') : null;
                if (filter) url += `?item_type=${encodeURIComponent(filter)}`;

                const resp = await fetch(url);
                const market = await resp.json();

                this.log(`<b>═══ GALACTIC MARKET ═══</b>`, 'system');
                if (!market || market.length === 0) {
                    this.log(`  No active orders${filter ? ' for ' + filter : ''}.`, 'info');
                    return;
                }

                let sells = 0, buys = 0;
                market.forEach(o => {
                    const typeColor = o.type === 'SELL' ? 'color:#38bdf8' : 'color:#fbbf24';
                    this.log(`  [#${o.id}] <span style="${typeColor}">${o.type}</span> <b>${o.item.replace('_', ' ')}</b> x${o.quantity} for <span style="color:#10b981">$${o.price}</span> ea`, 'info');
                    if (o.type === 'SELL') sells++; else buys++;
                });
                this.log(`  <i>${sells} SELL / ${buys} BUY orders total.</i>`, 'system');
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        if (actionType === 'MARKET_PICKUPS') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/market/pickups', { headers: { 'X-API-KEY': apiKey } });
                const pickups = await resp.json();

                this.log(`<b>═══ MARKET PICKUPS ═══</b>`, 'system');
                if (!pickups || pickups.length === 0) {
                    this.log(`  No items waiting for pickup.`, 'info');
                    return;
                }

                pickups.forEach(p => {
                    this.log(`  [#${p.id}] <b>${p.item.replace('_', ' ')}</b> x${p.qty}`, 'info');
                });
                this.log(`  <i>Use MARKET_CLAIM at a Market station to retrieve them.</i>`, 'system');
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: STATUS ──
        if (actionType === 'STATUS') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/my_agent', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Not authenticated.');
                const a = await resp.json();
                this.log(`<b>═══ AGENT STATUS ═══</b>`, 'system');
                this.log(`  Name:      <b>${a.name}</b>`, 'info');
                this.log(`  Level:     ${a.level || 1} (${a.experience || 0} XP)`, 'info');
                this.log(`  Pos:       (${a.q}, ${a.r})`, 'info');
                this.log(`  Structure: ${a.structure}/${a.max_structure} HP`, a.structure < a.max_structure * 0.3 ? 'error' : 'info');
                this.log(`  Energy:    ${a.capacitor}/100`, 'info');
                if (a.inventory && a.inventory.length > 0) {
                    this.log(`  Cargo:`, 'info');
                    a.inventory.forEach(item => this.log(`    ${item.type.replace(/_/g, ' ')} x${item.quantity}`, 'info'));
                } else {
                    this.log(`  Cargo:     [empty]`, 'info');
                }
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: PERCEIVE ──
        if (actionType === 'PERCEIVE') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/perception', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Not authenticated.');
                const p = await resp.json();
                this.log(`<b>═══ TACTICAL PERCEIVE ═══</b>`, 'system');
                this.log(`  Agent:     <b>${p.self.name}</b> at (${p.self.q}, ${p.self.r})`, 'info');

                // Agents
                if (p.nearby_agents && p.nearby_agents.length > 0) {
                    this.log(`  <span style="color:#f43f5e">Agents Detected:</span>`, 'info');
                    p.nearby_agents.forEach(a => this.log(`    [${a.id}] ${a.name} @ (${a.q}, ${a.r})`, 'error'));
                } else {
                    this.log(`  <span style="color:#f43f5e">Agents:</style> None`, 'info');
                }

                // Stations
                if (p.discovery && p.discovery.stations && p.discovery.stations.length > 0) {
                    this.log(`  <span style="color:#eab308">Stations:</span>`, 'info');
                    p.discovery.stations.forEach(s => this.log(`    ${s.id_type} @ (${s.q}, ${s.r})`, 'warning'));
                }

                // Resources
                if (p.discovery && p.discovery.resources && p.discovery.resources.length > 0) {
                    this.log(`  <span style="color:#10b981">Resources:</span>`, 'info');
                    p.discovery.resources.forEach(r => this.log(`    ${r.type} @ (${r.q}, ${r.r})`, 'success'));
                }

                // Loot
                if (p.loot && p.loot.length > 0) {
                    this.log(`  <span style="color:#a855f7">Loot Drops:</span>`, 'info');
                    p.loot.forEach(l => this.log(`    ${l.qty}x ${l.item} @ (${l.q}, ${l.r})`, 'info'));
                }
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: REQUEST_RESCUE ──
        if (actionType === 'REQUEST_RESCUE') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/rescue_quote', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Not authenticated.');
                const q = await resp.json();
                this.log(`<b>═══ RESCUE TOW QUOTE ═══</b>`, 'system');
                this.log(`  Distance to Hub (0,0): ${q.distance} hexes`, 'info');
                this.log(`  Tow Speed: 10 hexes / tick`, 'info');
                this.log(`  Estimated Time: ${q.eta_ticks} ticks`, 'info');
                this.log(`  Total Cost: <span style="color:#fbbf24">${q.cost} CREDITS</span>`, 'warning');
                this.log(`  To accept, type: <span style="color:#38bdf8">CONFIRM_RESCUE</span>`, 'system');
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: SCAN ──
        if (actionType === 'SCAN') {
            this.log(`Re-synchronizing sensors...`, 'info');
            await this.game.pollState();
            this.log(`Sync complete. State updated.`, 'success');
            return;
        }

        // ── DIRECT COMMANDS (NO INTENT) ──

        // ── DIRECT COMMANDS: SQUAD ──
        if (['SQUAD_INVITE', 'SQUAD_ACCEPT', 'SQUAD_DECLINE', 'SQUAD_LEAVE'].includes(actionType)) {
            const apiKey = localStorage.getItem('sv_api_key');
            if (actionType === 'SQUAD_INVITE') {
                if (args.length < 1) {
                    this.log(`✗ Usage: SQUAD_INVITE <target_id> (e.g. SQUAD_INVITE 41)`, 'error');
                    return;
                }
                try {
                    const resp = await fetch('/api/squad/invite', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                        body: JSON.stringify({ target_id: parseInt(args[0]) })
                    });
                    if (resp.ok) {
                        const result = await resp.json();
                        this.log(`✓ ${result.message}`, 'success');
                        this.game.pollState();
                    } else {
                        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                        this.log(`✗ ${err.detail || 'Server error'}`, 'error');
                    }
                } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
                return;
            }

            if (['SQUAD_ACCEPT', 'SQUAD_DECLINE'].includes(actionType)) {
                const endpoint = actionType === 'SQUAD_ACCEPT' ? '/api/squad/accept' : '/api/squad/decline';
                try {
                    const resp = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey }
                    });
                    if (resp.ok) {
                        const result = await resp.json();
                        this.log(`✓ ${result.message}`, 'success');
                        this.game.pollState();
                    } else {
                        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                        this.log(`✗ ${err.detail || 'Server error'}`, 'error');
                    }
                } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
                return;
            }

            if (actionType === 'SQUAD_LEAVE') {
                try {
                    const resp = await fetch('/api/squad/leave', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey }
                    });
                    if (resp.ok) {
                        const result = await resp.json();
                        this.log(`✓ ${result.message}`, 'success');
                        this.game.pollState();
                    } else {
                        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                        this.log(`✗ ${err.detail || 'Server error'}`, 'error');
                    }
                } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
                return;
            }
        }

        // ── DIRECT COMMANDS: STORAGE ──
        if (['STORAGE_DEPOSIT', 'STORAGE_WITHDRAW', 'STORAGE_UPGRADE'].includes(actionType)) {
            const apiKey = localStorage.getItem('sv_api_key');
            if (actionType === 'STORAGE_UPGRADE') {
                try {
                    const resp = await fetch('/api/storage/upgrade', {
                        method: 'POST',
                        headers: { 'X-API-KEY': apiKey }
                    });
                    const result = await resp.json();
                    if (resp.ok) {
                        this.log(`✓ ${result.message}`, 'success');
                        this.game.pollState();
                        if (window.storageUI) window.storageUI.refreshStorage();
                    } else {
                        this.log(`✗ ${result.detail || 'Server error'}`, 'error');
                    }
                } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
                return;
            }

            if (args.length < 2) {
                this.log(`✗ Usage: ${actionType} <item_type> <quantity>`, 'error');
                return;
            }

            const endpoint = actionType === 'STORAGE_DEPOSIT' ? '/api/storage/deposit' : '/api/storage/withdraw';
            try {
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                    body: JSON.stringify({ item_type: args[0].toUpperCase().replace(/-/g, '_'), quantity: parseInt(args[1]) })
                });
                const result = await resp.json();
                if (resp.ok) {
                    this.log(`✓ ${result.message}`, 'success');
                    this.game.pollState();
                    if (window.storageUI) window.storageUI.refreshStorage();
                } else {
                    this.log(`✗ ${result.detail || 'Server error'}`, 'error');
                }
            } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
            return;
        }

        if (actionType === 'MARKET_CLAIM') {
            const apiKey = localStorage.getItem('sv_api_key');
            try {
                const resp = await fetch('/api/market/pickup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey }
                });
                const result = await resp.json();
                if (resp.ok) {
                    this.log(`✓ ${result.message}`, 'success');
                    for (const [item, qty] of Object.entries(result.claimed)) {
                        this.log(`  Retrieved: ${item.replace(/_/g, ' ')} x${qty}`, 'info');
                    }
                    this.game.pollState();
                } else {
                    this.log(`✗ ${result.detail || 'Server error'}`, 'error');
                }
            } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
            return;
        }

        if (actionType === 'CLAIM_DAILY') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/claim_daily', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey }
                });
                if (resp.ok) {
                    const result = await resp.json();
                    this.log(`✓ Daily claimed! Acquired: ${result.items.join(', ')}`, 'success');
                    if (window.game) window.game.pollState();
                } else {
                    const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
                    this.log(`✗ ${err.detail || 'Server error'}`, 'error');
                }
            } catch (e) {
                this.log(`✗ ${e.message}`, 'error');
            }
            return;
        }

        // ── CHAT COMMANDS ──
        if (['SAY', 'PROX', 'SQUAD', 'CORP', 'GLOBAL'].includes(actionType)) {
            if (args.length < 1) {
                this.log(`✗ Usage: ${actionType} <message>`, 'error');
                return;
            }
            const channel = actionType === 'SAY' || actionType === 'PROX' ? 'PROX' : actionType;
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                    body: JSON.stringify({ channel: channel, message: args.join(' ') })
                });
                const result = await resp.json();
                if (resp.ok) {
                    this.log(`✓ Message sent via ${actionType}`, 'success');
                    if (window.game) window.game.pollState();
                } else {
                    this.log(`✗ ${result.detail || 'Server error'}`, 'error');
                }
            } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
            return;
        }

        // ── SERVER COMMANDS ──
        if (!this.commands[actionType]) {
            this.log(`Unknown command '${actionType}'. Type HELP for list.`, 'error');
            return;
        }

        try {
            const data = this.parseIntent(actionType, args);
            this.log(`Transmitting: <span style="color:#38bdf8">${actionType}</span>...`, 'info');

            const apiKey = localStorage.getItem('sv_api_key');
            const resp = await fetch('/api/intent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
                body: JSON.stringify({ action_type: actionType, data })
            });

            if (resp.ok) {
                const result = await resp.json();
                this.log(`✓ ACCEPTED — Tick #${result.tick}`, 'success');
            } else {
                const err = await resp.json().catch(() => ({ detail: 'Unknown server error' }));
                const errorDetail = typeof err.detail === 'object' ? JSON.stringify(err.detail) : err.detail;
                this.log(`✗ REJECTED — ${errorDetail || 'Server error'}`, 'error');
            }
        } catch (e) {
            this.log(`✗ ${e.message}`, 'error');
        }
    }
}
