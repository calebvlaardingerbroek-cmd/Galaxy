/* Galaxy — game client */

const SUFFIXES = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oc', 'No', 'Dc', 'UDc', 'DDc', 'TDc'];

let snapshot = null;
let pendingMoney = 0n;
let pendingClicks = 0;
let lastFloor = 0;

const $ = (id) => document.getElementById(id);

function isInf(value) {
  return value === 'Infinity' || value === '∞';
}

/** 1200000 -> "1.2M", 100000000000000000000000000000000 -> "100No", Infinity -> "∞" */
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
  const digits = n.toString();
  const group = Math.floor((digits.length - 1) / 3);
  const index = Math.min(group, SUFFIXES.length - 1);
  const head = digits.slice(0, digits.length - group * 3);
  const tail = digits
    .slice(digits.length - group * 3, digits.length - group * 3 + 2)
    .replace(/0+$/, '');
  return sign + head + (tail ? '.' + tail : '') + SUFFIXES[index];
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
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

function flash(message, kind = '') {
  const status = $('status');
  status.textContent = message;
  status.className = kind;
}

function setSnapshot(next) {
  snapshot = next;
  render();
}

function displayMoney() {
  const money = snapshot.player.money;
  if (isInf(money)) return '∞';
  let total = BigInt(money) + pendingMoney;
  if (total < 0n) total = 0n;
  return fmt(total);
}

function render() {
  if (!snapshot) return;
  const player = snapshot.player;

  $('money').textContent = displayMoney();
  $('per-click').textContent = fmt(player.click_income);
  $('per-sec').textContent = fmt(player.income_per_sec);
  $('floor').textContent = player.floor + ' / ' + player.total_floors;
  $('click-hint').textContent = '+' + fmt(player.click_income);
  $('boost-badge').hidden = !player.admin_click_boost;

  const floorInfo = snapshot.floors.find((item) => item.number === player.floor);
  if (floorInfo) {
    $('floor-name').textContent = floorInfo.name;
    $('floor-sub').textContent = 'Floor ' + floorInfo.number;
  }

  renderUpgrades();
  renderFloors();
  renderAwards();
}

function renderUpgrades() {
  const list = $('upgrades');
  list.innerHTML = '';
  for (const upgrade of snapshot.upgrades) {
    const item = document.createElement('li');
    item.className =
      'upgrade' + (upgrade.locked ? ' locked' : '') + (upgrade.count ? ' owned' : '');

    const info = document.createElement('div');
    info.className = 'upgrade-info';
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = upgrade.name;
    const text = document.createElement('span');
    text.className = 'muted small';
    text.textContent = upgrade.text;
    info.append(name, text);

    const action = document.createElement('div');
    action.className = 'upgrade-action';

    const count = document.createElement('span');
    count.className = 'count';
    count.textContent = upgrade.count ? '×' + upgrade.count : '';
    action.append(count);

    const button = document.createElement('button');
    button.className = 'buy';
    if (upgrade.locked) {
      button.textContent = 'Floor ' + upgrade.unlock_floor;
      button.disabled = true;
    } else {
      button.textContent = fmt(upgrade.cost);
      button.disabled = !upgrade.affordable;
      button.addEventListener('click', () => buy(upgrade.id));
    }
    action.append(button);

    item.append(info, action);
    list.append(item);
  }
}

function renderFloors() {
  const list = $('floors');
  list.innerHTML = '';
  for (const floor of snapshot.floors) {
    const item = document.createElement('li');
    item.className = floor.current ? 'current' : floor.unlocked ? 'unlocked' : '';
    const label = document.createElement('span');
    label.textContent = floor.number + '. ' + floor.name;
    const requirement = document.createElement('span');
    requirement.className = 'floor-req';
    requirement.textContent = floor.number === 1 ? 'start' : fmt(floor.requirement);
    item.append(label, requirement);
    list.append(item);
  }
  const floor = snapshot.player.floor;
  if (floor !== lastFloor) {
    lastFloor = floor;
    const current = list.querySelector('.current');
    if (current) current.scrollIntoView({ block: 'nearest' });
  }
}

function renderAwards() {
  const list = $('awards');
  list.innerHTML = '';
  for (const award of snapshot.awards) {
    const item = document.createElement('li');
    item.className = 'award' + (award.earned ? ' earned' : '');

    const info = document.createElement('div');
    info.className = 'award-info';
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = award.name;
    const requirement = document.createElement('span');
    requirement.className = 'muted small';
    requirement.textContent = 'at ' + fmt(award.requirement) + ' earned';
    info.append(name, requirement);

    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = award.earned ? '×' + award.multiplier + ' income' : 'locked';

    item.append(info, tag);
    list.append(item);
  }
}

async function buy(upgradeId) {
  try {
    setSnapshot(await api('/api/buy/' + upgradeId, { method: 'POST' }));
    flash('Purchased.', 'ok');
  } catch (error) {
    flash(error.message, 'error');
  }
}

async function doClick() {
  if (!snapshot) return;
  const gain = snapshot.player.click_income;

  pendingClicks += 1;
  if (!isInf(gain)) pendingMoney += BigInt(gain);
  render();

  try {
    const next = await api('/api/click', { method: 'POST' });
    pendingClicks = Math.max(0, pendingClicks - 1);
    if (!isInf(gain)) pendingMoney -= BigInt(gain);
    if (pendingMoney < 0n) pendingMoney = 0n;
    setSnapshot(next);
  } catch (error) {
    pendingClicks = 0;
    pendingMoney = 0n;
    flash(error.message, 'error');
    render();
  }
}

async function refresh() {
  try {
    setSnapshot(await api('/api/state'));
  } catch (error) {
    flash('Lost connection to the office…', 'error');
  }
}

$('click-btn').addEventListener('click', doClick);
document.addEventListener('keydown', (event) => {
  if (event.code === 'Space' && event.target === document.body) {
    event.preventDefault();
    doClick();
  }
});

refresh();
setInterval(refresh, 1000);
