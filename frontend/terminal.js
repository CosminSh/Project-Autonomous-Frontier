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
            'SMELT': { cat: 'INDUSTRY', syntax: 'SMELT <ore_type> <quantity>', example: 'SMELT IRON_ORE 5', help: 'Refine ore into ingots (SMELTER)' },
            'CRAFT': { cat: 'INDUSTRY', syntax: 'CRAFT <item_type>', example: 'CRAFT DRILL_MK1', help: 'Assemble parts (CRAFTER)' },
            'REFINE_GAS': { cat: 'INDUSTRY', syntax: 'REFINE_GAS <quantity>', example: 'REFINE_GAS 3', help: 'Helium Gas to He3 (REFINERY)' },
            'REPAIR': { cat: 'MAINT', syntax: 'REPAIR <amount>', example: 'REPAIR 20', help: 'Restore structure (REPAIR stn)' },
            'CORE_SERVICE': { cat: 'MAINT', syntax: 'CORE_SERVICE', example: 'CORE_SERVICE', help: 'Reset Wear and Tear' },
            'EQUIP': { cat: 'GEAR', syntax: 'EQUIP <item_type>', example: 'EQUIP DRILL_MK1', help: 'Attach part to chassis' },
            'UNEQUIP': { cat: 'GEAR', syntax: 'UNEQUIP <part_id>', example: 'UNEQUIP 3', help: 'Remove equipped part' },
            'CONSUME': { cat: 'GEAR', syntax: 'CONSUME <item_type>', example: 'CONSUME HE3_FUEL', help: 'Use consumable for buff' },
            'CHANGE_FACTION': { cat: 'OTHER', syntax: 'CHANGE_FACTION <faction_id>', example: 'CHANGE_FACTION 2', help: 'Realign to faction (1-3)' },
            'MISSIONS': { cat: 'OTHER', syntax: 'MISSIONS', example: 'MISSIONS', help: 'View active daily missions' },
            'RECIPES': { cat: 'META', syntax: 'RECIPES [filter]', example: 'RECIPES drills', help: 'Query crafting database' },
            'HELP': { cat: 'META', syntax: 'HELP [command]', example: 'HELP SMELT', help: 'Show commands or details' },
            'STATUS': { cat: 'META', syntax: 'STATUS', example: 'STATUS', help: 'Show your agent status' },
            'GUIDE': { cat: 'META', syntax: 'GUIDE', example: 'GUIDE', help: 'Read the survival guide' },
        };

        this.setupListeners();
        setTimeout(() => {
            this.log('TERMINAL v2.0 ONLINE. Type <span style="color:#38bdf8">HELP</span> for commands.', 'system');
        }, 500);
    }

    setupListeners() {
        if (!this.input) return;

        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.submit();
            else this.handleSuggestions(e);
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
        document.getElementById('btn-quick-status')?.addEventListener('click', () => {
            this.input.value = 'STATUS';
            this.submit();
        });
        document.getElementById('btn-quick-salvage')?.addEventListener('click', () => {
            this.input.value = 'SALVAGE ';
            this.input.focus();
        });
        document.getElementById('btn-quick-repair')?.addEventListener('click', () => {
            this.input.value = 'REPAIR ';
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
            return;
        }

        const matches = Object.keys(this.commands).filter(c => c.startsWith(val));
        if (matches.length > 0) {
            this.suggestionsEl.innerHTML = matches.map(m => {
                const cmd = this.commands[m];
                return `<div class="suggestion-item" onclick="game.terminal.useSuggestion('${m}')">${cmd.syntax} — ${cmd.help}</div>`;
            }).join('');
            this.suggestionsEl.classList.remove('hidden');
        } else {
            this.suggestionsEl.classList.add('hidden');
        }
    }

    useSuggestion(cmd) {
        this.input.value = cmd + ' ';
        this.suggestionsEl.classList.add('hidden');
        this.input.focus();
    }

    handleSuggestions(e) { }

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
            case 'REPAIR':
                if (args.length < 1) throw new Error('Usage: REPAIR <amount>  — e.g. REPAIR 20');
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
            case 'CHANGE_FACTION':
                if (args.length < 1) throw new Error('Usage: CHANGE_FACTION <faction_id>  — (1, 2, or 3)');
                data.faction_id = parseInt(args[0]);
                if (isNaN(data.faction_id)) throw new Error('Faction ID must be 1, 2, or 3.');
                break;
            case 'MINE': case 'CORE_SERVICE':
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
                'NAV': '🧭 NAVIGATION', 'RESOURCE': '⛏️ RESOURCES', 'COMBAT': '⚔️ COMBAT & PIRACY',
                'MARKET': '🏪 MARKET', 'INDUSTRY': '🏭 INDUSTRY', 'MAINT': '🔧 MAINTENANCE',
                'GEAR': '🎒 GEAR', 'OTHER': '🌐 OTHER', 'META': '📖 META'
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
                    const status = m.is_completed ? '<span style="color:#10b981">[COMPLETED]</span>' : `[${m.progress}/${m.target_amount}]`;
                    this.log(`  <b>${m.type.replace(/_/g, ' ')}</b> — ${status}`, 'info');
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

        // ── META: SCAN ──
        if (actionType === 'SCAN') {
            this.log(`Re-synchronizing sensors...`, 'info');
            await this.game.pollState();
            this.log(`Sync complete. State updated.`, 'success');
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
                this.log(`✓ ACCEPTED — Tick #${result.scheduled_tick}`, 'success');
            } else {
                const err = await resp.json().catch(() => ({ detail: 'Unknown server error' }));
                this.log(`✗ REJECTED — ${err.detail || 'Server error'}`, 'error');
            }
        } catch (e) {
            this.log(`✗ ${e.message}`, 'error');
        }
    }
}
