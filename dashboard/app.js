const peersContainer = document.getElementById('peers');
const callsContainer = document.getElementById('calls');
const baseURL = `${window.location.protocol}//${window.location.host}`;

function formatTimestamp(ts) {
  if (!ts) return "--"

  const date = new Date(ts * 1000);
  const now = new Date();

  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  const timeStr = date.toLocaleTimeString('en-US', { hour12: false });
  const dateStr = date.toLocaleDateString();

  const secondsAgo = Math.floor((now - date) / 1000);
  const rel = secondsAgo < 60
    ? `${secondsAgo}s ago`
    : secondsAgo < 3600
    ? `${Math.floor(secondsAgo / 60)}m ago`
    : secondsAgo < 86400
    ? `${Math.floor(secondsAgo / 3600)}h ago`
    : `${Math.floor(secondsAgo / 86400)}d ago`;

  return `${isToday ? timeStr : `${dateStr} ${timeStr}`} <span class="text-xs">(${rel})</span>`;
}

async function fetchData() {
  try {
    const dashboardRes = await fetch(`${baseURL}/api/dashboard`);
    const dashboardData = await dashboardRes.json();

    renderPeers(dashboardData.peers || []);
    renderCallsTable(dashboardData.calls || []);
  } catch (err) {
    console.error('Error fetching data:', err);
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'ACTIVE': return 'bg-green-900 text-green-200';
    case 'TIMEOUT': return 'bg-yellow-900 text-yellow-200';
    case 'DEAD': return 'bg-red-950 text-red-200';
    default: return 'bg-cyan-900 text-cyan-200';
  }
}

function toggleVisibility(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.toggle('hidden');
  }
}

let nextExpandedSectionId = 0;

function renderPeers(peers) {
  peersContainer.innerHTML = '';
  if (peers.length === 0) {
    peersContainer.innerHTML = '<p class="text-gray-500">No peers connected.</p>';
    return;
  }

  peers.forEach(peer => {
    const div = document.createElement('div');
    div.className = 'bg-gray-800 rounded-md shadow overflow-hidden';

    const cardTitleColor = getStatusColor(peer.status);
    const unitsHTML = (peer.units || [])
      .map(unit => `<span class="text-xs bg-cyan-800 text-cyan-200 px-2 py-1 rounded mr-1">${unit}</span>`)
      .join('');

    const callsign = peer.config.callsign || "--"

    const expandedSectionId = `expandable-${nextExpandedSectionId++}`;

    div.innerHTML = `
      <h3 class="text-lg font-bold p-3 py-1 ${cardTitleColor}">${peer.name}</h3>
      <div class="p-3 pt-2 pb-4">
        <div><strong>Callsign:</strong> ${callsign}</div>
        <div><strong>Address:</strong> ${peer.addr}</div>
        <div><strong>Status:</strong> ${peer.status}</div>
        <div><strong>Connected:</strong> ${formatTimestamp(peer.connect_time)}</div>
        <div><strong>Last Active:</strong> ${formatTimestamp(peer.active_time)}</div>
        ${unitsHTML? `<div class="mt-2">${unitsHTML}</div>` : ''}
      </div>
    `;

    peersContainer.appendChild(div);
  });
}

let tableUpdateIntervals = [];

function renderCallsTable(calls) {
  tableUpdateIntervals.forEach(tui => {
    clearInterval(tui)
  });
  tableUpdateIntervals = []

  const tableBody = document.getElementById('calls-table-body');
  tableBody.innerHTML = '';

  if (!calls.length) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-4 text-gray-500">No calls at the moment.</td>
      </tr>
    `;
    return;
  }

  calls.forEach(call => {
    const row = document.createElement('tr');
    row.className = `border-b border-gray-700 ${
      call.is_ended ? '' : 'bg-yellow-900 animate-pulse'
    }`;

    const durationCell = document.createElement('td');
    durationCell.className = 'px-4 py-2 text-center';

    if (call.is_ended) {
      durationCell.textContent = call.time;
    } else {
      // Dynamic live updating
      const startMs = call.start_time * 1000;
      function updateDuration() {
        const now = Date.now();
        const delta = ((now - startMs) / 1000).toFixed(1);
        durationCell.textContent = `${delta}s`;
        // console.log(`Upd dur ${durationCell}`)
      }
      updateDuration();
      tableUpdateIntervals.push(setInterval(updateDuration, 330));
    }

    let dstBadgeStyle = call.call_type === 'GROUP'
      ? 'bg-blue-900 text-blue-200'
      : 'bg-cyan-900 text-cyan-200';

    let dstBadgeText = call.call_type === 'GROUP'
      ? "TG-" + call.dst_id
      : call.dst_id;

    let routingHTML = '';
    if (call.broadcast) {
      routingHTML = `<span class="text-xs bg-gray-700 text-white px-2 py-1 rounded mr-1">Broadcast</span>`;
    } else if (call.route_to && call.route_to.length > 0) {
      routingHTML = call.route_to
        .map(r => `<span class="text-xs bg-green-900 text-green-200 px-2 py-1 rounded mr-1">${r}</span>`)
        .join('');
    }

    row.innerHTML = `
      <td class="px-4 py-2 text-right">${call.call_id}</td>
      <td class="px-4 py-2 text-left whitespace-nowrap">${formatTimestamp(call.start_time)}</td>
      <td class="px-4 py-2 text-left whitespace-nowrap">
        <span class="p-0.5 px-2 rounded bg-cyan-800 text-cyan-200">${call.src_id}</span>
        <span class="text-gray-400">⇉</span>
        <span class="p-0.5 px-2 rounded ${dstBadgeStyle}">${dstBadgeText}</span>
      </td>
      <td class="px-4 py-2 text-left whitespace-nowrap">${routingHTML}</td>
    `;

    row.appendChild(durationCell);
    tableBody.appendChild(row);
  });
}

fetchData();
setInterval(fetchData, 3000);
