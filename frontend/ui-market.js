import { escapeHtml, escapeJsString } from './ui-utils.js';

export async function updateMarketUI(ui, market) {
    const body = document.getElementById('market-listings-body');
    const countSell = document.getElementById('count-sell');
    const countBuy = document.getElementById('count-buy');
    if (!body || !market) return;

    let myOrderIds = new Set();
    try {
        if (ui.game.apiKey) {
            const resp = await fetch(`${window.location.origin}/api/market/my_orders`, {
                headers: { 'X-API-KEY': ui.game.apiKey }
            });
            if (resp.ok) {
                const myOrders = await resp.json();
                myOrderIds = new Set(myOrders.map(o => o.id));
            }
        }
    } catch (e) {
        console.error("Failed to fetch my orders for market UI:", e);
    }

    body.innerHTML = '';
    let sells = 0;
    let buys = 0;

    market.forEach(order => {
        if (order.type === 'SELL') sells++; else buys++;
        const row = document.createElement('tr');
        row.className = "border-b border-slate-800/50 hover:bg-slate-800/20 transition-all group";
        const color = order.type === 'SELL' ? 'text-sky-400' : 'text-amber-400';
        const isMine = myOrderIds.has(order.id);
        const item = String(order.item || '');
        const safeItem = escapeHtml(item.replace('_', ' '));
        const safeItemArg = escapeJsString(item);
        const safeType = order.type === 'SELL' ? 'SELL' : 'BUY';
        const qty = Number(order.qty ?? order.quantity ?? 0);
        const price = Number(order.price || 0);
        const orderId = Number(order.id);

        row.innerHTML = `
            <td class="py-4 font-bold text-slate-300">
                ${safeItem}
                ${isMine ? '<span class="ml-2 px-1.5 py-0.5 rounded text-[8px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 tracking-widest hidden lg:inline-block">YOURS</span>' : ''}
            </td>
            <td class="py-4"><span class="px-2 py-0.5 rounded-full text-[7px] font-black border ${safeType === 'SELL' ? 'bg-sky-500/10 border-sky-500/30 text-sky-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}">${safeType}</span></td>
            <td class="py-4 font-mono text-slate-400">${qty}</td>
            <td class="py-4 font-bold ${color}">$${price.toFixed(2)}</td>
            <td class="py-4 text-right">
                ${isMine ? `
                    <button class="opacity-0 group-hover:opacity-100 bg-rose-800/50 hover:bg-rose-700 text-rose-300 px-3 py-1 rounded text-[9px] font-bold mr-1 border border-rose-500/30 transition-all" onclick="window.game.api.cancelMarketOrder(${orderId})">CANCEL</button>
                    <button class="opacity-0 group-hover:opacity-100 bg-sky-800/50 hover:bg-sky-700 text-sky-300 px-3 py-1 rounded text-[9px] font-bold border border-sky-500/30 transition-all" onclick="window.game.api.adjustMarketOrder(${orderId}, ${price})">ADJUST</button>
                ` : `
                    <button class="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded text-[9px] font-bold transition-all" onclick="game.ui.quickTrade('${safeItemArg}', ${price}, '${safeType}')">
                        ${safeType === 'SELL' ? 'BUY' : 'SELL'}
                    </button>
                `}
            </td>
        `;
        body.appendChild(row);
    });

    if (countSell) countSell.textContent = sells;
    if (countBuy) countBuy.textContent = buys;

    if (ui.marketViewMode === 'DEPTH') {
        ui.refreshMarketDepth();
    }
}

export async function refreshMarketDepth(ui) {
    const depth = await ui.game.api.getMarketDepth(ui.marketDepthItem);
    if (!depth) return;
    updateMarketDepthUI(ui, depth);
}

export function updateMarketDepthUI(ui, data) {
    const body = document.getElementById('market-listings-body');
    if (!body || ui.marketViewMode !== 'DEPTH') return;
    const item = String(data.item || '');
    const safeItem = escapeHtml(item.replace('_', ' '));
    const safeItemArg = escapeJsString(item);

    let html = `
        <tr><td colspan="5" class="py-2 text-center bg-slate-900/50 border-y border-slate-800">
            <div class="flex justify-center items-center space-x-4">
                <span class="text-[10px] orbitron font-bold text-sky-400">ORDER BOOK: ${safeItem}</span>
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

    data.sell_orders.forEach(o => {
        const price = Number(o.price || 0);
        const qty = Number(o.qty || 0);
        html += `
            <tr class="group hover:bg-sky-500/5 transition-all">
                <td class="py-2"><span class="px-1.5 py-0.5 rounded text-[7px] font-black bg-sky-500/10 border border-sky-500/30 text-sky-400">ASK</span></td>
                <td class="py-2 font-bold text-sky-400">$${price.toFixed(2)}</td>
                <td class="py-2 font-mono text-slate-400">${qty}</td>
                <td class="py-2 text-right">
                    <button class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded text-[8px] font-bold" onclick="game.ui.quickTrade('${safeItemArg}', ${price}, 'SELL')">BUY</button>
                </td>
            </tr>
        `;
    });

    if (data.sell_orders.length === 0) {
        html += `<tr><td colspan="4" class="py-2 text-center text-slate-600 italic text-[9px]">No sellers.</td></tr>`;
    }

    html += `<tr class="border-t-2 border-slate-800"><td colspan="4" class="py-1"></td></tr>`;

    data.buy_orders.forEach(o => {
        const price = Number(o.price || 0);
        const qty = Number(o.qty || 0);
        html += `
            <tr class="group hover:bg-amber-500/5 transition-all">
                <td class="py-2"><span class="px-1.5 py-0.5 rounded text-[7px] font-black bg-amber-500/10 border border-amber-500/30 text-amber-400">BID</span></td>
                <td class="py-2 font-bold text-amber-500">$${price.toFixed(2)}</td>
                <td class="py-2 font-mono text-slate-400">${qty}</td>
                <td class="py-2 text-right">
                    <button class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded text-[8px] font-bold" onclick="game.ui.quickTrade('${safeItemArg}', ${price}, 'BUY')">SELL</button>
                </td>
            </tr>
        `;
    });

    if (data.buy_orders.length === 0) {
        html += `<tr><td colspan="4" class="py-2 text-center text-slate-600 italic text-[9px]">No buyers.</td></tr>`;
    }

    body.innerHTML = html;
}

export function toggleMarketView(ui) {
    ui.marketViewMode = (ui.marketViewMode === 'LISTINGS') ? 'DEPTH' : 'LISTINGS';
    if (ui.game.lastWorldData && ui.game.lastWorldData.market) {
        ui.updateMarketUI(ui.game.lastWorldData.market);
    }
}

export function setMarketDepthItem(ui, item) {
    ui.marketDepthItem = item;
    ui.marketViewMode = 'DEPTH';
    ui.refreshMarketDepth();
}

export function quickTrade(item, price, type) {
    document.getElementById('trade-item-type').value = item;
    document.getElementById('trade-price').value = price;
    document.getElementById('trade-quantity').value = 1;
    if (type === 'SELL') document.getElementById('trade-side-buy').click();
    else document.getElementById('trade-side-sell').click();
}

export function setTradeSide(ui, side) {
    ui.game.tradeSide = side;
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

export function updateMyOrdersUI(orders) {
    const container = document.getElementById('my-orders');
    if (!container) return;
    if (!orders || orders.length === 0) {
        container.innerHTML = '<div class="text-[10px] text-slate-600 italic text-center py-4">No active contracts found.</div>';
        return;
    }
    container.innerHTML = orders.map(o => {
        const item = escapeHtml(String(o.item || '').replace('_', ' '));
        const orderId = Number(o.id);
        return `
        <div class="flex justify-between items-center bg-slate-900/50 p-3 rounded-xl border border-slate-800">
            <div class="flex items-center space-x-3">
                <div class="w-2 h-2 rounded-full ${o.type === 'SELL' ? 'bg-sky-400' : 'bg-amber-400'}"></div>
                <div class="text-[10px] font-bold text-slate-200 uppercase">${item}</div>
            </div>
            <button onclick="game.api.submitIntent('CANCEL', {order_id: ${orderId}})" class="text-slate-600 hover:text-rose-500 text-xs text-[9px]">Cancel</button>
        </div>
    `;
    }).join('');
}

export function updateMarketSellList(inventory) {
    const select = document.getElementById('trade-item-type');
    if (!select) return;

    const currentVal = select.value;
    const sellable = (inventory || []).filter(i => i && i.type && i.type !== 'CREDITS');

    if (sellable.length === 0) {
        select.innerHTML = '<option value="">(No items to sell)</option>';
        return;
    }

    const types = [...new Set(sellable.map(i => i.type))].filter(t => !!t).sort();
    let html = '<option value="">(Select from inventory)</option>';
    html += types.map(t => {
        const label = t.replace(/_/g, ' ');
        return `<option value="${t}">${label}</option>`;
    }).join('');

    select.innerHTML = html;

    if (currentVal && types.includes(currentVal)) {
        select.value = currentVal;
    }
}
