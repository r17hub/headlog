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
      today: { label: 'Today', items: [], collapsed: false },
      this_week: { label: 'This week', items: [], collapsed: true },
      later: { label: 'Later', items: [], collapsed: true },
      open: { label: 'Open', items: [], collapsed: true },
    };

    for (const item of active) {
      const bucket = buckets[item.bucket] || buckets.open;
      bucket.items.push(item);
    }

    let html = '';
    const clockSvg = '<svg width="8" height="8" viewBox="0 0 16 16" style="flex-shrink:0"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M8 5V8.5L10.5 10" stroke="currentColor" stroke-width="1.3" fill="none" stroke-linecap="round"/></svg>';
    const checkSvg = '<svg width="10" height="10" viewBox="0 0 12 12"><path d="M2.5 6.5L4.5 8.5L9.5 3.5" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const editSvg = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M11.9 2.3a1.5 1.5 0 0 1 2.1 2.1l-7.6 7.6-3 .9.9-3z"></path><path d="M9.8 4.4l1.8 1.8"></path></svg>';
    const trashSvg = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 4.2h9"></path><path d="M6.2 4.2V3.1h3.6v1.1"></path><path d="M5.2 5.2v6.1"></path><path d="M8 5.2v6.1"></path><path d="M10.8 5.2v6.1"></path><path d="M4.4 4.2l.5 8a1 1 0 0 0 1 .9h4.2a1 1 0 0 0 1-.9l.5-8"></path></svg>';

    for (const bucket of Object.values(buckets)) {
      if (bucket.items.length === 0) continue;
      html += `<div class="upcoming-section-label">${bucket.label}</div>`;
      for (const item of bucket.items) {
        const isEditing = this.editingId === item.id;
        const isDeleteConfirm = this.deleteConfirmId === item.id;
        const collapsedClass = bucket.collapsed ? ' collapsed' : '';
        const editingClass = isEditing ? ' editing' : '';
        const deleteClass = isDeleteConfirm ? ' delete-confirming' : '';
        const deadlineText = item.deadline_label || 'open task';
        const showClock = item.time_remaining_seconds !== null && item.urgency_state !== 'open';
        const urgencyTier = item.urgency || item.urgency_state;
        const deadlineEmoji = urgencyTier === 'overdue' ? '🔥' : urgencyTier === 'critical' ? '⏳' : urgencyTier === 'soon' ? '📌' : urgencyTier === 'upcoming' ? '🗓️' : '';
        const countdownId = `countdown-${item.id}`;
        const tagHtml = (item.tags || []).slice(0, 2).map(t => `<span class="action-tag">${this.escapeHtml(t)}</span>`).join('');
        const editingDisabled = this.editingId && !isEditing ? ' disabled' : '';
        const textHtml = isEditing
          ? `<textarea class="inline-edit-textarea action-edit-textarea" id="action-edit-${item.id}" rows="3" oninput="ActionList.updateEditDraft(${item.id}, this.value)" onkeydown="ActionList.handleEditKeydown(event, ${item.id})">${this.escapeHtml(this.editDraft)}</textarea>
             <div class="inline-edit-bar">
               <span class="inline-edit-wc" id="action-edit-wc-${item.id}">${this.wordCountLabel(this.editDraft)}</span>
               <div class="inline-edit-btns">
                 <button class="inline-edit-btn-cancel" type="button" onclick="ActionList.cancelEdit(${item.id})">Cancel</button>
                 <button class="inline-edit-btn-save" type="button" onclick="ActionList.saveEdit(${item.id})">Save</button>
               </div>
             </div>`
          : `<div class="action-text">${urgencyTier === 'overdue' ? '🔥 ' : ''}${this.escapeHtml(item.text)}</div>
             <div class="action-meta">
               <span class="action-deadline">${deadlineEmoji ? deadlineEmoji + ' ' : (showClock ? clockSvg : '')}<span id="${countdownId}">${showClock ? this.formatRemaining(item.time_remaining_seconds, item.urgency_state) : deadlineText}</span></span>
               <span class="action-type">${item.item_type}</span>
               ${tagHtml}
             </div>`;
        html += `
          <div class="action-item${collapsedClass}${editingClass}${deleteClass}" data-urgency="${item.urgency || item.urgency_state}" data-thought-id="${item.id}" id="action-${item.id}">
            <button class="action-check" onclick="ActionList.complete(${item.id})" title="Mark done">${checkSvg}</button>
            <div class="action-body">
              ${textHtml}
            </div>
            <div class="entry-actions">
              <button class="entry-action-btn action-entry-btn action-entry-edit${editingDisabled}" type="button" title="Edit" aria-label="Edit item" onclick="ActionList.startEdit(${item.id})">${editSvg}</button>
              <button class="entry-action-btn action-entry-btn action-entry-delete${isDeleteConfirm ? ' confirm' : ''}" type="button" title="Delete" aria-label="Delete item" onclick="ActionList.confirmDelete(${item.id})">${isDeleteConfirm ? 'Delete?' : trashSvg}</button>
            </div>
          </div>`;
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
}

window.addEventListener('beforeunload', () => {
  AskHeadlog.saveHistory();
});

window.ActionList = ActionList;
window.AskHeadlog = AskHeadlog;
window.dismissBriefing = dismissBriefing;
window.initCaptureScreen = initCaptureScreen;
