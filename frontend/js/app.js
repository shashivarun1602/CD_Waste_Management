const state = { currentView: 'dashboard', facilities: [], selectedSiteId: null, selectedSiteSummary: null, selectedVehicleId: null, selectedVehicle: null, selectedTransportId: null };
const $ = (selector) => document.querySelector(selector);
const esc = (value = '') => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
const flash = (message, isError = false) => { const element = $('#flash'); element.textContent = message; element.style.background = isError ? '#fff0df' : ''; element.style.color = isError ? '#a75c18' : ''; element.classList.add('show'); setTimeout(() => element.classList.remove('show'), 3500); };

function showView(view) {
  state.currentView = view;
  document.querySelectorAll('.view').forEach((element) => element.classList.toggle('active-view', element.id === `${view}-view`));
  document.querySelectorAll('.nav-item').forEach((element) => element.classList.toggle('active', element.dataset.view === view));
  const labels = { dashboard: ['Overview', 'Chain of custody, at a glance.'], sites: ['Construction sites', 'Every origin, accounted for.'], 'site-detail': ['Site overview', 'Activity and vehicle participation at this site.'], 'vehicle-detail': ['Vehicle diary', 'Trips for this vehicle at the selected site.'], 'transport-detail': ['Transport detail', 'Recorded trip, verification, and telemetry.'], vehicles: ['Vehicles', 'A reusable fleet with a permanent history.'], facilities: ['Facilities', 'Authorized destinations for recovered material.'], devices: ['Devices', 'Permanent ESP32 identities mapped to vehicles.'], transport: ['Transport monitor', 'Follow every load to its authorized destination.'], tracking: ['GPS tracking', 'Simulate the same contract used by hardware.'] };
  $('#view-label').textContent = labels[view][0]; $('#page-title').textContent = labels[view][1];
  if (view === 'dashboard') loadOverview();
  if (view === 'sites') loadSites();
  if (view === 'site-detail' && state.selectedSiteId) loadSiteDetail(state.selectedSiteId);
  if (view === 'vehicle-detail' && state.selectedSiteId && state.selectedVehicleId) loadVehicleDetail(state.selectedSiteId, state.selectedVehicleId);
  if (view === 'transport-detail' && state.selectedTransportId) loadTransportDetail(state.selectedTransportId);
  if (view === 'vehicles') loadVehicles();
  if (view === 'facilities') loadFacilities();
  if (view === 'devices') loadDevices();
  if (view === 'transport') loadTransports();
  if (view === 'tracking') loadGps();
}

function statusTag(status) { return `<span class="status-tag ${status === 'Mismatch' ? 'warning' : ''}">${esc(status || 'Pending')}</span>`; }
function emptyRow(message, columns) { return `<tr><td colspan="${columns}" style="color:var(--muted)">${esc(message)}</td></tr>`; }
function displayValue(value) { return value === null || value === undefined || value === '' ? 'Not available' : esc(value); }
function displayWeight(value, count) { return value === null || value === undefined ? 'Not available' : `${Number(value).toLocaleString()} kg (${count} recorded)`; }
function summaryCard(label, value) { return `<article class="stat-card"><span>${esc(label)}</span><strong>${displayValue(value)}</strong></article>`; }

async function loadOverview() {
  try {
    const [healthResponse, data] = await Promise.all([fetch('/health'), dashboard.load()]);
    $('#health-status').textContent = healthResponse.ok ? 'API online' : 'API unavailable';
    const cards = [['total_sites', 'Total sites'], ['active_sites', 'Active sites'], ['total_vehicles', 'Vehicles'], ['active_transports', 'Active transports'], ['weight_mismatches', 'Weight mismatches']];
    $('#stats-grid').innerHTML = cards.map(([key, label]) => `<article class="stat-card"><span>${label}</span><strong>${data[key] ?? 0}</strong></article>`).join('');
    $('#recent-transports').innerHTML = data.recent_transports?.length ? data.recent_transports.map((item) => `<tr><td>${esc(item.transport_id)}</td><td>${esc(item.site_id)} -> ${esc(item.facility_id)}</td><td>${esc(item.waste_type || item.waste_id)}</td><td>${statusTag(item.status)}</td><td>${item.loaded_weight_kg ?? '-'} kg</td></tr>`).join('') : emptyRow('No transport records yet.', 5);
    $('#verification-alerts').innerHTML = data.weight_mismatches ? `<div class="alert-item"><strong>${data.weight_mismatches}</strong> load${data.weight_mismatches === 1 ? '' : 's'} require review.</div>` : '<div class="alert-item" style="border-left-color:var(--green);background:#f1f7ee;color:var(--green)">No mismatches in the queue.</div>';
  } catch (error) { $('#health-status').textContent = 'MongoDB offline'; flash('Connect MongoDB to load live dashboard data.', true); }
}

async function loadSites() {
  try {
    const sites = await dashboard.siteSummaries();
    $('#sites-table').innerHTML = sites.length ? sites.map((site) => `<tr><td>${esc(site.site_id)}</td><td><strong>${esc(site.project_name || site.name || 'Not available')}</strong></td><td>${displayValue(site.address)}</td><td>${displayValue(site.status)}</td><td>${displayValue(site.activity_status)}</td><td>${site.total_vehicles}</td><td>${site.total_transports}</td><td>${displayWeight(site.total_loaded_weight_kg, site.loaded_weight_records)}</td><td>${site.completed_transports}</td><td>${site.active_transports}</td><td>${site.mismatches}</td><td><button class="text-button" data-open-site="${esc(site.site_id)}">Open site</button></td></tr>`).join('') : emptyRow('Create your first construction site.', 12);
    document.querySelectorAll('[data-open-site]').forEach((button) => button.addEventListener('click', () => openSite(button.dataset.openSite)));
  } catch (error) {
    $('#sites-table').innerHTML = emptyRow('Unable to load site summaries.', 12);
    flash(error.message, true);
  }
}

function openSite(siteId) {
  state.selectedSiteId = siteId;
  state.selectedVehicleId = null;
  state.selectedTransportId = null;
  showView('site-detail');
}

async function loadSiteDetail(siteId) {
  try {
    const [site, vehicles] = await Promise.all([dashboard.siteSummary(siteId), dashboard.siteVehicles(siteId)]);
    state.selectedSiteSummary = site;
    $('#site-detail-breadcrumb').textContent = site.site_id;
    $('#site-detail-title').textContent = site.project_name || site.name || site.site_id;
    $('#site-summary-cards').innerHTML = [
      summaryCard('Site ID', site.site_id),
      summaryCard('Address', site.address),
      summaryCard('Site status', site.status),
      summaryCard('Activity', site.activity_status),
      summaryCard('Vehicles', site.total_vehicles),
      summaryCard('Transports', site.total_transports),
      summaryCard('Loaded weight recorded', displayWeight(site.total_loaded_weight_kg, site.loaded_weight_records)),
      summaryCard('Received weight recorded', displayWeight(site.total_received_weight_kg, site.received_weight_records)),
      summaryCard('Completed', site.completed_transports),
      summaryCard('Active', site.active_transports),
      summaryCard('Verified', site.verified_transports),
      summaryCard('Pending verification', site.pending_verification),
      summaryCard('Mismatches', site.mismatches)
    ].join('');
    $('#site-vehicles-table').innerHTML = vehicles.length ? vehicles.map((item) => {
      const vehicle = item.vehicle || {};
      return `<tr><td>${esc(item.vehicle_id)}</td><td>${displayValue(vehicle.registration_number)}</td><td>${displayValue(vehicle.vehicle_type)}</td><td>${vehicle.capacity_kg == null ? 'Not available' : `${esc(vehicle.capacity_kg)} kg`}</td><td>${item.total_transports}</td><td>${displayWeight(item.total_loaded_weight_kg, item.loaded_weight_records)}</td><td>${displayWeight(item.total_received_weight_kg, item.received_weight_records)}</td><td>${item.completed_transports}</td><td>${item.active_transports}</td><td>${item.mismatches}</td><td><button class="text-button" data-open-vehicle="${esc(item.vehicle_id)}">Open diary</button></td></tr>`;
    }).join('') : emptyRow('No vehicles have transport records for this site.', 11);
    document.querySelectorAll('[data-open-vehicle]').forEach((button) => button.addEventListener('click', () => openVehicle(button.dataset.openVehicle)));
  } catch (error) {
    flash(error.message, true);
    $('#site-vehicles-table').innerHTML = emptyRow('Unable to load site details.', 11);
  }
}

function openVehicle(vehicleId) {
  state.selectedVehicleId = vehicleId;
  state.selectedTransportId = null;
  showView('vehicle-detail');
}

async function loadVehicleDetail(siteId, vehicleId) {
  try {
    const [vehicles, transports] = await Promise.all([
      dashboard.siteVehicles(siteId),
      dashboard.siteVehicleTransports(siteId, vehicleId)
    ]);
    const item = vehicles.find((vehicle) => vehicle.vehicle_id === vehicleId);
    if (!item) throw new Error('Vehicle has no transport history at this site.');
    const vehicle = item.vehicle || {};
    state.selectedVehicle = vehicle;
    $('#vehicle-site-breadcrumb').textContent = siteId;
    $('#vehicle-detail-breadcrumb').textContent = vehicleId;
    $('#vehicle-detail-title').textContent = vehicle.registration_number || vehicleId;
    $('#vehicle-summary-cards').innerHTML = [
      summaryCard('Vehicle ID', vehicleId),
      summaryCard('Registration', vehicle.registration_number),
      summaryCard('Vehicle type', vehicle.vehicle_type),
      summaryCard('Capacity', vehicle.capacity_kg == null ? null : `${vehicle.capacity_kg} kg`),
      summaryCard('Transports at this site', item.total_transports),
      summaryCard('Loaded weight recorded', displayWeight(item.total_loaded_weight_kg, item.loaded_weight_records)),
      summaryCard('Received weight recorded', displayWeight(item.total_received_weight_kg, item.received_weight_records)),
      summaryCard('Completed', item.completed_transports),
      summaryCard('Active', item.active_transports),
      summaryCard('Pending verification', item.pending_verification),
      summaryCard('Mismatches', item.mismatches)
    ].join('');
    $('#vehicle-transports-table').innerHTML = transports.length ? transports.map((transport) => `<tr><td>${esc(transport.transport_id)}</td><td>${displayValue(transport.created_at)}</td><td>${displayValue(transport.loaded_weight_kg == null ? null : `${transport.loaded_weight_kg} kg`)}</td><td>${displayValue(transport.received_weight_kg == null ? null : `${transport.received_weight_kg} kg`)}</td><td>${displayValue(transport.facility_id)}</td><td>${displayValue(transport.status)}</td><td>${displayValue(transport.weight_status)}</td><td>${displayValue(transport.latest_route_status)}</td><td><button class="text-button" data-open-transport="${esc(transport.transport_id)}">Open</button></td></tr>`).join('') : emptyRow('No transports for this vehicle at this site.', 9);
    document.querySelectorAll('[data-open-transport]').forEach((button) => button.addEventListener('click', () => openTransport(button.dataset.openTransport)));
  } catch (error) {
    flash(error.message, true);
    $('#vehicle-transports-table').innerHTML = emptyRow('Unable to load this transport diary.', 9);
  }
}

function openTransport(transportId) {
  state.selectedTransportId = transportId;
  showView('transport-detail');
}

async function loadTransportDetail(transportId) {
  try {
    const transport = await api.get(`/transports/${encodeURIComponent(transportId)}`);
    const [facility, waste] = await Promise.all([
      transport.facility_id ? api.get(`/facilities/${encodeURIComponent(transport.facility_id)}`).catch(() => null) : null,
      transport.waste_id ? api.get(`/waste/${encodeURIComponent(transport.waste_id)}`).catch(() => null) : null
    ]);
    const latestGps = transport.latest_gps || (transport.gps_history || [])[0] || null;
    $('#transport-site-breadcrumb').textContent = transport.site_id || state.selectedSiteId;
    $('#transport-vehicle-breadcrumb').textContent = transport.vehicle_id || state.selectedVehicleId;
    $('#transport-detail-breadcrumb').textContent = transport.transport_id;
    $('#transport-detail-title').textContent = transport.transport_id;
    const details = [
      ['Transport ID', transport.transport_id],
      ['Site ID', transport.site_id],
      ['Site / project', state.selectedSiteSummary?.project_name || state.selectedSiteSummary?.name],
      ['Site address', state.selectedSiteSummary?.address],
      ['Vehicle ID', transport.vehicle_id],
      ['Vehicle registration', state.selectedVehicle?.registration_number],
      ['Vehicle type', state.selectedVehicle?.vehicle_type],
      ['Vehicle capacity', state.selectedVehicle?.capacity_kg == null ? null : `${state.selectedVehicle.capacity_kg} kg`],
      ['Facility', facility ? `${facility.name} (${facility.facility_id})` : transport.facility_id],
      ['Facility type', facility?.facility_type],
      ['Facility address', facility?.address],
      ['Waste ID', transport.waste_id],
      ['Waste type', waste?.waste_type],
      ['Driver ID', transport.driver_id],
      ['Lifecycle status', transport.status],
      ['Verification status', transport.weight_status],
      ['Expected weight', waste?.estimated_weight_kg == null ? null : `${waste.estimated_weight_kg} kg`],
      ['Loaded weight', transport.loaded_weight_kg == null ? null : `${transport.loaded_weight_kg} kg`],
      ['Received weight', transport.received_weight_kg == null ? null : `${transport.received_weight_kg} kg`],
      ['Difference', transport.weight_difference_kg == null ? null : `${transport.weight_difference_kg} kg`],
      ['Difference percentage', transport.difference_percentage == null ? null : `${transport.difference_percentage}%`],
      ['Route status', transport.latest_route_status || latestGps?.route_status],
      ['Route deviation', latestGps?.deviation_distance_meters == null ? null : `${latestGps.deviation_distance_meters} m`],
      ['Latest latitude', latestGps?.latitude],
      ['Latest longitude', latestGps?.longitude],
      ['Created', transport.created_at],
      ['Started', transport.started_at],
      ['Arrived', transport.arrived_at],
      ['Verified', transport.verified_at],
      ['Completed', transport.completed_at]
    ];
    $('#transport-detail-fields').innerHTML = details.map(([label, value]) => `<div class="detail-item"><dt>${esc(label)}</dt><dd>${displayValue(value)}</dd></div>`).join('');
    const gpsHistory = transport.gps_history || [];
    $('#transport-gps-table').innerHTML = gpsHistory.length ? gpsHistory.map((point) => `<tr><td>${displayValue(point.timestamp)}</td><td>${displayValue(point.latitude)}</td><td>${displayValue(point.longitude)}</td><td>${displayValue(point.route_status)}</td><td>${displayValue(point.deviation_distance_meters)}</td></tr>`).join('') : emptyRow('Not available', 5);
    const weightHistory = transport.weight_history || [];
    $('#transport-weight-table').innerHTML = weightHistory.length ? weightHistory.map((reading) => `<tr><td>${displayValue(reading.timestamp)}</td><td>${displayValue(reading.raw_value)}</td><td>${displayValue(reading.calibration_status)}</td><td>${reading.weight_kg == null ? 'Not available' : `${esc(reading.weight_kg)} kg`}</td><td>${displayValue(reading.source)}</td></tr>`).join('') : emptyRow('Not available', 5);
  } catch (error) {
    flash(error.message, true);
    $('#transport-detail-fields').innerHTML = '<div class="detail-item"><dt>Transport</dt><dd>Unable to load transport details.</dd></div>';
  }
}
async function loadVehicles() { try { const vehicles = await dashboard.vehicles(); $('#vehicles-table').innerHTML = vehicles.length ? vehicles.map((vehicle) => `<tr><td>${esc(vehicle.vehicle_id)}</td><td><strong>${esc(vehicle.registration_number)}</strong></td><td>${esc(vehicle.vehicle_type)}</td><td>${esc(vehicle.capacity_kg)} kg</td><td>${statusTag(vehicle.status)}</td><td><button class="text-button" data-history="${esc(vehicle.vehicle_id)}">View history</button></td></tr>`).join('') : emptyRow('Register your first vehicle.', 6); document.querySelectorAll('[data-history]').forEach((button) => button.addEventListener('click', () => showHistory(button.dataset.history))); } catch (error) { $('#vehicles-table').innerHTML = emptyRow('Unable to load vehicles. Is MongoDB running?', 6); } }
async function loadFacilities() {
  try {
    state.facilities = await facilitiesApi.list();
    $('#facilities-table').innerHTML = state.facilities.length ? state.facilities.map((facility) => `<tr><td>${esc(facility.facility_id)}</td><td><strong>${esc(facility.name)}</strong></td><td>${esc(facility.facility_type)}</td><td>${esc(facility.address)}</td><td>${facility.authorized ? 'Yes' : 'No'}</td><td>${statusTag(facility.status)}</td><td><button class="text-button" data-facility-edit="${esc(facility.facility_id)}">Edit</button><button class="text-button" data-facility-deactivate="${esc(facility.facility_id)}">Deactivate</button></td></tr>`).join('') : emptyRow('Add your first facility.', 7);
    document.querySelectorAll('[data-facility-edit]').forEach((button) => button.addEventListener('click', () => editFacility(button.dataset.facilityEdit)));
    document.querySelectorAll('[data-facility-deactivate]').forEach((button) => button.addEventListener('click', () => deactivateFacility(button.dataset.facilityDeactivate)));
  } catch (error) {
    $('#facilities-table').innerHTML = emptyRow('Unable to load facilities.', 7);
    flash(error.message, true);
  }
}
function editFacility(facilityId) {
  const facility = state.facilities.find((item) => item.facility_id === facilityId);
  if (!facility) return;
  const form = $('#facility-form');
  form.elements.name.value = facility.name || '';
  form.elements.facility_type.value = facility.facility_type || '';
  form.elements.address.value = facility.address || '';
  form.elements.latitude.value = facility.latitude ?? '';
  form.elements.longitude.value = facility.longitude ?? '';
  form.elements.authorized.checked = Boolean(facility.authorized);
  form.elements.authorized_waste_types.value = (facility.authorized_waste_types || []).join(', ');
  form.dataset.facilityId = facilityId;
  $('#facility-form-title').textContent = `Edit ${facility.name}`;
  $('#facility-submit').textContent = 'Save changes';
  $('#facility-cancel').hidden = false;
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function resetFacilityForm() {
  const form = $('#facility-form');
  form.reset();
  delete form.dataset.facilityId;
  $('#facility-form-title').textContent = 'Add facility';
  $('#facility-submit').textContent = 'Create facility';
  $('#facility-cancel').hidden = true;
}
async function submitFacilityForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const data = {
    name: formData.get('name').trim(),
    facility_type: formData.get('facility_type').trim(),
    address: formData.get('address').trim(),
    latitude: formData.get('latitude') === '' ? null : Number(formData.get('latitude')),
    longitude: formData.get('longitude') === '' ? null : Number(formData.get('longitude')),
    authorized: form.elements.authorized.checked,
    authorized_waste_types: formData.get('authorized_waste_types').split(',').map((value) => value.trim()).filter(Boolean)
  };
  try {
    if (form.dataset.facilityId) {
      await facilitiesApi.update(form.dataset.facilityId, data);
      flash('Facility updated successfully.');
    } else {
      await facilitiesApi.create(data);
      flash('Facility created successfully.');
    }
    resetFacilityForm();
    await loadFacilities();
  } catch (error) {
    flash(error.message, true);
  }
}
async function deactivateFacility(facilityId) {
  const facility = state.facilities.find((item) => item.facility_id === facilityId);
  if (!facility || !confirm(`Deactivate ${facility.name}?`)) return;
  try {
    await facilitiesApi.deactivate(facilityId);
    if ($('#facility-form').dataset.facilityId === facilityId) resetFacilityForm();
    flash('Facility deactivated.');
    await loadFacilities();
  } catch (error) {
    flash(error.message, true);
  }
}
async function loadDevices() {
  try {
    const devices = await dashboard.devices();
    $('#devices-table').innerHTML = devices.length ? devices.map((device) => {
      const gps = device.latest_gps || {};
      const reading = device.latest_weight || {};
      const coordinates = gps.gps_fix && gps.latitude != null && gps.longitude != null
        ? `${Number(gps.latitude).toFixed(5)}, ${Number(gps.longitude).toFixed(5)}`
        : '---';
      const weight = reading.weight_kg == null ? '---' : `${esc(reading.weight_kg)} kg`;
      return `<tr><td><strong>${esc(device.device_id)}</strong></td><td>${esc(device.vehicle_id || '-')}</td><td>${statusTag(device.online_status || 'OFFLINE')}<br><small>${esc(device.status || '')}</small></td><td>${esc(device.active_transport_id || 'None')}</td><td>${coordinates}</td><td>${esc(gps.satellites ?? '--')} / ${gps.gps_fix ? 'FIX' : 'NO FIX'}</td><td>${esc(reading.raw_value ?? '---')}</td><td>${esc(reading.calibration_status || 'NOT_SET')}</td><td>${weight}</td></tr>`;
    }).join('') : emptyRow('Register an ESP32 device.', 9);
    const select = $('#simulation-device');
    if (select) select.innerHTML = devices.map((device) => `<option value="${esc(device.device_id)}" data-transport-id="${esc(device.active_transport_id || '')}">${esc(device.device_id)} -> ${esc(device.vehicle_id || 'unassigned')} (${esc(device.active_transport_id || 'no active transport')})</option>`).join('');
  } catch (error) { $('#devices-table').innerHTML = emptyRow('Unable to load devices. Is MongoDB running?', 9); }
}
async function loadTransports() { try { const transports = await dashboard.transports(); $('#transport-table').innerHTML = transports.length ? transports.map((item) => `<tr><td><strong>${esc(item.transport_id)}</strong></td><td>${esc(item.site_id)}<br><small>${esc(item.facility_id)}</small></td><td>${esc(item.vehicle_id)}<br><small>${esc(item.device_id || 'No device')}</small></td><td>${esc(item.waste_type || item.waste_id)}</td><td>${item.latest_weight_kg ?? item.loaded_weight_kg ?? '-'} kg</td><td>${statusTag(item.latest_route_status)}</td><td>${statusTag(item.status)}</td><td>${actionButton(item)}</td></tr>`).join('') : emptyRow('Create a transport to begin tracking chain of custody.', 8); bindTransportActions(); } catch (error) { $('#transport-table').innerHTML = emptyRow('Unable to load transports. Is MongoDB running?', 8); } }
function actionButton(item) { const actions = { Created: ['load', 'Enter load'], Loaded: ['start', 'Start trip'], 'In Transit': ['arrive', 'Mark arrived'], Arrived: ['verify', 'Verify weight'], Verified: ['complete', 'Complete'] }; const action = actions[item.status]; return action ? `<button class="text-button" data-action="${action[0]}" data-id="${esc(item.transport_id)}">${action[1]}</button>` : item.status === 'Mismatch' ? '<span style="color:#a75c18;font-size:11px">Review mismatch</span>' : '<span style="color:var(--muted);font-size:11px">Complete</span>'; }
function bindTransportActions() { document.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => lifecycle(button.dataset.id, button.dataset.action))); }
async function lifecycle(id, action) { try { let data = {}; if (action === 'load') data = { weight_kg: Number(prompt('Loading weight (kg):')), source: 'manual' }; if (action === 'arrive') data = { received_weight_kg: Number(prompt('Receiving weight (kg):')), source: 'manual' }; if (action === 'load' || action === 'arrive') { if (!data[Object.keys(data)[0]]) return; } const result = action === 'load' || action === 'arrive' ? await api.post(`/transports/${id}/${action}`, data) : await api.post(`/transports/${id}/${action}`, {}); flash(result ? `Transport ${action} completed.` : 'Transport updated.'); loadTransports(); } catch (error) { flash(error.message, true); } }
async function loadGps() { try { const points = await dashboard.gps(); $('#gps-feed').innerHTML = points.length ? points.slice(0, 8).map((point) => `<div class="feed-item"><strong>${esc(point.transport_id)}</strong> · ${point.latitude == null || point.longitude == null ? 'No GPS fix' : `${Number(point.latitude).toFixed(4)}, ${Number(point.longitude).toFixed(4)}`}<br><small>${esc(point.satellites ?? '--')} satellites · ${point.gps_fix === false ? 'NO FIX' : point.gps_fix === true ? 'FIX' : 'fix unknown'} · ${esc(point.source)}</small></div>`).join('') : '<div class="feed-item">No GPS points recorded yet.</div>'; } catch (error) { $('#gps-feed').innerHTML = '<div class="feed-item">Unable to load GPS feed.</div>'; } }
async function sendSimulatedGps(latitude, longitude) {
  const select = $('#simulation-device');
  const option = select.selectedOptions[0];
  const deviceId = select.value;
  const token = $('#device-api-token').value.trim();
  if (!deviceId) return flash('Register or select a device with an active transport.', true);
  if (!token) return flash('Enter the device API token.', true);
  try {
    const result = await api.post('/device/gps', {
      device_id: deviceId,
      transport_id: option.dataset.transportId || undefined,
      latitude,
      longitude,
      satellites: 8,
      gps_fix: true,
      timestamp: new Date().toISOString()
    }, { 'X-Device-Token': token });
    $('#simulation-status').innerHTML = `<div class="feed-item"><strong>${esc(result.device_id)} -> ${esc(result.vehicle_id)} -> ${esc(result.transport_id)}</strong><br>Route status: ${statusTag(result.route_status)}${result.deviation_distance_meters != null ? ` · ${esc(result.deviation_distance_meters)} m deviation` : ''}</div>`;
    loadGps();
    loadDevices();
  } catch (error) { flash(error.message, true); }
}

function openModal(title, fields, submit) { $('#modal-content').innerHTML = `<p class="eyebrow">Manual entry</p><h2>${title}</h2><form id="modal-form" class="form-grid" style="padding:25px 0 0">${fields.map((field) => `<label>${field.label}<input name="${field.name}" type="${field.type || 'text'}" ${field.required === false ? '' : 'required'}></label>`).join('')}<button class="primary-button" type="submit">Create record</button></form>`; $('#modal').classList.add('open'); $('#modal').setAttribute('aria-hidden', 'false'); $('#modal-form').addEventListener('submit', async (event) => { event.preventDefault(); const form = new FormData(event.target); const data = Object.fromEntries(form.entries()); fields.filter((field) => field.type === 'number').forEach((field) => { if (data[field.name]) data[field.name] = Number(data[field.name]); }); try { await submit(data); $('#modal').classList.remove('open'); flash('Record created successfully.'); showView(state.currentView); } catch (error) { flash(error.message, true); } }); }
async function showHistory(vehicleId) { try { const records = await api.get(`/vehicles/${vehicleId}/history`); openModal(`${vehicleId} history`, [], async () => {}); $('#modal-content').innerHTML += `<div class="table-wrap" style="margin-top:20px"><table><thead><tr><th>Transport</th><th>Site</th><th>Facility</th><th>Status</th></tr></thead><tbody>${records.length ? records.map((item) => `<tr><td>${esc(item.transport_id)}</td><td>${esc(item.site_id)}</td><td>${esc(item.facility_id)}</td><td>${statusTag(item.status)}</td></tr>`).join('') : emptyRow('No historical trips.', 4)}</tbody></table></div>`; $('#modal-form')?.remove(); } catch (error) { flash(error.message, true); } }

document.querySelectorAll('.nav-item,[data-view]').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view)));
$('#modal-close').addEventListener('click', () => $('#modal').classList.remove('open'));
$('#site-detail-back').addEventListener('click', () => showView('sites'));
$('#vehicle-site-breadcrumb').addEventListener('click', () => showView('site-detail'));
$('#vehicle-detail-back').addEventListener('click', () => showView('site-detail'));
$('#transport-site-breadcrumb').addEventListener('click', () => showView('site-detail'));
$('#transport-vehicle-breadcrumb').addEventListener('click', () => showView('vehicle-detail'));
$('#transport-detail-back').addEventListener('click', () => showView('vehicle-detail'));
$('#add-site').addEventListener('click', () => openModal('Add construction site', [{ name: 'name', label: 'Site name' }, { name: 'project_name', label: 'Project name' }, { name: 'address', label: 'Address' }], (data) => api.post('/sites', data)));
$('#add-vehicle').addEventListener('click', () => openModal('Register vehicle', [{ name: 'registration_number', label: 'Registration number' }, { name: 'vehicle_type', label: 'Vehicle type' }, { name: 'capacity_kg', label: 'Capacity (kg)', type: 'number' }], (data) => api.post('/vehicles', data)));
$('#facility-form').addEventListener('submit', submitFacilityForm);
$('#facility-cancel').addEventListener('click', resetFacilityForm);
$('#add-device').addEventListener('click', () => openModal('Register ESP32 device', [{ name: 'device_id', label: 'Device ID (for example DEV-0001)' }, { name: 'vehicle_id', label: 'Vehicle ID' }], (data) => api.post('/devices', data)));
$('#add-transport').addEventListener('click', () => openModal('Create transport', [{ name: 'site_id', label: 'Site ID' }, { name: 'vehicle_id', label: 'Vehicle ID' }, { name: 'facility_id', label: 'Facility ID' }], (data) => api.post('/transports', data)));
$('#device-gps-form').addEventListener('submit', async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); await sendSimulatedGps(Number(data.latitude), Number(data.longitude)); });
$('#device-api-token').value = sessionStorage.getItem('device-api-token') || '';
$('#device-api-token').addEventListener('input', (event) => sessionStorage.setItem('device-api-token', event.target.value));
$('#device-weight-form').addEventListener('submit', async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); const token = $('#device-api-token').value.trim(); if (!token) return flash('Enter the device API token.', true); try { const result = await api.post('/device/weight', { device_id: $('#simulation-device').value, transport_id: $('#simulation-device').selectedOptions[0]?.dataset.transportId || undefined, weight_kg: Number(data.weight_kg), timestamp: new Date().toISOString() }, { 'X-Device-Token': token }); $('#simulation-status').innerHTML = `<div class="feed-item"><strong>Weight routed</strong><br>${esc(result.device_id)} -> ${esc(result.vehicle_id)} -> ${esc(result.transport_id)} · ${esc(result.weight_kg)} kg</div>` + $('#simulation-status').innerHTML; loadDevices(); } catch (error) { flash(error.message, true); } });
$('#simulate-route').addEventListener('click', () => { const latitude = Number($('#device-gps-form [name="latitude"]').value); const longitude = Number($('#device-gps-form [name="longitude"]').value); sendSimulatedGps(latitude || 17.385, longitude || 78.4867); });
$('#simulate-deviation').addEventListener('click', () => { const latitude = Number($('#device-gps-form [name="latitude"]').value) || 17.385; const longitude = Number($('#device-gps-form [name="longitude"]').value) || 78.4867; sendSimulatedGps(latitude + 0.02, longitude - 0.02); });
showView(new URLSearchParams(location.search).get('view') || 'dashboard');
setInterval(() => {
  if (state.currentView === 'devices') loadDevices();
  if (state.currentView === 'tracking') { loadDevices(); loadGps(); }
}, 10000);
