/**
 * Inline edit module for Headlog thought entries (Capture screen widgets).
 * Exposes a global `InlineEdit` used by frontend/js/app.js.
 */
(function () {
    const API_BASE = `http://${location.hostname}:5959`;

    const InlineEdit = {
        _active: null, // thought id currently being edited

        activate(entryEl, thoughtId, currentText, textEl) {
            if (!entryEl || !textEl) return;
            if (this._active) return;
            this._active = thoughtId;

            // Hide display text
            textEl.style.display = 'none';

            const ta = document.createElement('textarea');
            ta.className = 'inline-edit-textarea';
            ta.value = currentText || '';
            ta.rows = Math.max(2, Math.min(10, Math.ceil((ta.value.length || 0) / 40)));
            ta.dataset.thoughtId = String(thoughtId);

            const bar = document.createElement('div');
            bar.className = 'inline-edit-bar';

            const wc = document.createElement('span');
            wc.className = 'inline-edit-wc';
            wc.textContent = this._wordCountLabel(ta.value);

            const btns = document.createElement('div');
            btns.className = 'inline-edit-btns';

            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'inline-edit-btn-cancel';
            cancelBtn.type = 'button';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.deactivate(entryEl, textEl);
            });

            const saveBtn = document.createElement('button');
            saveBtn.className = 'inline-edit-btn-save';
            saveBtn.type = 'button';
            saveBtn.textContent = 'Save';
            saveBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.save(entryEl, thoughtId, ta.value, textEl);
            });

            btns.appendChild(cancelBtn);
            btns.appendChild(saveBtn);
            bar.appendChild(wc);
            bar.appendChild(btns);

            textEl.parentNode.insertBefore(ta, textEl.nextSibling);
            textEl.parentNode.insertBefore(bar, ta.nextSibling);

            ta.focus();
            ta.setSelectionRange(ta.value.length, ta.value.length);

            ta.addEventListener('input', () => {
                wc.textContent = this._wordCountLabel(ta.value);
            });

            ta.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    this.deactivate(entryEl, textEl);
                }
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault();
                    this.save(entryEl, thoughtId, ta.value, textEl);
                }
            });

            entryEl.classList.add('editing');
        },

        deactivate(entryEl, textEl) {
            if (!entryEl || !textEl) return;
            const ta = entryEl.querySelector('.inline-edit-textarea');
            const bar = entryEl.querySelector('.inline-edit-bar');
            if (ta) ta.remove();
            if (bar) bar.remove();
            textEl.style.display = '';
            entryEl.classList.remove('editing');
            this._active = null;
        },

        async save(entryEl, thoughtId, newText, textEl) {
            const cleaned = (newText || '').trim();
            if (!cleaned) return;

            try {
                const res = await fetch(`${API_BASE}/api/thoughts/${thoughtId}/edit`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: cleaned }),
                });
                const result = await res.json().catch(() => ({}));

                if (res.ok && result.success) {
                    if (result.changed) {
                        textEl.textContent = cleaned;
                        if (typeof window.showToast === 'function') window.showToast('Thought updated');
                    }
                } else {
                    if (typeof window.showToast === 'function') {
                        window.showToast(result.error ? `Error: ${result.error}` : 'Failed to update');
                    }
                }
            } catch (err) {
                console.error('Edit failed:', err);
                if (typeof window.showToast === 'function') window.showToast('Failed to update');
            }

            this.deactivate(entryEl, textEl);

            // Full refresh to pick up recomputed tags + ordering
            if (typeof window.loadSidePanels === 'function') window.loadSidePanels();
            if (typeof window.loadTagFilters === 'function' &&
                document.getElementById('browseView')?.classList.contains('active')) {
                window.loadTagFilters();
            }
        },

        async delete(entryEl, thoughtId) {
            if (!entryEl) return;

            try {
                const res = await fetch(`${API_BASE}/api/thoughts/${thoughtId}`, { method: 'DELETE' });
                const result = await res.json().catch(() => ({}));

                if (!res.ok || (result && result.success === false)) {
                    throw new Error(result.error || 'Delete failed');
                }

                entryEl.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                entryEl.style.opacity = '0';
                entryEl.style.transform = 'translateX(16px)';

                setTimeout(() => {
                    entryEl.remove();
                    if (typeof window.loadSidePanels === 'function') window.loadSidePanels();
                }, 260);

                if (typeof window.showToast === 'function') window.showToast('Thought deleted');
            } catch (err) {
                console.error('Delete failed:', err);
                if (typeof window.showToast === 'function') window.showToast('Failed to delete');
            }
        },

        _wordCountLabel(text) {
            const count = (text || '').trim()
                ? text.trim().split(/\s+/).filter(Boolean).length
                : 0;
            return `${count} word${count !== 1 ? 's' : ''}`;
        }
    };

    window.InlineEdit = InlineEdit;
})();

