import re
import time
import html
from pathlib import Path
from flask import Flask, render_template_string, Response, request, jsonify
from utils.board_etl import(
    complete_task as etl_complete_task, 
    delete_line,
    make_line_today,
    move_line_to_bottom,
    parse_tasks, 
    shift_line_to_tomorrow, 
    toggle_line_focus 
) 
from datetime import datetime
from utils.ics_utils import generate_task_ics

app = Flask(__name__)
TASK_FILE = Path("tasks.txt")

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADHD Executive Focus Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background-color: #0f172a; }
        .card { background-color: #1e293b; border-color: #334155; }
        .badge-strong { background-color: #ef4444; }
        .badge-fluid { background-color: #06b6d4; }
        .badge-arbitrary { background-color: #f59e0b; color: #000; }
        .btn-complete { padding: 0.1rem 0.4rem; font-size: 0.75rem; border-radius: 0.25rem; }
        /* Table Layout Locking */
        .table-fixed {
            table-layout: fixed;
            width: 100%;
        }

        /* Ensure Type and Time cells never collapse or overflow */
        .table-fixed td:first-child, 
        .table-fixed td:nth-child(2) {
            white-space: nowrap;
            overflow: hidden;
        }

        /* Task Title Styling */
        .task-title-cell {
            word-break: break-word;
            overflow-wrap: anywhere;
        }

        /* Subtask Container */
        .subtask-text-container {
            min-width: 0;
            flex-grow: 1;
            word-break: break-word;
            overflow-wrap: anywhere;
        }

        .subtask-action-container {
            display: inline-flex;
            align-items: center;
            justify-content: flex-end;
            min-width: 75px;
        }

        .btn-complete-subtask {
            font-weight: 600;
            line-height: 1.4;
            transition: all 0.15s ease-in-out;
        }

        /* Give main action button group enough horizontal space */
        .action-cell {
            width: 350px !important;
            white-space: nowrap;
        }
    </style>
</head>
<body class="text-light py-4">
    <div class="container">
        <header class="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom border-secondary">
            <h1 class="h3 m-0 text-cyan">⚡ Executive Focus Engine</h1>
            <span class="badge bg-outline-light border text-muted" id="status-badge">Live Sync Active</span>
        </header>

        <div id="dashboard-content">
            {% include 'board_partial.html' %}
        </div>
    </div>

    <script>
        let evtSource;
        
        // Function to reload dashboard partial HTML
        function refreshDashboard() {
            fetch('/partial')
                .then(res => {
                    if (res.ok) return res.text();
                    throw new Error('Partial refresh failed');
                })
                .then(html => {
                    const container = document.getElementById('dashboard-content');
                    if (container) {
                        container.innerHTML = html;
                        initTooltips();
                    }
                })
                .catch(err => console.error("Auto-refresh error:", err));
        }

        // 1. Re-sync immediately when computer wakes up or tab regains focus
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'visible') {
                refreshDashboard();
                if (evtSource && evtSource.readyState === EventSource.CLOSED) {
                    connectSSE();
                }
            }
        });

        // 2. Schedule automatic refresh every night at 12:10 AM
        function scheduleMidnightRefresh() {
            const now = new Date();
            const nextRefresh = new Date();

            // Target 12:10:00 AM (00:10:00)
            nextRefresh.setHours(0, 10, 0, 0);

            // If 12:10 AM has already passed today, target 12:10 AM tomorrow
            if (now >= nextRefresh) {
                nextRefresh.setDate(nextRefresh.getDate() + 1);
            }

            const msUntilRefresh = nextRefresh.getTime() - now.getTime();
            console.log(`Scheduled next 12:10 AM refresh in ${(msUntilRefresh / 1000 / 60).toFixed(1)} minutes.`);

            setTimeout(() => {
                refreshDashboard();
                // Repeat daily
                setInterval(refreshDashboard, 24 * 60 * 60 * 1000);
            }, msUntilRefresh);
        }

        // Initialize on page load
        document.addEventListener("DOMContentLoaded", function() {
            initTooltips();
            scheduleMidnightRefresh();
        });

        function initTooltips() {
            const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            [...tooltipTriggerList].map(tooltipTriggerEl => bootstrap.Tooltip.getOrCreateInstance(tooltipTriggerEl));
        }

        document.addEventListener("DOMContentLoaded", initTooltips);

        function connectSSE() {
            evtSource = new EventSource("/stream");

            evtSource.onmessage = function(e) {
                if (e.data === "reload") {
                    fetch('/partial')
                        .then(res => res.text())
                        .then(html => {
                            document.getElementById('dashboard-content').innerHTML = html;
                            initTooltips();
                        });
                }
            };

            evtSource.onerror = function() {
                document.getElementById('status-badge').textContent = "Sync Reconnecting...";
                document.getElementById('status-badge').className = "badge bg-outline-light border text-warning";
                
                evtSource.close();
                setTimeout(connectSSE, 3000);
            };
        }

        connectSSE();

        document.addEventListener('click', function(e) {
            if (e.target.closest('button')) {
                const shiftBtn = e.target.closest('.btn-shift-task');
                if (shiftBtn) {
                    const rawLine = shiftBtn.getAttribute('data-raw');
                    fetch('/shift_task', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: rawLine })
                    });
                    return;
                }

                const subtaskBtn = e.target.closest('.btn-complete-subtask');
                if (subtaskBtn) {
                    const parentTitle = subtaskBtn.getAttribute('data-parent');
                    const subtaskText = subtaskBtn.getAttribute('data-subtask');
                    fetch('/complete_subtask', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ parent_title: parentTitle, subtask: subtaskText })
                    });
                    return;
                }

                const taskBtn = e.target.closest('.btn-complete-task');
                if (taskBtn) {
                    const rawLine = taskBtn.getAttribute('data-raw');
                    fetch('/complete_task', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: rawLine })
                    });
                    return;
                }

                const makeTodayBtn = e.target.closest('.btn-make-today');
                if (makeTodayBtn) {
                    const rawLine = makeTodayBtn.getAttribute('data-raw');
                    fetch('/make_today', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: rawLine })
                    });
                    return;
                }

                const deleteBtn = e.target.closest('.btn-delete-task');
                if (deleteBtn) {
                    const tooltip = bootstrap.Tooltip.getInstance(deleteBtn);
                    if (tooltip) tooltip.hide();

                    fetch('/delete_task', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: deleteBtn.getAttribute('data-raw') })
                    });
                    return;
                }

                const moveBottomBtn = e.target.closest('.btn-move-bottom');
                if (moveBottomBtn) {
                    const tooltip = bootstrap.Tooltip.getInstance(moveBottomBtn);
                    if (tooltip) tooltip.hide();

                    fetch('/move_to_bottom', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: moveBottomBtn.getAttribute('data-raw') })
                    });
                    return;
                }

                return;
            }

            const taskRow = e.target.closest('.task-row');
            if (taskRow) {
                const rawLine = taskRow.getAttribute('data-raw');
                fetch('/toggle_focus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ raw_line: rawLine })
                });
            }
        });

        document.addEventListener('click', function(e) {
            const editBtn = e.target.closest('.btn-edit-task');
            if (editBtn) {
                const tooltip = bootstrap.Tooltip.getInstance(editBtn);
                if (tooltip) tooltip.hide();

                const oldRawEl = document.getElementById('edit-old-raw');
                const dateEl = document.getElementById('edit-task-date');
                const typeEl = document.getElementById('edit-task-type');
                const descEl = document.getElementById('edit-task-desc');
                const tagsEl = document.getElementById('edit-task-tags-input');
                const editFibEl = document.getElementById('edit-task-fib-score');
                const tagsList = (editBtn.getAttribute('data-tags') || '').split(/\s+/);
                const fibTag = tagsList.find(t => t.toLowerCase().startsWith('fib:'));

                if (editFibEl) {
                    editFibEl.value = fibTag ? fibTag.split(':')[1] : '';
                }

                if (!oldRawEl || !dateEl || !typeEl || !descEl || !tagsEl) {
                    console.error("Edit modal elements missing from DOM");
                    return;
                }

                // Strip fib: tag from general tags input field so it stays clean
                oldRawEl.value = editBtn.getAttribute('data-raw') || '';
                dateEl.value = editBtn.getAttribute('data-date') || '';
                typeEl.value = editBtn.getAttribute('data-symbol') || '*';
                descEl.value = editBtn.getAttribute('data-title') || '';
                tagsEl.value = tagsList.filter(t => !t.toLowerCase().startsWith('fib:')).join(' ');
                                
                const subtasksContainer = document.getElementById('edit-subtasks-container');
                if (subtasksContainer) {
                    subtasksContainer.innerHTML = '';
                    const subtasks = JSON.parse(editBtn.getAttribute('data-subtasks') || '[]');
                    
                    if (subtasks.length > 0) {
                        subtasks.forEach(sub => {
                            const row = document.createElement('div');
                            row.className = 'input-group input-group-sm mb-1 subtask-row';
                            row.innerHTML = `
                                <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                                <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" value="${sub}">
                                <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                            `;
                            subtasksContainer.appendChild(row);
                        });
                    } else {
                        subtasksContainer.innerHTML = `
                            <div class="input-group input-group-sm mb-1 subtask-row">
                                <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                                <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                                <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                            </div>
                        `;
                    }
                }

                const modalEl = document.getElementById('editTaskModal');
                if (modalEl) {
                    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
                    modal.show();
                }
                return;
            }

            if (e.target && e.target.id === 'btn-add-edit-subtask-field') {
                const container = document.getElementById('edit-subtasks-container');
                if (container) {
                    const row = document.createElement('div');
                    row.className = 'input-group input-group-sm mb-1 subtask-row';
                    row.innerHTML = `
                        <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                        <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                        <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                    `;
                    container.appendChild(row);
                    row.querySelector('input').focus();
                }
                return;
            }
        });

        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'btn-add-subtask-field') {
                const container = document.getElementById('subtasks-container');
                const row = document.createElement('div');
                row.className = 'input-group input-group-sm mb-1 subtask-row';
                row.innerHTML = `
                    <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                    <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                    <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                `;
                container.appendChild(row);
                row.querySelector('input').focus();
                return;
            }

            const removeBtn = e.target.closest('.btn-remove-subtask');
            if (removeBtn) {
                const row = removeBtn.closest('.subtask-row');
                if (row) row.remove();
                return;
            }
        });

        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'btn-save-task') {
                const dateVal = document.getElementById('task-date').value;
                const symbol = document.getElementById('task-type').value;
                const description = document.getElementById('task-desc').value.trim();
                const rawTags = document.getElementById('task-tags-input').value.trim();
                const fibScore = document.getElementById('task-fib-score').value;

                if (!description) {
                    document.getElementById('task-desc').classList.add('is-invalid');
                    return;
                }

                // Single declaration of tags
                let tags = rawTags ? rawTags.split(/\s+/).map(t => t.replace(/^#/, '')) : [];
                if (fibScore) {
                    tags.push(`fib:${fibScore}`);
                }

                const subtaskInputs = document.querySelectorAll('#subtasks-container .subtask-input');
                const subtasks = Array.from(subtaskInputs)
                    .map(input => input.value.trim())
                    .filter(val => val.length > 0);

                fetch('/add_task', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ date: dateVal, symbol, description, tags, subtasks })
                }).then(res => {
                    if (res.ok) {
                        const modalEl = document.getElementById('addTaskModal');
                        const modal = bootstrap.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                        document.getElementById('create-task-form').reset();

                        document.getElementById('subtasks-container').innerHTML = `
                            <div class="input-group input-group-sm mb-1 subtask-row">
                                <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                                <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                                <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                            </div>
                        `;
                    }
                });
            }
});

        // Ensure create modal always opens with clean default state and today's date
        document.addEventListener('show.bs.modal', function(e) {
            if (e.target && e.target.id === 'addTaskModal') {
                const form = document.getElementById('create-task-form');
                if (form) form.reset();

                // Default the date field to today (YYYY-MM-DD)
                const dateInput = document.getElementById('task-date');
                if (dateInput) {
                    const today = new Date();
                    const year = today.getFullYear();
                    const month = String(today.getMonth() + 1).padStart(2, '0');
                    const day = String(today.getDate()).padStart(2, '0');
                    dateInput.value = `${year}-${month}-${day}`;
                }

                const container = document.getElementById('subtasks-container');
                if (container) {
                    container.innerHTML = `
                        <div class="input-group input-group-sm mb-1 subtask-row">
                            <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                            <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                            <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                        </div>
                    `;
                }
            }
        });
        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'btn-update-task') {
                const oldRaw = document.getElementById('edit-old-raw').value;
                const dateVal = document.getElementById('edit-task-date').value;
                const symbol = document.getElementById('edit-task-type').value;
                const description = document.getElementById('edit-task-desc').value.trim();
                const rawTags = document.getElementById('edit-task-tags-input').value.trim();
                const fibScore = document.getElementById('edit-task-fib-score').value;

                if (!description) {
                    document.getElementById('edit-task-desc').classList.add('is-invalid');
                    return;
                }

                // Single declaration of tags
                let tags = rawTags ? rawTags.split(/\s+/).map(t => t.replace(/^#/, '')) : [];
                if (fibScore) {
                    tags.push(`fib:${fibScore}`);
                }

                const subtaskInputs = document.querySelectorAll('#edit-subtasks-container .subtask-input');
                const subtasks = Array.from(subtaskInputs)
                    .map(input => input.value.trim())
                    .filter(val => val.length > 0);

                fetch('/edit_task', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        old_raw: oldRaw,
                        date: dateVal,
                        symbol: symbol,
                        description: description,
                        tags: tags,
                        subtasks: subtasks
                    })
                }).then(res => {
                    if (res.ok) {
                        const modalEl = document.getElementById('editTaskModal');
                        const modal = bootstrap.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                    }
                });
                return;
            }
        });
    </script>
    <!-- Inside HTML_TEMPLATE, above </body> -->

    <!-- Task Creation Modal -->
    <div class="modal fade" id="addTaskModal" tabindex="-1" aria-labelledby="addTaskModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-light border border-secondary shadow-lg">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title fs-6 fw-bold text-info" id="addTaskModalLabel">📌 Create Scheduled Task</h5>
                </div>
                <!-- Task Creation Modal Body -->
                <div class="modal-body">
                    <form id="create-task-form">
                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">SCHEDULED DATE</label>
                            <input type="date" class="form-control bg-dark text-light border-secondary" id="task-date">
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TASK TYPE</label>
                            <select class="form-select bg-dark text-light border-secondary" id="task-type">
                                <option value="*" selected>* Fluid Task (Default)</option>
                                <option value="!">! Strong Commitment</option>
                                <option value="?">? Arbitrary / Optional</option>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TASK DESCRIPTION</label>
                            <input type="text" class="form-control bg-dark text-light border-secondary" id="task-desc" placeholder="e.g. Review pull request" required autocomplete="off">
                        </div>

                        <div class="row g-2 mb-3">
                            <div class="col-8">
                                <label class="form-label text-secondary small fw-bold">TAGS (Type or select historical)</label>
                                <input type="text" class="form-control bg-dark text-light border-secondary" id="task-tags-input" list="historical-tags-list" placeholder="e.g. priority work">
                                <datalist id="historical-tags-list">
                                    {% for tag in data.all_tags %}
                                        <option value="{{ tag }}"></option>
                                    {% endfor %}
                                </datalist>
                            </div>
                            <div class="col-4">
                                <label class="form-label text-secondary small fw-bold">FIB SCORE</label>
                                <select class="form-select bg-dark text-light border-secondary" id="task-fib-score">
                                    <option value="" selected>None</option>
                                    <option value="1">1 pt</option>
                                    <option value="2">2 pts</option>
                                    <option value="3">3 pts</option>
                                    <option value="5">5 pts</option>
                                    <option value="8">8 pts</option>
                                    <option value="13">13 pts</option>
                                </select>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold d-flex justify-content-between align-items-center">
                                <span>SUBTASKS (Optional)</span>
                                <button type="button" class="btn btn-sm btn-outline-info py-0 px-2 fs-7" id="btn-add-subtask-field">＋ Add Subtask</button>
                            </label>
                            <div id="subtasks-container">
                                <div class="input-group input-group-sm mb-1 subtask-row">
                                    <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                                    <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                                    <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-sm btn-info text-dark fw-bold" id="btn-save-task">Save Task</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Task Edit Modal -->
    <div class="modal fade" id="editTaskModal" tabindex="-1" aria-labelledby="editTaskModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-light border border-secondary shadow-lg">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title fs-6 fw-bold text-info" id="editTaskModalLabel">✏️ Edit Scheduled Task</h5>
                </div>
                <div class="modal-body">
                    <form id="edit-task-form">
                        <input type="hidden" id="edit-old-raw">
                        
                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">SCHEDULED DATE</label>
                            <input type="date" class="form-control bg-dark text-light border-secondary" id="edit-task-date">
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TASK TYPE</label>
                            <select class="form-select bg-dark text-light border-secondary" id="edit-task-type">
                                <option value="*">* Fluid Task (Default)</option>
                                <option value="!">! Strong Commitment</option>
                                <option value="?">? Arbitrary / Optional</option>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TASK DESCRIPTION</label>
                            <input type="text" class="form-control bg-dark text-light border-secondary" id="edit-task-desc" required autocomplete="off">
                        </div>

                        <div class="mb-3">
                            <div class="row g-2 mb-3">
                                <div class="col-8">
                                    <label class="form-label text-secondary small fw-bold">TAGS</label>
                                    <input type="text" class="form-control bg-dark text-light border-secondary" id="edit-task-tags-input" list="historical-tags-list">
                                </div>
                                <div class="col-4">
                                    <label class="form-label text-secondary small fw-bold">FIB SCORE</label>
                                    <select class="form-select bg-dark text-light border-secondary" id="edit-task-fib-score">
                                        <option value="" selected>None</option>
                                        <option value="1">1 pt</option>
                                        <option value="2">2 pts</option>
                                        <option value="3">3 pts</option>
                                        <option value="5">5 pts</option>
                                        <option value="8">8 pts</option>
                                        <option value="13">13 pts</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold d-flex justify-content-between align-items-center">
                                <span>SUBTASKS</span>
                                <button type="button" class="btn btn-sm btn-outline-info py-0 px-2 fs-7" id="btn-add-edit-subtask-field">＋ Add Subtask</button>
                            </label>
                            <div id="edit-subtasks-container"></div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-sm btn-info text-dark fw-bold" id="btn-update-task">Save Changes</button>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

PARTIAL_TEMPLATE = """
<!-- Schedule Structure Table (Today) -->
<div class="card mb-4 shadow-sm">
    <div class="card-header fw-bold text-uppercase text-secondary fs-6 d-flex justify-content-between align-items-center">
        <span>Today's Schedule Structure</span>
        <div class="d-flex align-items-center gap-2">
            <span class="badge bg-secondary">{{ data.today|length }} Tasks Total</span>
            {% if data.today|length > 10 %}
            <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#todayCollapse">
                Toggle All
            </button>
            {% endif %}
            <button class="btn btn-sm btn-info text-dark fw-bold px-2" type="button" data-bs-toggle="modal" data-bs-target="#addTaskModal">
                ＋ Task
            </button>
        </div>
    </div>
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-dark table-hover m-0 align-middle table-fixed">
                <thead>
                    <tr class="text-secondary">
                        <th style="width: 12%">Type</th>
                        <th style="width: 10%">Time / Date</th>
                        <th style="width: 10%">Context</th>
                        <th style="width: 30%">Task Description</th>
                        <th style="width: 10%">Tags</th>
                        <th style="width: 28%" class="action-cell text-end">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for t in data.today[:10] %}
                        <tr class="task-row {% if 'focus' in t.tags %}table-primary text-light fw-bold border-start border-4 border-info{% endif %}"
                            data-raw="{{ t.raw|forceescape }}"
                            style="cursor: pointer;">
                            <td class="align-top" style="white-space: nowrap;">
                                {% if 'focus' in t.tags %}
                                    <span class="badge bg-info text-dark fw-bold px-2 py-1">🎯 IN FOCUS</span>
                                {% elif t.symbol == '!' %}
                                    <span class="badge badge-strong">STRONG</span>
                                {% elif t.symbol == '?' %}
                                    <span class="badge badge-arbitrary">ARBITRARY</span>
                                {% else %}
                                    <span class="badge badge-fluid">FLUID</span>
                                {% endif %}
                            </td>
                            <td class="text-info fw-semibold align-top" style="white-space: nowrap;">{{ t.time or 'Flexible' }}</td>
                          <td class="align-top">
                            {% if t.contexts %}
                                <span class="badge bg-secondary">@{{ t.contexts[0] }}</span>
                            {% endif %}
                            {% if t.fib_score %}
                                <span class="badge bg-purple text-light border border-purple ms-1" style="background-color: #6b21a8;" title="Fibonacci Effort Score">⚡ {{ t.fib_score }}</span>
                            {% endif %}
                        </td>
                            <td class="align-top">
                                <div class="task-title-cell {% if t.symbol == '?' %}text-muted fst-italic{% else %}fw-semibold{% endif %}">
                                    {{ t.title | render_links | safe }}
                                </div>
                                {% if t.subtasks %}
                                    <ul class="list-unstyled ms-2 mt-2 mb-0 small">
                                        {% for sub in t.subtasks %}
                                            <li class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom border-secondary-subtle">
                                                <span class="subtask-text-container me-3">
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-secondary{% endif %} me-1">↳</span> 
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-muted{% endif %}">{{ sub | render_links | safe }}</span>
                                                </span>
                                                <div class="subtask-action-container flex-shrink-0">
                                                    <button 
                                                        data-parent="{{ t.title|forceescape }}" 
                                                        data-subtask="{{ sub|forceescape }}" 
                                                        class="btn btn-sm {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete-subtask py-0 px-2 fs-7"
                                                        data-bs-toggle="tooltip"
                                                        data-bs-placement="top"
                                                        title="Complete subtask">✓ Done</button>
                                                </div>
                                            </li>
                                        {% endfor %}
                                    </ul>
                                {% endif %}
                            </td>
                            <td class="align-top">
                                {% for tag in t.tags %}
                                    {% if tag != 'focus' %}
                                        <span class="badge bg-dark border border-secondary text-light">#{{ tag }}</span>
                                    {% endif %}
                                {% endfor %}
                            </td>
                            <td class="align-top action-cell text-end" style="white-space: nowrap;">
                                {% if 'focus' in t.tags %}
                                <div class="btn-group btn-group-sm">
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}"
                                        data-title="{{ t.title|forceescape }}"
                                        data-symbol="{{ t.symbol }}"
                                        data-date="{{ t.parsed_date.strftime('%Y-%m-%d') if t.parsed_date else data.today_iso }}"
                                        data-tags="{{ t.tags|join(' ') }}"
                                        data-subtasks='{{ t.subtasks|tojson }}'
                                        class="btn btn-dark text-info border-info btn-edit-task"
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Edit task">✏️</button>
                                    {% if t.time %}
                                        <a 
                                            href="/export_ics?title={{ t.title|urlencode }}&date={{ t.parsed_date.strftime('%Y-%m-%d') if t.parsed_date else data.today_iso }}&time={{ t.time|urlencode if t.time else '' }}" 
                                            class="btn btn-dark text-info border-info"
                                            data-bs-toggle="tooltip"
                                            data-bs-placement="top"
                                            title="Export to Outlook/iCal">📅</a>
                                    {% endif %}

                                    {% if 'priority' not in t.tags %}
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-secondary border-secondary btn-move-bottom"
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Move task to bottom">⬇️</button>
                                    {% endif %}

                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-warning border-warning btn-shift-task"
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Shift to tomorrow">➡️ Tomorrow</button>

                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-success border-success btn-complete-task"
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Mark task completed">✓ Done</button>

                                    <button 
                                        type="button" 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-danger border-danger btn-delete-task" 
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Delete task">✕</button>
                                </div>
                                {% endif %}
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>

            {% if data.today|length > 10 %}
            <div class="collapse" id="todayCollapse">
                <table class="table table-dark table-hover m-0 align-middle border-top border-secondary">
                    <tbody>
                        {% for t in data.today[10:] %}
                        <tr class="task-row {% if 'focus' in t.tags %}table-primary text-light fw-bold border-start border-4 border-info{% endif %}"
                            data-raw="{{ t.raw|forceescape }}"
                            style="cursor: pointer;">
                            <td style="width: 12%" class="align-top">
                                {% if 'focus' in t.tags %}
                                    <span class="badge bg-info text-dark">🎯 IN FOCUS</span>
                                {% elif t.symbol == '!' %}
                                    <span class="badge badge-strong">STRONG</span>
                                {% elif t.symbol == '?' %}
                                    <span class="badge badge-arbitrary">ARBITRARY</span>
                                {% else %}
                                    <span class="badge badge-fluid">FLUID</span>
                                {% endif %}
                            </td>
                            <td style="width: 18%" class="text-info fw-semibold align-top">{{ t.time or 'Flexible' }}</td>
                            <td style="width: 12%" class="align-top">
                                {% if t.contexts %}
                                    <span class="badge bg-secondary">@{{ t.contexts[0] }}</span>
                                {% endif %}
                            </td>
                            <!-- Main Table Row in PARTIAL_TEMPLATE -->
                            <td>
                                <div class="{% if t.symbol == '?' %}text-muted fst-italic{% else %}fw-semibold{% endif %}">
                                    {{ t.title | render_links | safe }}
                                </div>
                                {% if t.subtasks %}
                                    <ul class="list-unstyled ms-2 mt-2 mb-0 small">
                                        {% for sub in t.subtasks %}
                                            <li class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom border-secondary-subtle">
                                                <!-- Left column: Arrow + Text/Links -->
                                                <span class="subtask-text-container me-3" title="{{ sub }}">
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-secondary{% endif %} me-1">↳</span> 
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-muted{% endif %}">{{ sub | render_links | safe }}</span>
                                                </span>
                                                
                                                <!-- Right column: Standardized subtask button group -->
                                                <div class="subtask-action-container flex-shrink-0">
                                                    <button 
                                                        data-parent="{{ t.title|forceescape }}" 
                                                        data-subtask="{{ sub|forceescape }}" 
                                                        class="btn btn-sm {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete-subtask py-0 px-2 fs-7"
                                                        data-bs-toggle="tooltip"
                                                        data-bs-placement="top"
                                                        title="Complete subtask">✓ Done</button>
                                                </div>
                                            </li>
                                        {% endfor %}
                                    </ul>
                                {% endif %}
                            </td>
                            <td class="align-top">
                                {% for tag in t.tags %}
                                    {% if tag != 'focus' %}
                                        <span class="badge bg-dark border border-secondary text-light">#{{ tag }}</span>
                                    {% endif %}
                                {% endfor %}
                            </td>
                            <td style="width: 12%" class="align-top text-end">
                                {% if 'focus' in t.tags %}
                                <div class="btn-group btn-group-sm">
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-warning border-warning{% else %}btn-outline-warning{% endif %} btn-shift-task">➡️ Tomorrow</button>
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete-task">✓ Done</button>
                                    <button 
                                        type="button" 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-danger border-danger btn-delete-task" 
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Delete task">✕</button>
                                </div>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}

            {% if not data.today %}
            <table class="table table-dark m-0">
                <tbody>
                    <tr>
                        <td colspan="6" class="text-center text-muted py-3 fst-italic">No active tasks scheduled for today!</td>
                    </tr>
                </tbody>
            </table>
            {% endif %}
        </div>
    </div>
</div>

<!-- Future Scheduled Tasks -->
{% if data.future %}
<div class="card mb-4 border-info shadow-sm">
    <div class="card-header bg-dark text-info fw-bold d-flex justify-content-between align-items-center">
        <span>📅 Future Scheduled Tasks ({{ data.future|length }} Total)</span>
        {% if data.future|length > 3 %}
        <button class="btn btn-sm btn-outline-info" type="button" data-bs-toggle="collapse" data-bs-target="#futureCollapse">
            Toggle All {{ data.future|length }} Items
        </button>
        {% endif %}
    </div>
    <div class="card-body p-0">
        <ul class="list-group list-group-flush border-bottom border-secondary">
            {% for t in data.future[:3] %}
                <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center">
                    <div>
                        <span class="badge bg-info text-dark me-2">{{ t.time }}</span>
                        <span class="fw-semibold">{{ t.title }}</span>
                        {% if t.contexts %}<span class="badge bg-secondary ms-2">@{{ t.contexts[0] }}</span>{% endif %}
                        {% for tag in t.tags %}
                            <span class="badge bg-dark border border-secondary text-light ms-1">#{{ tag }}</span>
                        {% endfor %}
                    </div>
                    <div class="btn-group btn-group-sm">
                        <button 
                            data-raw="{{ t.raw|forceescape }}"
                            data-title="{{ t.title|forceescape }}"
                            data-symbol="{{ t.symbol }}"
                            data-date="{{ t.parsed_date.strftime('%Y-%m-%d') if t.parsed_date else data.today_iso }}"
                            data-tags="{{ t.tags|join(' ') }}"
                            data-subtasks='{{ t.subtasks|tojson }}'
                            class="btn btn-dark text-info border-info btn-edit-task"
                            data-bs-toggle="tooltip"
                            data-bs-placement="top"
                            title="Edit task">✏️</button>
                        <button 
                            data-raw="{{ t.raw|forceescape }}" 
                            class="btn btn-outline-info btn-make-today">📌 Today</button>
                    </div>
                </li>
            {% endfor %}
        </ul>
        
        {% if data.future|length > 3 %}
        <div class="collapse" id="futureCollapse">
            <ul class="list-group list-group-flush">
                {% for t in data.future[3:] %}
                    <li class="list-group-item bg-transparent text-muted border-secondary d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge bg-secondary me-2">{{ t.time }}</span>
                            <span>{{ t.title }}</span>
                            {% if t.contexts %}<span class="badge bg-secondary ms-2">@{{ t.contexts[0] }}</span>{% endif %}
                            {% for tag in t.tags %}
                                <span class="badge bg-dark border border-secondary text-light ms-1">#{{ tag }}</span>
                            {% endfor %}
                        </div>
                        <div class="btn-group btn-group-sm">
                            <button 
                                data-raw="{{ t.raw|forceescape }}"
                                data-title="{{ t.title|forceescape }}"
                                data-symbol="{{ t.symbol }}"
                                data-date="{{ t.parsed_date.strftime('%Y-%m-%d') if t.parsed_date else data.today_iso }}"
                                data-tags="{{ t.tags|join(' ') }}"
                                data-subtasks='{{ t.subtasks|tojson }}'
                                class="btn btn-dark text-info border-info btn-edit-task"
                                data-bs-toggle="tooltip"
                                data-bs-placement="top"
                                title="Edit task">✏️</button>
                            <button 
                                data-raw="{{ t.raw|forceescape }}" 
                                class="btn btn-outline-info btn-make-today">📌 Today</button>
                        </div>
                    </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>
</div>
{% endif %}

<div class="row g-4 mb-4">
    <!-- Low-Hanging Fruit -->
    <div class="col-md-6">
        <div class="card h-100 border-success shadow-sm">
            <div class="card-header bg-success text-white fw-bold">
                ⚡ Low-Hanging Fruit (<15m / Low Energy)
            </div>
            <ul class="list-group list-group-flush">
                {% set quick_count = namespace(value=0) %}
                {% for t in data.today %}
                    {% if 'quick' in t.tags or 'low_energy' in t.tags %}
                        {% set quick_count.value = quick_count.value + 1 %}
                        <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center">
                            <span>{{ t.title }}</span>
                            <button data-raw="{{ t.raw|forceescape }}" class="btn btn-outline-success btn-complete btn-complete-task">✓</button>
                        </li>
                    {% endif %}
                {% endfor %}
                {% if quick_count.value == 0 %}
                    <li class="list-group-item bg-transparent text-muted fst-italic border-secondary">None logged</li>
                {% endif %}
            </ul>
        </div>
    </div>

    <!-- Gap Fillers -->
    <div class="col-md-6">
        <div class="card h-100 border-warning shadow-sm">
            <div class="card-header bg-warning text-dark fw-bold">
                ⏳ Gap Fillers (While Waiting on Main Task)
            </div>
            <ul class="list-group list-group-flush">
                {% set wait_count = namespace(value=0) %}
                {% for t in data.today %}
                    {% set has_wait = false %}
                    {% for tag in t.tags %}
                        {% if tag == 'wait' or tag.startswith('wait:') %}
                            {% set has_wait = true %}
                        {% endif %}
                    {% endfor %}
                    
                    {% if has_wait %}
                        {% set wait_count.value = wait_count.value + 1 %}
                        <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center">
                            <span>{{ t.title }}</span>
                            <div>
                                {% for tag in t.tags %}
                                    {% if tag == 'wait' or tag.startswith('wait:') %}
                                        <span class="badge bg-secondary me-2">#{{ tag }}</span>
                                    {% endif %}
                                {% endfor %}
                                <button data-raw="{{ t.raw|forceescape }}" class="btn btn-outline-success btn-complete btn-complete-task">✓</button>
                            </div>
                        </li>
                    {% endif %}
                {% endfor %}
                {% if wait_count.value == 0 %}
                    <li class="list-group-item bg-transparent text-muted fst-italic border-secondary">None logged</li>
                {% endif %}
            </ul>
        </div>
    </div>
</div>

<!-- Collapsible Completed Items Panel -->
{% if data.completed %}
<div class="card border-secondary">
    <div class="card-header bg-dark text-muted d-flex justify-content-between align-items-center">
        <span>Completed Tasks</span>
        <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#completedCollapse">
            View {{ data.completed|length }} Completed Items
        </button>
    </div>
    <div class="collapse" id="completedCollapse">
        <ul class="list-group list-group-flush">
            {% for item in data.completed %}
                <li class="list-group-item bg-transparent text-muted text-decoration-line-through border-secondary small">
                    ✓ {{ item }}
                </li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endif %}
"""

# Helpers

def insert_date_at_front(raw_line: str, date_str: str) -> str:
    stripped = raw_line.strip()
    if stripped and stripped[0] in "!*?":
        symbol = stripped[0]
        content = stripped[1:].strip()
        return f"{symbol} {date_str} {content}"
    return f"{date_str} {stripped}"

import re

# web_app.py

# web_app.py
import re
import html

def render_links(text: str) -> str:
    """
    Converts Markdown link syntax into HTML anchor tags supporting http, https, and custom schemes like obsidian://.
    Handles standard [Label](URL) and (URL)[Label] patterns.
    """
    if not text:
        return ""

    # Unescape HTML entities first in case Jinja escaped & to &amp;
    text = html.unescape(text)

    # Standard [Label](URL)
    pattern_std = r'\[([^\]]+)\]\((obsidian://[^\s)]+|https?://[^\s)]+)\)'
    text = re.sub(
        pattern_std, 
        r'<a href="\2" target="_blank" class="text-info text-decoration-underline" onclick="event.stopPropagation();">\1</a>', 
        text
    )

    # Alternative (URL)[Label]
    pattern_alt = r'\((obsidian://[^\s)]+|https?://[^\s)]+)\)\[([^\]]+)\]'
    text = re.sub(
        pattern_alt, 
        r'<a href="\1" target="_blank" class="text-info text-decoration-underline" onclick="event.stopPropagation();">\1</a>', 
        text
    )

    return text

app.jinja_env.filters['render_links'] = render_links

# Endpoints

@app.route("/")
def index():
    data = parse_tasks(str(TASK_FILE))
    return render_template_string(
        HTML_TEMPLATE.replace("{% include 'board_partial.html' %}", PARTIAL_TEMPLATE), 
        data=data
    )

@app.route("/add_task", methods=["POST"])
def add_task():
    req_data = request.get_json()
    symbol = req_data.get("symbol", "*")
    description = req_data.get("description", "").strip()
    tags = req_data.get("tags", [])
    subtasks = req_data.get("subtasks", [])
    selected_date_str = req_data.get("date")

    if not description or not TASK_FILE.exists():
        return jsonify({"status": "error", "message": "Description required"}), 400

    if selected_date_str:
        try:
            target_dt = datetime.strptime(selected_date_str, "%Y-%m-%d")
        except ValueError:
            target_dt = datetime.now()
    else:
        target_dt = datetime.now()

    date_shorthand = f"{target_dt.month}/{target_dt.day}"

    formatted_tags = " ".join([f"#{t.strip('#')}" for t in tags if t.strip()])
    parent_line = f"{symbol} {date_shorthand} {description}"
    if formatted_tags:
        parent_line += f" {formatted_tags}"

    task_block = [parent_line]
    for sub in subtasks:
        sub_clean = sub.strip()
        if sub_clean:
            task_block.append(f"  * {sub_clean}")

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []
    inserted = False

    for line in lines:
        if line.strip() == "# Done" and not inserted:
            new_lines.extend(task_block)
            new_lines.append("")
            inserted = True
        new_lines.append(line)

    if not inserted:
        new_lines.extend(task_block)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

@app.route("/delete_task", methods=["POST"])
def delete_task():
    req_data = request.get_json() or {}
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    delete_line(str(TASK_FILE), raw_line)
    return jsonify({"status": "ok"})

@app.route("/edit_task", methods=["POST"])
def edit_task():
    req_data = request.get_json() or {}
    old_raw = req_data.get("old_raw")
    symbol = req_data.get("symbol", "*")
    description = req_data.get("description", "").strip()
    tags = req_data.get("tags", [])
    subtasks = req_data.get("subtasks", [])
    selected_date_str = req_data.get("date")

    if not old_raw or not description or not TASK_FILE.exists():
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    if selected_date_str:
        try:
            target_dt = datetime.strptime(selected_date_str, "%Y-%m-%d")
        except ValueError:
            target_dt = datetime.now()
    else:
        target_dt = datetime.now()

    date_shorthand = f"{target_dt.month}/{target_dt.day}"

    formatted_tags = " ".join([f"#{t.strip('#')}" for t in tags if t.strip()])
    new_parent_line = f"{symbol} {date_shorthand} {description}"
    if formatted_tags:
        new_parent_line += f" {formatted_tags}"

    new_block = [new_parent_line]
    for sub in subtasks:
        sub_clean = sub.strip()
        if sub_clean:
            new_block.append(f"  * {sub_clean}")

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []
    replacing = False
    target_clean = html.unescape(old_raw).strip()

    for line in lines:
        if line.strip().lower() == target_clean.lower():
            replacing = True
            new_lines.extend(new_block)
            continue

        if replacing:
            if line.startswith(" ") or line.startswith("\t"):
                continue
            else:
                replacing = False

        new_lines.append(line)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

@app.route("/export_ics", methods=["GET"])
def export_ics():
    title = request.args.get("title", "Scheduled Task")
    date_str = request.args.get("date")
    time_str = request.args.get("time")

    ics_data = generate_task_ics(title=title, date_str=date_str, time_str=time_str)
    
    safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', title).lower()[:20] or "task"
    
    return Response(
        ics_data,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}.ics"}
    )

@app.route("/move_to_bottom", methods=["POST"])
def move_to_bottom():
    req_data = request.get_json() or {}
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    move_line_to_bottom(str(TASK_FILE), raw_line)
    return jsonify({"status": "ok"})

@app.route("/partial")
def partial():
    data = parse_tasks(str(TASK_FILE))
    data["today_iso"] = datetime.now().strftime("%Y-%m-%d")
    return render_template_string(PARTIAL_TEMPLATE, data=data)

@app.route("/shift_task", methods=["POST"])
def shift_task():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []

    for line in lines:
        if line.strip() == raw_line.strip():
            new_lines.append(shift_line_to_tomorrow(line))
        else:
            new_lines.append(line)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

@app.route("/stream")
def stream():
    def event_stream():
        last_mtime = 0
        while True:
            if TASK_FILE.exists():
                mtime = TASK_FILE.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    yield "data: reload\n\n"
            
            yield ": keep-alive\n\n"
            time.sleep(0.5)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/toggle_focus", methods=["POST"])
def toggle_focus():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    toggle_line_focus(str(TASK_FILE), raw_line)
    return jsonify({"status": "ok"})

@app.route("/complete_subtask", methods=["POST"])
def complete_subtask():
    req_data = request.get_json()
    parent_title = req_data.get("parent_title")
    subtask_text = req_data.get("subtask")

    if not parent_title or not subtask_text or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []
    in_target_parent = False

    for line in lines:
        stripped = line.strip()

        # Identify parent task line
        if stripped and stripped[0] in "!*?" and parent_title in line:
            in_target_parent = True
            new_lines.append(line)
            continue

        # If inside target subtask block, check if this is the target subtask line to delete
        if in_target_parent and (line.startswith(" ") or line.startswith("\t")):
            if subtask_text in line:
                continue  # Delete/drop this completed subtask line
        elif stripped and stripped[0] in "!*?#":
            in_target_parent = False

        new_lines.append(line)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

@app.route("/complete_task", methods=["POST"])
def complete_task():
    req_data = request.get_json() or {}
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error", "message": "Missing raw_line or task file"}), 400

    # Delegate task manipulation directly to utils/board_etl.py
    etl_complete_task(str(TASK_FILE), raw_line)

    return jsonify({"status": "ok"})

@app.route("/make_today", methods=["POST"])
def make_today():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []

    for line in lines:
        if line.strip() == raw_line.strip():
            new_lines.append(make_line_today(line))
        else:
            new_lines.append(line)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    if not TASK_FILE.exists():
        TASK_FILE.write_text("! 10:30 - 11:00 Weekly Sync @admin #30-min\n* Dry Whites @home #wait\n")
    
    print("Serving Bootstrap 5 Dashboard at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)