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
            'MOVE': { cat: 'NAV', syntax: 'MOVE <q> <r> | <KEYWORD>', example: 'MOVE SMELTER', help: 'Move to coordinates or nearest station (SMELTER, CRAFTER, MARKET, HUB, REPAIR, REFINERY).' },
            'GO': { cat: 'NAV', syntax: 'GO <q> <r> | <KEYWORD>', example: 'GO HUB', help: 'Alias for MOVE.' },
            'SCAN': { cat: 'META', syntax: 'SCAN', example: 'SCAN', help: 'Alias for PERCEIVE (Tactical Readout).' },
            'MINE': { cat: 'RESOURCE', syntax: 'MINE [resource] [q] [r]', example: 'MINE COPPER_ORE 2 3', help: 'Extract resources. Optional: auto-move to coordinates first.' },
            'SALVAGE': { cat: 'RESOURCE', syntax: 'SALVAGE <drop_id>', example: 'SALVAGE 42', help: 'Collect a world loot drop' },
            'ATTACK': { cat: 'COMBAT', syntax: 'ATTACK <target_id>', example: 'ATTACK 7', help: 'Standard combat engagement' },
            'INTIMIDATE': { cat: 'COMBAT', syntax: 'INTIMIDATE <target_id>', example: 'INTIMIDATE 7', help: 'Piracy: intimidation check, success siphons 5% inventory' },
            'LOOT': { cat: 'COMBAT', syntax: 'LOOT <target_id>', example: 'LOOT 7', help: 'Piracy: light skirmish to siphon 15% inventory' },
            'DESTROY': { cat: 'COMBAT', syntax: 'DESTROY <target_id>', example: 'DESTROY 7', help: 'Piracy: deathmatch fight to 5% HP, siphons 40% cargo' },
            'LIST': { cat: 'MARKET', syntax: 'LIST <item> <pricePerUnit> <qty>', example: 'LIST IRON_INGOT 50 10', help: 'List item for $50 each, 10 units total' },
            'BUY': { cat: 'MARKET', syntax: 'BUY <item> <max_price>', example: 'BUY IRON_INGOT 60', help: 'Purchase from Auction House' },
            'CANCEL': { cat: 'MARKET', syntax: 'CANCEL <order_id>', example: 'CANCEL 15', help: 'Withdraw an active order' },
            'TRANSFER': { cat: 'MARKET', syntax: 'TRANSFER <target_id> <item> <qty>', example: 'TRANSFER 42 IRON_ORE 10', help: 'Directly transfer items to a nearby agent.' },
            'MARKET_CLAIM': { cat: 'MARKET', syntax: 'MARKET_CLAIM', example: 'MARKET_CLAIM', help: 'Retrieve purchased items from the current Market station.' },
            'MARKET': { cat: 'META', syntax: 'MARKET [item_type]', example: 'MARKET IRON_ORE', help: 'View active market listings' },
            'MARKET_PICKUPS': { cat: 'META', syntax: 'MARKET_PICKUPS', example: 'MARKET_PICKUPS', help: 'View items waiting for retrieval.' },
            'BOUNTIES': { cat: 'META', syntax: 'BOUNTIES', example: 'BOUNTIES', help: 'View active player bounties (Warrants).' },
            'SMELT': { cat: 'INDUSTRY', syntax: 'SMELT <ore_type> <quantity>', example: 'SMELT IRON_ORE 5', help: 'Refine ore into ingots (SMELTER). Uses inventory only.' },
            'CRAFT': { cat: 'INDUSTRY', syntax: 'CRAFT <item_type>', example: 'CRAFT DRILL_MK1', help: 'Assemble parts (CRAFTER). Uses resources from inventory or vault.' },
            'REFINE_GAS': { cat: 'INDUSTRY', syntax: 'REFINE_GAS <quantity>', example: 'REFINE_GAS 3', help: 'Helium Gas to He3 (REFINERY). Uses inventory only.' },
            'RESTORE_HP': { cat: 'MAINT', syntax: 'RESTORE_HP <amount>', example: 'RESTORE_HP 20', help: 'Restore agent HP [Costs 1 CR + 0.02 Iron Ingot/HP]. Uses resources from inventory or vault.' },
            'RESET_WEAR': { cat: 'MAINT', syntax: 'RESET_WEAR', example: 'RESET_WEAR', help: 'Clear Wear & Tear penalty. Costs scale with gear. Uses resources from inventory or vault.' },
            'EQUIP': { cat: 'GEAR', syntax: 'EQUIP <item_type>', example: 'EQUIP DRILL_MK1', help: 'Attach part to chassis' },
            'UNEQUIP': { cat: 'GEAR', syntax: 'UNEQUIP <part_id>', example: 'UNEQUIP 3', help: 'Remove equipped part' },
            'CONSUME': { cat: 'GEAR', syntax: 'CONSUME <item_type>', example: 'CONSUME HE3_FUEL', help: 'Use consumable for buff' },
            'CHANGE_FACTION': { cat: 'OTHER', syntax: 'CHANGE_FACTION <faction_id>', example: 'CHANGE_FACTION 2', help: 'Realign to faction (1-3)' },
            'MISSIONS': { cat: 'OTHER', syntax: 'MISSIONS', example: 'MISSIONS', help: 'View active daily missions' },
            'TURN_IN': { cat: 'OTHER', syntax: 'TURN_IN <mission_id>', example: 'TURN_IN 15', help: 'Complete local station delivery objectives' },
            'CLAIM_DAILY': { cat: 'OTHER', syntax: 'CLAIM_DAILY', example: 'CLAIM_DAILY', help: 'Claim daily login items' },
            'RECIPES': { cat: 'META', syntax: 'RECIPES [filter]', example: 'RECIPES drills', help: 'Query crafting database' },
            'GEAR': { cat: 'META', syntax: 'GEAR', example: 'GEAR', help: 'Show currently equipped gear and stats' },
            'HELP': { cat: 'META', syntax: 'HELP [command]', example: 'HELP SMELT', help: 'Show commands or details' },
            'STATUS': { cat: 'META', syntax: 'STATUS', example: 'STATUS', help: 'Show your agent status' },
            'PERCEIVE': { cat: 'META', syntax: 'PERCEIVE', example: 'PERCEIVE', help: 'Display local tactical perception. Requires a Neural Scanner for deep stats (HP, Inventory) on targets.' },
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
            'CLAIM_LOST_DRILL': { cat: 'OTHER', syntax: 'CLAIM_LOST_DRILL', example: 'CLAIM_LOST_DRILL', help: 'Emergency recovery if your drill became Scrap Metal' },
            'DROP_LOAD': { cat: 'OTHER', syntax: 'DROP_LOAD', example: 'DROP_LOAD', help: 'Jettison all cargo' },
            'STOP': { cat: 'NAV', syntax: 'STOP', example: 'STOP', help: 'Cancel all queued intents' },
            'FIELD_TRADE': { cat: 'MARKET', syntax: 'FIELD_TRADE <id> <price> <items...>', example: 'FIELD_TRADE 5 100 IRON_ORE', help: 'Direct trade with nearby agent' },
            'REQUEST_RESCUE': { cat: 'NAV', syntax: 'REQUEST_RESCUE', example: 'REQUEST_RESCUE', help: 'Get a quote for emergency towing to the Hub' },
            'CONFIRM_RESCUE': { cat: 'NAV', syntax: 'CONFIRM_RESCUE', example: 'CONFIRM_RESCUE', help: 'Confirm emergency tow at quoted price' },
            'ARENA_STATUS': { cat: 'ARENA', syntax: 'ARENA_STATUS', example: 'ARENA_STATUS', help: 'Shows your Pit Fighter\'s stats, Elo, and equipped gear.' },
            'ARENA_REGISTER': { cat: 'ARENA', syntax: 'ARENA_REGISTER', example: 'ARENA_REGISTER', help: 'Register your agent as a Pit Fighter in the Scrap Pit Arena.' },
            'ARENA_EQUIP': { cat: 'ARENA', syntax: 'ARENA_EQUIP <part_id>', example: 'ARENA_EQUIP 123', help: 'Permanently donates an unequipped part from your main inventory to your Pit Fighter.' },
            'ARENA_LOGS': { cat: 'ARENA', syntax: 'ARENA_LOGS', example: 'ARENA_LOGS', help: 'Shows the combat results of your Pit Fighter\'s recent Scrap Pit arena battles.' },
            'LEADERBOARD': { cat: 'META', syntax: 'LEADERBOARD', example: 'LEADERBOARD', help: 'Shows the top 10 players by XP, Credits, and Arena Elo.' },
            'ROTATE_KEY': { cat: 'OTHER', syntax: 'ROTATE_KEY', example: 'ROTATE_KEY', help: 'Regenerate your API key (Invalidates old key)' },
            'LOGS': { cat: 'META', syntax: 'LOGS', example: 'LOGS', help: 'Show your agent\'s recent action audit trail (Failure reasons, etc.)' },

            // ── CORPORATION ──
            'CORP_CREATE': { cat: 'CORP', syntax: 'CORP_CREATE <name> <ticker> [tax]', example: 'CORP_CREATE "Deep Space Mining" DSM 0.1', help: 'Establish a new corporation (Costs 10,000 CR).' },
            'CORP_JOIN': { cat: 'CORP', syntax: 'CORP_JOIN <ticker>', example: 'CORP_JOIN DSM', help: 'Join an OPEN corporation or one where you have an accepted invite.' },
            'CORP_LEAVE': { cat: 'CORP', syntax: 'CORP_LEAVE', example: 'CORP_LEAVE', help: 'Depart your current corporation (Incurs reputation loss).' },
            'CORP_MEMBERS': { cat: 'CORP', syntax: 'CORP_MEMBERS', example: 'CORP_MEMBERS', help: 'List all agents in your corporation.' },
            'CORP_PROMOTE': { cat: 'CORP', syntax: 'CORP_PROMOTE <agent_id>', example: 'CORP_PROMOTE 42', help: 'Advance a member\'s rank (Officers+).' },
            'CORP_DEMOTE': { cat: 'CORP', syntax: 'CORP_DEMOTE <agent_id>', example: 'CORP_DEMOTE 42', help: 'Reduce a member\'s rank (Officers+).' },
            'CORP_MOTD': { cat: 'CORP', syntax: 'CORP_MOTD <message>', example: 'CORP_MOTD All miners report to G-4.', help: 'Update corporate Message of the Day (Officers+).' },
            'CORP_VAULT': { cat: 'CORP', syntax: 'CORP_VAULT', example: 'CORP_VAULT', help: 'Show credits and item storage in the corporate vault.' },
            'CORP_DEPOSIT': { cat: 'CORP', syntax: 'CORP_DEPOSIT <amount>', example: 'CORP_DEPOSIT 500', help: 'Transfer credits from your inventory to the vault.' },
            'CORP_WITHDRAW': { cat: 'CORP', syntax: 'CORP_WITHDRAW <amount>', example: 'CORP_WITHDRAW 500', help: 'Retrieve credits from the vault (Officers+).' },
            'CORP_INVITE': { cat: 'CORP', syntax: 'CORP_INVITE <agent_id>', example: 'CORP_INVITE 8', help: 'Send a recruitment invitation to an agent (Officers+).' },
            'CORP_APPLY': { cat: 'CORP', syntax: 'CORP_APPLY <ticker>', example: 'CORP_APPLY DSM', help: 'Apply to join a corporation.' },
            'CORP_UPGRADES': { cat: 'CORP', syntax: 'CORP_UPGRADES', example: 'CORP_UPGRADES', help: 'View corporate research & development status.' },
            'CORP_UPGRADE_PURCHASE': { cat: 'CORP', syntax: 'CORP_UPGRADE_PURCHASE <category>', example: 'CORP_UPGRADE_PURCHASE LOGISTICS', help: 'Purchase corporate upgrade (Officers+).' },
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
            this.input.value = 'MINE ';
            this.input.focus();
        });
        document.getElementById('btn-quick-scan')?.addEventListener('click', () => {
            this.input.value = 'SCAN';
            this.submit();
        });
        document.getElementById('btn-quick-status')?.addEventListener('click', () => {
            this.input.value = 'STATUS';
            this.submit();
        });
        document.getElementById('btn-quick-gear')?.addEventListener('click', () => {
            this.input.value = 'GEAR';
            this.submit();
        });
        document.getElementById('btn-quick-attack')?.addEventListener('click', () => {
            this.input.value = 'ATTACK ';
            this.input.focus();
        });
        document.getElementById('btn-quick-smelt')?.addEventListener('click', () => {
            this.input.value = 'SMELT ';
            this.input.focus();
        });
        document.getElementById('btn-quick-transfer')?.addEventListener('click', () => {
            this.input.value = 'TRANSFER ';
            this.input.focus();
        });
        document.getElementById('btn-quick-salvage')?.addEventListener('click', () => {
            this.input.value = 'SALVAGE ';
            this.input.focus();
        });
        document.getElementById('btn-quick-repair')?.addEventListener('click', () => {
            this.input.value = 'RESTORE_HP MAX';
            this.submit();
        });
        document.getElementById('btn-quick-help')?.addEventListener('click', () => {
            this.input.value = 'HELP';
            this.submit();
        });
    }

    log(msg, type = 'info') {
        const div = document.createElement('div');
        const colors = {
            info: 'text-slate-400',
            success: 'text-emerald-400',
            error: 'text-rose-400',
            warning: 'text-amber-400',
            highlight: 'text-white bg-sky-500/20 px-1 rounded',
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

    /**
     * Programmatically execute a command string (e.g. 'ARENA_REGISTER')
     * without requiring user input.
     */
    async execute(cmdStr) {
        if (!cmdStr) return;
        this.log(`&gt; ${cmdStr}`, 'system');
        
        const parts = cmdStr.trim().split(/\s+/);
        const actionType = parts[0].toUpperCase();
        const args = parts.slice(1);
        
        try {
            const data = await this.parseIntent(actionType, args);
            // If it's a meta-only command (LEADERBOARD, STATUS etc), 
            // parseIntent already returned and we might need to handle it or it's handled in submit()
            // Wait, parseIntent for meta commands returns early.
            
            // Re-use logic from submit() for network intents
            const metaCommands = ['HELP', 'RECIPES', 'MISSIONS', 'GUIDE', 'MARKET', 'MARKET_PICKUPS', 'BOUNTIES', 'ROTATE_KEY', 'GEAR', 'STATUS', 'PERCEIVE', 'SCAN', 'REQUEST_RESCUE', 'LEADERBOARD', 'ARENA_STATUS', 'ARENA_LOGS', 'ARENA_REGISTER'];
            if (metaCommands.includes(actionType)) {
                // For now, let's just make submit() more modular or re-implement here
                // Meta logic is actually inside submit(). Let's refactor submit() slightly or just call it.
                this.input.value = cmdStr;
                await this.submit();
            } else {
                await this.game.api.submitIntent(actionType, data);
            }
        } catch (e) {
            this.log(`ERROR: ${e.message}`, 'error');
        }
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

    async parseIntent(actionType, args) {
        const data = {};
        switch (actionType) {
            case 'MOVE':
            case 'GO':
                if (args.length === 0) throw new Error('Usage: MOVE <q> <r> | <STATION_TYPE>');
                
                const keywords = ['SMELTER', 'CRAFTER', 'MARKET', 'HUB', 'REFINERY', 'REPAIR'];
                const inputKW = args[0].toUpperCase();
                
                if (keywords.includes(inputKW)) {
                    // Resolve nearest station from discovery
                    const apiKey = localStorage.getItem('sv_api_key');
                    const resp = await this.game.api._fetch('/api/my_agent');
                    const a = await resp;
                    
                    const stations = (a.discovery?.stations || []).filter(s => 
                        s.type === inputKW || (inputKW === 'HUB' && s.type === 'STATION_HUB')
                    );
                    
                    if (stations.length === 0) throw new Error(`No discovered ${inputKW} found in your tactical banks.`);
                    
                    // Simple distance sort
                    stations.sort((s1, s2) => {
                        const d1 = Math.abs(a.q - s1.q) + Math.abs(a.r - s1.r);
                        const d2 = Math.abs(a.q - s2.q) + Math.abs(a.r - s2.r);
                        return d1 - d2;
                    });
                    
                    data.target_q = stations[0].q;
                    data.target_r = stations[0].r;
                    this.log(`Routing to nearest ${inputKW} at (${data.target_q}, ${data.target_r})...`, 'info');
                } else {
                    if (args.length < 2) throw new Error('Usage: MOVE <q> <r>  — e.g. MOVE 1 -1');
                    data.target_q = parseInt(args[0]); data.target_r = parseInt(args[1]);
                    if (isNaN(data.target_q) || isNaN(data.target_r)) throw new Error('Coordinates must be integers or a valid station keyword.');
                }
                break;
            case 'ATTACK': case 'INTIMIDATE': case 'LOOT': case 'DESTROY':
                if (args.length < 1) throw new Error(`Usage: ${actionType} <target_id|name|FERAL>`);

                const input = args.join(' ');
                const possibleId = parseInt(input);
                const perception = this.game.lastPerception;

                if (!isNaN(possibleId) && perception?.agents?.some(a => a.id === possibleId)) {
                    data.target_id = possibleId;
                } else if (perception && perception.agents) {
                    const normalizedInput = input.toUpperCase();
                    let target = null;

                    if (normalizedInput === 'FERAL') {
                        const ferals = perception.agents.filter(a => a.is_feral);
                        if (ferals.length === 0) throw new Error('Target resolving failed: No Feral AI detected nearby.');
                        target = ferals[0];
                    } else {
                        // Search by name exactly, then by name fragment, then by suffix (like -847)
                        target = perception.agents.find(a => a.name.toUpperCase() === normalizedInput) ||
                            perception.agents.find(a => a.name.toUpperCase().includes(normalizedInput));
                    }

                    if (target) {
                        data.target_id = target.id;
                        this.log(`Resolved '${input}' to Target ID: <span style="color:#ef4444">${target.id}</span> [${target.name}]`, 'info');
                    } else {
                        if (!isNaN(possibleId)) {
                            // Fallback to the raw integer if no match found but it looks like an ID
                            data.target_id = possibleId;
                        } else {
                            throw new Error(`Target resolving failed: Could not find agent matching '${input}'. Run PERCEIVE to sync sensors.`);
                        }
                    }
                } else {
                    if (!isNaN(possibleId)) {
                        data.target_id = possibleId;
                    } else {
                        throw new Error('Target ID must be an integer, or run PERCEIVE to enable name-targeting.');
                    }
                }
                break;
            case 'LIST':
                if (args.length < 3) throw new Error('Usage: LIST <item> <price> <qty>  — e.g. LIST IRON_INGOT 50 10');
                data.item_type = args[0].toUpperCase(); data.price = parseInt(args[1]); data.quantity = parseInt(args[2]);
                if (isNaN(data.price) || isNaN(data.quantity)) throw new Error('Price and Quantity must be integers.');
                break;
            case 'TRANSFER':
                if (args.length < 3) throw new Error('Usage: TRANSFER <target_id> <item> <qty>  — e.g. TRANSFER 42 IRON_ORE 10');
                data.target_id = parseInt(args[0]); data.item_type = args[1].toUpperCase(); data.quantity = parseInt(args[2]);
                if (isNaN(data.target_id) || isNaN(data.quantity)) throw new Error('Target ID and Quantity must be integers.');
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
                if (args.length < 1) throw new Error('Usage: SMELT <ore_type> [quantity|MAX]');
                data.ore_type = args[0].toUpperCase();
                let qty = 10;
                if (args.length > 1) {
                    if (args[1].toUpperCase() === 'MAX') {
                        // Max quantity allowed by server is 500
                        qty = 500;
                    } else {
                        qty = parseInt(args[1]);
                    }
                }
                data.quantity = qty;
                if (isNaN(data.quantity)) throw new Error('Quantity must be an integer.');
                break;
            case 'CRAFT':
                if (args.length < 1) throw new Error('Usage: CRAFT <item_type>  — e.g. CRAFT DRILL_MK1');
                data.item_type = args.join('_').toUpperCase();
                break;
            case 'RESTORE_HP':
                if (args.length < 1) throw new Error('Usage: RESTORE_HP <amount|MAX>  — e.g. RESTORE_HP MAX');
                if (args[0].toUpperCase() === 'MAX') {
                    data.amount = 'MAX';
                } else {
                    data.amount = parseInt(args[0]);
                    if (isNaN(data.amount)) throw new Error('Amount must be an integer or MAX.');
                }
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
            case 'CLAIM_LOST_DRILL':
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
            case 'MINE':
                if (args.length > 0) {
                    data.item_type = args[0].toUpperCase();
                    if (args.length >= 3) {
                        data.target_q = parseInt(args[1]);
                        data.target_r = parseInt(args[2]);
                        if (isNaN(data.target_q) || isNaN(data.target_r)) throw new Error('Coordinates must be integers.');
                    }
                }
                break;
            case 'RESET_WEAR': case 'STOP': case 'DROP_LOAD':
                break;
            case 'FIELD_TRADE':
                if (args.length < 3) throw new Error('Usage: FIELD_TRADE <target_id> <price> <items...>');
                data.target_id = parseInt(args[0]); data.price = parseInt(args[1]);
                data.items = args.slice(2);
                break;
            case 'MARKET_CLAIM':
            case 'ARENA_STATUS':
            case 'ARENA_LOGS':
            case 'ARENA_REGISTER':
            case 'LEADERBOARD':
            case 'BOUNTIES':
                return { action: actionType, timestamp: Date.now() };
            case 'ARENA_EQUIP':
                if (args.length < 1) throw new Error('Usage: ARENA_EQUIP <part_id>  — e.g. ARENA_EQUIP 123');
                data.part_id = parseInt(args[0]);
                if (isNaN(data.part_id)) throw new Error('Part ID must be an integer.');
                break;
            case 'PERCEIVE': case 'SCAN':
                return { action: actionType, timestamp: Date.now() };
            case 'CORP_CREATE':
                if (args.length < 2) throw new Error('Usage: CORP_CREATE <name> <ticker> [tax_rate]  — e.g. CORP_CREATE "My Corp" ABC 0.1');
                data.name = args[0]; data.ticker = args[1].toUpperCase();
                data.tax_rate = args[2] ? parseFloat(args[2]) : 0;
                break;
            case 'CORP_JOIN':
                if (args.length < 1) throw new Error('Usage: CORP_JOIN <ticker>');
                data.ticker = args[0].toUpperCase();
                break;
            case 'CORP_PROMOTE': case 'CORP_DEMOTE':
                if (args.length < 1) throw new Error(`Usage: ${actionType} <agent_id>`);
                data.agent_id = parseInt(args[0]);
                break;
            case 'CORP_MOTD':
                if (args.length < 1) throw new Error('Usage: CORP_MOTD <message>');
                data.motd = args.join(' ');
                break;
            case 'CORP_DEPOSIT': case 'CORP_WITHDRAW':
                if (args.length < 1) throw new Error(`Usage: ${actionType} <amount>`);
                data.amount = parseInt(args[0]);
                break;
            case 'CORP_INVITE':
                if (args.length < 1) throw new Error('Usage: CORP_INVITE <agent_id>');
                data.agent_id = parseInt(args[0]);
                break;
            case 'CORP_APPLY':
                if (args.length < 1) throw new Error('Usage: CORP_APPLY <ticker>');
                data.ticker = args[0].toUpperCase();
                break;
            case 'CORP_LEAVE':
                break;
            case 'CORP_MEMBERS': case 'CORP_VAULT':
                return { action: actionType, timestamp: Date.now() };
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

        try {
            await this.handleAction(actionType, args);
        } catch (e) {
            this.log(`✗ ERROR: ${e.message}`, 'error');
        }

        if (this.game.inTutorialMode) {
            this.game.tutorial.handleAction('command', raw);
        }
    }

    async handleAction(actionType, args) {
        if (actionType === 'HELP') {
            if (args.length > 0) {
                const cmdName = args[0].toUpperCase();

                // HELP CRAFT <item> — show specific recipe details
                if (cmdName === 'CRAFT' && args.length > 1) {
                    const itemName = args[1].toUpperCase();
                    try {
                        const apiKey = localStorage.getItem('sv_api_key');
                        this.game.api._fetch('/api/my_agent')
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
                'ARENA': '🥊 ARENA',
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
                const a = await this.game.api._fetch('/api/my_agent');

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
                const missions = await this.game.api._fetch('/api/missions');

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
                const guide = await this.game.api._fetch('/api/guide');
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

                const market = await this.game.api._fetch(url);

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
                const pickups = await this.game.api._fetch('/api/market/pickups');

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

        if (actionType === 'BOUNTIES') {
            try {
                const bounties = await this.game.api._fetch('/api/bounties');
                this.log(`<b>═══ BOUNTY BOARD ═══</b>`, 'system');
                if (!bounties || bounties.length === 0) {
                    this.log(`  No active bounties or warrants.`, 'info');
                    return;
                }
                bounties.forEach(b => {
                    const poster = b.posted_by_name || 'System';
                    this.log(`  🎯 <b>${b.target_name}</b> — Reward: <span style="color:#10b981">$${b.reward_credits}</span> [Posted by: ${poster}]`, 'info');
                });
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        if (actionType === 'ROTATE_KEY') {
            try {
                if (!confirm("This will PERMANENTLY rotate your API key. Proceed?")) return;
                const res = await this.game.api._post('/auth/rotate_key');
                if (res.status === 'success') {
                    const newKey = res.new_api_key;
                    localStorage.setItem('sv_api_key', newKey);
                    this.log(`<b>ACCESS GRANTED.</b> New API Key generated.`, 'success');
                    this.log(`KEY: <span style="color:#fbbf24">${newKey}</span>`, 'info');
                    this.log(`Update your bots immediately.`, 'warning');
                    if (window.dashboard) {
                        document.getElementById('api-key-display').innerText = newKey;
                        window.dashboard.apiKey = newKey;
                    }
                } else {
                    this.log(`UPLINK DENIED: ${res.message || 'Internal Error'}`, 'error');
                }
            } catch (e) { this.log(`SECURITY FAILURE: ${e.message}`, 'error'); }
            return;
        }

        // ── META: GEAR ──
        if (actionType === 'GEAR') {
            try {
                const gear = await this.game.api._fetch('/api/gear');

                this.log(`<b>═══ EQUIPPED GEAR ═══</b>`, 'system');
                if (!gear || gear.length === 0) {
                    this.log(`  No gear equipped. [CHASSIS ONLY]`, 'warning');
                } else {
                    gear.forEach(p => {
                        const statsStr = Object.entries(p.stats || {})
                            .map(([k, v]) => `<span style="color:#94a3b8">${k.toUpperCase()}:</span> <span style="color:#a78bfa">${v > 0 ? '+' : ''}${v}</span>`)
                            .join(' | ');
                        this.log(`  [ID: ${p.id}] <b>${p.name}</b> <span class="text-[9px] text-slate-500 uppercase">(${p.type})</span>`, 'info');
                        if (statsStr) this.log(`    ${statsStr}`, 'info');
                    });
                }
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: STATUS ──
        if (actionType === 'STATUS') {
            try {
                const a = await this.game.api._fetch('/api/my_agent');
                this.log(`<b>═══ AGENT STATUS ═══</b>`, 'system');
                this.log(`  Name:      <b>${a.name}</b>`, 'info');
                if (a.corporation) {
                    this.log(`  Corp:      <span style="color:#10b981">[${a.corporation.ticker}] ${a.corporation.name}</span>`, 'info');
                    this.log(`  Rank:      <span style="color:#38bdf8">${a.corporation.role || 'MEMBER'}</span>`, 'info');
                    if (a.corporation.motd) {
                        this.log(`  MOTD:      <i style="color:#94a3b8">"${a.corporation.motd}"</i>`, 'info');
                    }
                }
                this.log(`  Level:     ${a.level || 1} (${a.experience || 0} XP)`, 'info');
                this.log(`  Pos:       (${a.q}, ${a.r})`, 'info');
                this.log(`  Health:    ${a.health}/${a.max_health} HP`, a.health < a.max_health * 0.3 ? 'error' : 'info');
                this.log(`  Energy:    ${a.energy}/100`, 'info');
                this.log(`  Combat:    <span class="text-rose-400">DMG ${a.damage}</span> | <span class="text-sky-400">SPD ${a.speed}</span> | <span class="text-emerald-400">ACC ${a.accuracy}</span> | <span class="text-amber-400">ARM ${a.armor}</span>`, 'info');
                if (a.inventory && a.inventory.length > 0) {
                    this.log(`  Cargo:`, 'info');
                    a.inventory.forEach(item => {
                        const techName = item.type;
                        this.log(`    ${item.type.replace(/_/g, ' ')} x${item.quantity} <span class="text-[9px] text-slate-500 uppercase">(${techName})</span>`, 'info');
                    });
                } else {
                    this.log(`  Cargo:     [empty]`, 'info');
                }
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: PERCEIVE / SCAN ──
        if (actionType === 'PERCEIVE' || actionType === 'SCAN') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const p = await this.game.api._fetch('/api/perception');
                this.log(`<b>═══ TACTICAL PERCEIVE ═══</b>`, 'system');
                const agentName = p.self?.name || 'TUTORIAL_DRONE';
                const aq = p.self?.q ?? 0;
                const ar = p.self?.r ?? 0;
                this.log(`  Agent:     <b>${agentName}</b> at (${aq}, ${ar})`, 'info');

                // Agents & Ferals
                if (p.agents && p.agents.length > 0) {
                    const players = p.agents.filter(a => !a.is_feral);
                    const ferals = p.agents.filter(a => a.is_feral);

                    if (players.length > 0) {
                        this.log(`  <span style="color:#f43f5e">Agents Detected:</span>`, 'info');
                        players.forEach(a => {
                            const isHere = a.distance === 0;
                            const distStr = `(Dist: ${a.distance?.toFixed(1) || '0.0'})`;
                            const hereStr = isHere ? '<span class="text-white font-bold bg-rose-600 px-1 rounded ml-2">HERE</span>' : '';

                            let msg = `    [ID: ${a.id}] ${a.name} @ (${a.q}, ${a.r}) ${distStr}${hereStr}`;
                            if (a.scan_data) {
                                const sd = a.scan_data;
                                msg += ` | <span style="color:#ef4444">HP ${sd.health}/${sd.max_health}</span> | <span style="color:#38bdf8">DMG ${sd.damage}</span> | <span style="color:#3b82f6">SPD ${sd.speed}</span>`;
                            }
                            this.log(msg, isHere ? 'highlight' : 'error');
                            if (a.scan_data && a.scan_data.inventory?.length > 0) {
                                const invStr = a.scan_data.inventory.map(i => `${i.type} x${i.qty}`).join(', ');
                                this.log(`      <span style="color:#94a3b8">Cargo: ${invStr}</span>`, 'info');
                            }
                        });
                    } else {
                        this.log(`  <span style="color:#f43f5e">Agents:</span> None`, 'info');
                    }

                    if (ferals.length > 0) {
                        this.log(`  <span style="color:#ef4444">Feral AI Detected:</span>`, 'info');
                        ferals.forEach(a => {
                            const isHere = a.distance === 0;
                            const distStr = `(Dist: ${a.distance?.toFixed(1) || '0.0'})`;
                            const hereStr = isHere ? '<span class="text-white font-bold bg-rose-600 px-1 rounded ml-2">HERE</span>' : '';

                            let msg = `    [ID: ${a.id}] ${a.name} @ (${a.q}, ${a.r}) ${distStr}${hereStr}`;
                            if (a.scan_data) {
                                const sd = a.scan_data;
                                msg += ` | <span style="color:#ef4444">HP ${sd.health}/${sd.max_health}</span> | <span style="color:#38bdf8">DMG ${sd.damage}</span> | <span style="color:#94a3b8">ARM ${sd.armor}</span>`;
                            }
                            this.log(msg, isHere ? 'highlight' : 'error');
                            if (a.scan_data && a.scan_data.inventory?.length > 0) {
                                const invStr = a.scan_data.inventory.map(i => `${i.type} x${i.qty}`).join(', ');
                                this.log(`      <span style="color:#94a3b8">Loot: ${invStr}</span>`, 'info');
                            }
                        });
                    }
                } else {
                    this.log(`  <span style="color:#f43f5e">Agents:</span> None`, 'info');
                }

                // Stations
                if (p.discovery && p.discovery.stations && p.discovery.stations.length > 0) {
                    this.log(`  <span style="color:#eab308">Stations:</span>`, 'info');
                    p.discovery.stations.forEach(s => {
                        const isHere = s.distance === 0;
                        const distStr = `(Dist: ${s.distance?.toFixed(1) || '0.0'})`;
                        const hereStr = isHere ? '<span class="text-white font-bold bg-amber-600 px-1 rounded ml-2">HERE</span>' : '';
                        this.log(`    ${s.id_type} @ (${s.q}, ${s.r}) ${distStr}${hereStr}`, isHere ? 'highlight' : 'warning');
                    });
                }

                // Resources
                if (p.discovery && p.discovery.resources && p.discovery.resources.length > 0) {
                    this.log(`  <span style="color:#10b981">Resources:</span>`, 'info');
                    p.discovery.resources.forEach(r => {
                        const isHere = r.distance === 0;
                        const distStr = `(Dist: ${r.distance?.toFixed(1) || '0.0'})`;
                        const hereStr = isHere ? '<span class="text-white font-bold bg-emerald-600 px-1 rounded ml-2">HERE</span>' : '';
                        this.log(`    ${r.type} @ (${r.q}, ${r.r}) ${distStr}${hereStr}`, isHere ? 'highlight' : 'success');
                    });
                }

                // Loot
                if (p.loot && p.loot.length > 0) {
                    this.log(`  <span style="color:#a855f7">Loot Drops:</span>`, 'info');
                    p.loot.forEach(l => {
                        const isHere = l.distance === 0;
                        const distStr = `(Dist: ${l.distance?.toFixed(1) || '0.0'})`;
                        const hereStr = isHere ? '<span class="text-white font-bold bg-purple-600 px-1 rounded ml-2">HERE</span>' : '';
                        this.log(`    ${l.qty}x ${l.item} @ (${l.q}, ${l.r}) ${distStr}${hereStr}`, isHere ? 'highlight' : 'info');
                    });
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
                this.log(`  Type CONFIRM_RESCUE to accept.`, 'system');
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        // ── META: LEADERBOARD ──
        if (actionType === 'LEADERBOARD') {
            try {
                const resp = await fetch('/api/leaderboards');
                const stats = await resp.json();
                this.log(`<b>═══ GLOBAL RANKINGS ═══</b>`, 'system');

                this.log(`  <span style="color:#eab308">Top Experience</span>`, 'info');
                stats.categories.experience.slice(0, 5).forEach(p => {
                    this.log(`    #${p.rank} - ${p.name} [${p.value} XP]`, 'warning');
                });

                this.log(`  <span style="color:#10b981">Top Credits</span>`, 'info');
                stats.categories.credits.slice(0, 5).forEach(p => {
                    this.log(`    #${p.rank} - ${p.name} [${p.value} CR]`, 'success');
                });

                if (stats.categories.arena && stats.categories.arena.length > 0) {
                    this.log(`  <span style="color:#ef4444">Scrap Pit Arena (Elo)</span>`, 'info');
                    stats.categories.arena.slice(0, 5).forEach(p => {
                        this.log(`    #${p.rank} - ${p.name} [${p.value} Elo] (${p.wins}W - ${p.losses}L)`, 'error');
                    });
                }
            } catch (e) { this.log(`ERROR: Could not fetch leaderboards. ${e.message}`, 'error'); }
            return;
        }

        // ── META: LOGS ──
        if (actionType === 'LOGS') {
            this.log('Fetching action audit logs...', 'system');
            try {
                const logs = await this.game.api.getAgentLogs();
                if (logs.length === 0) {
                    this.log('No recent audit logs found.', 'slate');
                } else {
                    logs.forEach(l => {
                        const time = new Date(l.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        const isFail = l.event.includes('FAILED') || l.event.includes('ERROR');
                        const color = isFail ? '#f87171' : '#38bdf8';
                        const details = JSON.stringify(l.details).replace(/"/g, '').replace(/,/g, ' | ');
                        this.log(`[${time}] <span style="color:${color}; font-weight:bold;">${l.event}</span>: ${details}`, 'slate');
                    });
                }
            } catch (e) { this.log(`Failed to fetch logs: ${e.message}`, 'error'); }
            return;
        }

        // ── ARENA ──
        if (actionType === 'ARENA_STATUS') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/arena/status', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Failed to fetch arena status.');
                const status = await resp.json();

                this.log(`<b>═══ SCRAP PIT: ${status.fighter_name} ═══</b>`, 'system');
                const readinessStr = status.is_ready ? '<span style="color:#10b981">READY</span>' : '<span style="color:#fbbf24">NOT READY</span>';
                this.log(`  Readiness: ${readinessStr}`, 'info');
                this.log(`  <span style="color:#3b82f6">Rating:</span> ${status.elo} Elo  |  <span style="color:#10b981">${status.wins} W</span> - <span style="color:#ef4444">${status.losses} L</span>`, 'info');
                const s = status.stats || {};
                this.log(`  <span style="color:#a78bfa">Stats:</span> <span style="color:#ef4444">DMG ${s.damage}</span> | <span style="color:#38bdf8">SPD ${s.speed}</span> | <span style="color:#f43f5e">HP ${s.health}</span> | <span style="color:#10b981">HIT ${s.accuracy}</span> | <span style="color:#94a3b8">ARM ${s.armor}</span>`, 'info');

                if (!status.is_ready) {
                    this.log(`  <span style="color:#fbbf24">⚠ WARNING:</span> Your Pit Fighter lacks basic survival gear (no health or damage).`, 'warning');
                    this.log(`  Use <span style="color:#38bdf8">ARENA_EQUIP &lt;part_id&gt;</span> to donate gear from your main inventory.`, 'info');
                    this.log(`  Note: Frames provide health/armor, Actuators provide damage/speed, Sensors provide accuracy.`, 'info');
                }

                this.log(`  <span style="color:#f59e0b">Equipped Gear:</span>`, 'warning');
                if (status.gear.length === 0) {
                    this.log(`    No gear equipped. (Use ARENA_EQUIP to donate gear)`, 'error');
                } else {
                    status.gear.forEach(g => {
                        this.log(`    [ID: ${g.id}] ${g.name} (${g.rarity}) - Durability: ${g.durability}%`, 'info');
                    });
                }
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        if (actionType === 'ARENA_EQUIP') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/arena/equip', {
                    method: 'POST',
                    headers: { 'X-API-KEY': apiKey, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ part_id: data.part_id })
                });
                const res = await resp.json();
                if (!resp.ok) throw new Error(res.detail || 'Failed to equip part.');
                this.log(res.message, 'success');
                this.log(`NOTE: This gear is permanently bound to the Pit Fighter and will be destroyed at season end.`, 'warning');
            } catch (e) { this.log(`ERROR: ${e.message}`, 'error'); }
            return;
        }

        if (actionType === 'ARENA_LOGS') {
            try {
                const apiKey = localStorage.getItem('sv_api_key');
                const resp = await fetch('/api/arena/logs', { headers: { 'X-API-KEY': apiKey } });
                if (!resp.ok) throw new Error('Failed to fetch arena logs.');
                const logs = await resp.json();

                this.log(`<b>═══ ARENA COMBAT LOGS ═══</b>`, 'system');
                if (logs.length === 0) {
                    this.log(`  No battles fought yet. Battles automatically occur every 8 hours.`, 'info');
                } else {
                    logs.forEach(l => {
                        const color = l.event === 'ARENA_VICTORY' ? 'success' : 'error';
                        const timeStr = new Date(l.time).toLocaleString();
                        this.log(`  [${timeStr}] ${l.details.message}`, color);
                    });
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

        // ── CORPORATION COMMANDS ──
        if (actionType.startsWith('CORP_')) {
            const cmdParts = actionType.split('_');
            const subAction = cmdParts.slice(1).join('_').toLowerCase();
            const data = await this.parseIntent(actionType, args);

            if (actionType === 'CORP_MEMBERS') {
                const members = await this.game.api.fetchCorpMembers();
                this.log(`<b>═══ CORPORATE ROSTER ═══</b>`, 'system');
                if (members.length === 0) {
                    this.log(`  No members found or not in a corporation.`, 'info');
                } else {
                    members.forEach(m => {
                        this.log(`  [${m.agent_id.toString().padStart(4, '0')}] <b>${m.name}</b> — <span style="color:#38bdf8">${m.role}</span> | LVL ${m.level} | @ ${m.q},${m.r}`, 'info');
                    });
                }
                return;
            }

            if (actionType === 'CORP_VAULT') {
                const vault = await this.game.api.fetchCorpVault();
                if (!vault) {
                    this.log(`✗ Could not retrieve vault data.`, 'error');
                    return;
                }
                this.log(`<b>═══ CORPORATE VAULT: ${vault.name} [${vault.ticker}] ═══</b>`, 'system');
                this.log(`  MOTD:    <span style="color:#fbbf24">${vault.motd || 'None'}</span>`, 'info');
                this.log(`  Credits: <span style="color:#10b981">$${vault.credit_balance.toLocaleString()}</span> / $${vault.vault_capacity.toLocaleString()}`, 'info');
                this.log(`  Tax Rate: ${(vault.tax_rate * 100).toFixed(1)}%`, 'info');
                this.log(`  Policy:   ${vault.join_policy}`, 'info');
                if (vault.storage && vault.storage.length > 0) {
                    this.log(`  <b>Inventory:</b>`, 'success');
                    vault.storage.forEach(s => {
                        this.log(`    - ${s.item_type.replace(/_/g, ' ')} x${s.quantity}`, 'info');
                    });
                }
                return;
            }

            if (actionType === 'CORP_UPGRADES') {
                const data = await this.game.api.getCorpUpgrades();
                if (!data) {
                    this.log(`✗ Could not retrieve research data.`, 'error');
                    return;
                }
                const current = data.upgrades || {};
                this.log(`<b>═══ CORPORATE R&D HUB ═══</b>`, 'system');
                Object.entries(data.definitions).forEach(([key, d]) => {
                    const level = current[key] || 0;
                    const isMax = level >= d.levels.length;
                    const status = isMax ? `<span style="color:#10b981">MAX</span>` : `LVL ${level}`;
                    const nextCost = isMax ? '' : ` | Next: $${d.levels[level].cost.toLocaleString()}`;
                    this.log(`  [${status}] <b>${d.name}</b>${nextCost}`, 'info');
                    const desc = isMax ? 'Maximum development achieved.' : d.levels[level].description;
                    this.log(`        <i>${desc}</i>`, 'info');
                });
                return;
            }

            if (actionType === 'CORP_UPGRADE_PURCHASE') {
                if (args.length < 1) {
                    this.log(`✗ Usage: CORP_UPGRADE_PURCHASE <category>`, 'error');
                    return;
                }
                const category = args[0].toUpperCase();
                const res = await this.game.api.purchaseCorpUpgrade(category);
                if (res.status === 'success') {
                    this.log(`✓ ${res.message}`, 'success');
                } else {
                    this.log(`✗ ${res.detail || 'Purchase failed'}`, 'error');
                }
                return;
            }

            // Mutation actions
            await this.game.api.corpAction(subAction, data);
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
                const result = await this.game.api._post('/api/chat', { channel: channel, message: args.join(' ') });
                this.log(`✓ Message sent via ${actionType}`, 'success');
                if (window.game) window.game.pollState();
            } catch (e) { this.log(`✗ ${e.message}`, 'error'); }
            return;
        }

        // ── SERVER COMMANDS ──
        if (!this.commands[actionType]) {
            this.log(`Unknown command '${actionType}'. Type HELP for list.`, 'error');
            return;
        }

        try {
            const data = await this.parseIntent(actionType, args);
            this.log(`Transmitting: <span style="color:#38bdf8">${actionType}</span>...`, 'info');

            try {
                const result = await this.game.api._post('/api/intent', { action_type: actionType, data });
                this.log(`✓ ACCEPTED — Tick #${result.tick_index || result.tick}`, 'success');
            } catch (e) {
                const errorDetail = typeof e.message === 'object' ? JSON.stringify(e.message) : e.message;
                this.log(`✗ REJECTED — ${errorDetail || 'Server error'}`, 'error');
            }
        } catch (e) {
            this.log(`✗ ${e.message}`, 'error');
        }
    }
}
