/* ── Section 1: State & Constants ─────────────────────────────── */

const API = `http://${location.hostname}:5959`;

const TAG_COLORS = {
    routine: '#8B7355', health: '#2A9D8F', finance: '#C4A265', idea: '#7C5CBF',
    career: '#4A7FB5', learning: '#3D8B6E', tech: '#5C7AEA', productivity: '#D4814A',
    spiritual: '#9B72AA', reflection: '#6B8E9B', gratitude: '#68A67D', vent: '#C75D5D',
    lesson: '#B08D57', decision: '#7B8FA1', question: '#5EAAA8', todo: '#D08C60',
    reminder: '#D47070', people: '#7E9B6E', selfhelp: '#B07AAF', travel: '#5BA0C5',
    random: '#A0998F', private_todo: '#6B6560', private_reminder: '#6B6560'
};

const TAG_LABELS = Object.keys(TAG_COLORS);

let toastTimeout = null;
const peekTimers = {};

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}


/* ── Section 2: View Switching ───────────────────────────────── */

function switchView(view) {
    document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab-btn[data-view="${view}"]`)?.classList.add('active');

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(view + 'View')?.classList.add('active');

    if (view === 'capture') {
        document.getElementById('captureInput')?.focus();
    } else if (view === 'browse') {
        try { if (typeof renderBrowseView === 'function') renderBrowseView(); } catch (_) {}
    }
}


/* ── Section 3: Word Count ───────────────────────────────────── */

function updateWordCount() {
    const { content } = getContentAndTagLine(
        document.getElementById('captureInput').value
    );
    const text = content.trim();
    const count = text ? text.split(/\s+/).filter(Boolean).length : 0;
    document.getElementById('wordCount').textContent =
        `${count} word${count !== 1 ? 's' : ''}`;
}


/* ── Section 4: Tag Chip Selection ───────────────────────────── */

function getSelectedTags() {
    return Array.from(document.querySelectorAll('.chip.selected'))
        .map(c => c.dataset.tag);
}

function toggleChipsExpand() {
    const extra = document.getElementById('chipsExtra');
    const btn = document.getElementById('chipsToggle');
    extra.classList.toggle('expanded');
    btn.textContent = extra.classList.contains('expanded')
        ? 'fewer tags' : 'more tags';
}


/* ── Section 4a: Tag Line in Textarea ─────────────────────────── */

function getContentAndTagLine(text) {
    const lines = text.split('\n');
    let lastNonEmptyIdx = -1;
    for (let i = lines.length - 1; i >= 0; i--) {
        if (lines[i].trim() !== '') { lastNonEmptyIdx = i; break; }
    }
    if (lastNonEmptyIdx < 0) return { content: '', tags: [] };

    const lastLine = lines[lastNonEmptyIdx].trim();
    const tokens = lastLine.split(/\s+/);
    const allTags = tokens.length > 0 && tokens.every(t =>
        t.startsWith('#') && TAG_LABELS.includes(t.slice(1))
    );

    if (allTags) {
        const content = lines.slice(0, lastNonEmptyIdx).join('\n').replace(/\s+$/, '');
        return { content, tags: tokens.map(t => t.slice(1)) };
    }
    return { content: text, tags: [] };
}

function appendTagToTextarea(label) {
    const textarea = document.getElementById('captureInput');
    const cursorPos = textarea.selectionStart;
    const { content, tags } = getContentAndTagLine(textarea.value);

    if (tags.includes(label)) return;
    tags.push(label);

    const tagLine = tags.map(t => `#${t}`).join(' ');
    textarea.value = content + (content ? '\n' : '') + tagLine;

    const safePos = Math.min(cursorPos, content.length);
    textarea.selectionStart = textarea.selectionEnd = safePos;
    updateWordCount();
    clearSuggestion();
}

function removeTagFromTextarea(label) {
    const textarea = document.getElementById('captureInput');
    const cursorPos = textarea.selectionStart;
    const { content, tags } = getContentAndTagLine(textarea.value);

    const idx = tags.indexOf(label);
    if (idx !== -1) tags.splice(idx, 1);

    if (tags.length > 0) {
        const tagLine = tags.map(t => `#${t}`).join(' ');
        textarea.value = content + (content ? '\n' : '') + tagLine;
    } else {
        textarea.value = content;
    }

    const safePos = Math.min(cursorPos, content.length);
    textarea.selectionStart = textarea.selectionEnd = safePos;
    updateWordCount();
    clearSuggestion();
}


/* ── Section 4b: Inline Tag Autocomplete ─────────────────────── */

let currentSuggestion = null;

function extractTagFragment(text, cursorPos) {
    const before = text.slice(0, cursorPos);
    const hashMatch = before.match(/#([a-z_]*)$/);
    if (!hashMatch) return null;

    const partial = hashMatch[1];
    const hashIndex = before.length - hashMatch[0].length;

    if (hashIndex > 0 && !/\s/.test(text[hashIndex - 1])) return null;
    if (partial.length === 0) return null;

    return { partial, hashIndex };
}

function findBestMatch(partial) {
    const selected = new Set(getSelectedTags());
    const matches = TAG_LABELS
        .filter(label => label.startsWith(partial) && !selected.has(label));
    if (matches.length === 0) return null;
    matches.sort((a, b) => a.length - b.length);
    return matches[0];
}

function updateGhostLayer() {
    const textarea = document.getElementById('captureInput');
    const ghost = document.getElementById('ghostLayer');
    if (!textarea || !ghost) return;

    const text = textarea.value;
    const cursorPos = textarea.selectionStart;

    if (textarea.selectionStart !== textarea.selectionEnd) {
        clearSuggestion();
        return;
    }

    const frag = extractTagFragment(text, cursorPos);
    if (!frag) { clearSuggestion(); return; }

    const match = findBestMatch(frag.partial);
    if (!match) { clearSuggestion(); return; }

    const completion = match.slice(frag.partial.length);
    currentSuggestion = {
        partial: frag.partial,
        full: match,
        hashIndex: frag.hashIndex,
    };

    const beforeCursor = text.slice(0, cursorPos);
    const afterCursor = text.slice(cursorPos);

    ghost.innerHTML =
        `<span class="ghost-match">${escapeHtml(beforeCursor)}</span>` +
        `<span class="ghost-completion">${escapeHtml(completion)}</span>` +
        `<span class="ghost-match">${escapeHtml(afterCursor)}</span>`;
}

function clearSuggestion() {
    currentSuggestion = null;
    const ghost = document.getElementById('ghostLayer');
    if (ghost) ghost.innerHTML = '';
}

function acceptSuggestion() {
    if (!currentSuggestion) return false;

    const { full, hashIndex } = currentSuggestion;
    const textarea = document.getElementById('captureInput');
    const text = textarea.value;
    const cursorPos = textarea.selectionStart;

    const before = text.slice(0, hashIndex).replace(/ +$/, '');
    const after = text.slice(cursorPos);
    textarea.value = before + after;
    textarea.selectionStart = textarea.selectionEnd = before.length;

    activateChipFromAutocomplete(full);
    clearSuggestion();

    return true;
}

function activateChipFromAutocomplete(label) {
    const chipEl = document.querySelector(`.chip[data-tag="${label}"]`);
    if (!chipEl) return;

    const chipsExtra = document.getElementById('chipsExtra');
    if (chipsExtra && chipsExtra.contains(chipEl) && !chipsExtra.classList.contains('expanded')) {
        chipsExtra.classList.add('expanded');
        document.getElementById('chipsToggle').textContent = 'fewer tags';
    }

    chipEl.classList.add('selected');
    chipEl.classList.add('just-activated');
    chipEl.addEventListener('animationend', () => {
        chipEl.classList.remove('just-activated');
    }, { once: true });

    appendTagToTextarea(label);
}


/* ── Section 5: Save Thought ─────────────────────────────────── */

async function saveThought() {
    const textarea = document.getElementById('captureInput');
    const { content } = getContentAndTagLine(textarea.value);
    const text = content.trim();

    if (!text) {
        const box = document.getElementById('captureBox');
        box.classList.add('shake');
        setTimeout(() => box.classList.remove('shake'), 400);
        return;
    }

    const tags = getSelectedTags();

    try {
        const res = await fetch(`${API}/api/thoughts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, tags })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Save failed');

        textarea.value = '';
        updateWordCount();
        clearSuggestion();
        document.querySelectorAll('.chip.selected').forEach(c => c.classList.remove('selected'));

        const extra = document.getElementById('chipsExtra');
        if (extra.classList.contains('expanded')) {
            extra.classList.remove('expanded');
            document.getElementById('chipsToggle').textContent = 'more tags';
        }

        const tagStr = data.thought.tags.map(t => `#${t}`).join(', ');
        showToast(`Saved — ${tagStr}`);

        textarea.focus();
        loadSidePanels();
    } catch (e) {
        showToast(`Error: ${e.message}`);
    }
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => toast.classList.remove('show'), 2400);
}


/* ── Section 6: Side Panels — Reminders & Todos ──────────────── */

function formatRelativeDate(isoString) {
    const dt = new Date(isoString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const target = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
    const diffDays = Math.round((today - target) / 86400000);

    const time = dt.toLocaleTimeString('en-US', {
        hour: 'numeric', minute: '2-digit', hour12: true
    });

    if (diffDays === 0) return `Today, ${time}`;
    if (diffDays === 1) return `Yesterday, ${time}`;
    if (diffDays > 1 && diffDays < 7) {
        return `${dt.toLocaleDateString('en-US', { weekday: 'short' })}, ${time}`;
    }
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function renderTagPills(tags, exclude) {
    return tags
        .filter(t => t !== exclude)
        .map(t => {
            const color = TAG_COLORS[t] || TAG_COLORS.random;
            return `<span class="thought-tag" style="background:${hexToRgba(color, 0.15)};color:${color}">#${escapeHtml(t)}</span>`;
        })
        .join(' ');
}

function renderReminderItem(thought) {
    return `<div class="side-item">
        <div class="side-item-time">
            ${formatRelativeDate(thought.created_at)}
            ${renderTagPills(thought.tags, 'reminder')}
        </div>
        <div class="side-item-text">${escapeHtml(thought.text)}</div>
    </div>`;
}

function renderTodoItem(thought) {
    return `<div class="side-item">
        <div class="todo-item">
            <input type="checkbox" class="todo-checkbox">
            <div>
                <div class="side-item-time">${renderTagPills(thought.tags, 'todo')}</div>
                <div class="side-item-text">${escapeHtml(thought.text)}</div>
            </div>
        </div>
    </div>`;
}

async function loadSidePanels() {
    try {
        const [remRes, privRemRes] = await Promise.all([
            fetch(`${API}/api/thoughts?tag=reminder&limit=10`),
            fetch(`${API}/api/thoughts?tag=private_reminder&limit=5`)
        ]);
        const reminders = (await remRes.json()).filter(t => !t.is_private);
        const privReminders = await privRemRes.json();

        document.getElementById('remindersWidget').innerHTML = reminders.length
            ? reminders.map(renderReminderItem).join('')
            : '<p class="empty-message">No upcoming reminders</p>';

        document.getElementById('privateReminders').innerHTML =
            privReminders.map(renderReminderItem).join('');
    } catch (_) {}

    try {
        const [todoRes, privTodoRes] = await Promise.all([
            fetch(`${API}/api/thoughts?tag=todo&limit=10`),
            fetch(`${API}/api/thoughts?tag=private_todo&limit=5`)
        ]);
        const todos = (await todoRes.json()).filter(t => !t.is_private);
        const privTodos = await privTodoRes.json();

        document.getElementById('todosWidget').innerHTML = todos.length
            ? todos.map(renderTodoItem).join('')
            : '<p class="empty-message">No open todos</p>';

        document.getElementById('privateTodos').innerHTML =
            privTodos.map(renderTodoItem).join('');
    } catch (_) {}
}


/* ── Section 7: Todo Checkbox ────────────────────────────────── */

function handleTodoCheck(e) {
    if (!e.target.matches('.todo-checkbox')) return;
    const item = e.target.closest('.todo-item');
    if (e.target.checked) {
        item.classList.add('done');
    } else {
        item.classList.remove('done');
    }
}


/* ── Section 8: Private Peek (3-second reveal) ───────────────── */

function peekPrivate(type) {
    const containerId = type === 'reminders' ? 'privateReminders' : 'privateTodos';
    const container = document.getElementById(containerId);
    const panel = container.closest('.side-panel');
    const btn = panel.querySelector('.peek-btn');
    const bar = panel.querySelector('.peek-bar');

    if (btn.classList.contains('active')) {
        clearInterval(peekTimers[type + '_i']);
        clearTimeout(peekTimers[type + '_t']);
        btn.classList.remove('active');
        btn.textContent = '\u{1F512}';
        container.classList.remove('revealed');
        bar.style.transition = 'none';
        bar.style.transform = 'scaleX(0)';
        return;
    }

    btn.classList.add('active');
    container.classList.add('revealed');

    let count = 3;
    btn.textContent = count;

    bar.style.transition = 'none';
    bar.style.transform = 'scaleX(1)';
    void bar.offsetWidth;
    bar.style.transition = 'transform 3s linear';
    bar.style.transform = 'scaleX(0)';

    peekTimers[type + '_i'] = setInterval(() => {
        count--;
        if (count > 0) btn.textContent = count;
    }, 1000);

    peekTimers[type + '_t'] = setTimeout(() => {
        clearInterval(peekTimers[type + '_i']);
        btn.classList.remove('active');
        btn.textContent = '\u{1F512}';
        container.classList.remove('revealed');
        bar.style.transition = 'none';
        bar.style.transform = 'scaleX(0)';
    }, 3000);
}


/* ── Browse: State ───────────────────────────────────────────── */

let searchDebounce = null;
let browseOffset = 0;
let browseLoading = false;
let browseHasMore = true;
let chatInitialized = false;

function escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatCardDate(isoString) {
    const dt = new Date(isoString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const target = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
    const diffDays = Math.round((today - target) / 86400000);
    const hh = String(dt.getHours()).padStart(2, '0');
    const mm = String(dt.getMinutes()).padStart(2, '0');
    const time = `${hh}:${mm}`;

    if (diffDays === 0) return `Today \u00b7 ${time}`;
    if (diffDays === 1) return `Yesterday \u00b7 ${time}`;
    const mon = dt.toLocaleDateString('en-US', { month: 'short' });
    if (dt.getFullYear() === now.getFullYear()) return `${mon} ${dt.getDate()} \u00b7 ${time}`;
    return `${mon} ${dt.getDate()}, ${dt.getFullYear()} \u00b7 ${time}`;
}

function highlightText(escapedHtml, query) {
    if (!query) return escapedHtml;
    try {
        const pat = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return escapedHtml.replace(new RegExp(`(${pat})`, 'gi'), '<mark>$1</mark>');
    } catch (_) { return escapedHtml; }
}

function getActiveFilters() {
    const tab = document.querySelector('.sub-tab.active');
    const subTab = tab ? tab.dataset.filter : 'all';
    const pills = document.querySelectorAll('.tag-pill.active-filter');
    const tags = Array.from(pills).map(p => p.dataset.tag);
    const query = (document.getElementById('searchInput')?.value || '').trim();
    return { subTab, tags, query };
}


/* ── Browse: Render orchestrator ─────────────────────────────── */

function renderBrowseView() {
    loadTagFilters();
    loadThoughts();
    loadStats();
    loadModelBadge();

    if (!chatInitialized) {
        chatInitialized = true;
        addChatMessage('assistant',
            'Ask me anything about your thoughts. I can find, summarize, and connect ideas from your entries.');
    }
}


/* ── Browse: Tag filter pills ────────────────────────────────── */

async function loadTagFilters() {
    try {
        const res = await fetch(`${API}/api/thoughts?limit=500`);
        const thoughts = await res.json();

        const counts = {};
        thoughts.forEach(t => {
            t.tags.forEach(tag => {
                if (tag === 'private_todo' || tag === 'private_reminder') return;
                counts[tag] = (counts[tag] || 0) + 1;
            });
        });

        const sorted = Object.entries(counts).sort((a, b) => {
            if (a[0] === 'random') return 1;
            if (b[0] === 'random') return -1;
            return b[1] - a[1];
        });

        const container = document.getElementById('tagFilters');
        if (!container) return;

        const active = new Set(
            Array.from(container.querySelectorAll('.tag-pill.active-filter'))
                .map(p => p.dataset.tag)
        );

        container.innerHTML = sorted.map(([tag, count]) => {
            const color = TAG_COLORS[tag] || TAG_COLORS.random;
            const cls = active.has(tag) ? ' active-filter' : '';
            return `<button class="tag-pill${cls}" data-tag="${tag}"
                style="background:${hexToRgba(color, 0.10)};color:${color}">
                ${escapeHtml(tag)} <span class="pill-count">${count}</span>
            </button>`;
        }).join('');
    } catch (_) {}
}


/* ── Browse: Load & render thoughts ──────────────────────────── */

async function loadThoughts() {
    const { subTab, tags, query } = getActiveFilters();
    browseOffset = 0;
    browseHasMore = true;

    let thoughts = [];

    try {
        if (query) {
            const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}&limit=100`);
            thoughts = await res.json();
        } else {
            const res = await fetch(`${API}/api/thoughts?limit=100`);
            thoughts = await res.json();
        }

        if (subTab === 'reminders') {
            thoughts = thoughts.filter(t =>
                t.tags.includes('reminder') || t.tags.includes('private_reminder'));
        } else if (subTab === 'todos') {
            thoughts = thoughts.filter(t =>
                t.tags.includes('todo') || t.tags.includes('private_todo'));
        }

        if (tags.length > 0) {
            thoughts = thoughts.filter(t => tags.every(ft => t.tags.includes(ft)));
        }

        browseOffset = thoughts.length;
        browseHasMore = !query && thoughts.length >= 100;

        renderThoughtCards(thoughts, query);
    } catch (_) {
        renderThoughtCards([], query);
    }
}

function renderThoughtCards(thoughts, highlightQuery) {
    const container = document.getElementById('thoughtCards');
    if (!container) return;

    if (!thoughts.length) {
        const msg = highlightQuery ? 'No thoughts found.' : 'Your thoughts will appear here.';
        container.innerHTML = `<div class="empty-browse"><p>${msg}</p></div>`;
        return;
    }

    container.innerHTML = thoughts.map((t, i) => {
        const isPrivate = t.tags.includes('private_todo') || t.tags.includes('private_reminder');
        const safeText = escapeHtml(t.text);
        const displayText = isPrivate
            ? '\u{1F512} Private thought'
            : highlightText(safeText, highlightQuery);

        const tagPills = t.tags
            .filter(tag => !(tag === 'random' && t.tags.length > 1))
            .map(tag => {
                const c = TAG_COLORS[tag] || TAG_COLORS.random;
                return `<span class="thought-tag" style="background:${hexToRgba(c, 0.10)};color:${c}">#${escapeHtml(tag)}</span>`;
            }).join('');

        const priv = isPrivate ? ` private-card" data-text="${escapeAttr(t.text)}` : '';

        return `<div class="thought-card${priv}" style="animation-delay:${i * 30}ms">
            <div class="thought-header">
                <span class="thought-time">${formatCardDate(t.created_at)}</span>
                <div class="thought-tags">${tagPills}</div>
            </div>
            <div class="thought-text">${displayText}</div>
        </div>`;
    }).join('');
}


/* ── Browse: Private card reveal ─────────────────────────────── */

function handlePrivateCardClick(e) {
    const card = e.target.closest('.private-card');
    if (!card || card.classList.contains('revealed')) return;

    const original = card.dataset.text;
    if (!original) return;

    const textEl = card.querySelector('.thought-text');
    textEl.textContent = original;
    card.classList.add('revealed');

    setTimeout(() => {
        textEl.textContent = '\u{1F512} Private thought';
        card.classList.remove('revealed');
    }, 3000);
}


/* ── Browse: Infinite scroll ─────────────────────────────────── */

async function loadMoreThoughts() {
    if (browseLoading || !browseHasMore) return;
    const { subTab, tags, query } = getActiveFilters();
    if (query) return;

    browseLoading = true;

    try {
        let url = `${API}/api/thoughts?limit=50&offset=${browseOffset}`;
        if (subTab === 'reminders') url += '&tag=reminder';
        else if (subTab === 'todos') url += '&tag=todo';
        else if (tags.length === 1) url += `&tag=${encodeURIComponent(tags[0])}`;

        const res = await fetch(url);
        let thoughts = await res.json();

        if (subTab === 'reminders') {
            thoughts = thoughts.filter(t =>
                t.tags.includes('reminder') || t.tags.includes('private_reminder'));
        } else if (subTab === 'todos') {
            thoughts = thoughts.filter(t =>
                t.tags.includes('todo') || t.tags.includes('private_todo'));
        }
        if (tags.length > 0) {
            thoughts = thoughts.filter(t => tags.every(ft => t.tags.includes(ft)));
        }

        if (!thoughts.length) { browseHasMore = false; browseLoading = false; return; }

        browseOffset += thoughts.length;
        const container = document.getElementById('thoughtCards');
        const startIdx = container.querySelectorAll('.thought-card').length;

        thoughts.forEach((t, i) => {
            const idx = startIdx + i;
            const isPrivate = t.tags.includes('private_todo') || t.tags.includes('private_reminder');
            const displayText = isPrivate ? '\u{1F512} Private thought' : escapeHtml(t.text);
            const tagPills = t.tags
                .filter(tag => !(tag === 'random' && t.tags.length > 1))
                .map(tag => {
                    const c = TAG_COLORS[tag] || TAG_COLORS.random;
                    return `<span class="thought-tag" style="background:${hexToRgba(c, 0.10)};color:${c}">#${escapeHtml(tag)}</span>`;
                }).join('');

            const div = document.createElement('div');
            div.className = `thought-card${isPrivate ? ' private-card' : ''}`;
            div.style.animationDelay = `${idx * 30}ms`;
            if (isPrivate) div.dataset.text = t.text;
            div.innerHTML = `<div class="thought-header">
                <span class="thought-time">${formatCardDate(t.created_at)}</span>
                <div class="thought-tags">${tagPills}</div>
            </div>
            <div class="thought-text">${displayText}</div>`;
            container.appendChild(div);
        });
    } catch (_) {}

    browseLoading = false;
}


/* ── Browse: Stats loader ────────────────────────────────────── */

async function loadStats() {
    try {
        const res = await fetch(`${API}/api/stats`);
        const s = await res.json();
        const el = document.getElementById('statsDisplay');
        if (el) {
            el.innerHTML = `
                <div class="settings-stat"><span class="settings-stat-label">Thoughts</span><span class="settings-stat-value">${s.total_thoughts}</span></div>
                <div class="settings-stat"><span class="settings-stat-label">Words</span><span class="settings-stat-value">${s.total_words}</span></div>
                <div class="settings-stat"><span class="settings-stat-label">Today</span><span class="settings-stat-value">${s.today_count}</span></div>
                <div class="settings-stat"><span class="settings-stat-label">DB size</span><span class="settings-stat-value">${s.db_size}</span></div>`;
        }
    } catch (_) {}
}


/* ── Chat: Helpers ───────────────────────────────────────────── */

function formatChatText(text) {
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`(.+?)`/g, '<code>$1</code>');
    html = html.replace(/^- (.+)$/gm, '<span class="chat-bullet">\u2022 $1</span>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

function addChatMessage(role, text) {
    const messages = document.getElementById('chatMessages');
    if (!messages) return;
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = role === 'assistant' ? formatChatText(text) : escapeHtml(text);
    messages.appendChild(div);
    messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    input.value = '';
    addChatMessage('user', msg);

    const messages = document.getElementById('chatMessages');
    const typing = document.createElement('div');
    typing.className = 'typing-indicator';
    typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    messages.appendChild(typing);
    messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });

    try {
        const res = await fetch(`${API}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
        });
        const data = await res.json();
        typing.remove();

        if (data.status === 'error' || data.status === 'disabled') {
            const div = document.createElement('div');
            div.className = 'chat-msg assistant chat-error';
            div.innerHTML = formatChatText(data.response);
            messages.appendChild(div);
        } else {
            addChatMessage('assistant', data.response);
        }
    } catch (_) {
        typing.remove();
        addChatMessage('assistant', "Couldn't reach the server. Is Headlog running?");
    }

    messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
}

async function loadModelBadge() {
    const badge = document.getElementById('modelBadge');
    if (!badge) return;

    try {
        const res = await fetch(`${API}/api/config`);
        const config = await res.json();
        const provider = config.ai_provider || 'ollama';
        const model = config.ai_model || 'llama3.2:3b';

        if (provider === 'ollama') {
            const label = model.includes(':') ? model.split(':')[1].toUpperCase() : model;
            badge.textContent = `Ollama ${label}`;
            badge.classList.remove('disabled');
        } else if (provider === 'gemini') {
            badge.textContent = 'Gemini Flash';
            badge.classList.remove('disabled');
        } else {
            badge.textContent = 'AI Disabled';
            badge.classList.add('disabled');
        }
    } catch (_) {
        badge.textContent = 'Offline';
        badge.classList.add('disabled');
    }
}

async function syncSettingsUI() {
    try {
        const res = await fetch(`${API}/api/config`);
        const config = await res.json();
        const provider = config.ai_provider || 'ollama';

        document.querySelectorAll('.radio-row').forEach(row => {
            const dot = row.querySelector('.radio-dot');
            if (row.dataset.provider === provider) {
                dot.classList.add('selected');
            } else {
                dot.classList.remove('selected');
            }
        });

        const keyRow = document.getElementById('apiKeyRow');
        if (keyRow) keyRow.style.display = provider === 'gemini' ? 'flex' : 'none';
    } catch (_) {}
}


/* ── Section 9: Settings Drawer ──────────────────────────────── */

function openSettings() {
    document.getElementById('settingsOverlay').classList.add('open');
    document.getElementById('settingsDrawer').classList.add('open');
    syncSettingsUI();
    loadStats();
}

function closeSettings() {
    document.getElementById('settingsOverlay').classList.remove('open');
    document.getElementById('settingsDrawer').classList.remove('open');
}


/* ── Section 10: Initialization ──────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('captureInput');
    textarea.focus();

    loadSidePanels();

    

    document.querySelectorAll('.tab-btn').forEach(tab => {
        tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    textarea.addEventListener('input', updateWordCount);
    textarea.addEventListener('input', updateGhostLayer);
    textarea.addEventListener('click', updateGhostLayer);

    textarea.addEventListener('keyup', (e) => {
        if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(e.key)) {
            updateGhostLayer();
        }
    });

    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Tab' && currentSuggestion) {
            e.preventDefault();
            acceptSuggestion();
            return;
        }
        if (e.key === 'Escape' && currentSuggestion) {
            e.preventDefault();
            clearSuggestion();
            return;
        }
    });

    textarea.addEventListener('scroll', () => {
        const ghost = document.getElementById('ghostLayer');
        if (ghost) ghost.scrollTop = textarea.scrollTop;
    });

    document.querySelector('.chips-section').addEventListener('click', e => {
        const chip = e.target.closest('.chip');
        if (!chip) return;
        const wasSelected = chip.classList.contains('selected');
        chip.classList.toggle('selected');
        const tag = chip.dataset.tag;
        if (wasSelected) {
            removeTagFromTextarea(tag);
        } else {
            appendTagToTextarea(tag);
        }
    });

    document.getElementById('chipsToggle').addEventListener('click', toggleChipsExpand);
    document.getElementById('saveBtn').addEventListener('click', saveThought);

    document.addEventListener('keydown', e => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            saveThought();
        }
    });

    document.getElementById('settingsBtn').addEventListener('click', openSettings);
    document.getElementById('settingsClose').addEventListener('click', closeSettings);
    document.getElementById('settingsOverlay').addEventListener('click', closeSettings);

    document.querySelectorAll('.radio-row').forEach(row => {
        row.addEventListener('click', () => {
            const group = row.closest('.radio-group');
            group.querySelectorAll('.radio-dot').forEach(d => d.classList.remove('selected'));
            row.querySelector('.radio-dot').classList.add('selected');

            const provider = row.dataset.provider;
            if (provider) {
                fetch(`${API}/api/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ai_provider: provider }),
                }).then(() => {
                    loadModelBadge();
                    const keyRow = document.getElementById('apiKeyRow');
                    if (keyRow) keyRow.style.display = provider === 'gemini' ? 'flex' : 'none';
                }).catch(() => {});
            }
        });
    });

    const apiKeySave = document.getElementById('apiKeySave');
    if (apiKeySave) {
        apiKeySave.addEventListener('click', () => {
            const key = document.getElementById('apiKeyInput')?.value || '';
            fetch(`${API}/api/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: key }),
            }).then(() => showToast('API key saved'))
              .catch(() => showToast('Failed to save key'));
        });
    }

    document.addEventListener('change', handleTodoCheck);

    document.querySelectorAll('.peek-btn').forEach(btn => {
        btn.addEventListener('click', () => peekPrivate(btn.dataset.type));
    });

    const chatSend = document.getElementById('chatSend');
    const chatInput = document.getElementById('chatInput');

    if (chatSend) chatSend.addEventListener('click', sendChatMessage);
    if (chatInput) chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // ── Browse view listeners ──

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            if (searchDebounce) clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => loadThoughts(), 250);
        });
    }

    document.querySelectorAll('.sub-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            loadThoughts();
        });
    });

    document.getElementById('tagFilters')?.addEventListener('click', e => {
        const pill = e.target.closest('.tag-pill');
        if (pill) {
            pill.classList.toggle('active-filter');
            loadThoughts();
        }
    });

    document.getElementById('thoughtCards')?.addEventListener('click', handlePrivateCardClick);

    const browseMain = document.querySelector('.browse-main');
    if (browseMain) {
        browseMain.addEventListener('scroll', () => {
            if (!document.getElementById('browseView')?.classList.contains('active')) return;
            if (browseMain.scrollHeight - browseMain.clientHeight - browseMain.scrollTop < 200) {
                loadMoreThoughts();
            }
        });
    }
});
