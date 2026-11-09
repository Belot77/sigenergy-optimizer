'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { Script } = require('node:vm');

const template = readFileSync(join(__dirname, '../templates/index.html'), 'utf8');
const handlers = ['applyMode', 'applyESS'].map((name) => {
  const match = template.match(new RegExp(`^async function ${name}\\(btn\\) \\{[\\s\\S]*?^\\}`, 'm'));
  assert.ok(match, `Expected inline ${name} handler in templates/index.html`);
  return match[0];
});
const script = new Script(handlers.join('\n'), { filename: 'templates/index.html' });

async function submitControl(handler, { pvMax = '0', postError } = {}) {
  const values = {
    modeSelect: 'Force Full Export',
    emsMode: 'Maximum Self Consumption',
    expLim: '8.5',
    impLim: '4.2',
    pvMax,
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
    post: async (path, payload) => {
      requests.push({ path, payload: { ...payload } });
      if (postError) {
        // A dashboard refresh can change a field while the POST is in flight.
        if (path === 'api/set_ess') fields.pvMax.value = '19.3';
        throw postError;
      }
      return { ok: true };
    },
    setActionMessage: (id, level, message) => messages.push({ id, level, message }),
    setPendingBadge: (id, on, status, label) => badges.push({ id, on, status, label }),
    clearActionMessage: (id) => messages.push({ id, level: '', message: '' }),
    ts: () => '12:00:00',
    waitForStatusMatch: async () => { statusChecks++; return true; },
    poll() { polls++; },
    syncSel: (id, value) => { fields[id].value = value; },
    formatFieldErrors: (errors = []) => errors.map(({ key, error }) => `${key}: ${error}`).join(' | '),
    console: { error() {} },
    setTimeout: (callback, delay) => timers.push({ callback, delay }),
  };
  script.runInNewContext(context);
  await context[handler](btn);
  return { btn, requests, messages, badges, timers, statusChecks, polls, fields, values };
}

for (const [input, expected] of [['0', 0], ['0.0', 0], ['12.4', 12.4]]) {
  test(`Manual ESS submits PV Max "${input}" as numeric ${expected}`, async () => {
    const { requests } = await submitControl('applyESS', { pvMax: input });
    assert.deepEqual(requests, [{
      path: 'api/set_ess',
      payload: {
        ems_mode: 'Maximum Self Consumption',
        grid_export_limit: 8.5,
        grid_import_limit: 4.2,
        pv_max_power_limit: expected,
        ess_charge_limit: 3.1,
        ess_discharge_limit: 2.4,
        ha_control: true,
      },
    }]);
  });
}

for (const input of ['', '   ', 'not-a-number', 'Infinity', '-0.1']) {
  test(`Manual ESS rejects PV Max ${JSON.stringify(input)} before posting`, async () => {
    const { btn, requests, messages } = await submitControl('applyESS', { pvMax: input });
    assert.deepEqual(requests, []);
    assert.equal(btn.textContent, 'Error');
    const error = messages.at(-1);
    assert.equal(error.id, 'msgEss');
    assert.equal(error.level, 'err');
    assert.match(error.message, /PV Max/i);
  });
}

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

  test(`${label} reports a rejected POST and restores the form`, async () => {
    const postError = Object.assign(new Error('Rejected by server'), {
      fieldErrors: [{ key: 'request', error: 'invalid value' }],
    });
    const { btn, requests, messages, badges, timers, statusChecks, polls, fields, values } =
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
    assert.equal(polls, 0);
    if (handler === 'applyMode') {
      assert.equal(fields.modeSelect.value, 'Automated');
    } else {
      assert.deepEqual(Object.fromEntries(Object.entries(fields).map(([id, field]) => [id, field.value])), values);
    }
    assert.equal(timers.length, 1);
    timers[0].callback();
    assert.equal(btn.textContent, buttonLabel);
    assert.equal(btn.title, '');
    assert.equal(btn.disabled, false);
  });
}
