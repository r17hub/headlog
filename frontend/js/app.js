/* ── Section 1: State & Constants ─────────────────────────────── */

const API = `http://${location.hostname}:5959`;

const TAG_PALETTE = {
    learning:   { bg: '#EDE8F5', text: '#6B52A3', dot: '#7C5FC2' },
    health:     { bg: '#E8F5EE', text: '#2D7A5A', dot: '#3D8B6E' },
    routine:    { bg: '#FFF3E6', text: '#A66B1A', dot: '#C47A20' },
    people:     { bg: '#FCE8E6', text: '#A8453B', dot: '#C44B3F' },
    tech:       { bg: '#E6F0FA', text: '#3B6FA8', dot: '#4A80C0' },
    idea:       { bg: '#F5F0E6', text: '#8A7340', dot: '#A68B4D' },
    todo:       { bg: '#EAF0E8', text: '#4A7040', dot: '#5A8A50' },
    reminder:   { bg: '#F0E8F5', text: '#7A52A3', dot: '#8B63B5' },
    vent:       { bg: '#F5E8E8', text: '#A05050', dot: '#B86060' },
    reflection: { bg: '#E8EEF5', text: '#4A6090', dot: '#5A72A5' },
    finance:    { bg: '#F5F0E6', text: '#8A7340', dot: '#A68B4D' },
    career:     { bg: '#E6F0FA', text: '#3B6FA8', dot: '#4A80C0' },
    productivity: { bg: '#EAF0E8', text: '#4A7040', dot: '#5A8A50' },
    spiritual:  { bg: '#F0E8F5', text: '#7A52A3', dot: '#8B63B5' },
    gratitude:  { bg: '#E8F5EE', text: '#2D7A5A', dot: '#3D8B6E' },
    lesson:     { bg: '#FFF3E6', text: '#A66B1A', dot: '#C47A20' },
    decision:   { bg: '#E8EEF5', text: '#4A6090', dot: '#5A72A5' },
    question:   { bg: '#E6F0FA', text: '#3B6FA8', dot: '#4A80C0' },
    selfhelp:   { bg: '#F0E8F5', text: '#7A52A3', dot: '#8B63B5' },
    travel:     { bg: '#E6F0FA', text: '#3B6FA8', dot: '#4A80C0' },
    random:     { bg: '#F0ECE6', text: '#A89E95', dot: '#A89E95' },
    private_todo:     { bg: '#F0ECE6', text: '#6B5F56', dot: '#6B5F56' },
    private_reminder: { bg: '#F0ECE6', text: '#6B5F56', dot: '#6B5F56' },
};

const TAG_COLORS = {};
Object.entries(TAG_PALETTE).forEach(([k, v]) => { TAG_COLORS[k] = v.dot; });

const TAG_LABELS = Object.keys(TAG_PALETTE);

const PRIMARY_TAGS = ['routine', 'health', 'idea', 'tech', 'todo', 'reminder'];
const EXTRA_TAGS = ['vent', 'reflection', 'learning', 'people'];
const ALL_VISIBLE_TAGS = [...PRIMARY_TAGS, ...EXTRA_TAGS];
const EXTENDED_TAGS = TAG_LABELS.filter(t =>
    !ALL_VISIBLE_TAGS.includes(t) && t !== 'private_todo' && t !== 'private_reminder'
);

const PRIORITY_CONFIG = [
    { value: 'p0', label: 'P0', color: '#C44B3F', bg: 'rgba(196,75,63,0.06)', desc: 'Urgent' },
    { value: 'p1', label: 'P1', color: '#C47A20', bg: 'rgba(196,122,32,0.08)', desc: 'Important' },
    { value: 'p2', label: 'P2', color: '#3D8B6E', bg: 'rgba(61,139,110,0.08)', desc: 'Someday' },
];

let toastTimeout = null;
const peekTimers = {};
let selectedPriority = null;
let markImportant = false;

const starredIds = new Set(
    JSON.parse(localStorage.getItem('headlog_starred') || '[]')
);

function saveStarredIds() {
    localStorage.setItem('headlog_starred', JSON.stringify([...starredIds]));
}

let cachedReminders = [];
let cachedTodos = [];
let cachedRecentThoughts = [];


/* ── Section 1a: Utility Helpers ──────────────────────────────── */

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

function escapeAttr(str) {
    const s = String(str ?? '');
    return s.replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\r/g, '&#13;')
            .replace(/\n/g, '&#10;');
}

function starSVG(active) {
    const fill = active ? '#D4940E' : 'none';
    const stroke = active ? '#D4940E' : '#C8BFB6';
    return `<svg width="13" height="13" viewBox="0 0 16 16" stroke-width="1.5"><path d="M8 1.5l1.85 4.1L14.5 6.2l-3.35 3 .9 4.6L8 11.5l-4.05 2.3.9-4.6-3.35-3 4.65-.6L8 1.5z" fill="${fill}" stroke="${stroke}" stroke-linejoin="round" stroke-linecap="round" /></svg>`;
}


/* ── Section 2: View Switching ───────────────────────────────── */

function switchView(view) {
    document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab-btn[data-view="${view}"]`)?.classList.add('active');

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(view + 'View')?.classList.add('active');

    if (view === 'capture') {
        document.getElementById('captureInput')?.focus();
        if (typeof initCaptureScreen === 'function') {
            initCaptureScreen();
        }
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


/* ── Section 3a: Save Button State ────────────────────────────── */

function updateSaveButtonState() {
    const textarea = document.getElementById('captureInput');
    const saveBtn = document.getElementById('saveBtn');
    if (!textarea || !saveBtn) return;
    if (textarea.value.trim()) {
        saveBtn.classList.add('has-content');
    } else {
        saveBtn.classList.remove('has-content');
    }
}


/* ── Section 4: Tag Chip Selection ───────────────────────────── */

function getSelectedTags() {
    return Array.from(document.querySelectorAll('.tag-chip.selected'))
        .map(c => c.dataset.tag);
}

function toggleChipsExpand() {
    const extra = document.getElementById('chipsExtra');
    const btn = document.getElementById('chipsToggle');
    extra.classList.toggle('expanded');
    btn.textContent = extra.classList.contains('expanded')
        ? 'fewer tags' : `+${EXTRA_TAGS.length + EXTENDED_TAGS.length} more`;
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
    updateSaveButtonState();
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
    updateSaveButtonState();
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
    const chipEl = document.querySelector(`.tag-chip[data-tag="${label}"]`);
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


/* ── Section 5: Tag Picker Rendering ──────────────────────────── */

function renderTagPicker() {
    const defaultGrid = document.getElementById('chipsDefault');
    const extraGrid = document.getElementById('chipsExtra');
    if (!defaultGrid || !extraGrid) return;

    defaultGrid.innerHTML = PRIMARY_TAGS.map(tag => renderTagChipButton(tag)).join('');

    const allExtra = [...EXTRA_TAGS, ...EXTENDED_TAGS];
    extraGrid.innerHTML = allExtra.map(tag => renderTagChipButton(tag)).join('') +
        `<button class="tag-chip private-chip" data-tag="private_todo"><span class="tag-chip-dot" style="background:#6B5F56"></span>&#128274; #private_todo</button>` +
        `<button class="tag-chip private-chip" data-tag="private_reminder"><span class="tag-chip-dot" style="background:#6B5F56"></span>&#128274; #private_reminder</button>`;

    const toggle = document.getElementById('chipsToggle');
    if (toggle) toggle.textContent = `+${allExtra.length + 2} more`;
}

function renderTagChipButton(tag) {
    const palette = TAG_PALETTE[tag] || TAG_PALETTE.random;
    return `<button class="tag-chip" data-tag="${tag}" data-bg="${palette.bg}" data-color="${palette.text}" data-dot="${palette.dot}"><span class="tag-chip-dot" style="background:${palette.dot}"></span>#${tag}</button>`;
}

function applyTagChipStyles(chip) {
    const isSelected = chip.classList.contains('selected');
    if (isSelected) {
        chip.style.background = chip.dataset.bg || '#F0ECE6';
        chip.style.color = chip.dataset.color || '#A89E95';
        chip.style.opacity = '1';
    } else {
        chip.style.background = '';
        chip.style.color = '';
        chip.style.opacity = '';
    }
}


/* ── Section 5a: Priority Button Handlers ─────────────────────── */

function initPriorityButtons() {
    document.querySelectorAll('.priority-btn').forEach(btn => {
        const prio = btn.dataset.priority;
        const config = PRIORITY_CONFIG.find(p => p.value === prio);
        if (!config) return;

        btn.addEventListener('click', () => {
            if (selectedPriority === prio) {
                selectedPriority = null;
                btn.classList.remove('selected');
                document.getElementById('priorityDescriptor').textContent = '';
            } else {
                document.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('selected'));
                selectedPriority = prio;
                btn.classList.add('selected');
                document.getElementById('priorityDescriptor').textContent = config.desc;
            }
        });
    });
}

function resetPriorityButtons() {
    selectedPriority = null;
    document.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('priorityDescriptor').textContent = '';
}


/* ── Section 5b: Pin Toggle ───────────────────────────────────── */

function initPinToggle() {
    const pinBtn = document.getElementById('pinToggle');
    if (!pinBtn) return;

    pinBtn.addEventListener('click', () => {
        markImportant = !markImportant;
        pinBtn.classList.toggle('active', markImportant);
    });
}


/* ── Section 6: Save Thought ─────────────────────────────────── */

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
    const priority = selectedPriority;

    try {
        const postBody = { text, tags };
        if (priority) postBody.priority = priority;
        if (markImportant) postBody.important = true;

        const res = await fetch(`${API}/api/thoughts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(postBody)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Save failed');

        if (markImportant && data.thought && data.thought.id) {
            starredIds.add(data.thought.id);
            saveStarredIds();
        }

        textarea.value = '';
        updateWordCount();
        updateSaveButtonState();
        clearSuggestion();
        resetPriorityButtons();
        markImportant = false;
        document.getElementById('pinToggle')?.classList.remove('active');
        document.querySelectorAll('.tag-chip.selected').forEach(c => {
            c.classList.remove('selected');
            applyTagChipStyles(c);
        });

        const extra = document.getElementById('chipsExtra');
        if (extra && extra.classList.contains('expanded')) {
            extra.classList.remove('expanded');
            const toggle = document.getElementById('chipsToggle');
            if (toggle) toggle.textContent = `+${EXTRA_TAGS.length + EXTENDED_TAGS.length + 2} more`;
        }

        const tagStr = data.thought.tags.map(t => `#${t}`).join(', ');
        showToast(`Saved — ${tagStr}`);

        textarea.focus();
        if (window.ActionList && typeof ActionList.poll === 'function') {
            ActionList.poll();
        }
        loadSidePanels();
        loadRecentThoughts();
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


/* ── Section 7: Tag Pill Rendering (inline in lists) ──────────── */

function renderTagPill(tag) {
    const p = TAG_PALETTE[tag] || TAG_PALETTE.random;
    return `<span class="tag-pill" style="background:${p.bg};color:${p.text}"><span class="pill-dot" style="background:${p.dot}"></span>${escapeHtml(tag)}</span>`;
}

function renderTagPills(tags, exclude) {
    return tags
        .filter(t => t !== exclude)
        .map(t => renderTagPill(t))
        .join(' ');
}


/* ── Section 8: Date Formatting ───────────────────────────────── */

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


/* ── Section 9: Reminder Rendering ────────────────────────────── */

function getFirstTagColor(tags) {
    for (const t of tags) {
        const p = TAG_PALETTE[t];
        if (p) return p.dot;
    }
    return '#E8E2DB';
}

function renderReminderItem(thought) {
    const isStarred = starredIds.has(thought.id);
    const urgency = window.Urgency ? window.Urgency.getColor(thought.alarm_anchor, thought.alarm_zone) : { color: '#B0A99F' };
    const badge = window.Urgency ? window.Urgency.renderBadge(thought.priority) : '';
    const deadline = window.Urgency ? window.Urgency.renderDeadlineLine(thought) : '';
    const anchorAttr = thought.alarm_anchor ? ` data-anchor="${escapeAttr(thought.alarm_anchor)}"` : '';
    const zoneAttr = thought.alarm_zone ? ` data-zone="${escapeAttr(thought.alarm_zone)}"` : '';
    const borderColor = urgency.color || getFirstTagColor(thought.tags || []);
    const starredClass = isStarred ? ' starred-item' : '';

    return `<div class="side-item reminder-entry has-urgency-border${starredClass}" data-id="${thought.id}" data-real-text="${escapeAttr(thought.text || '')}"${anchorAttr}${zoneAttr} style="--urgency-color:${borderColor}">
        <div class="entry-actions">
            <button type="button" class="entry-action-btn entry-edit-btn" title="Edit">
                <svg viewBox="0 0 24 24"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button type="button" class="entry-action-btn entry-delete-btn" title="Delete">
                <svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6h12z"/></svg>
            </button>
        </div>
        <div class="side-item-header">
            <span class="side-item-time">${formatRelativeDate(thought.created_at)}</span>
            <span class="side-item-tags">${badge} ${renderTagPills(thought.tags, 'reminder')}</span>
            <span class="side-item-star">
                <button type="button" class="star-btn${isStarred ? ' starred' : ''}" data-id="${thought.id}" data-type="reminder">
                    ${starSVG(isStarred)}
                </button>
            </span>
        </div>
        <div class="side-item-text">${escapeHtml(thought.text)}</div>
        ${deadline}
    </div>`;
}


/* ── Section 10: Todo Rendering ───────────────────────────────── */

function renderTodoItem(thought, isDone) {
    const isStarred = starredIds.has(thought.id);
    const urgency = window.Urgency ? window.Urgency.getColor(thought.alarm_anchor, thought.alarm_zone) : { color: '#B0A99F' };
    const badge = window.Urgency ? window.Urgency.renderBadge(thought.priority) : '';
    const deadline = window.Urgency ? window.Urgency.renderDeadlineLine(thought) : '';
    const anchorAttr = thought.alarm_anchor ? ` data-anchor="${escapeAttr(thought.alarm_anchor)}"` : '';
    const zoneAttr = thought.alarm_zone ? ` data-zone="${escapeAttr(thought.alarm_zone)}"` : '';
    const starredClass = isStarred && !isDone ? ' starred-item' : '';
    const doneClass = isDone ? ' done' : '';

    const hasDeadline = thought.alarm_anchor && thought.alarm_zone !== 'open_todo';
    const urgencyBorderClass = hasDeadline ? ' has-urgency-border' : '';
    const urgencyStyle = hasDeadline ? ` style="--urgency-color:${urgency.color}"` : '';

    return `<div class="todo-item-row side-item todo-entry${urgencyBorderClass}${starredClass}${doneClass}" data-id="${thought.id}" data-real-text="${escapeAttr(thought.text || '')}"${anchorAttr}${zoneAttr}${urgencyStyle}>
        <div class="entry-actions">
            <button type="button" class="entry-action-btn entry-edit-btn" title="Edit">
                <svg viewBox="0 0 24 24"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button type="button" class="entry-action-btn entry-delete-btn" title="Delete">
                <svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6h12z"/></svg>
            </button>
        </div>
        <div class="todo-checkbox-wrapper">
            <input type="checkbox" class="todo-checkbox"${isDone ? ' checked' : ''}>
        </div>
        <div class="todo-content">
            <div class="todo-text">${escapeHtml(thought.text)}</div>
            <div class="todo-tags">${badge} ${renderTagPills(thought.tags, 'todo')}</div>
            ${deadline}
        </div>
        <div class="todo-star">
            <button type="button" class="star-btn${isStarred ? ' starred' : ''}" data-id="${thought.id}" data-type="todo">
                ${starSVG(isStarred)}
            </button>
        </div>
    </div>`;
}


/* ── Section 11: Side Panels — Load & Render ──────────────────── */

async function loadSidePanels() {
    try {
        const [remRes, privRemRes] = await Promise.all([
            fetch(`${API}/api/thoughts?tag=reminder&status=active&limit=20`),
            fetch(`${API}/api/thoughts?tag=private_reminder&status=active&limit=5`)
        ]);
        let reminders = (await remRes.json()).filter(t => {
            if (t.is_private) return false;
            const tags = t.tags || [];
            if (tags.includes('todo') || tags.includes('private_todo')) return false;
            return true;
        });
        let privReminders = (await privRemRes.json()).filter(t => {
            const tags = t.tags || [];
            if (tags.includes('private_todo')) return false;
            return true;
        });

        if (window.Urgency) {
            reminders = window.Urgency.sortByPriorityThenUrgency(reminders);
            privReminders = window.Urgency.sortByPriorityThenUrgency(privReminders);
        }

        cachedReminders = reminders;

        const remWidget = document.getElementById('remindersWidget');
        const remCount = document.getElementById('reminderCount');
        if (remCount) remCount.textContent = reminders.length || '';
        remWidget.innerHTML = reminders.length
            ? reminders.map(r => renderReminderItem(r)).join('')
            : '<p class="empty-message">No active reminders</p>';

        if (window.SwipeDismiss) {
            remWidget.querySelectorAll('.reminder-entry').forEach(el => {
                const id = parseInt(el.dataset.id, 10);
                SwipeDismiss.attach(el, id, '/api/thoughts/dismiss', () => loadSidePanels());
                SwipeDismiss.addDismissButton(el, id, '/api/thoughts/dismiss', () => loadSidePanels());
            });
        }

        const privRemEl = document.getElementById('privateReminders');
        privRemEl.innerHTML = privReminders.map(r => renderReminderItem(r)).join('');

        if (window.SwipeDismiss) {
            privRemEl.querySelectorAll('.reminder-entry').forEach(el => {
                const id = parseInt(el.dataset.id, 10);
                SwipeDismiss.attach(el, id, '/api/thoughts/dismiss', () => loadSidePanels());
                SwipeDismiss.addDismissButton(el, id, '/api/thoughts/dismiss', () => loadSidePanels());
            });
        }
    } catch (_) {}

    try {
        const [todoRes, privTodoRes] = await Promise.all([
            fetch(`${API}/api/thoughts?tag=todo&status=active,stale&limit=30`),
            fetch(`${API}/api/thoughts?tag=private_todo&status=active,stale&limit=5`)
        ]);
        let todos = (await todoRes.json())
            .filter(t => !t.is_private && !t.tags.includes('reminder'));
        let privTodos = (await privTodoRes.json())
            .filter(t => !t.tags.includes('private_reminder'));

        if (window.Urgency) {
            todos = window.Urgency.sortByPriorityThenUrgency(todos);
            privTodos = window.Urgency.sortByPriorityThenUrgency(privTodos);
        }

        cachedTodos = todos;

        const todoWidget = document.getElementById('todosWidget');
        todoWidget.innerHTML = todos.length
            ? todos.map(t => renderTodoItem(t, false)).join('')
            : '<p class="empty-message">All clear</p>';

        todoWidget.querySelectorAll('.todo-entry').forEach(el => {
            const id = parseInt(el.dataset.id, 10);
            const thought = todos.find(t => t.id === id);
            if (thought && thought.status === 'stale') {
                el.classList.add('stale');
            }
            if (window.SwipeDismiss) {
                SwipeDismiss.attach(el, id, '/api/thoughts/archive', () => loadSidePanels());
                SwipeDismiss.addDismissButton(el, id, '/api/thoughts/archive', () => loadSidePanels());
            }
        });

        const privTodoEl = document.getElementById('privateTodos');
        privTodoEl.innerHTML = privTodos.map(t => renderTodoItem(t, false)).join('');

        privTodoEl.querySelectorAll('.todo-entry').forEach(el => {
            const id = parseInt(el.dataset.id, 10);
            const thought = privTodos.find(t => t.id === id);
            if (thought && thought.status === 'stale') {
                el.classList.add('stale');
            }
            if (window.SwipeDismiss) {
                SwipeDismiss.attach(el, id, '/api/thoughts/archive', () => loadSidePanels());
                SwipeDismiss.addDismissButton(el, id, '/api/thoughts/archive', () => loadSidePanels());
            }
        });
    } catch (_) {}

    renderPinnedCard();
}


/* ── Section 12: Pinned Card ──────────────────────────────────── */

function renderPinnedCard() {
    const card = document.getElementById('pinnedCard');
    if (!card) return;

    const pinnedReminders = cachedReminders
        .filter(r => starredIds.has(r.id))
        .slice(0, 3);

    const pinnedTodos = cachedTodos
        .filter(t => starredIds.has(t.id))
        .slice(0, 3);

    const hasReminders = pinnedReminders.length > 0;
    const hasTodos = pinnedTodos.length > 0;
    const hasAnything = hasReminders || hasTodos;

    let html = `<div class="pinned-header">
        ${starSVG(true)}
        <span class="pinned-header-label">PINNED</span>
        <span class="pinned-header-sub">— needs your attention</span>
    </div>`;

    html += '<div class="pinned-body">';

    if (!hasAnything) {
        html += '<div class="pinned-empty">Nothing pinned — star items to surface them here</div>';
    } else {
        if (hasReminders) {
            html += '<div class="pinned-subsection">';
            html += '<div class="pinned-sub-header">REMINDERS</div>';
            pinnedReminders.forEach(r => {
                const dotColor = getFirstTagColor(r.tags || []);
                const tagPill = (r.tags || []).filter(t => t !== 'reminder').slice(0, 1).map(t => renderTagPill(t)).join('');
                html += `<div class="pinned-item">
                    <span class="pinned-dot" style="background:${dotColor}"></span>
                    <span class="pinned-text">${escapeHtml(r.text)}</span>
                    ${tagPill}
                </div>`;
            });
            html += '</div>';
        }

        if (hasTodos) {
            html += '<div class="pinned-subsection">';
            html += '<div class="pinned-sub-header">TASKS</div>';
            pinnedTodos.forEach(t => {
                const tagPill = (t.tags || []).filter(tg => tg !== 'todo').slice(0, 1).map(tg => renderTagPill(tg)).join('');
                html += `<div class="pinned-item">
                    <span class="pinned-square"></span>
                    <span class="pinned-text">${escapeHtml(t.text)}</span>
                    ${tagPill}
                </div>`;
            });
            html += '</div>';
        }
    }

    html += '</div>';
    card.innerHTML = html;
}


/* ── Section 13: Recent Thoughts ──────────────────────────────── */

async function loadRecentThoughts() {
    try {
        const res = await fetch(`${API}/api/thoughts?limit=10`);
        let thoughts = await res.json();
        thoughts = thoughts.filter(t => {
            if (t.is_private) return false;
            const tags = t.tags || [];
            if (tags.includes('private_todo') || tags.includes('private_reminder')) return false;
            if (tags.includes('reminder') || tags.includes('todo')) return false;
            return true;
        }).slice(0, 5);

        cachedRecentThoughts = thoughts;
        renderRecentThoughts();
    } catch (_) {}
}

function renderRecentThoughts() {
    const container = document.getElementById('recentThoughts');
    if (!container) return;

    if (!cachedRecentThoughts.length) {
        container.innerHTML = '<p class="empty-message">Your recent thoughts will appear here</p>';
        return;
    }

    container.innerHTML = cachedRecentThoughts.map(t => {
        const isStarred = starredIds.has(t.id);
        const borderColor = isStarred ? '#D4940E' : getFirstTagColor(t.tags || []);
        const starredClass = isStarred ? ' starred-item' : '';
        const tagPills = (t.tags || [])
            .filter(tag => !(tag === 'random' && t.tags.length > 1))
            .map(tag => renderTagPill(tag))
            .join('');

        return `<div class="recent-thought${starredClass}" data-id="${t.id}" style="border-left-color:${borderColor}">
            <div class="recent-thought-header">
                <span class="recent-thought-time">${formatRelativeDate(t.created_at)}</span>
                <span class="recent-thought-tags">${tagPills}</span>
                <span class="recent-thought-star">
                    <button type="button" class="star-btn${isStarred ? ' starred' : ''}" data-id="${t.id}" data-type="thought">
                        ${starSVG(isStarred)}
                    </button>
                </span>
            </div>
            <div class="recent-thought-text">${escapeHtml(t.text)}</div>
        </div>`;
    }).join('');
}


/* ── Section 14: Star Toggle Handler ──────────────────────────── */

function handleStarToggle(e) {
    const btn = e.target.closest('.star-btn');
    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();

    const id = parseInt(btn.dataset.id, 10);
    if (!Number.isFinite(id)) return;

    if (starredIds.has(id)) {
        starredIds.delete(id);
    } else {
        starredIds.add(id);
    }
    saveStarredIds();

    const isNowStarred = starredIds.has(id);
    btn.innerHTML = starSVG(isNowStarred);
    btn.classList.toggle('starred', isNowStarred);

    const row = btn.closest('.side-item, .todo-item-row, .recent-thought');
    if (row) {
        row.classList.toggle('starred-item', isNowStarred);
        if (row.classList.contains('recent-thought')) {
            row.style.borderLeftColor = isNowStarred ? '#D4940E' : getFirstTagColor([]);
            renderRecentThoughts();
        }
    }

    renderPinnedCard();
}


/* ── Section 15: Todo Checkbox Handler ────────────────────────── */

function handleTodoCheck(e) {
    if (!e.target.matches('.todo-checkbox')) return;
    const row = e.target.closest('.todo-item-row');
    if (!row) return;

    if (e.target.checked) {
        row.classList.add('done');
        row.classList.remove('starred-item');
    } else {
        row.classList.remove('done');
        const id = parseInt(row.dataset.id, 10);
        if (starredIds.has(id)) row.classList.add('starred-item');
    }

    renderPinnedCard();
}


/* ── Section 16: Entry Actions (Edit/Delete) ──────────────────── */

function showDeleteConfirm(entryEl, thoughtId) {
    if (!entryEl) return;
    if (entryEl.querySelector('.delete-confirm')) return;

    document.querySelectorAll('.delete-confirm').forEach(el => {
        if (!entryEl.contains(el)) el.remove();
    });

    const confirm = document.createElement('div');
    confirm.className = 'delete-confirm';
    confirm.innerHTML = `
        Delete this thought?
        <span class="delete-confirm-yes">Yes</span>
        <span class="delete-confirm-no">No</span>
    `;

    confirm.querySelector('.delete-confirm-yes').addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (window.InlineEdit) window.InlineEdit.delete(entryEl, thoughtId);
    });
    confirm.querySelector('.delete-confirm-no').addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        confirm.remove();
    });

    entryEl.appendChild(confirm);
    setTimeout(() => { if (confirm.parentNode) confirm.remove(); }, 4000);
}

function handleSideEntryActions(e) {
    const btn = e.target.closest('.entry-action-btn');
    if (!btn) return;

    const entry = btn.closest('.side-item');
    if (!entry) return;

    const thoughtId = parseInt(entry.dataset.id, 10);
    if (!Number.isFinite(thoughtId)) return;

    e.preventDefault();
    e.stopPropagation();

    if (!btn.classList.contains('entry-delete-btn')) {
        document.querySelectorAll('.entry-delete-btn.confirm').forEach(b => {
            if (b._confirmTimeout) clearTimeout(b._confirmTimeout);
            b.classList.remove('confirm');
            if (b._iconHTML) b.innerHTML = b._iconHTML;
        });
    }

    if (btn.classList.contains('entry-edit-btn')) {
        const textEl = entry.querySelector('.side-item-text, .todo-text');
        if (!textEl || !window.InlineEdit) return;
        const realText = entry.dataset.realText || textEl.textContent || '';
        window.InlineEdit.activate(entry, thoughtId, realText, textEl);
        return;
    }

    if (btn.classList.contains('entry-delete-btn')) {
        if (!window.InlineEdit) return;

        if (btn.classList.contains('confirm')) {
            if (btn._confirmTimeout) clearTimeout(btn._confirmTimeout);
            btn.classList.remove('confirm');
            if (btn._iconHTML) btn.innerHTML = btn._iconHTML;
            window.InlineEdit.delete(entry, thoughtId);
            return;
        }

        document.querySelectorAll('.entry-delete-btn.confirm').forEach(b => {
            if (b._confirmTimeout) clearTimeout(b._confirmTimeout);
            b.classList.remove('confirm');
            if (b._iconHTML) b.innerHTML = b._iconHTML;
        });

        btn._iconHTML = btn.innerHTML;
        btn.classList.add('confirm');
        btn.textContent = 'Delete?';
        btn._confirmTimeout = setTimeout(() => {
            btn.classList.remove('confirm');
            if (btn._iconHTML) btn.innerHTML = btn._iconHTML;
        }, 3000);
    }
}


/* ── Section 17: Delete Thought (Browse) ──────────────────────── */

function handleDeleteClick(e) {
    const btn = e.target.closest('.delete-btn');
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();

    if (btn.classList.contains('confirm')) {
        if (btn._confirmTimeout) clearTimeout(btn._confirmTimeout);
        const item = btn.closest('[data-id]');
        if (item) performDelete(item.dataset.id, item, btn);
        return;
    }

    document.querySelectorAll('.delete-btn.confirm').forEach(b => {
        if (b !== btn) {
            if (b._confirmTimeout) clearTimeout(b._confirmTimeout);
            b.classList.remove('confirm');
            b.innerHTML = '&times;';
        }
    });

    btn.classList.add('confirm');
    btn.textContent = 'Delete?';

    btn._confirmTimeout = setTimeout(() => {
        btn.classList.remove('confirm');
        btn.innerHTML = '&times;';
    }, 3000);
}

async function performDelete(id, element, btn) {
    btn.textContent = '...';
    btn.style.pointerEvents = 'none';

    try {
        const res = await fetch(`${API}/api/thoughts/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Delete failed');

        element.style.animation = 'none';
        element.style.transition = 'opacity 250ms ease, transform 250ms ease';
        element.style.opacity = '0';
        element.style.transform = 'translateX(16px)';

        setTimeout(() => {
            element.remove();
            loadSidePanels();
            loadRecentThoughts();
        }, 260);

        showToast('Thought deleted');

        if (document.getElementById('browseView')?.classList.contains('active')) {
            loadTagFilters();
        }
    } catch (err) {
        showToast(`Error: ${err.message}`);
        btn.classList.remove('confirm');
        btn.innerHTML = '&times;';
        btn.style.pointerEvents = '';
    }
}


/* ── Section 18: Private Peek ─────────────────────────────────── */

function peekPrivate(type) {
    const containerId = type === 'reminders' ? 'privateReminders' : 'privateTodos';
    const container = document.getElementById(containerId);
    const column = container.closest('.left-column, .right-column');
    const btn = column.querySelector('.peek-btn');
    const bar = column.querySelector('.peek-bar');

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


/* ── Section 19: Quick Add Todo ───────────────────────────────── */

function initQuickAdd() {
    const addBtn = document.getElementById('addTodoBtn');
    if (!addBtn) return;

    addBtn.addEventListener('click', () => {
        const container = document.getElementById('quickAddContainer');
        if (!container) return;

        if (container.querySelector('.quick-add-input')) {
            container.innerHTML = '';
            return;
        }

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'quick-add-input';
        input.placeholder = 'Quick todo...';
        container.innerHTML = '';
        container.appendChild(input);
        input.focus();

        input.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter' && input.value.trim()) {
                try {
                    const res = await fetch(`${API}/api/thoughts`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: input.value.trim(), tags: ['todo'] })
                    });
                    if (!res.ok) throw new Error('Save failed');
                    container.innerHTML = '';
                    showToast('Todo added');
                    loadSidePanels();
                } catch (err) {
                    showToast(`Error: ${err.message}`);
                }
            }
            if (e.key === 'Escape') {
                container.innerHTML = '';
            }
        });

        input.addEventListener('blur', () => {
            setTimeout(() => { container.innerHTML = ''; }, 150);
        });
    });
}


/* ── Browse: State ───────────────────────────────────────────── */

let searchDebounce = null;
let browseOffset = 0;
let browseLoading = false;
let browseHasMore = true;
let chatInitialized = false;

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
    const pills = document.querySelectorAll('.browse-tag-pill.active-filter');
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
            Array.from(container.querySelectorAll('.browse-tag-pill.active-filter'))
                .map(p => p.dataset.tag)
        );

        container.innerHTML = sorted.map(([tag, count]) => {
            const p = TAG_PALETTE[tag] || TAG_PALETTE.random;
            const cls = active.has(tag) ? ' active-filter' : '';
            return `<button class="browse-tag-pill${cls}" data-tag="${tag}"
                style="background:${hexToRgba(p.dot, 0.10)};color:${p.dot}">
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

        const priorityBadge = window.Urgency ? window.Urgency.renderBadge(t.priority) : '';
        const tagPills = t.tags
            .filter(tag => !(tag === 'random' && t.tags.length > 1))
            .map(tag => {
                const p = TAG_PALETTE[tag] || TAG_PALETTE.random;
                return `<span class="thought-tag" style="background:${hexToRgba(p.dot, 0.10)};color:${p.dot}">#${escapeHtml(tag)}</span>`;
            }).join('');

        const priv = isPrivate ? ` private-card" data-text="${escapeAttr(t.text)}` : '';

        return `<div class="thought-card${priv}" data-id="${t.id}" style="animation-delay:${i * 30}ms">
            <div class="thought-header">
                <span class="thought-time">${formatCardDate(t.created_at)}</span>
                <div class="thought-tags">${priorityBadge} ${tagPills}</div>
            </div>
            <div class="thought-text">${displayText}</div>
            <button class="delete-btn" title="Delete thought">&times;</button>
        </div>`;
    }).join('');
}


/* ── Browse: Private card reveal ─────────────────────────────── */

function handlePrivateCardClick(e) {
    if (e.target.closest('.delete-btn')) return;
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
            const priorityBadge = window.Urgency ? window.Urgency.renderBadge(t.priority) : '';
            const tagPills = t.tags
                .filter(tag => !(tag === 'random' && t.tags.length > 1))
                .map(tag => {
                    const p = TAG_PALETTE[tag] || TAG_PALETTE.random;
                    return `<span class="thought-tag" style="background:${hexToRgba(p.dot, 0.10)};color:${p.dot}">#${escapeHtml(tag)}</span>`;
                }).join('');

            const div = document.createElement('div');
            div.className = `thought-card${isPrivate ? ' private-card' : ''}`;
            div.dataset.id = t.id;
            div.style.animationDelay = `${idx * 30}ms`;
            if (isPrivate) div.dataset.text = t.text;
            div.innerHTML = `<div class="thought-header">
                <span class="thought-time">${formatCardDate(t.created_at)}</span>
                <div class="thought-tags">${priorityBadge} ${tagPills}</div>
            </div>
            <div class="thought-text">${displayText}</div>
            <button class="delete-btn" title="Delete thought">&times;</button>`;
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


/* ── Settings Drawer ──────────────────────────────────────────── */

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


/* ── Initialization ───────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('captureInput');
    textarea.focus();

    renderTagPicker();
    initPriorityButtons();
    initPinToggle();
    initQuickAdd();

    loadSidePanels();
    loadRecentThoughts();
    if (typeof initCaptureScreen === 'function') {
        initCaptureScreen();
    }

    if (window.Urgency) window.Urgency.startUpdater();

    window.showToast = showToast;
    window.loadSidePanels = loadSidePanels;
    window.refreshRemindersWidget = loadSidePanels;
    window.refreshTodosWidget = loadSidePanels;
    window.loadTagFilters = loadTagFilters;
    window.renderBrowseView = renderBrowseView;

    document.querySelectorAll('.tab-btn').forEach(tab => {
        tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    textarea.addEventListener('input', () => {
        updateWordCount();
        updateSaveButtonState();
    });
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

    document.getElementById('tagPicker').addEventListener('click', e => {
        const chip = e.target.closest('.tag-chip');
        if (!chip) return;
        const wasSelected = chip.classList.contains('selected');
        chip.classList.toggle('selected');
        applyTagChipStyles(chip);
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

    document.addEventListener('click', handleStarToggle);

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
        const pill = e.target.closest('.browse-tag-pill');
        if (pill) {
            pill.classList.toggle('active-filter');
            loadThoughts();
        }
    });

    document.getElementById('thoughtCards')?.addEventListener('click', handleDeleteClick);
    document.getElementById('thoughtCards')?.addEventListener('click', handlePrivateCardClick);
    document.getElementById('remindersWidget')?.addEventListener('click', handleSideEntryActions);
    document.getElementById('todosWidget')?.addEventListener('click', handleSideEntryActions);
    document.getElementById('privateReminders')?.addEventListener('click', handleSideEntryActions);
    document.getElementById('privateTodos')?.addEventListener('click', handleSideEntryActions);

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
