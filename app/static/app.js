const output = document.getElementById('output');
const statusBtn = document.getElementById('btn-status');
const startBtn = document.getElementById('btn-start');
const stopBtn = document.getElementById('btn-stop');

async function fetchJson(path, options) {
  const res = await fetch(path, options);
  return res.json();
}

async function updateStatus() {
  const status = await fetchJson('/api/status');
  output.textContent = JSON.stringify(status, null, 2);
}

statusBtn.onclick = updateStatus;
startBtn.onclick = async () => {
  await fetchJson('/api/control/start', { method: 'POST' });
  updateStatus();
};
stopBtn.onclick = async () => {
  await fetchJson('/api/control/stop', { method: 'POST' });
  updateStatus();
};

updateStatus();
