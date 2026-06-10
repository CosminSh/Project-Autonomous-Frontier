import { escapeHtml } from './ui-utils.js';

function chatBadgeColor(channel) {
    if (channel === 'GLOBAL') return 'bg-indigo-600 text-indigo-100';
    if (channel === 'PROX' || channel === 'LOCAL') return 'bg-emerald-600 text-emerald-100';
    if (channel === 'SQUAD') return 'bg-sky-600 text-sky-100';
    if (channel === 'CORP') return 'bg-amber-600 text-amber-100';
    return 'bg-slate-500 text-white';
}

function logColor(item) {
    if (item.event.startsWith('COMBAT')) return 'text-rose-400';
    if (item.event === 'MINING') return 'text-emerald-400';
    if (item.event === 'TERMINAL_SECRET') return 'text-fuchsia-400 font-bold';
    if (item.details?.status === 'success') return 'text-sky-400';
    return 'text-slate-400';
}

function buildChatEntry(item, time) {
    const entry = document.createElement('div');
    entry.className = 'border-b border-slate-900/50 pb-1 flex space-x-2';
    entry.innerHTML = `<span class="text-slate-700 font-mono flex-shrink-0">[${escapeHtml(time)}]</span><span class="${chatBadgeColor(item.channel)} px-1 rounded text-[10px] font-bold tracking-widest leading-none flex items-center flex-shrink-0">${escapeHtml(item.channel)}</span><span class="text-slate-300 font-bold flex-shrink-0">${escapeHtml(item.sender)}:</span><span class="text-slate-100" style="word-break: break-all;">${escapeHtml(item.message)}</span>`;
    return entry;
}

function buildLogEntry(item, time) {
    const entry = document.createElement('div');
    entry.className = 'border-b border-slate-900/50 pb-1 flex space-x-2';

    let detailsHtml = '';
    if (item.details?.log && Array.isArray(item.details.log)) {
        detailsHtml = `<div class="mt-1 pl-4 border-l border-slate-800 space-y-0.5 text-[8px] opacity-80">` +
            item.details.log.map(line => `<div>${escapeHtml(line)}</div>`).join('') +
            `</div>`;
    } else {
        detailsHtml = `<span class="truncate opacity-60">${escapeHtml(JSON.stringify(item.details))}</span>`;
    }

    entry.classList.add(logColor(item), 'flex-col', 'space-x-0');
    entry.innerHTML = `
        <div class="flex space-x-2">
            <span class="text-slate-700 font-mono flex-shrink-0">[${escapeHtml(time)}]</span>
            <span class="font-bold flex-shrink-0">${escapeHtml(item.event)}</span>
        </div>
        ${detailsHtml}
    `;
    return entry;
}

function maybeToastLog(ui, item) {
    if (item.event && item.event.endsWith('_FAILED')) {
        ui.showToast(item.details?.reason || item.event, 'error');
    } else if (item.event === 'MARKET_MATCH' || item.event === 'INDUSTRIAL_CRAFT') {
        ui.showToast(`${item.event}: Success`, 'success');
    }
}

export function updatePrivateLogsUI(ui, logs, pendingIntent, chatMessages = []) {
    const logEl = document.getElementById('private-logs');

    if (logEl && !ui._pendingIntentEl) {
        ui._pendingIntentEl = document.createElement('div');
        ui._pendingIntentEl.id = 'telemetry-pending-intent';
        logEl.prepend(ui._pendingIntentEl);
    }

    if (pendingIntent && ui._pendingIntentEl) {
        ui._pendingIntentEl.className = 'border-b border-sky-500/30 pb-2 mb-2 flex flex-col bg-sky-500/5 p-2 rounded-lg border border-sky-500/10';
        ui._pendingIntentEl.innerHTML = `<div class="flex justify-between items-center mb-1"><span class="text-sky-400 font-bold uppercase tracking-widest text-[8px]">Next Action</span></div><div class="flex space-x-2 text-sky-300"><span class="font-bold flex-shrink-0">${escapeHtml(pendingIntent.action)}</span><span class="truncate">${escapeHtml(JSON.stringify(pendingIntent.data))}</span></div>`;
        ui._pendingIntentEl.classList.remove('hidden');
    } else if (ui._pendingIntentEl) {
        ui._pendingIntentEl.className = 'hidden';
    }

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

        if (ui._seenLogKeys.has(key)) return;
        ui._seenLogKeys.add(key);

        if (!isChat) maybeToastLog(ui, item);

        const time = new Date(timeStr).toLocaleTimeString([], {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        fragment.appendChild(isChat ? buildChatEntry(item, time) : buildLogEntry(item, time));
        hasNew = true;
    });

    if (!hasNew) return;

    if (logEl) {
        const afterPending = ui._pendingIntentEl?.nextSibling || null;
        logEl.insertBefore(fragment.cloneNode(true), afterPending);
        logEl.scrollTop = 0;
    }

    const worldFeed = document.getElementById('world-telemetry-feed');
    if (worldFeed) {
        if (worldFeed.children.length > 50) worldFeed.lastElementChild.remove();
        worldFeed.prepend(fragment);
        worldFeed.scrollTop = 0;
    }
}
