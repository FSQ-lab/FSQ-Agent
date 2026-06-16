const state = {
  currentRequestId: null,
  progressTimer: null,
  progressSequence: 0,
};

const els = {
  status: document.getElementById('server-status'),
  refresh: document.getElementById('refresh'),
  deviceSelect: document.getElementById('device-select'),
  createSession: document.getElementById('create-session'),
  destroySession: document.getElementById('destroy-session'),
  sessionMessage: document.getElementById('session-message'),
  goal: document.getElementById('goal'),
  caseYaml: document.getElementById('case-yaml'),
  runSelected: document.getElementById('run-selected'),
  runModeInputs: Array.from(document.querySelectorAll('input[name="run-mode"]')),
  progress: document.getElementById('progress'),
  runtimeInfo: document.getElementById('runtime-info'),
  refreshScreenshot: document.getElementById('refresh-screenshot'),
  screenshot: document.getElementById('screenshot'),
  previewEmpty: document.getElementById('preview-empty'),
  previewTab: document.getElementById('preview-tab'),
  reportTab: document.getElementById('report-tab'),
  previewPane: document.getElementById('preview-pane'),
  reportPane: document.getElementById('report-pane'),
  reportContent: document.getElementById('report-content'),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `${response.status} ${response.statusText}`);
  }
  return data;
}

async function refreshAll() {
  await refreshStatus();
  await refreshSetup();
  await autoCreateSessionIfPossible({ silent: true });
  await refreshStatus();
  await refreshRuntime();
}

async function refreshStatus() {
  try {
    const status = await api('/status');
    els.status.textContent = status.busy ? 'Running' : 'Ready';
    els.runSelected.disabled = Boolean(status.busy);
    if (status.session?.connected) {
      els.sessionMessage.textContent = `Connected to ${status.session.displayName || status.session.deviceId}`;
    } else {
      els.sessionMessage.textContent = 'No active session.';
    }
  } catch (error) {
    els.status.textContent = error.message;
  }
}

async function refreshSetup() {
  try {
    const setup = await api('/session/setup');
    const options = setup.targets || [];
    els.deviceSelect.innerHTML = '';
    for (const target of options) {
      const option = document.createElement('option');
      option.value = target.id;
      option.textContent = target.description ? `${target.label} (${target.description})` : target.label;
      if (target.isDefault || setup.fields?.[0]?.defaultValue === target.id) option.selected = true;
      els.deviceSelect.appendChild(option);
    }
    if (setup.notice) {
      els.sessionMessage.textContent = `${setup.notice.message}: ${setup.notice.description || ''}`;
    }
  } catch (error) {
    els.sessionMessage.textContent = error.message;
  }
}

async function refreshRuntime() {
  try {
    const runtime = await api('/runtime-info');
    const device = runtime.metadata?.selectedDeviceId || 'none';
    const app = runtime.metadata?.appIdPresent ? 'app id set' : 'missing app id';
    els.runtimeInfo.textContent = `${runtime.title} · device: ${device} · ${app}`;
  } catch (error) {
    els.runtimeInfo.textContent = error.message;
  }
}

async function createSession() {
  const deviceId = els.deviceSelect.value;
  if (!deviceId) {
    els.sessionMessage.textContent = 'Select a device first.';
    return;
  }
  try {
    await api('/session', { method: 'POST', body: JSON.stringify({ deviceId }) });
    await refreshAll();
  } catch (error) {
    els.sessionMessage.textContent = error.message;
  }
}

async function autoCreateSessionIfPossible({ silent = false } = {}) {
  try {
    const session = await api('/session');
    if (session.connected) return true;
    const result = await api('/session/auto', { method: 'POST', body: JSON.stringify({}) });
    if (!silent) {
      els.sessionMessage.textContent = `Connected to ${result.session.displayName || result.session.deviceId}`;
    } else if (result.session?.connected) {
      els.sessionMessage.textContent = `Connected to ${result.session.displayName || result.session.deviceId}`;
    }
    return true;
  } catch (error) {
    if (!silent || error.message.includes('Multiple') || error.message.includes('No online')) {
      els.sessionMessage.textContent = error.message;
    }
    return false;
  }
}

async function ensureSession() {
  try {
    const session = await api('/session');
    if (session.connected) return true;
  } catch (error) {
    els.sessionMessage.textContent = error.message;
    return false;
  }
  if (await autoCreateSessionIfPossible()) return true;
  if (els.deviceSelect.value) {
    els.sessionMessage.textContent = 'Select a device, then use it to continue.';
  }
  return false;
}

async function destroySession() {
  try {
    await api('/session', { method: 'DELETE' });
    await refreshAll();
  } catch (error) {
    els.sessionMessage.textContent = error.message;
  }
}

async function runGoal() {
  const goal = els.goal.value.trim();
  if (!goal) return;
  await startExecution({ goal });
}

async function runYaml() {
  const caseYamlPath = els.caseYaml.value.trim();
  if (!caseYamlPath) return;
  await startExecution({ caseYamlPath });
}

async function runSelected() {
  if (currentRunMode() === 'yaml') {
    await runYaml();
    return;
  }
  await runGoal();
}

function currentRunMode() {
  return els.runModeInputs.find((input) => input.checked)?.value || 'goal';
}

function updateRunMode() {
  const mode = currentRunMode();
  const isYaml = mode === 'yaml';
  els.goal.hidden = isYaml;
  els.caseYaml.hidden = !isYaml;
  els.runSelected.textContent = 'Run';
}

async function startExecution(payload) {
  if (!(await ensureSession())) return;
  state.progressSequence = 0;
  els.progress.innerHTML = '';
  els.reportContent.textContent = 'No report yet.';
  try {
    const result = await api('/execute', { method: 'POST', body: JSON.stringify(payload) });
    state.currentRequestId = result.requestId;
    startProgressPolling();
    await refreshStatus();
  } catch (error) {
    appendProgress(`Error: ${error.message}`);
  }
}

function startProgressPolling() {
  if (state.progressTimer) window.clearInterval(state.progressTimer);
  state.progressTimer = window.setInterval(refreshProgress, 1000);
  refreshProgress();
}

async function refreshProgress() {
  if (!state.currentRequestId) return;
  try {
    const progress = await api(`/task-progress/${encodeURIComponent(state.currentRequestId)}`);
    els.progress.innerHTML = '';
    state.progressSequence = 0;
    for (const event of progress.events || []) {
      appendProgress(eventLabel(event), event.sequence, eventDetails(event), eventStatus(event));
    }
    if (progress.status !== 'running') {
      window.clearInterval(state.progressTimer);
      state.progressTimer = null;
      appendProgress(`Finished: ${progress.status}`, null, [], statusFromValue(progress.status));
      if (progress.error) appendProgress(`Error: ${progress.error}`, null, [], 'failed');
      if (progress.result?.runId) {
        await loadReport(progress.result.runId);
      }
      await refreshStatus();
      await refreshRuntime();
    }
  } catch (error) {
    appendProgress(`Progress error: ${error.message}`, null, [], 'failed');
  }
}

async function loadReport(runId) {
  try {
    els.reportContent.textContent = 'Loading report...';
    const report = await api(`/reports/${encodeURIComponent(runId)}?format=markdown`);
    els.reportContent.textContent = report.content || 'Report is empty.';
  } catch (error) {
    els.reportContent.textContent = `Unable to load report: ${error.message}`;
  }
}

function showRightTab(tabName) {
  const showReport = tabName === 'report';
  els.previewPane.hidden = showReport;
  els.reportPane.hidden = !showReport;
  els.previewTab.classList.toggle('active', !showReport);
  els.reportTab.classList.toggle('active', showReport);
  els.previewTab.setAttribute('aria-selected', String(!showReport));
  els.reportTab.setAttribute('aria-selected', String(showReport));
  els.refreshScreenshot.hidden = showReport;
}

function appendProgress(text, backendSequence = null, details = [], status = 'neutral') {
  const hasBackendSequence = Number.isInteger(backendSequence) && backendSequence >= 0;
  if (hasBackendSequence) {
    state.progressSequence = Math.max(state.progressSequence, backendSequence);
  } else {
    state.progressSequence += 1;
  }
  const item = document.createElement('div');
  item.className = 'progress-item';
  const sequence = String(hasBackendSequence ? backendSequence : state.progressSequence).padStart(3, '0');
  const number = document.createElement('span');
  number.className = 'progress-number';
  number.textContent = `${sequence}.`;
  const statusDot = document.createElement('span');
  statusDot.className = `progress-status-dot progress-status-${status}`;
  statusDot.title = status;
  const body = document.createElement('span');
  body.className = 'progress-text';
  body.textContent = text;
  item.appendChild(number);
  item.appendChild(statusDot);
  item.appendChild(body);
  for (const detail of details) {
    item.appendChild(renderProgressDetail(detail.label, detail.value));
  }
  els.progress.appendChild(item);
  els.progress.scrollTop = els.progress.scrollHeight;
}

function eventStatus(event) {
  if (event.type === 'tool_call_failed' || event.type === 'run_failed') return 'failed';
  if (event.type === 'run_completed') return statusFromValue(event.payload?.status);
  const payloadStatus = statusFromValue(event.payload?.status);
  if (payloadStatus !== 'neutral') return payloadStatus;
  if (hasDisplayValue(event.payload?.error_message) || hasDisplayValue(event.payload?.failure_category)) {
    return 'failed';
  }
  const output = parseMaybeJson(event.tool_output_preview);
  const outputStatus = statusFromValue(output?.status ?? output?.result?.status);
  if (outputStatus !== 'neutral') return outputStatus;
  if (event.type === 'tool_call_completed') return 'success';
  return 'neutral';
}

function statusFromValue(value) {
  if (typeof value !== 'string') return 'neutral';
  const normalized = value.toLowerCase();
  if (['success', 'passed', 'pass', 'completed', 'recorded'].includes(normalized)) return 'success';
  if (['failed', 'failure', 'error', 'cancelled', 'skipped'].includes(normalized)) return 'failed';
  return 'neutral';
}

function parseMaybeJson(value) {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function eventLabel(event) {
  const title = event.title || event.type || 'Event';
  const message = event.message ? `: ${event.message}` : '';
  const tool = event.tool_name ? ` [${event.tool_name}]` : '';
  return `${title}${tool}${message}`;
}

function eventDetails(event) {
  const details = [];
  if (hasDisplayValue(event.tool_arguments)) {
    details.push({ label: 'Input', value: event.tool_arguments });
  }
  if (hasDisplayValue(event.tool_output_preview)) {
    details.push({ label: 'Output', value: event.tool_output_preview });
  }
  if (hasMeaningfulPayload(event.payload)) {
    details.push({ label: 'Payload', value: event.payload });
  }
  return details;
}

function renderProgressDetail(label, value) {
  const detail = document.createElement('details');
  detail.className = 'progress-detail';
  const summary = document.createElement('summary');
  summary.textContent = label;
  const pre = document.createElement('pre');
  pre.textContent = formatProgressValue(value);
  detail.appendChild(summary);
  detail.appendChild(pre);
  return detail;
}

function formatProgressValue(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return '';
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      return trimmed;
    }
  }
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function hasDisplayValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  return true;
}

function hasMeaningfulPayload(payload) {
  if (!payload || typeof payload !== 'object') return false;
  return Object.entries(payload).some(([, value]) => hasDisplayValue(value));
}

async function refreshScreenshot() {
  try {
    const result = await api('/screenshot');
    if (!result.available) {
      els.previewEmpty.textContent = result.error || 'Screenshot unavailable.';
      els.previewEmpty.style.display = 'block';
      els.screenshot.style.display = 'none';
      return;
    }
    els.screenshot.src = `data:image/png;base64,${result.screenshot}`;
    els.screenshot.style.display = 'block';
    els.previewEmpty.style.display = 'none';
  } catch (error) {
    els.previewEmpty.textContent = error.message;
    els.previewEmpty.style.display = 'block';
    els.screenshot.style.display = 'none';
  }
}

els.refresh.addEventListener('click', refreshAll);
els.createSession.addEventListener('click', createSession);
els.destroySession.addEventListener('click', destroySession);
els.runSelected.addEventListener('click', runSelected);
for (const input of els.runModeInputs) {
  input.addEventListener('change', updateRunMode);
}
els.previewTab.addEventListener('click', () => showRightTab('preview'));
els.reportTab.addEventListener('click', () => showRightTab('report'));
els.refreshScreenshot.addEventListener('click', refreshScreenshot);

updateRunMode();
showRightTab('preview');
refreshAll();