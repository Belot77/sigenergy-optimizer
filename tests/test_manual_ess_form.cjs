'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { Script } = require('node:vm');

const template = readFileSync(join(__dirname, '../templates/index.html'), 'utf8');
const handler = template.match(/^async function applyESS\(btn\) \{[\s\S]*?^\}/m);
assert.ok(handler, 'Expected inline applyESS handler in templates/index.html');
const script = new Script(handler[0], { filename: 'templates/index.html' });

async function submitESS(pvMax) {
  const values = {
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
  const context = {
    document: { getElementById: (id) => fields[id] },
    post: async (path, payload) => requests.push({ path, payload: { ...payload } }),
    setActionMessage: (id, level, message) => messages.push({ id, level, message }),
    setPendingBadge() {},
    ts: () => '12:00:00',
    waitForStatusMatch: async () => true,
    poll() {},
    formatFieldErrors: () => '',
    console: { error() {} },
    setTimeout() {},
  };
  script.runInNewContext(context);
  await context.applyESS(btn);
  return { btn, requests, messages };
}

for (const [input, expected] of [['0', 0], ['0.0', 0], ['12.4', 12.4]]) {
  test(`Manual ESS submits PV Max "${input}" as numeric ${expected}`, async () => {
    const { requests } = await submitESS(input);
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
    const { btn, requests, messages } = await submitESS(input);
    assert.deepEqual(requests, []);
    assert.equal(btn.textContent, 'Error');
    const error = messages.at(-1);
    assert.equal(error.id, 'msgEss');
    assert.equal(error.level, 'err');
    assert.match(error.message, /PV Max/i);
  });
}
