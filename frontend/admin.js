/* Galaxy — owner admin panel */

const KEY = 'galaxy.admin.key';

const $ = (id) => document.getElementById(id);

function adminKey() {
  return sessionStorage.getItem(KEY) || '';
}

function isInf(value) {
  return value === 'Infinity' || value === '∞';
}

function fmt(value) {
  if (value === null || value === undefined) return '0';
  if (isInf(value)) return '∞';
  let n = BigInt(value);
  let sign = '';
  if (n < 0n) {
    sign = '-';
    n = -n;
  }
  if (n < 1000n) return sign + n.toString();
  const suffixes = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oc', 'No', 'Dc'];
  const digits = n.toString();
  const group = Math.floor((digits.length - 1) / 3);
  const index = Math.min(group, suffixes.length - 1);
  const head = digits.slice(0, digits.length - group * 3);
  const tail = digits
    .slice(digits.length - group * 3, digits.length - group * 3 + 2)
    .replace(/0+$/, '');
  return sign + head + (tail ? '.' + tail : '') + suffixes[index];
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', 'X-Admin-Key': adminKey() },
    ...options,
  });
  if (!response.ok) {
    let message = 'Something went wrong';
    try {
      const body = await response.json();
      if (body && body.detail) message = body.detail;
    } catch (error) {
      /* keep the generic message */
    }
    throw new Error(message);
  }
  return response.json();
}

function message(text, kind = '') {
  const el = $('message');
  el.textContent = text;
  el.className = 'message ' + kind;
}

function show(snapshot) {
  const player = snapshot.player;
  $('money').textContent = fmt(player.money);
  $('per-click').textContent = fmt(player.click_income);
  $('per-sec').textContent = fmt(player.income_per_sec);
  $('floor').textContent = player.floor + ' / ' + player.total_floors;
  $('boost').checked = player.admin_click_boost;
}

async function refresh() {
  try {
    show(await api('/api/state'));
  } catch (error) {
    unlockFailed(error.message);
  }
}

function open() {
  $('gate-panel').classList.add('hidden');
  $('panel').classList.remove('hidden');
  refresh();
}

function unlockFailed(text) {
  $('panel').classList.add('hidden');
  $('gate-panel').classList.remove('hidden');
  const el = $('gate-message');
  el.textContent = text;
  el.className = 'message error';
}

async function unlock() {
  const password = $('password').value;
  try {
    const response = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Wrong admin password');
    }
    sessionStorage.setItem(KEY, password);
    $('gate-message').textContent = '';
    open();
  } catch (error) {
    unlockFailed(error.message);
  }
}

$('unlock').addEventListener('click', unlock);
$('password').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') unlock();
});

$('grant').addEventListener('click', async () => {
  try {
    show(await api('/api/admin/grant', { method: 'POST' }));
    message('100 nonillion delivered.', 'ok');
  } catch (error) {
    message(error.message, 'error');
  }
});

$('boost').addEventListener('change', async (event) => {
  const enabled = event.target.checked;
  try {
    show(
      await api('/api/admin/click-boost', {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      })
    );
    message(enabled ? 'Every click now pays 100 nonillion.' : 'Click boost off.', 'ok');
  } catch (error) {
    message(error.message, 'error');
    refresh();
  }
});

$('reset').addEventListener('click', async () => {
  if (!window.confirm('Wipe the whole save and start from floor 1?')) return;
  try {
    show(await api('/api/admin/reset', { method: 'POST' }));
    message('Game reset.', 'ok');
  } catch (error) {
    message(error.message, 'error');
  }
});

if (adminKey()) {
  open();
}
