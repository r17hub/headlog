/**
 * Urgency color computation for Headlog reminder/todo cards.
 * Computes time-to-deadline colors client-side so they stay current
 * without re-fetching.
 */
(function () {
    const URGENCY_COLORS = {
        green:  '#16a34a',
        yellow: '#ca8a04',
        orange: '#ea580c',
        red:    '#dc2626',
        muted:  '#B0A99F',
    };

    const PRIORITY_COLORS = {
        p0: '#5B21B6',
        p1: '#1D4ED8',
        p2: '#0F766E',
    };

    function getUrgencyColor(anchorISO, zone) {
        if (!anchorISO || zone === 'open_todo') {
            return { color: URGENCY_COLORS.muted, level: 'muted' };
        }

        const now = new Date();
        const anchor = new Date(anchorISO);
        const diffMs = anchor - now;
        const diffMins = diffMs / (1000 * 60);

        if (diffMins <= 0) {
            return { color: URGENCY_COLORS.red, level: 'red' };
        }
        if (diffMins <= 30) {
            return { color: URGENCY_COLORS.red, level: 'red' };
        }
        if (diffMins <= 120) {
            return { color: URGENCY_COLORS.orange, level: 'orange' };
        }
        if (diffMins <= 360) {
            return { color: URGENCY_COLORS.yellow, level: 'yellow' };
        }
        return { color: URGENCY_COLORS.green, level: 'green' };
    }

    function renderPriorityBadge(priority) {
        if (!priority) return '';
        const label = priority.toUpperCase();
        return `<span class="priority-badge priority-${priority}">${label}</span>`;
    }

    function renderDeadlineLine(thought) {
        const label = thought.deadline_label;
        if (!label) return '';
        const { color } = getUrgencyColor(thought.alarm_anchor, thought.alarm_zone);
        return `<div class="card-deadline-line">` +
            `<span class="urgency-dot" style="background:${color}"></span>` +
            `<span class="deadline-text">${label}</span>` +
            `</div>`;
    }

    function sortByPriorityThenUrgency(thoughts) {
        const priorityOrder = { p0: 0, p1: 1, p2: 2 };
        return thoughts.sort((a, b) => {
            const pa = a.priority ? (priorityOrder[a.priority] ?? 3) : 3;
            const pb = b.priority ? (priorityOrder[b.priority] ?? 3) : 3;
            if (pa !== pb) return pa - pb;

            const aa = a.alarm_anchor ? new Date(a.alarm_anchor).getTime() : Infinity;
            const ab = b.alarm_anchor ? new Date(b.alarm_anchor).getTime() : Infinity;
            return aa - ab;
        });
    }

    let _urgencyInterval = null;

    function startUrgencyUpdater() {
        if (_urgencyInterval) clearInterval(_urgencyInterval);
        _urgencyInterval = setInterval(() => {
            document.querySelectorAll('[data-anchor]').forEach(card => {
                const anchor = card.dataset.anchor;
                const zone = card.dataset.zone || '';
                const { color } = getUrgencyColor(anchor, zone);
                card.style.setProperty('--urgency-color', color);
            });
        }, 60000);
    }

    window.Urgency = {
        getColor: getUrgencyColor,
        renderBadge: renderPriorityBadge,
        renderDeadlineLine: renderDeadlineLine,
        sortByPriorityThenUrgency: sortByPriorityThenUrgency,
        startUpdater: startUrgencyUpdater,
        PRIORITY_COLORS: PRIORITY_COLORS,
        URGENCY_COLORS: URGENCY_COLORS,
    };
})();
