'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { Script } = require('node:vm');

const template = readFileSync(join(__dirname, '../templates/index.html'), 'utf8');
const handlers = ['applyMode', 'applyESS', 'recordAcceptedEssControls', 'sameEssControlValue', 'syncEssControls', 'post'].map((name) => {
  const match = template.match(new RegExp(`^(?:async )?function ${name}\\([^)]+\\) \\{[\\s\\S]*?^\\}`, 'm'));
  assert.ok(match, `Expected inline ${name} handler in templates/index.html`);
  return match[0];
});
const definitions = template.match(/^const ESS_CONTROL_FIELDS = \[[\s\S]*?^const essControlsInFlight = new Set\(\);/m)[0];
const script = new Script([definitions, ...handlers].join('\n'), { filename: 'templates/index.html' });

async function submitControl(handler, { edits = { pvMax: '0' }, snapshot = {}, refresh, postError, duringPost } = {}) {
  const values = {
    modeSelect: 'Force Full Export',
    emsMode: 'Maximum Self Consumption',
    expLim: '8.5',
    impLim: '4.2',
    pvMax: '25',
    haCtrl: 'on',
    essChgLim: '3.1',
    essDchLim: '2.4',
  };
  const fields = Object.fromEntries(
    Object.entries(values).map(([id, value]) => [id, { value }]),
  );
  const btn = {};
  const requests = [];
  const messages = [];
  const badges = [];
  const timers = [];
  let statusChecks = 0;
  let polls = 0;
  const context = {
    S: { sigenergy_mode: 'Automated' },
    document: { getElementById: (id) => fields[id] },
    addonApiUrl: path => path,
    buildAuthHeaders: headers => headers,
    fetch: async (path, { body }) => {
      const payload = JSON.parse(body);
      requests.push({ path, payload: { ...payload } });
      duringPost?.(fields, changes => context.syncEssControls({ ...status, ...changes }, ''));
      if (postError) return { ok: false, json: async () => ({ detail: postError }) };
      return { ok: true, json: async () => ({ ok: true, accepted_fields: Object.keys(payload) }) };
    },
    setActionMessage: (id, level, message) => messages.push({ id, level, message }),
    setPendingBadge: (id, on, status, label) => badges.push({ id, on, status, label }),
    clearActionMessage: (id) => messages.push({ id, level: '', message: '' }),
    ts: () => '12:00:00',
    fc: (number, places) => number.toFixed(places),
    waitForStatusMatch: async () => { statusChecks++; return true; },
    poll() { polls++; },
    syncSel: (id, value) => { fields[id].value = value; },
    formatFieldErrors: (errors = []) => errors.map(({ key, error }) => `${key}: ${error}`).join(' | '),
    console: { error() {} },
    setTimeout: (callback, delay) => timers.push({ callback, delay }),
  };
  script.runInNewContext(context);
  const status = {
    ems_mode: values.emsMode, export_limit: 8.5, import_limit: 4.2,
    pv_max_power_limit: 25, ha_control_enabled: true,
    ess_charge_limit: 3.1, ess_discharge_limit: 2.4, ...snapshot,
  };
  context.syncEssControls(status, '');
  for (const [id, value] of Object.entries(edits)) fields[id].value = value;
  if (refresh) context.syncEssControls({ ...status, ...refresh }, 'pvMax');
  await context[handler](btn);
  return { btn, requests, messages, badges, timers, statusChecks, polls, fields, values };
}

for (const [input, expected] of [['0', 0], ['0.0', 0], ['12.4', 12.4]]) {
  test(`Manual ESS submits PV Max "${input}" as numeric ${expected}`, async () => {
    const { requests } = await submitControl('applyESS', { edits: { pvMax: input } });
    assert.deepEqual(requests, [{
      path: 'api/set_ess_fields',
      payload: { pv_max_power_limit: expected },
    }]);
  });
}

for (const input of ['', '   ', 'not-a-number', 'Infinity', '-0.1']) {
  test(`Manual ESS rejects PV Max ${JSON.stringify(input)} before posting`, async () => {
    const { btn, requests, messages } = await submitControl('applyESS', { edits: { pvMax: input } });
    assert.deepEqual(requests, []);
    assert.equal(btn.textContent, 'Error');
    const error = messages.at(-1);
    assert.equal(error.id, 'msgEss');
    assert.equal(error.level, 'err');
    assert.match(error.message, /PV Max/i);
  });
}

test('Editing PV Max keeps other controls current without submitting them', async () => {
  const { fields, requests } = await submitControl('applyESS', {
    snapshot: { ems_mode: 'Command Discharging (PV First)' },
    edits: { pvMax: '12' },
    refresh: { ems_mode: 'Maximum Self Consumption', export_limit: 0.01, ha_control_enabled: false },
  });
  assert.equal(fields.emsMode.value, 'Maximum Self Consumption');
  assert.equal(fields.expLim.value, '0.01');
  assert.equal(fields.haCtrl.value, 'off');
  assert.equal(fields.pvMax.value, '12');
  assert.deepEqual(requests, [{ path: 'api/set_ess_fields', payload: { pv_max_power_limit: 12 } }]);
});

test('No changes and fields with no reported values produce no request', async () => {
  const { btn, fields, requests } = await submitControl('applyESS', {
    edits: { pvMax: '25', haCtrl: 'off' }, snapshot: { ha_control_enabled: null },
  });
  assert.equal(fields.haCtrl.disabled, true);
  assert.equal(btn.textContent, 'No changes');
  assert.deepEqual(requests, []);
});

test('Explicit Remote EMS Off and zero grid export are sent as edits', async () => {
  const { requests } = await submitControl('applyESS', { edits: { haCtrl: 'off', expLim: '0' } });
  assert.deepEqual(requests, [{ path: 'api/set_ess_fields', payload: { grid_export_limit: 0, ha_control: false } }]);
});

const controls = [
  ['applyMode', 'Mode', 'msgMode', 'pending-mode', 'Apply Mode'],
  ['applyESS', 'ESS', 'msgEss', 'pending-ess', 'Apply ESS Controls'],
];

for (const [handler, label, messageId, badgeId, buttonLabel] of controls) {
  test(`${label} acknowledges the request and refreshes status without claiming settlement`, async () => {
    const { btn, requests, messages, badges, timers, statusChecks, polls } = await submitControl(handler);
    if (handler === 'applyMode') {
      assert.deepEqual(requests, [{ path: 'api/set_mode', payload: { mode: 'Force Full Export' } }]);
    }
    assert.equal(btn.textContent, 'Request accepted');
    assert.equal(btn.disabled, true);
    assert.deepEqual(badges.at(-1), { id: badgeId, on: true, status: 'saved', label: 'Accepted' });
    assert.equal(messages.at(-1).id, messageId);
    assert.equal(messages.at(-1).level, 'ok');
    assert.match(messages.at(-1).message, /request accepted/i);
    assert.doesNotMatch(messages.at(-1).message, /applied|updated|settling/i);
    assert.equal(statusChecks, 0);
    assert.equal(polls, 1);
    assert.equal(timers.length, 1);
    assert.equal(timers[0].delay, 2000);
    timers[0].callback();
    assert.equal(btn.textContent, buttonLabel);
    assert.equal(btn.disabled, false);
    assert.equal(badges.at(-1).on, false);
    assert.equal(messages.at(-1).message, '');
  });

  test(`${label} reports a rejected POST`, async () => {
    const postError = { message: 'Rejected by server', field_errors: [{ key: 'request', error: 'invalid value' }] };
    const { btn, requests, messages, badges, timers, statusChecks, polls, fields } =
      await submitControl(handler, { postError });
    assert.equal(requests.length, 1);
    assert.equal(btn.textContent, 'Error');
    assert.equal(btn.title, 'Rejected by server');
    assert.equal(btn.disabled, true);
    assert.deepEqual(badges.at(-1), { id: badgeId, on: true, status: 'failed', label: 'Failed' });
    assert.equal(messages.at(-1).id, messageId);
    assert.equal(messages.at(-1).level, 'err');
    assert.match(messages.at(-1).message, /Rejected by server \| request: invalid value/);
    assert.equal(statusChecks, 0);
    assert.equal(polls, handler === 'applyESS' ? 1 : 0);
    if (handler === 'applyMode') {
      assert.equal(fields.modeSelect.value, 'Automated');
    } else {
      assert.equal(fields.pvMax.value, '0');
    }
    assert.equal(timers.length, 1);
    timers[0].callback();
    assert.equal(btn.textContent, buttonLabel);
    assert.equal(btn.title, '');
    assert.equal(btn.disabled, false);
  });
}

test('Partial failure lists accepted requests, refreshes status and preserves newer edits', async () => {
  const postError = { message: 'Grid export request failed', accepted_fields: ['ems_mode'] };
  const { fields, messages, polls, timers } = await submitControl('applyESS', {
    edits: { emsMode: 'Command Discharging (PV First)', expLim: '4', pvMax: '12' },
    duringPost: current => { current.pvMax.value = '19.3'; },
    postError,
  });
  assert.equal(fields.expLim.value, '4');
  assert.equal(fields.pvMax.value, '19.3');
  assert.equal(polls, 1);
  assert.match(messages.at(-1).message, /Home Assistant accepted: EMS mode\./);
  assert.doesNotMatch(messages.at(-1).message, /accepted:.*(?:Grid export|PV Max)/);
  timers[0].callback();
  assert.match(messages.at(-1).message, /Grid export request failed/);
});

test('Status during submission preserves a newer draft equal to the original value', async () => {
  const { fields, polls } = await submitControl('applyESS', {
    edits: { pvMax: '12' },
    duringPost: (current, updateStatus) => {
      current.pvMax.value = '25';
      updateStatus({ pv_max_power_limit: 12, export_limit: 0.01 });
    },
  });
  assert.equal(fields.pvMax.value, '25');
  assert.equal(fields.expLim.value, '0.01');
  assert.equal(polls, 1);
});
