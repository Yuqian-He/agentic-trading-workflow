const output = document.getElementById('output');
const statusBtn = document.getElementById('btn-status');
const startBtn = document.getElementById('btn-start');
const stopBtn = document.getElementById('btn-stop');
const barIntervalSelect = document.getElementById('bar-interval');
const updateIntervalBtn = document.getElementById('btn-update-interval');

async function fetchJson(path, options) {
  const res = await fetch(path, options);
  return res.json();
}

async function updateStatus() {
  const status = await fetchJson('/api/status');
  output.textContent = JSON.stringify(status, null, 2);
}

async function updateSettings() {
  const settings = await fetchJson('/api/settings');
  if (barIntervalSelect) {
    barIntervalSelect.innerHTML = settings.options
      .map(option => `
        <option value="${option}"${option === settings.bar_interval ? ' selected' : ''}>
          ${option}
        </option>`)
      .join('');
  }
}

statusBtn.onclick = updateStatus;
startBtn.onclick = async () => {
  await fetchJson('/api/control/start', { method: 'POST' });
  await updateStatus();
};
stopBtn.onclick = async () => {
  await fetchJson('/api/control/stop', { method: 'POST' });
  await updateStatus();
};

if (updateIntervalBtn) {
  updateIntervalBtn.onclick = async () => {
    const interval = barIntervalSelect.value;
    await fetchJson('/api/settings/bar-interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval }),
    });
    await Promise.all([updateStatus(), updateSettings()]);
  };
}

updateSettings();
updateStatus();
