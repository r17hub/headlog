/**
 * Shared swipe-to-dismiss gesture for Headlog widget cards.
 * Works with touch (iPhone) and mouse drag (desktop).
 *
 * Usage:
 *   SwipeDismiss.attach(cardEl, thoughtId, apiEndpoint, onDismissedCallback)
 */
(function () {
    const API_BASE = `http://${location.hostname}:5959`;
    const THRESHOLD = 80;

    function attach(cardElement, thoughtId, apiEndpoint, onDismissedCallback) {
        let startX = 0;
        let currentX = 0;
        let isDragging = false;

        function onStart(x) {
            startX = x;
            currentX = x;
            isDragging = true;
            cardElement.style.transition = 'none';
        }

        function onMove(x) {
            if (!isDragging) return;
            currentX = x;
            const diff = currentX - startX;
            if (diff > 0) {
                cardElement.style.transform = `translateX(${diff}px)`;
                cardElement.style.opacity = Math.max(0.2, 1 - diff / 200);
            }
        }

        async function onEnd() {
            if (!isDragging) return;
            isDragging = false;
            const diff = currentX - startX;

            if (diff >= THRESHOLD) {
                cardElement.style.transition = 'transform 0.25s ease-out, opacity 0.25s ease-out';
                cardElement.style.transform = 'translateX(120%)';
                cardElement.style.opacity = '0';

                try {
                    await fetch(`${API_BASE}${apiEndpoint}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ thought_id: thoughtId }),
                    });
                } catch (e) {
                    console.error('Dismiss failed:', e);
                }

                setTimeout(() => {
                    cardElement.remove();
                    if (onDismissedCallback) onDismissedCallback(thoughtId);
                }, 260);

                if (typeof window.showToast === 'function') {
                    window.showToast('Dismissed');
                }
            } else {
                cardElement.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
                cardElement.style.transform = 'translateX(0)';
                cardElement.style.opacity = '1';
            }
        }

        cardElement.addEventListener('touchstart', e => onStart(e.touches[0].clientX), { passive: true });
        cardElement.addEventListener('touchmove', e => onMove(e.touches[0].clientX), { passive: true });
        cardElement.addEventListener('touchend', onEnd);

        cardElement.addEventListener('mousedown', e => {
            if (e.target.closest('.entry-action-btn, .todo-checkbox, .inline-edit-textarea, .inline-edit-btn-cancel, .inline-edit-btn-save, .dismiss-btn, .star-btn')) return;
            e.preventDefault();
            onStart(e.clientX);

            function mouseMoveHandler(ev) { onMove(ev.clientX); }
            function mouseUpHandler() {
                onEnd();
                document.removeEventListener('mousemove', mouseMoveHandler);
                document.removeEventListener('mouseup', mouseUpHandler);
            }
            document.addEventListener('mousemove', mouseMoveHandler);
            document.addEventListener('mouseup', mouseUpHandler);
        });
    }

    function addDismissButton(cardElement, thoughtId, apiEndpoint, onDismissedCallback) {
        const btn = document.createElement('button');
        btn.className = 'dismiss-btn';
        btn.textContent = '\u00d7';
        btn.title = 'Dismiss';
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            cardElement.style.transition = 'transform 0.25s ease-out, opacity 0.25s ease-out';
            cardElement.style.transform = 'translateX(120%)';
            cardElement.style.opacity = '0';
            try {
                await fetch(`${API_BASE}${apiEndpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ thought_id: thoughtId }),
                });
            } catch (err) { console.error(err); }
            setTimeout(() => {
                cardElement.remove();
                if (onDismissedCallback) onDismissedCallback(thoughtId);
                if (typeof window.showToast === 'function') window.showToast('Dismissed');
            }, 260);
        });
        cardElement.appendChild(btn);
    }

    window.SwipeDismiss = { attach, addDismissButton };
})();
