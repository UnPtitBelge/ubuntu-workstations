'use strict';

const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = (name, extra = '') => `<svg class="icon ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const status = (value) => `<span class="status ${esc(String(value).toLowerCase())}"><span class="live-dot"></span>${esc(({HEALTHY:'Healthy',STALE:'Needs review',FAILED:'Failed',UNKNOWN:'Unknown',DISABLED:'Disabled',COMPLETED:'Completed',RUNNING:'Running',CONNECTED:'Connected locally',DISCONNECTED:'Not connected'})[value] || value)}</span>`;
const button = (label, action, extra = '', glyph = '') => `<button class="button ${extra || 'secondary'}" data-action="${action}">${glyph ? icon(glyph) : ''}${esc(label)}</button>`;
const link = (label, action) => `<button class="text-link" data-action="${action}">${esc(label)}${icon('arrow')}</button>`;
const age = (hours) => hours === null || hours === undefined ? 'No dated evidence' : hours < 1 ? `${Math.max(0,Math.round(hours * 60))} min ago` : hours < 48 ? `${Math.round(hours)} hours ago` : `${Math.round(hours / 24)} days ago`;
const timeLabel = (value) => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString([], {dateStyle:'medium', timeStyle:'short'}) : 'Unknown';
const titles = {overview:'Overview',machines:'Machines',setup:'Setup',operations:'Operations',changes:'Changes',activity:'Activity',lifecycle:'Lifecycle',guide:'How it works'};
const state = {snapshot:null, settings:{values:{},fields:[]}, draft:{}, activities:[], machines:[], page:'overview', setupTab:'backup', category:'all', search:'', filter:'all', busy:false, demo:false, online:true};
let review = null;
let pendingPlanId = null;
let dialogRequest = 0;
let toastTimer;
let handledActivity = '';
let refreshing = false;
let activityPolling = false;
const incoming = new URLSearchParams(location.hash.slice(1));
if (incoming.has('token')) {
  sessionStorage.setItem('workstation-session', incoming.get('token'));
  history.replaceState(null, '', location.pathname + '#overview');
}
const token = sessionStorage.getItem('workstation-session') || '';

async function api(path, body) {
  const response = await fetch('/api/' + path, {
    method: body === undefined ? 'GET' : 'POST', credentials:'omit', cache:'no-store',
    headers:{Authorization:'Bearer ' + token, ...(body === undefined ? {} : {'Content-Type':'application/json'})},
    body:body === undefined ? undefined : JSON.stringify(body), signal:AbortSignal.timeout(15000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}

function notify(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 6500);
}

function changes() {
  return Object.keys(state.draft).filter(key => JSON.stringify(state.draft[key]) !== JSON.stringify(state.settings.values[key]));
}

function chrome() {
  const snapshot = state.snapshot;
  if (!snapshot) return;
  $('#sidebar-host').textContent = snapshot.host;
  $('#breadcrumb').textContent = titles[state.page];
  $('#mode-label').innerHTML = `<span class="live-dot"></span>${state.demo ? 'Demo · sample data' : 'Local workspace'}`;
  const count = snapshot.jobs.filter(job => ['FAILED','STALE','UNKNOWN'].includes(job.state)).length;
  $('#attention-count').textContent = count || '';
  $('#draft-count').textContent = changes().length || '';
  $('#connection-status').textContent = state.online ? `${state.demo ? 'Sample' : 'Local'} evidence · ${timeLabel(snapshot.observed_at)}` : 'Connection lost · displaying last observation';
  document.body.classList.toggle('is-busy', state.busy);
  document.querySelectorAll('[data-page]').forEach(item => {
    item.classList.toggle('active', item.dataset.page === state.page);
    if (item.dataset.page === state.page) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current');
  });
  document.title = `${titles[state.page]} · Workstation`;
}

function heading(eyebrow, title, description, actions = '') {
  return `<div class="heading-row"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${actions ? `<div class="heading-actions">${actions}</div>` : ''}</div>`;
}

function job(id) { return state.snapshot.jobs.find(row => row.id === id); }
function metric(label, value, note, glyph, color = '') {
  return `<article class="metric"><div class="metric-top"><span class="metric-label">${esc(label)}</span><span class="icon-tile ${color}">${icon(glyph)}</span></div><div class="metric-value">${esc(value)}</div><div class="metric-note">${icon('clock')}${esc(note)}</div></article>`;
}

function overview() {
  const s = state.snapshot;
  const attention = s.jobs.filter(row => ['FAILED','STALE','UNKNOWN'].includes(row.state)).sort((a,b) => ({FAILED:3,STALE:2,UNKNOWN:1})[b.state] - ({FAILED:3,STALE:2,UNKNOWN:1})[a.state]);
  const health = job('health'), backup = job('backup'), updates = job('updates');
  const continuous = s.jobs.filter(row => row.kind === 'continuous' || row.id === 'sync');
  const active = continuous.filter(row => row.activity === 'active').length;
  const providerLabels = {backup:['Cloud backup','cloud'],sync:['File sync','refresh'],vpn:['VPN','shield'],mail:['Mail','file'],passwords:['Passwords','shield']};
  return heading('YOUR WORKSPACE', 'Your workstation, at a glance.', 'A clear view of your setup, what’s working, and what needs a little attention.', button('Manage setup','setup','primary','settings')) +
    `<section class="hero" aria-label="Current machine"><div class="hero-identity"><div class="monitor-illustration">${icon('monitor')}</div><div><span class="eyebrow">CURRENT WORKSTATION</span><h2>${esc(s.host)}</h2><div class="hero-meta"><span>Ubuntu · local inventory</span><span>${esc(s.profile.replaceAll('_',' '))}</span><span>${esc(s.inventory_host)}</span></div></div></div><div class="hero-right">${status(s.overall)}<p>${state.demo ? 'Illustrative workspace' : 'Observed on this machine only'}</p></div></section>` +
    `<section class="metrics" aria-label="Status summaries">${metric('System health', health ? ({HEALTHY:'Looking good',FAILED:'Needs attention',STALE:'Check overdue',UNKNOWN:'Not verified',DISABLED:'Disabled'})[health.state] : 'Not verified', age(health?.age_hours), 'activity')}${metric('Latest backup', backup?.state === 'HEALTHY' ? age(backup.age_hours).replace(' ago','') : backup ? ({STALE:'Overdue',FAILED:'Failed',DISABLED:'Not scheduled',UNKNOWN:'Not verified'})[backup.state] : 'Not verified', 'Restore evidence is checked separately', 'cloud', 'blue')}${metric('Update discovery', updates?.state === 'HEALTHY' ? 'Report ready' : 'Review needed', age(updates?.age_hours), 'box', 'sand')}${metric('Managed services', `${active} / ${continuous.length} active`, 'Continuous services observed locally', 'shield', 'lavender')}</section>` +
    `<div class="section-title"><h2>Needs your attention ${attention.length ? `<span class="muted">(${attention.length})</span>` : ''}</h2>${link('View operations','operations')}</div>` +
    (attention.length ? `<section class="attention-panel">${icon('alert')}<div class="attention-content"><strong>${esc(attention[0].label)}</strong><p>${esc(attention[0].reasons[0])}${attention.length > 1 ? ` · ${attention.length-1} more items to review` : ''}</p></div>${button('Review details','report:'+attention[0].id,'secondary','arrow')}</section>` : `<section class="attention-panel">${icon('check')}<div class="attention-content"><strong>No issues in the available checks</strong><p>Local checks passed. Backup and recovery scope still deserve a separate review.</p></div></section>`) +
    `<div class="two-columns"><section class="panel"><div class="panel-heading"><h2>Your setup</h2>${link('Configure','setup')}</div>${Object.entries(providerLabels).map(([key,[label,glyph]]) => `<div class="provider-row"><span class="icon-tile">${icon(glyph)}</span><div><strong>${label}</strong><small>Selected provider</small></div><span class="provider-name">${esc(s.providers[key] || 'Not configured')}</span></div>`).join('')}<div class="panel-footer">${icon('settings')}From the last deployed configuration</div></section><section class="panel"><div class="panel-heading"><h2>Recent checks</h2>${link('View all','operations')}</div>${s.jobs.filter(row => ['health','drift','backup','restore','updates'].includes(row.id)).map(row => `<div class="check-row"><span class="check-dot ${row.state === 'HEALTHY' ? '' : 'attention'}">${icon(row.state === 'HEALTHY' ? 'check' : 'clock')}</span><div><strong>${esc(row.label)}</strong><small>${age(row.age_hours)}</small></div>${status(row.state)}</div>`).join('')}<div class="panel-footer">${icon('clock')}Saved evidence, refreshed every 30 seconds</div></section></div>` +
    `<p class="quiet-note">${icon('shield')}Browsing only reads local evidence. Changes and job runs always start with a review.</p>`;
}

function settingsPage() {
  const cfg = state.settings;
  const tabs = [['backup','Backup & recovery'],['development','Development'],['desktop','Desktop'],['providers','Providers']];
  const labels = {backup:['Backup & recovery','Choose what is protected and when managed checks run.'],development:['Development environment','Keep your toolchains and development features aligned with inventory.'],desktop:['Desktop & notifications','Make this workstation comfortable to work with.']};
  let result = heading('CONFIGURATION', 'Make this setup yours.', 'Review settings here. Save a diff, preview its effects, then apply when you’re ready.', button('Review changes'+(changes().length ? ` (${changes().length})` : ''),'changes','primary','file'));
  if (!cfg.available) result += `<div class="notice ${state.demo ? '' : 'warning'}">${esc(cfg.error)}</div>`;
  result += `<div class="tabs" role="tablist" aria-label="Setup sections">${tabs.map(([id,label]) => `<button class="tab ${id === state.setupTab ? 'active' : ''}" data-setup-tab="${id}" role="tab" aria-selected="${id === state.setupTab}">${label}</button>`).join('')}</div>`;
  if (state.setupTab === 'providers') {
    return result + `<section class="panel"><div class="panel-heading"><div><h2>Connected capabilities</h2><p>Desired provider selections from the last deployment.</p></div></div>${Object.entries(state.snapshot.providers).map(([key,value]) => `<div class="provider-row"><span class="icon-tile">${icon('box')}</span><div><strong>${esc(key[0].toUpperCase()+key.slice(1))}</strong><small>Selection does not certify authentication or migration</small></div><span class="provider-name">${esc(value)}</span></div>`).join('')}</section><p class="quiet-note">${icon('shield')}Provider transitions need data verification and an explicit cutover. ${link('Open lifecycle guide','lifecycle')}</p>`;
  }
  const [label,description] = labels[state.setupTab];
  const fields = cfg.fields.filter(field => field[3] === state.setupTab);
  result += `<section class="panel form-card"><div class="panel-heading"><div><h2>${label}</h2><p>${description}</p></div></div><div class="form-body">`;
  result += fields.map(([key,title,help,,type]) => {
    const known = Object.hasOwn(state.draft, key), value = state.draft[key];
    const literal = item => typeof item === 'string' && !item.includes('{{') && !item.includes('{%');
    const valid = known && (type === 'boolean' ? typeof value === 'boolean' : type === 'list' ? Array.isArray(value) && value.every(literal) : literal(value));
    const disabled = !cfg.available || state.busy || !valid ? 'disabled' : '';
    let control;
    if (type === 'boolean') control = `<div class="switch"><span>${known ? value ? 'Enabled' : 'Disabled' : 'Unknown'}</span><input type="checkbox" id="${key}" data-setting="${key}" data-type="boolean" ${value === true ? 'checked' : ''} ${disabled} role="switch" aria-label="${esc(title)}"></div>`;
    else if (type === 'list') control = `<textarea id="${key}" data-setting="${key}" data-type="list" rows="${Math.min(6,Math.max(3,Array.isArray(value) ? value.length : 3))}" spellcheck="false" ${disabled}>${esc(Array.isArray(value) ? value.join('\n') : '')}</textarea>`;
    else control = `<input type="text" id="${key}" data-setting="${key}" data-type="string" value="${esc(known ? value : '')}" ${disabled} spellcheck="false">`;
    return `<div class="field-row"><div class="field-description"><label for="${key}">${esc(title)}</label><p>${esc(help)}${valid ? '' : ' Not available as a literal value in this configuration; edit inventory manually or redeploy the dashboard.'}</p><code>${esc(key)}</code></div><div class="field-control">${control}</div></div>`;
  }).join('');
  result += `</div><div class="form-actions"><small id="form-draft-note">${changes().length ? changes().length + ' unsaved changes' : 'Changes stay in your browser until reviewed.'}</small>${button('Review changes','changes','primary','arrow')}</div></section><p class="quiet-note">${icon('file')}Values combine host-file overrides and last-deployed defaults. Other inventory overrides may take precedence; review the Ansible preview. Disabling a foundation role does not uninstall packages or stop its services.</p>`;
  return result;
}

function operations() {
  const filtered = filteredJobs();
  return heading('LOCAL OPERATIONS','Keep things running smoothly.','Inspect saved evidence, understand failures, and deliberately run supported checks.') +
    `<div class="tabs" role="tablist" aria-label="Operation categories">${[['all','All jobs'],['health','Health'],['backup','Backup'],['updates','Updates'],['services','Services'],['reports','Reports']].map(([id,label]) => `<button class="tab ${state.category === id ? 'active' : ''}" data-category="${id}" role="tab" aria-selected="${state.category === id}">${label}</button>`).join('')}</div><div class="toolbar"><label class="search-box">${icon('search')}<input id="job-search" type="search" placeholder="Find a job…" aria-label="Search jobs" value="${esc(state.search)}"></label><select id="state-filter" class="filter-select" aria-label="Filter jobs by state"><option value="all" ${state.filter === 'all' ? 'selected' : ''}>All states</option><option value="attention" ${state.filter === 'attention' ? 'selected' : ''}>Needs attention</option><option value="healthy" ${state.filter === 'healthy' ? 'selected' : ''}>Healthy</option><option value="disabled" ${state.filter === 'disabled' ? 'selected' : ''}>Disabled</option></select></div><section class="panel"><div class="table-wrap"><table><thead><tr><th>JOB</th><th>STATUS</th><th>EVIDENCE</th><th></th></tr></thead><tbody id="jobs-body">${jobRows(filtered)}</tbody></table></div></section><p class="quiet-note">${icon('clock')}Schedules alone do not prove success. A successful upload is not a verified restore. Refresh rereads evidence; it does not run checks.</p>`;
}

function filteredJobs() {
  return state.snapshot.jobs.filter(row => (state.category === 'all' || row.category === state.category) &&
    (!state.search || (row.label+' '+row.reasons.join(' ')).toLowerCase().includes(state.search.toLowerCase())) &&
    (state.filter === 'all' || state.filter === 'attention' && ['FAILED','STALE','UNKNOWN'].includes(row.state) || row.state.toLowerCase() === state.filter));
}

function jobRows(rows) {
  return rows.length ? rows.map(row => {
    const ready = !state.busy && state.online && row.enabled === true &&
      row.service_properties?.LoadState === 'loaded' && ['inactive','failed'].includes(row.activity);
    const run = row.runnable ? `<button class="row-action run-action" data-action="run:${esc(row.id)}" aria-label="Review manual run for ${esc(row.label)}" ${ready ? '' : 'disabled title="Requires an enabled, available, idle service and no running dashboard action"'}>${icon('activity')}Run check</button>` : '';
    return `<tr><td><strong>${esc(row.label)}</strong><small>${esc(row.reasons[0])}</small></td><td>${status(row.state)}</td><td><span class="muted">${age(row.age_hours)}</span></td><td><div class="row-actions"><button class="row-action" data-action="report:${esc(row.id)}" aria-label="View details for ${esc(row.label)}">View details ${icon('chevron')}</button>${run}</div></td></tr>`;
  }).join('') : '<tr><td colspan="4"><div class="empty-state">No jobs match these filters.</div></td></tr>';
}

function changesPage() {
  const keys = changes(), cfg = state.settings;
  const names = Object.fromEntries(cfg.fields.map(field => [field[0],field[1]]));
  return heading('REVIEW & APPLY','Small changes. Clear intentions.','Configuration changes are separate from provisioning. Review each step before moving on.') +
    `<div class="step-list"><article class="step-card"><span class="step-number">1</span><h3>Save the configuration</h3><p>Review the exact inventory diff. Save only the changes you approve.</p><button class="button secondary" data-action="review-settings" ${!keys.length || !cfg.available || state.busy ? 'disabled' : ''}>Review & save ${icon('arrow')}</button></article><article class="step-card"><span class="step-number">2</span><h3>Preview the effects</h3><p>Run Ansible check mode on the saved inventory. Read the output in your terminal.</p><button class="button secondary" data-action="ansible:preview" ${!cfg.available || !cfg.terminal || state.busy || keys.length ? 'disabled' : ''}>Preview in terminal</button></article><article class="step-card"><span class="step-number">3</span><h3>Apply when ready</h3><p>A successful preview of unchanged inputs is required before applying.</p><button class="button primary" data-action="ansible:apply" ${!cfg.available || !cfg.terminal || !cfg.preview_ready || state.busy || keys.length ? 'disabled' : ''}>Review & apply</button></article></div>` +
    (!cfg.terminal && !state.demo ? '<div class="notice">Ansible actions need an interactive terminal. Start <code>workstation</code> in your terminal; sudo prompts and full output stay there.</div>' : '') +
    (state.busy ? '<div class="notice">An operation is running. Follow its progress in Activity or the launching terminal.</div>' : '') +
    `<section class="panel"><div class="panel-heading"><h2>Pending configuration ${keys.length ? `(${keys.length})` : ''}</h2>${keys.length ? button('Discard draft','discard','ghost') : ''}</div>${keys.length ? keys.map(key => `<div class="change-item"><strong>${esc(names[key] || key)}</strong><code><del>${esc(JSON.stringify(cfg.values[key]))}</del><br>→ ${esc(JSON.stringify(state.draft[key]))}</code></div>`).join('') : `<div class="empty-state">${icon('check')}<h2>No unsaved changes</h2><p>Make a change in Setup, then come here to review its diff. You can also preview the current inventory.</p>${button('Explore setup','setup','secondary','settings')}</div>`}</section><p class="quiet-note">${icon('shield')}After applying, ${link('run the strict audit','ansible:audit')} and repeat preview/apply to check idempotency. Reverting a configuration file does not roll back packages or provider data.</p>`;
}

function activityPage() {
  return heading('SESSION ACTIVITY','See what happened.','Actions and outcomes from this dashboard session. Existing reports remain available in Operations.') +
    `<section class="panel">${state.activities.length ? state.activities.map(item => `<article class="activity-row"><span class="icon-tile">${icon(item.kind === 'settings' ? 'file' : item.kind === 'job' ? 'activity' : 'terminal')}</span><div class="activity-body"><h3>${esc(item.title)}</h3><p>${esc(item.message)}</p><time>${timeLabel(item.started_at)}</time></div>${status(item.state)}</article>`).join('') : `<div class="empty-state">${icon('clock')}<h2>A fresh start</h2><p>Reviewed configuration saves and confirmed operations will appear here. Browsing does not run jobs.</p>${button('Explore operations','operations','secondary','arrow')}</div>`}</section><p class="quiet-note">${icon('file')}Activity is kept in memory for this server session, up to 50 entries. Reports and journals provide the underlying evidence.</p>`;
}

function machinesPage() {
  return heading('YOUR MACHINES','One workspace. Clear boundaries.','Manage the workstation you’re on. Other inventory entries are shown for orientation.') +
    `<div class="machine-grid">${state.machines.map(machine => `<article class="panel machine-card"><span class="icon-tile">${icon('monitor')}</span>${status(machine.local ? 'CONNECTED' : 'DISCONNECTED')}<h2>${esc(machine.local ? machine.host : machine.id)}</h2><p>${machine.local ? `Connected locally · inventory target <strong>${esc(machine.id)}</strong>. The dashboard uses this machine’s reports and user session.` : 'Inventory entry only. No remote connection is configured, and no health has been observed.'}</p>${machine.local ? button('Manage this setup','setup','primary','settings') : '<span class="status disabled">Remote management · planned</span>'}</article>`).join('')}</div><p class="quiet-note">${icon('shield')}Run this dashboard separately on each workstation. Selecting an inventory limit here cannot remotely provision another machine.</p>`;
}

function lifecyclePage() {
  return heading('SETUP LIFECYCLE','Build a setup you can trust.','Guided paths for growing and maintaining your workstation. Data transitions remain deliberate.') +
    `<div class="guide-grid"><article class="panel guide-card"><span class="icon-tile">${icon('box')}</span><h2>Add or configure features</h2><p>Choose your development, desktop and backup settings in Setup. Save the reviewed inventory diff, preview with Ansible, then explicitly apply.</p><p>Turning a foundation feature off skips its role. It does not remove installed packages or stop existing services. Review health lists and service intent separately.</p>${link('Configure features','setup')}</article><article class="panel guide-card"><span class="icon-tile blue">${icon('refresh')}</span><h2>Change a provider</h2><ol><li>Inventory data, identity, metadata and retention requirements.</li><li>Prove independent recovery from the source.</li><li>Set up the replacement in parallel and transfer a small dataset.</li><li>Verify destination data, recovery and scheduled runs.</li><li>Explicitly approve cutover with a rollback window.</li><li>Decommission separately; preserve data until then.</li></ol><p>Provider/profile edits remain manual. Follow <code>docs/MIGRATE.md</code> and <code>docs/DEPLOY.md</code>.</p></article><article class="panel guide-card"><span class="icon-tile sand">${icon('monitor')}</span><h2>Enroll another workstation</h2><p>Start with <code>TUTORIAL.md</code> and <code>setup.yml.example</code>. The onboarding helper creates inventory configuration; provisioning runs on the new machine.</p><p>Enroll accounts locally and pair a distinct Syncthing device. Never copy machine identity or authentication.</p>${link('View inventory machines','machines')}</article><article class="panel guide-card"><span class="icon-tile lavender">${icon('shield')}</span><h2>Verify & recover</h2><p>After applying, run the strict audit and another normal pass for idempotency. Expected: no failed/unreachable tasks and no recurring changes.</p><p>Configuration rollback starts with a reviewed Git diff and another preview. Packages and provider data have their own compatibility and recovery requirements.</p>${link('Review configuration workflow','changes')}</article></div>`;
}

function guidePage() {
  return heading('A LITTLE ORIENTATION','Your setup, without the guesswork.','Three layers work together. The dashboard helps you see and control their relationship.') +
    `<div class="guide-grid"><article class="panel guide-card"><span class="icon-tile">${icon('file')}</span><h2>Git declares intent</h2><p>Your profiles and inventory describe the setup. Settings edits produce a file diff for review; they never automatically commit, push or provision.</p><p>Some displayed defaults come from the last dashboard deployment. A new Git revision does not mean it is applied.</p></article><article class="panel guide-card"><span class="icon-tile blue">${icon('terminal')}</span><h2>Ansible applies configuration</h2><p>Preview first. Apply only after reviewing effects. Passwords and full command output stay in the terminal that launched this dashboard.</p><p>Check mode is not an integration test. Stop at the first failed task and diagnose before retrying.</p></article><article class="panel guide-card"><span class="icon-tile lavender">${icon('activity')}</span><h2>Evidence records outcomes</h2><p>Reports and local systemd observations distinguish healthy, failed, stale, unknown and disabled states. A timer is a schedule, not proof of a successful run.</p><p>A backup upload is not recovery proof, and Syncthing is synchronization, not backup. Notification delivery is not certified by service success.</p></article><article class="panel guide-card"><span class="icon-tile sand">${icon('shield')}</span><h2>You choose the actions</h2><p>Browsing stays read-only. Every configuration save and supported job run has a separate review and explicit confirmation. No automatic repair, cleanup or provider cutover.</p><p>The session is loopback-only. Treat its browser link as private. Remote management is deferred.</p></article></div>`;
}

function render() {
  if (!state.snapshot) return;
  chrome();
  const pages = {overview,setup:settingsPage,operations,changes:changesPage,activity:activityPage,machines:machinesPage,lifecycle:lifecyclePage,guide:guidePage};
  $('#main').innerHTML = (state.online ? '' : '<div class="notice error">Connection lost. The values below are from the last observation. Reconnect before taking action.</div>') + (state.snapshot.config_warning ? `<div class="notice warning">${esc(state.snapshot.config_warning)}</div>` : '') + pages[state.page]();
}

function navigate(page) {
  if (!Object.hasOwn(titles,page)) page = 'overview';
  state.page = page;
  if (location.hash !== '#'+page) history.pushState(null,'','#'+page);
  render();
  window.scrollTo({top:0});
}

function showDialog(title, html, confirmLabel = null, callback = null) {
  dialogRequest += 1;
  review = callback;
  $('#dialog-title').textContent = title;
  $('#dialog-body').innerHTML = html;
  $('#dialog-confirm').hidden = !confirmLabel;
  $('#dialog-confirm').textContent = confirmLabel || 'Confirm';
  $('#dialog-confirm').disabled = false;
  $('#dialog-cancel').textContent = confirmLabel ? 'Cancel' : 'Close';
  if (!$('#review-dialog').open) $('#review-dialog').showModal();
}

function closeDialog() {
  dialogRequest += 1;
  if (pendingPlanId) {
    api('cancel',{id:pendingPlanId}).catch(() => {});
    pendingPlanId = null;
  }
  review = null;
  $('#review-dialog').close();
}

async function reviewPlan(body) {
  if (!state.online) return notify('Reconnect before creating an action plan.');
  const plan = await api('plan',body);
  pendingPlanId = plan.id;
  const diff = plan.diff ? `<pre>${plan.diff.split('\n').map(line => `<span class="${line.startsWith('+') ? 'diff-add' : line.startsWith('-') ? 'diff-remove' : ''}">${esc(line)}</span>`).join('\n')}</pre>` : '';
  showDialog(plan.title, `<p class="host-note">LOCAL TARGET · ${esc(plan.host)}</p><p>${esc(plan.effect)}</p>${plan.command ? `<pre>${esc(plan.command)}</pre>` : ''}${diff}`, body.kind === 'settings' ? 'Save configuration' : 'Confirm & run', async () => {
    pendingPlanId = null;
    await api('confirm',{id:plan.id});
    state.busy = true;
    closeDialog();
    navigate('activity');
    notify(body.kind === 'preview' || body.kind === 'apply' || body.kind === 'audit' ? 'Continue in the launching terminal for sudo and full output.' : 'Action accepted. Follow the result in Activity.');
    await pollActivity();
  });
}

async function evidence(jobId, mode = 'report') {
  showDialog(mode === 'logs' ? 'Local journal' : job(jobId)?.label || 'Job details', '<p>Reading local evidence…</p>');
  const request = dialogRequest;
  const result = await api(`evidence/${encodeURIComponent(jobId)}/${mode}`);
  if (!$('#review-dialog').open || request !== dialogRequest) return;
  const row = job(jobId);
  showDialog(row?.label || 'Evidence', `<p>Local ${mode === 'logs' ? 'journal' : 'report'} · may contain private paths. Text stays in this browser.</p><pre>${esc(result.text)}</pre><div class="heading-actions">${mode === 'report' ? button('Read journal','logs:'+jobId,'secondary','file') : button('Read report','report:'+jobId,'secondary','file')}${row?.runnable ? `<button class="button primary" data-action="run:${esc(jobId)}" ${state.busy ? 'disabled' : ''}>Review manual run ${icon('arrow')}</button>` : ''}</div>`);
}

async function loadSettings() {
  state.settings = await api('settings');
  state.draft = structuredClone(state.settings.values);
}

async function refresh() {
  if (refreshing || !token) return;
  refreshing = true;
  try {
    const response = await api('status');
    state.snapshot = response.snapshot;
    state.demo = response.demo;
    state.online = true;
    if (['overview','machines'].includes(state.page) && !$('#review-dialog').open) render(); else chrome();
  } catch (error) {
    state.online = false;
    chrome();
    notify(error.message);
  } finally { refreshing = false; }
}

async function pollActivity() {
  if (activityPolling || !token || !state.snapshot) return;
  activityPolling = true;
  try {
    const result = await api('activity');
    const changed = JSON.stringify(result.activities) !== JSON.stringify(state.activities) || result.busy !== state.busy;
    state.activities = result.activities;
    state.busy = result.busy;
    const latest = result.activities[0];
    if (latest && latest.state !== 'RUNNING' && latest.id !== handledActivity) {
      handledActivity = latest.id;
      if (latest.kind === 'settings' && latest.state === 'COMPLETED') await loadSettings();
      else {
        const settings = await api('settings');
        state.settings.preview_ready = settings.preview_ready;
      }
      await refresh();
    }
    if (changed && !$('#review-dialog').open && ['activity','changes','operations'].includes(state.page)) render(); else chrome();
  } catch (error) { $('#connection-status').textContent = 'Connection lost · actions unavailable'; state.online = false; }
  finally { activityPolling = false; }
}

document.addEventListener('click', async (event) => {
  const actionElement = event.target.closest('[data-action]');
  const pageElement = event.target.closest('[data-page]');
  const tabElement = event.target.closest('[data-setup-tab], [data-category]');
  try {
    if (pageElement) { event.preventDefault(); navigate(pageElement.dataset.page); }
    else if (tabElement) {
      if (tabElement.dataset.setupTab) state.setupTab = tabElement.dataset.setupTab;
      else state.category = tabElement.dataset.category;
      render();
    } else if (actionElement && !actionElement.disabled) {
      const action = actionElement.dataset.action;
      if (Object.hasOwn(titles,action)) navigate(action);
      else if (action.startsWith('report:')) await evidence(action.slice(7));
      else if (action.startsWith('logs:')) await evidence(action.slice(5),'logs');
      else if (action.startsWith('run:')) await reviewPlan({kind:'job',job:action.slice(4)});
      else if (action.startsWith('ansible:')) await reviewPlan({kind:action.slice(8)});
      else if (action === 'review-settings') await reviewPlan({kind:'settings',values:Object.fromEntries(changes().map(key => [key,state.draft[key]]))});
      else if (action === 'discard') {
        showDialog('Discard your draft?', '<p>This removes only the unsaved settings held in this browser. Saved inventory files are unaffected.</p>', 'Discard draft', async () => { state.draft = structuredClone(state.settings.values); closeDialog(); render(); });
      }
    }
  } catch (error) { notify(error.message); }
});

document.addEventListener('input',(event) => {
  const element = event.target;
  if (element.dataset.setting) {
    state.draft[element.dataset.setting] = element.dataset.type === 'boolean' ? element.checked : element.dataset.type === 'list' ? element.value.split('\n').filter(line => line.trim()) : element.value;
    chrome();
    const note = $('#form-draft-note');
    if (note) note.textContent = changes().length ? `${changes().length} unsaved changes` : 'Changes stay in your browser until reviewed.';
    if (element.type === 'checkbox') element.previousElementSibling.textContent = element.checked ? 'Enabled' : 'Disabled';
  } else if (element.id === 'job-search') { state.search = element.value; $('#jobs-body').innerHTML = jobRows(filteredJobs()); }
});
$('#main').addEventListener('change',(event) => { if (event.target.id === 'state-filter') { state.filter = event.target.value; $('#jobs-body').innerHTML = jobRows(filteredJobs()); } });
$('#dialog-confirm').addEventListener('click',async () => {
  if (!review || $('#dialog-confirm').disabled) return;
  const callback = review;
  review = null;
  $('#dialog-confirm').disabled = true;
  try { await callback(); }
  catch (error) { closeDialog(); notify(error.message + ' Review again before retrying.'); }
});
$('#dialog-cancel').addEventListener('click',closeDialog);
$('#dialog-close').addEventListener('click',closeDialog);
$('#review-dialog').addEventListener('cancel',closeDialog);
$('#machine-switch').addEventListener('click',() => navigate('machines'));
$('#refresh').addEventListener('click',async () => { await refresh(); if (state.online) { render(); notify('Local evidence reread. No jobs were started.'); } });
window.addEventListener('popstate',() => navigate(location.hash.slice(1)));
window.addEventListener('beforeunload',event => { if (changes().length) { event.preventDefault(); event.returnValue = ''; } });

async function start() {
  if (!token) {
    $('#main').innerHTML = `<section class="panel connect-card"><span class="icon-tile">${icon('shield')}</span><h1>Your local workspace.</h1><p>Open the private session link printed by <code>workstation</code> in your terminal to connect this browser.</p><div class="notice">The dashboard only listens on this machine. Its session link changes each time the server starts.</div></section>`;
    $('#connection-status').textContent = 'Waiting for a local session';
    return;
  }
  try {
    const [response,,machines,result] = await Promise.all([api('status'),loadSettings(),api('machines'),api('activity')]);
    state.snapshot = response.snapshot; state.demo = response.demo;
    state.machines = machines.machines; state.activities = result.activities; state.busy = result.busy;
    navigate(location.hash.slice(1));
    setInterval(refresh,30000);
    setInterval(pollActivity,2000);
  } catch (error) {
    $('#main').innerHTML = `<section class="panel connect-card"><h1>Let’s reconnect.</h1><p>${esc(error.message)}</p><p>Reopen the current private session link from your terminal. The server may have restarted.</p></section>`;
    $('#connection-status').textContent = 'Not connected';
  }
}
start();
