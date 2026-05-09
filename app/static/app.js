const output = document.getElementById('output');
const startBtn = document.getElementById('btn-start');
const stopBtn = document.getElementById('btn-stop');
const logEl = document.getElementById('log');

const tickerSelect = document.getElementById('ticker');
const barIntervalSelect = document.getElementById('bar-interval');
const sessionEl = document.getElementById('session');
const indicatorsEl = document.getElementById('indicators');
const featuresEl = document.getElementById('features');
const smaSourceSelect = document.getElementById('sma-source');
const smaLengthInput = document.getElementById('sma-length');
const smaTimeframeSelect = document.getElementById('sma-timeframe');
const rsiLengthInput = document.getElementById('rsi-length');
const rsiSourceSelect = document.getElementById('rsi-source');
const rsiOverboughtInput = document.getElementById('rsi-overbought');
const rsiOversoldInput = document.getElementById('rsi-oversold');
const rsiTimeframeSelect = document.getElementById('rsi-timeframe');
const logBuffer = [];
const DEFAULT_TICKERS = ['QQQ', 'AAPL', 'MSFT'];
const DEFAULT_INTERVALS = ['1m', '3m', '5m', '15m', '30m', '45m', '1H', '2H', '3H', '4H'];
let lastSeenLoopStatus = null;
let lastSeenLoopError = null;

function setBusy(isBusy) {
  if (startBtn) startBtn.disabled = isBusy;
  if (stopBtn) stopBtn.disabled = isBusy;
}

async function fetchJson(path, options = {}, timeoutMs = 12000, logMode = 'verbose') {
  const method = options?.method || 'GET';
  const shouldLogRequest = logMode === 'verbose';
  const shouldLogSuccess = logMode === 'verbose';
  const shouldLogError = true;

  if (shouldLogRequest) appendLog(`request: ${method} ${path}`);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(path, { ...options, signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) {
      const text = await res.text();
      if (shouldLogError) appendLog(`response error: ${res.status} ${path}`);
      throw new Error(`${res.status} ${res.statusText}: ${text}`);
    }
    if (shouldLogSuccess) appendLog(`response ok: ${res.status} ${path}`);
    return res.json();
  } catch (err) {
    if (err?.name === 'AbortError') {
      if (shouldLogError) appendLog(`request timeout: ${method} ${path}`);
      throw new Error(`request timeout for ${path}`);
    }
    throw err;
  }
}

function appendLog(message) {
  if (!logEl) return;
  const ts = new Date().toLocaleTimeString();
  logBuffer.push(`[${ts}] ${message}`);
  if (logBuffer.length > 200) logBuffer.shift();
  const rendered = logBuffer
    .map((line) => {
      const escaped = line
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      const isErrorLine = /\berror\b|failed|timeout/i.test(line);
      const cls = isErrorLine ? 'logLine logError' : 'logLine';
      return `<div class="${cls}">${escaped}</div>`;
    })
    .join('');
  logEl.innerHTML = rendered;
  logEl.scrollTop = logEl.scrollHeight;
}

function renderSession({ symbol, bar_interval }) {
  if (!sessionEl) return;
  sessionEl.innerHTML = `
    <div class="pill">Ticker: ${symbol ?? '-'}</div>
    <div class="pill">Interval: ${bar_interval ?? '-'}</div>
  `;
}

function formatLastRun(rawTs) {
  if (!rawTs) return '-';
  const dt = new Date(rawTs);
  if (Number.isNaN(dt.getTime())) return String(rawTs);
  return dt.toLocaleString();
}

function renderIndicators(live) {
  if (!indicatorsEl) return;
  const summary = live?.signals_summary || {};
  const indicators = summary?.indicators || {};
  const inputs = summary?.inputs || {};
  const lastRun = formatLastRun(summary?.last_run || live?.last_run);
  const keys = Array.from(new Set([...Object.keys(indicators), ...Object.keys(inputs)]));

  indicatorsEl.innerHTML = keys
    .map((name) => {
      const cfgObj = inputs[name] || {};
      const cfg = Object.keys(cfgObj).length > 0 ? JSON.stringify(cfgObj) : '-';
      const cfgInline = Object.keys(cfgObj).length > 0
        ? Object.entries(cfgObj).map(([k, v]) => `${k}:${v}`).join(', ')
        : 'no input';
      return `
        <div class="indicatorCard">
          <div class="indicatorHead">
            <div class="indicatorName">${String(name).toUpperCase()} (${cfgInline})</div>
            <div class="indicatorRun">Last run: ${lastRun}</div>
          </div>
          <div class="kv"><div class="k">Input</div><div class="v">${cfg}</div></div>
          <div class="kv"><div class="k">Value</div><div class="v">${indicators[name] ?? '-'}</div></div>
        </div>
      `;
    })
    .join('');
}

function renderFeatures(live) {
  if (!featuresEl) return;
  const summary = live?.features_summary || {};
  const features = summary?.features || {};
  const lastRun = formatLastRun(summary?.last_run || live?.last_run);
  const keys = Object.keys(features);

  if (keys.length === 0) {
    featuresEl.innerHTML = `
      <div class="indicatorCard">
        <div class="indicatorHead">
          <div class="indicatorName">Feature Snapshot</div>
          <div class="indicatorRun">Last run: ${lastRun}</div>
        </div>
        <div class="kv"><div class="k">status</div><div class="v">No features yet</div></div>
      </div>
    `;
    return;
  }

  featuresEl.innerHTML = `
    <div class="indicatorCard">
      <div class="indicatorHead">
        <div class="indicatorName">Feature Snapshot</div>
        <div class="indicatorRun">Last run: ${lastRun}</div>
      </div>
      ${keys
        .map((k) => `<div class="kv"><div class="k">${k}</div><div class="v">${features[k]}</div></div>`)
        .join('')}
    </div>
  `;
}

function getIndicatorInputs() {
  return {
    sma: {
      source: smaSourceSelect?.value ?? 'close',
      length: Number(smaLengthInput?.value ?? 20),
      timeframe: smaTimeframeSelect?.value ?? 'chart',
    },
    rsi: {
      length: Number(rsiLengthInput?.value ?? 14),
      source: rsiSourceSelect?.value ?? 'close',
      overbought: Number(rsiOverboughtInput?.value ?? 70),
      oversold: Number(rsiOversoldInput?.value ?? 30),
      timeframe: rsiTimeframeSelect?.value ?? 'chart',
    },
  };
}

function applyIndicatorInputsToForm(rawInputs) {
  const inputs = rawInputs || {};
  const sma = inputs.sma || {};
  const rsi = inputs.rsi || {};

  if (smaSourceSelect && sma.source != null) smaSourceSelect.value = String(sma.source);
  if (smaLengthInput && sma.length != null) smaLengthInput.value = String(sma.length);
  if (smaTimeframeSelect && sma.timeframe != null) smaTimeframeSelect.value = String(sma.timeframe);

  if (rsiLengthInput && rsi.length != null) rsiLengthInput.value = String(rsi.length);
  if (rsiSourceSelect && rsi.source != null) rsiSourceSelect.value = String(rsi.source);
  if (rsiOverboughtInput && rsi.overbought != null) rsiOverboughtInput.value = String(rsi.overbought);
  if (rsiOversoldInput && rsi.oversold != null) rsiOversoldInput.value = String(rsi.oversold);
  if (rsiTimeframeSelect && rsi.timeframe != null) rsiTimeframeSelect.value = String(rsi.timeframe);
}

async function persistIndicatorInputs() {
  const payload = getIndicatorInputs();
  await fetchJson('/api/settings/indicator-inputs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 12000, 'silent');
  appendLog(`indicator inputs saved: ${JSON.stringify(payload)}`);
}

function normalizeOptions(raw, fallback = []) {
  if (!Array.isArray(raw)) return fallback;
  const normalized = raw
    .map((item) => {
      if (typeof item === 'string') return item.trim();
      if (item == null) return '';
      return String(item).trim();
    })
    .filter(Boolean);
  return normalized.length > 0 ? normalized : fallback;
}

function setSelectOptions(selectEl, options, selectedValue) {
  if (!selectEl) return;
  selectEl.innerHTML = '';

  if (!options || options.length === 0) {
    const emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = 'No options available';
    emptyOpt.disabled = true;
    emptyOpt.selected = true;
    selectEl.appendChild(emptyOpt);
    return;
  }

  options.forEach((value) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = value;
    if (value === selectedValue) opt.selected = true;
    selectEl.appendChild(opt);
  });

  if (!selectEl.value) selectEl.value = options[0];
}

async function updateStatus() {
  try {
    const status = await fetchJson('/api/status', {}, 12000, 'silent');
    renderSession(status);
  } catch (err) {
    appendLog(`status update failed: ${err.message}`);
  }
}

function formatLiveData(live) {
  const tick = live?.tick || {};
  const bar = live?.bar || {};
  const ticker = live?.user_input?.ticker ?? '-';
  const interval = live?.user_input?.interval ?? '-';
  const running = live?.status ?? (live?.running ? 'running' : 'stopped');
  const latestPrice = live?.latest_price ?? '-';

  const bidAsk = `${tick.bid ?? '-'} / ${tick.ask ?? '-'}`;
  const ohlc = `${bar.open ?? '-'} / ${bar.high ?? '-'} / ${bar.low ?? '-'} / ${bar.close ?? '-'}`;
  return `
    <div class="liveBlock">
      <p class="liveBlockTitle">User Input</p>
      <div class="kv"><div class="k">Ticker</div><div class="v">${ticker}</div></div>
      <div class="kv"><div class="k">Interval</div><div class="v">${interval}</div></div>
      <div class="kv"><div class="k">Status</div><div class="v">${running}</div></div>
      <div class="kv"><div class="k">Latest Px</div><div class="v">${latestPrice}</div></div>
    </div>
    <div class="liveBlock">
      <p class="liveBlockTitle">Live Tick</p>
      <div class="kv"><div class="k">Symbol</div><div class="v">${tick.symbol ?? '-'}</div></div>
      <div class="kv"><div class="k">Price</div><div class="v">${tick.price ?? '-'}</div></div>
      <div class="kv"><div class="k">Bid/Ask</div><div class="v">${bidAsk}</div></div>
      <div class="kv"><div class="k">Volume</div><div class="v">${tick.volume ?? '-'}</div></div>
      <div class="kv"><div class="k">Time</div><div class="v">${tick.timestamp ?? '-'}</div></div>
      <div class="kv"><div class="k">Source</div><div class="v">${tick.source ?? '-'}</div></div>
    </div>
    <div class="liveBlock liveWide">
      <p class="liveBlockTitle">Live Bar</p>
      <div class="kv"><div class="k">Symbol</div><div class="v">${bar.symbol ?? '-'}</div></div>
      <div class="kv"><div class="k">OHLC</div><div class="v">${ohlc}</div></div>
      <div class="kv"><div class="k">Volume</div><div class="v">${bar.volume ?? '-'}</div></div>
      <div class="kv"><div class="k">Time</div><div class="v">${bar.timestamp ?? '-'}</div></div>
      <div class="kv"><div class="k">Source</div><div class="v">${bar.source ?? '-'}</div></div>
    </div>
  `;
}

async function updateLive() {
  try {
    const live = await fetchJson('/api/live', {}, 12000, 'silent');
    if (live?.status && live.status !== lastSeenLoopStatus) {
      appendLog(`loop status changed: ${lastSeenLoopStatus || 'unknown'} -> ${live.status}`);
      lastSeenLoopStatus = live.status;
    }
    if (live?.status === 'error' && live?.last_error && live.last_error !== lastSeenLoopError) {
      appendLog(`loop error: ${live.last_error}`);
      lastSeenLoopError = live.last_error;
    }
    output.innerHTML = formatLiveData(live);
    renderIndicators(live);
    renderFeatures(live);
  } catch (err) {
    appendLog(`live data update failed: ${err.message}`);
  }
}

function renderUserSelectionPreview() {
  const preview = {
    running: false,
    latest_price: '-',
    user_input: {
      ticker: tickerSelect?.value ?? '-',
      interval: barIntervalSelect?.value ?? '-',
    },
    tick: {},
    bar: {},
    signals_summary: {},
  };
  output.innerHTML = formatLiveData(preview);
  renderIndicators(preview);
  renderFeatures(preview);
}

if (tickerSelect) {
  tickerSelect.addEventListener('change', () => {
    appendLog(`ticker changed: ${tickerSelect.value || '-'}`);
    renderUserSelectionPreview();
  });
}

if (barIntervalSelect) {
  barIntervalSelect.addEventListener('change', () => {
    appendLog(`interval changed: ${barIntervalSelect.value || '-'}`);
    renderUserSelectionPreview();
  });
}

[
  smaSourceSelect,
  smaLengthInput,
  smaTimeframeSelect,
  rsiLengthInput,
  rsiSourceSelect,
  rsiOverboughtInput,
  rsiOversoldInput,
  rsiTimeframeSelect,
].forEach((el) => {
  if (!el) return;
  el.addEventListener('change', async () => {
    appendLog(`indicator input updated: ${JSON.stringify(getIndicatorInputs())}`);
    try {
      await persistIndicatorInputs();
      await updateLive();
    } catch (err) {
      appendLog(`indicator input save failed: ${err.message}`);
    }
  });
});

async function updateSettings() {
  if (tickerSelect && tickerSelect.options.length === 0) {
    setSelectOptions(tickerSelect, DEFAULT_TICKERS, DEFAULT_TICKERS[0]);
  }
  if (barIntervalSelect && barIntervalSelect.options.length === 0) {
    setSelectOptions(barIntervalSelect, DEFAULT_INTERVALS, DEFAULT_INTERVALS[0]);
  }

  try {
    const settings = await fetchJson('/api/settings', {}, 12000, 'verbose');
    const tickers = normalizeOptions(settings.ticker_options, DEFAULT_TICKERS);
    const intervals = normalizeOptions(settings.options, DEFAULT_INTERVALS);

    if (tickerSelect) {
      setSelectOptions(tickerSelect, tickers, settings.symbol);
    }

    if (barIntervalSelect) {
      setSelectOptions(barIntervalSelect, intervals, settings.bar_interval);
    }
    applyIndicatorInputsToForm(settings.indicator_inputs);

    appendLog(`settings loaded: ${tickers.length} tickers, ${intervals.length} intervals`);
    renderSession({ symbol: settings.symbol, bar_interval: settings.bar_interval });
  } catch (err) {
    appendLog(`settings fetch failed, using local defaults: ${err.message}`);
    renderSession({
      symbol: tickerSelect?.value || DEFAULT_TICKERS[0],
      bar_interval: barIntervalSelect?.value || DEFAULT_INTERVALS[0],
    });
  }
}

async function applySelections() {
  const interval = barIntervalSelect?.value;
  const symbol = tickerSelect?.value;

  if (!symbol) throw new Error('ticker is empty');
  if (!interval) throw new Error('interval is empty');

  await fetchJson('/api/settings/ticker', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol }),
  });

  await fetchJson('/api/settings/bar-interval', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interval }),
  });

  await persistIndicatorInputs();
}

async function handleStartClick() {
  setBusy(true);
  try {
    appendLog(`start requested: applying ${tickerSelect?.value} / ${barIntervalSelect?.value}`);
    appendLog(`indicator inputs: ${JSON.stringify(getIndicatorInputs())}`);
    renderUserSelectionPreview();
    await applySelections();
    appendLog('settings applied, starting loop');
    await fetchJson('/api/control/start', { method: 'POST' });
    appendLog(`loop started with ${tickerSelect?.value} / ${barIntervalSelect?.value}`);
    await Promise.all([updateStatus(), updateLive()]);
  } catch (err) {
    appendLog(`start failed: ${err.message}`);
  } finally {
    appendLog('start action finished');
    setBusy(false);
  }
}

async function handleStopClick() {
  setBusy(true);
  try {
    appendLog('stop requested');
    await fetchJson('/api/control/stop', { method: 'POST' });
    appendLog('loop stopped');
    await Promise.all([updateStatus(), updateLive()]);
  } catch (err) {
    appendLog(`stop failed: ${err.message}`);
  } finally {
    appendLog('stop action finished');
    setBusy(false);
  }
}

if (startBtn) {
  startBtn.addEventListener('click', () => {
    appendLog('start button clicked');
    handleStartClick();
  });
}

if (stopBtn) {
  stopBtn.addEventListener('click', () => {
    appendLog('stop button clicked');
    handleStopClick();
  });
}

Promise.all([updateSettings(), updateStatus(), updateLive()])
  .then(() => {
    appendLog('ui ready');
    appendLog('button handlers attached');
  })
  .catch((err) => appendLog(`init failed: ${err.message}`));

setInterval(updateStatus, 5000);
setInterval(updateLive, 2000);
