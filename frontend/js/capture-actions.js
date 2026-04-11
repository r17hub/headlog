const CAPTURE_API = `http://${location.hostname}:5959`;

function captureApi(path) {
  return `${CAPTURE_API}${path}`;
}

const ActionList = {
  items: [],
  doneItems: [],
  doneExpanded: true,
  pollTimer: null,
  countdownTimer: null,
  initialized: false,
  editingId: null,
  editDraft: '',
  deleteConfirmId: null,
  deleteConfirmTimer: null,

  init() {
    if (this.initialized) return;
    this.initialized = true;
    this.poll();
    this.pollTimer = setInterval(() => this.poll(), 30000);
    this.countdownTimer = setInterval(() => this.tickCountdowns(), 1000);
  },

  async poll() {
    try {
      const resp = await fetch(captureApi('/api/reminders/active'));
      if (!resp.ok) return;
      const data = await resp.json();
      this.items = data.items || [];
      if (this.editingId && !this.items.some(item => item.id === this.editingId)) {
        this.editingId = null;
        this.editDraft = '';
      }
      this.render();
    } catch (e) {
      console.warn('Action list poll failed:', e);
    }
  },

  tickCountdowns() {
    let needsRerender = false;
    for (const item of this.items) {
      if (item.time_remaining_seconds === null || item.time_remaining_seconds === undefined) {
        continue;
      }
      if (item.urgency_state === 'open') continue;

      item.time_remaining_seconds -= 1;
      if (item.time_remaining_seconds <= 0 && item.urgency_state !== 'overdue') {
        item.urgency_state = 'overdue';
        item.urgency = 'overdue';
        item.bucket = 'next_hours';
        needsRerender = true;
      }

      const el = document.getElementById(`countdown-${item.id}`);
      if (el) {
        el.textContent = this.formatRemaining(item.time_remaining_seconds, item.urgency_state);
      }
    }
    if (needsRerender) this.render();
  },

  formatRemaining(seconds, state) {
    if (seconds === null || seconds === undefined) return 'open task';
    if (state === 'overdue' || seconds <= 0) {
      const over = Math.abs(seconds);
      if (over < 60) return 'overdue';
      if (over < 3600) return `overdue ${Math.floor(over / 60)}m`;
      if (over < 86400) return `overdue ${Math.floor(over / 3600)}h`;
      return `overdue ${Math.floor(over / 86400)}d`;
    }
    if (seconds < 60) return `${seconds}s left`;
    if (seconds < 3600) {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${m}m ${s}s`;
    }
    if (seconds < 86400) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      return m > 0 ? `${h}h ${m}m` : `${h}h left`;
    }
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    return h > 0 ? `${d}d ${h}h left` : `${d}d left`;
  },

  urgencyBorderColor(tier) {
    const map = {
      overdue:  '#dc2626',
      critical: '#ea580c',
      hot:      '#ea580c',
      soon:     '#ca8a04',
      warming:  '#ca8a04',
      calm:     '#16a34a',
      upcoming: '#16a34a',
      open:     '#B0A99F',
    };
    return map[tier] || '#B0A99F';
  },

  render() {
    const scroll = document.getElementById('upcoming-scroll');
    const countEl = document.getElementById('upcoming-count');
    const emptyEl = document.getElementById('upcoming-empty');
    if (!scroll || !countEl || !emptyEl) return;

    const doneIds = new Set(this.doneItems.map(d => d.id));
    const active = this.items.filter(i => !doneIds.has(i.id));

    countEl.textContent = active.length;

    if (active.length === 0 && this.doneItems.length === 0) {
      emptyEl.style.display = 'block';
      scroll.querySelectorAll('.upcoming-section-label, .action-item, .done-section').forEach(el => el.remove());
      return;
    }
    emptyEl.style.display = 'none';

    const buckets = {
      next_hours: { label: 'Next few hours', items: [], collapsed: false },
      today:      { label: 'Today',          items: [], collapsed: false },
      this_week:  { label: 'This week',      items: [], collapsed: true  },
      later:      { label: 'Later',          items: [], collapsed: true  },
      open:       { label: 'Open',           items: [], collapsed: true  },
    };

    for (const item of active) {
      const bucket = buckets[item.bucket] || buckets.open;
      bucket.items.push(item);
    }

    const checkSvg = '<svg width="10" height="10" viewBox="0 0 12 12"><path d="M2.5 6.5L4.5 8.5L9.5 3.5" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const bellOnSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>';
    const bellOffSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 21a2 2 0 01-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0018 8"/><path d="M6.26 6.26A5.86 5.86 0 006 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 00-9.33-5"/><path d="M1 1L23 23"/></svg>';
    const editMenuSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
    const trashMenuSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>';

    let html = '';

    for (const bucket of Object.values(buckets)) {
      if (bucket.items.length === 0) continue;
      html += `<div class="upcoming-section-label">${bucket.label}</div>`;

      for (const item of bucket.items) {
        const isEditing = this.editingId === item.id;
        const isMuted = !!item.is_muted;
        const urgencyTier = item.urgency || item.urgency_state || 'open';
        const borderColor = isMuted ? '#B4B2A9' : this.urgencyBorderColor(urgencyTier);
        const mutedClass = isMuted ? ' action-muted' : '';
        const collapsedClass = (bucket.collapsed && !isEditing) ? ' collapsed' : '';
        const editingClass = isEditing ? ' action-editing' : '';
        const countdownId = `countdown-${item.id}`;
        const deadlineText = item.deadline_label || 'open task';
        const showClock = item.time_remaining_seconds !== null && item.time_remaining_seconds !== undefined && item.urgency_state !== 'open';
        const countdownText = showClock ? this.formatRemaining(item.time_remaining_seconds, item.urgency_state) : deadlineText;
        const tagHtml = (item.tags || []).slice(0, 2).map(t => `<span class="action-tag">${this.escapeHtml(t)}</span>`).join('');
        const bellBtn = `<button class="action-bell${isMuted ? ' muted' : ''}" onclick="ActionList.toggleMute(${item.id},event)" title="${isMuted ? 'Unmute notifications' : 'Mute notifications'}">${isMuted ? bellOffSvg : bellOnSvg}</button>`;
        const menuBtn = `<button class="action-menu-btn" onclick="ActionList.openMenu(${item.id},event)" title="More options"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="5" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="19" r="1" fill="currentColor"/></svg></button>`;

        if (isEditing) {
          html += `<div class="action-item${mutedClass}${editingClass}" data-urgency="${urgencyTier}" data-thought-id="${item.id}" id="action-${item.id}" style="--urgency-color:${borderColor}">
  <textarea class="inline-edit-textarea action-edit-textarea" id="action-edit-${item.id}" rows="3" oninput="ActionList.updateEditDraft(${item.id},this.value)" onkeydown="ActionList.handleEditKeydown(event,${item.id})">${this.escapeHtml(this.editDraft)}</textarea>
  <div class="inline-edit-bar">
    <span class="inline-edit-wc" id="action-edit-wc-${item.id}">${this.wordCountLabel(this.editDraft)}</span>
    <div class="inline-edit-btns">
      <button class="inline-edit-btn-cancel" type="button" onclick="ActionList.cancelEdit(${item.id})">Cancel</button>
      <button class="inline-edit-btn-save" type="button" onclick="ActionList.saveEdit(${item.id})">Save</button>
    </div>
  </div>
</div>`;
        } else {
          html += `<div class="action-item${mutedClass}${collapsedClass}" data-urgency="${urgencyTier}" data-thought-id="${item.id}" id="action-${item.id}" style="--urgency-color:${borderColor}">
  <div class="action-row1">
    <button class="action-check" onclick="ActionList.complete(${item.id})" title="Mark done">${checkSvg}</button>
    <div class="action-title">${this.escapeHtml(item.text)}</div>
  </div>
  <div class="action-row2">
    <span class="action-deadline" id="${countdownId}">${countdownText}</span>
    ${tagHtml}
    <div class="action-row2-right">
      ${bellBtn}
      ${menuBtn}
    </div>
  </div>
  <div class="action-overflow-menu" id="action-menu-${item.id}" style="display:none">
    <button class="action-menu-item action-menu-edit" onclick="ActionList.startEdit(${item.id});ActionList.closeMenu(${item.id})">${editMenuSvg}<span>Edit</span></button>
    <button class="action-menu-item action-menu-delete" onclick="ActionList.confirmDelete(${item.id});ActionList.closeMenu(${item.id})">${trashMenuSvg}<span>Delete</span></button>
  </div>
</div>`;
        }
      }
    }

    if (this.doneItems.length > 0) {
      const chevClass = this.doneExpanded ? ' open' : '';
      const listClass = this.doneExpanded ? '' : ' collapsed';
      html += `<div class="done-section">
        <div class="done-header" onclick="ActionList.toggleDone()">
          <span class="done-label">Done today 🎉 <span class="done-count-badge">${this.doneItems.length}</span></span>
          <span class="done-chevron${chevClass}">&#9656;</span>
        </div>
        <div class="done-list${listClass}" id="done-list">
          ${this.doneItems.map(d => `<div class="done-item" id="done-${d.id}">
            <button class="action-check" onclick="ActionList.undo(${d.id})" title="Undo">${checkSvg}</button>
            <div class="action-body"><div class="action-text">${this.escapeHtml(d.text)}</div></div>
            <span class="done-time">${d.completedAt}</span>
          </div>`).join('')}
        </div>
      </div>`;
    }

    const scrollTop = scroll.scrollTop;
    scroll.querySelectorAll('.upcoming-section-label, .action-item, .done-section').forEach(el => el.remove());
    scroll.insertAdjacentHTML('beforeend', html);
    scroll.scrollTop = scrollTop;

    if (this.editingId) {
      const ta = document.getElementById(`action-edit-${this.editingId}`);
      if (ta) {
        ta.focus();
        ta.selectionStart = ta.value.length;
        ta.selectionEnd = ta.value.length;
      }
    }
  },

  wordCountLabel(text) {
    const count = (text || '').trim() ? (text || '').trim().split(/\s+/).filter(Boolean).length : 0;
    return `${count} word${count === 1 ? '' : 's'}`;
  },

  startEdit(thoughtId) {
    if (this.editingId && this.editingId !== thoughtId) return;
    const item = this.items.find(i => i.id === thoughtId);
    if (!item) return;
    this._clearDeleteConfirm(false);
    this.editingId = thoughtId;
    this.editDraft = item.text || '';
    this.render();
  },

  updateEditDraft(thoughtId, value) {
    if (this.editingId !== thoughtId) return;
    this.editDraft = value;
    const wc = document.getElementById(`action-edit-wc-${thoughtId}`);
    if (wc) wc.textContent = this.wordCountLabel(value);
  },

  handleEditKeydown(event, thoughtId) {
    if (this.editingId !== thoughtId) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelEdit(thoughtId);
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      this.saveEdit(thoughtId);
    }
  },

  cancelEdit(thoughtId) {
    if (this.editingId !== thoughtId) return;
    this.editingId = null;
    this.editDraft = '';
    this.render();
  },

  async saveEdit(thoughtId) {
    if (this.editingId !== thoughtId) return;
    const cleaned = (this.editDraft || '').trim();
    if (!cleaned) {
      if (window.showToast) window.showToast('Text cannot be empty');
      return;
    }

    try {
      const resp = await fetch(captureApi(`/api/thoughts/${thoughtId}/edit`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleaned }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.success === false) {
        throw new Error(data.error || 'Failed to update');
      }
      this.editingId = null;
      this.editDraft = '';
      await this.poll();
      if (window.showToast) window.showToast('Updated');
    } catch (err) {
      if (window.showToast) window.showToast(`Error: ${err.message}`);
    }
  },

  confirmDelete(thoughtId) {
    if (this.deleteConfirmId === thoughtId) {
      this.deleteThought(thoughtId);
      return;
    }
    this._clearDeleteConfirm(false);
    this.deleteConfirmId = thoughtId;
    this.deleteConfirmTimer = setTimeout(() => {
      this._clearDeleteConfirm();
    }, 3000);
    this.render();
  },

  _clearDeleteConfirm(shouldRender = true) {
    if (this.deleteConfirmTimer) {
      clearTimeout(this.deleteConfirmTimer);
      this.deleteConfirmTimer = null;
    }
    this.deleteConfirmId = null;
    if (shouldRender) this.render();
  },

  async deleteThought(thoughtId) {
    const card = document.getElementById(`action-${thoughtId}`);
    this._clearDeleteConfirm(false);
    if (this.editingId === thoughtId) {
      this.editingId = null;
      this.editDraft = '';
    }

    if (card) {
      card.classList.add('deleting');
    }

    try {
      const resp = await fetch(captureApi(`/api/thoughts/${thoughtId}`), { method: 'DELETE' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.success === false) {
        throw new Error(data.error || 'Delete failed');
      }
      this.doneItems = this.doneItems.filter(d => d.id !== thoughtId);
      await this.poll();
      if (window.showToast) window.showToast('Deleted');
    } catch (err) {
      if (card) card.classList.remove('deleting');
      if (window.showToast) window.showToast(`Error: ${err.message}`);
    }
  },

  async complete(thoughtId) {
    if (this.editingId === thoughtId) {
      this.cancelEdit(thoughtId);
    }
    const item = this.items.find(i => i.id === thoughtId);
    if (!item) return;
    const el = document.getElementById(`action-${thoughtId}`);
    if (el) {
      el.style.transition = 'opacity 0.3s, max-height 0.4s ease 0.1s, margin 0.4s ease 0.1s, padding 0.4s ease 0.1s';
      el.style.opacity = '0';
      setTimeout(() => {
        el.style.maxHeight = '0';
        el.style.marginBottom = '0';
        el.style.padding = '0 10px';
        el.style.overflow = 'hidden';
      }, 100);
    }
    try {
      const resp = await fetch(captureApi('/api/thoughts/complete'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thought_id: thoughtId }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.success === false) {
        throw new Error(data.error || 'Failed to complete');
      }
      const timeStr = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      this.doneItems = this.doneItems.filter(d => d.id !== thoughtId);
      this.doneItems.push({ id: thoughtId, text: item.text, completedAt: timeStr });
      setTimeout(() => this.render(), 400);
      if (window.showToast) window.showToast('Done - moved to completed');
    } catch (e) {
      if (el) {
        el.style.opacity = '';
        el.style.maxHeight = '';
        el.style.marginBottom = '';
        el.style.padding = '';
        el.style.overflow = '';
      }
      console.error('Complete failed:', e);
      if (window.showToast) window.showToast(`Error: ${e.message}`);
    }
  },

  async toggleMute(thoughtId, event) {
    if (event) event.stopPropagation();
    const item = this.items.find(i => i.id === thoughtId);
    if (!item) return;
    const newMuted = !item.is_muted;
    // Optimistic update
    item.is_muted = newMuted;
    this.render();
    try {
      const resp = await fetch(captureApi(`/api/thoughts/${thoughtId}/mute`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ muted: newMuted }),
      });
      if (!resp.ok) throw new Error('Mute failed');
    } catch (e) {
      // Revert on failure
      item.is_muted = !newMuted;
      this.render();
      if (window.showToast) window.showToast('Failed to update mute setting');
    }
  },

  openMenu(thoughtId, event) {
    if (event) event.stopPropagation();
    // Close any other open menus
    document.querySelectorAll('.action-overflow-menu').forEach(m => {
      if (m.id !== `action-menu-${thoughtId}`) m.style.display = 'none';
    });
    const menu = document.getElementById(`action-menu-${thoughtId}`);
    if (!menu) return;
    const isOpen = menu.style.display !== 'none';
    menu.style.display = isOpen ? 'none' : 'block';
  },

  closeMenu(thoughtId) {
    const menu = document.getElementById(`action-menu-${thoughtId}`);
    if (menu) menu.style.display = 'none';
  },

  closeAllMenus() {
    document.querySelectorAll('.action-overflow-menu').forEach(m => {
      m.style.display = 'none';
    });
  },

  async undo(thoughtId) {
    try {
      const resp = await fetch(captureApi('/api/thoughts/revive'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thought_id: thoughtId }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.success === false) {
        throw new Error(data.error || 'Failed to restore');
      }
      this.doneItems = this.doneItems.filter(d => d.id !== thoughtId);
      await this.poll();
      if (window.showToast) window.showToast('Restored to upcoming');
    } catch (e) {
      console.error('Undo failed:', e);
      if (window.showToast) window.showToast(`Error: ${e.message}`);
    }
  },

  toggleDone() {
    this.doneExpanded = !this.doneExpanded;
    this.render();
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  },
};

const MorningBriefing = {
  STORAGE_KEY: 'headlog_last_briefing',
  MIN_GAP_HOURS: 4,
  AUTO_DISMISS_MS: 10000,

  async maybeShow() {
    const last = localStorage.getItem(this.STORAGE_KEY);
    if (last) {
      const hoursSince = (Date.now() - parseInt(last, 10)) / (1000 * 60 * 60);
      if (hoursSince < this.MIN_GAP_HOURS) return;
    }
    try {
      const resp = await fetch(captureApi('/api/reminders/briefing'));
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.active_count === 0 && data.overdue_count === 0) return;
      this.display(data);
      localStorage.setItem(this.STORAGE_KEY, Date.now().toString());
    } catch (_) {}
  },

  display(data) {
    const el = document.getElementById('morning-briefing');
    const greeting = document.getElementById('briefing-greeting');
    const stat = document.getElementById('briefing-stat');
    if (!el || !greeting || !stat) return;

    const greetings = { morning: 'Good morning', afternoon: 'Good afternoon', evening: 'Good evening' };
    greeting.textContent = greetings[data.greeting] || 'Hey';
    const parts = [];
    if (data.overdue_count > 0) parts.push(`${data.overdue_count} overdue`);
    parts.push(`${data.active_count} item${data.active_count !== 1 ? 's' : ''} active`);
    if (data.next_deadline && data.next_deadline.fire_at) {
      const nextAt = new Date(data.next_deadline.fire_at);
      if (!Number.isNaN(nextAt.getTime())) {
        parts.push(`next ${nextAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`);
      }
    }
    if (data.yesterday_total > 0) {
      const rate = Math.round((data.yesterday_completed / data.yesterday_total) * 100);
      parts.push(`yesterday ${rate}% done`);
    }
    stat.textContent = parts.join(' · ');
    el.style.display = 'flex';
    setTimeout(() => dismissBriefing(), this.AUTO_DISMISS_MS);
  },
};

function dismissBriefing() {
  const el = document.getElementById('morning-briefing');
  if (!el || el.style.display === 'none') return;
  el.classList.add('dismissing');
  setTimeout(() => {
    el.style.display = 'none';
    el.classList.remove('dismissing');
  }, 400);
}

const AskHeadlog = {
  history: [],
  MAX_HISTORY: 5,

  async send() {
    const input = document.getElementById('ask-input');
    if (!input) return;
    const q = (input.value || '').trim();
    if (!q) return;
    const resultEl = document.getElementById('ask-result');
    const questionEl = document.getElementById('ask-question');
    const answerEl = document.getElementById('ask-answer');
    const sourceEl = document.getElementById('ask-source');
    if (!resultEl || !questionEl || !answerEl || !sourceEl) return;

    questionEl.textContent = q;
    answerEl.textContent = 'Thinking...';
    sourceEl.textContent = '';
    resultEl.style.display = 'block';
    input.value = '';

    this.history = [q, ...this.history.filter(h => h !== q)].slice(0, this.MAX_HISTORY);
    this.renderHistory();
    this.saveHistory();

    try {
      const resp = await fetch(captureApi('/api/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: q }),
      });
      const data = await resp.json();
      answerEl.textContent = data.response || data.error || "Couldn't get a response.";
      sourceEl.textContent = data.context_count ? `Searched ${data.context_count} thoughts` : '';
    } catch (_) {
      answerEl.textContent = 'Failed to reach AI. Is Ollama running?';
    }
  },

  askFromHistory(index) {
    const q = this.history[index];
    const input = document.getElementById('ask-input');
    if (!q || !input) return;
    input.value = q;
    this.send();
  },

  renderHistory() {
    const container = document.getElementById('ask-history');
    if (!container) return;
    if (this.history.length === 0) {
      container.innerHTML = '';
      return;
    }
    container.innerHTML = `<div class="ask-history-label">Recent questions</div>
      ${this.history.map((q, i) => `<div class="ask-history-item" onclick="AskHeadlog.askFromHistory(${i})">${ActionList.escapeHtml(q)}</div>`).join('')}`;
  },

  loadHistory() {
    try {
      const saved = localStorage.getItem('headlog_ask_history');
      if (saved) this.history = JSON.parse(saved);
    } catch (_) {}
    this.renderHistory();
  },

  saveHistory() {
    localStorage.setItem('headlog_ask_history', JSON.stringify(this.history));
  },
};

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    document.getElementById('ask-input')?.focus();
  }
});

function initCaptureScreen() {
  ActionList.init();
  MorningBriefing.maybeShow();
  AskHeadlog.loadHistory();
  // Close overflow menus when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.action-overflow-menu') && !e.target.closest('.action-menu-btn')) {
      ActionList.closeAllMenus();
    }
  });
}

window.addEventListener('beforeunload', () => {
  AskHeadlog.saveHistory();
});

window.ActionList = ActionList;
window.AskHeadlog = AskHeadlog;
window.dismissBriefing = dismissBriefing;
window.initCaptureScreen = initCaptureScreen;
