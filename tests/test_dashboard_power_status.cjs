'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { Script } = require('node:vm');

const template = readFileSync(join(__dirname, '../templates/index.html'), 'utf8');
const scriptMatch = template.match(/<script>\r?\n(\/\/ ------ State[^\n]*\n[\s\S]*?)<\/script>/);
assert.ok(scriptMatch, 'Expected the dashboard state script in templates/index.html');
const script = new Script(scriptMatch[1], { filename: 'templates/index.html' });

function openDashboard() {
  const noop = () => {};
  const classList = { add: noop, remove: noop, toggle: noop, contains: () => false };
  const style = { setProperty: noop, removeProperty: noop };
  const ids = /^(?:power-|powerStatusAge$|reasonBar$|lbl-gBattFlow$|nowFlow$|expLim$|impLim$|pvMax$|essChgLim$|essDchLim$|haCtrl$|wsDot$)/;
  const elements = new Map([...template.matchAll(/\bid="([^"]+)"/g)]
    .map(([, id]) => id)
    .filter(id => ids.test(id))
    .map(id => [id, { classList, style }]));
  let response;
  let socket;
  const context = {
    document: { getElementById: id => elements.get(id), documentElement: { classList } },
    window: { location: { href: 'http://test.invalid/', protocol: 'http:' } },
    URL,
    WebSocket: class {
      constructor(url) {
        assert.equal(url, 'ws://test.invalid/api/ws');
        socket = this;
      }
    },
    addonApiUrl: path => `./${path}`,
    buildAuthHeaders: () => ({}),
    fetch: async url => {
      assert.equal(url, './api/status');
      return { ok: true, json: async () => response };
    },
    console: { warn: (...args) => assert.fail(args.join(' ')) },
  };
  script.runInNewContext(context);
  return {
    elements,
    async poll(status) {
      response = status;
      await context.poll();
    },
    receive(status) {
      if (!socket) context.connectLiveWs();
      socket.onmessage({ data: JSON.stringify(status) });
    },
  };
}

function reportedRow(target_kw, target_source, ha_limit_kw, measured_power_kw) {
  return {
    target_kw, target_source, ha_limit_kw, ha_limit_status: 'reported',
    measured_power_kw, measured_power_status: 'reported',
  };
}

function rowText(dashboard, key) {
  return ['target', 'limit', 'measured'].map(field =>
    dashboard.elements.get(`power-${key}-${field}`).textContent);
}

test('REST renders separate targets, reported HA limits, and measured power including zero', async () => {
  const dashboard = openDashboard();
  await dashboard.poll({
    outcome_reason: 'Solar surplus',
    export_limit: 9,
    import_limit: 10,
    ess_charge_limit: 11,
    power_status: {
      snapshot_age_seconds: 0,
      grid_export: reportedRow(0, 'optimizer', 1.25, 0.5),
      grid_import: reportedRow(8, 'preset', 7, 0),
      ess_charge: reportedRow(4.5, 'optimizer', 0, -2.5),
    },
  });
  assert.equal(dashboard.elements.get('powerStatusAge').textContent, 'Snapshot age at refresh: 0 s');
  assert.deepEqual(rowText(dashboard, 'grid_export'), ['0.00 kW (Last optimizer)', '1.25 kW', '0.50 kW']);
  assert.deepEqual(rowText(dashboard, 'grid_import'), ['8.00 kW (Preset)', '7.00 kW', '0.00 kW']);
  assert.deepEqual(rowText(dashboard, 'ess_charge'), ['4.50 kW (Last optimizer)', '0.00 kW', '-2.50 kW (discharging)']);
  assert.equal(dashboard.elements.get('reasonBar').textContent, 'Control summary: Solar surplus');
  assert.match(dashboard.elements.get('lbl-gBattFlow').textContent, /^Battery power \(sensor or estimate\)/);
  assert.match(dashboard.elements.get('nowFlow').innerHTML, /Sensor snapshot/);
  assert.equal(dashboard.elements.get('expLim').value, '9.00');
  assert.equal(dashboard.elements.get('impLim').value, '10.00');
  assert.equal(dashboard.elements.get('essChgLim').value, '11.00');
});

test('WebSocket replaces previous evidence, and a later REST response clears missing evidence', async () => {
  const dashboard = openDashboard();
  const reported = reportedRow(3, 'preset', 4, 1);
  await dashboard.poll({
    power_status: { snapshot_age_seconds: 5, grid_export: reported, grid_import: reported, ess_charge: reported },
  });
  dashboard.receive({
    power_status: {
      snapshot_age_seconds: null,
      grid_export: {
        target_kw: null, target_source: null, ha_limit_kw: null, ha_limit_status: 'stale',
        measured_power_kw: null, measured_power_status: 'unverified',
      },
      grid_import: {
        target_kw: null, target_source: null, ha_limit_kw: null, ha_limit_status: 'unavailable',
        measured_power_kw: null, measured_power_status: 'unavailable',
      },
      ess_charge: reportedRow(0, 'optimizer', 2, 1.5),
    },
  });
  assert.equal(dashboard.elements.get('powerStatusAge').textContent, 'Snapshot age at refresh: Unknown');
  assert.deepEqual(rowText(dashboard, 'grid_export'), ['Unknown', 'Stale', 'Unverified']);
  assert.deepEqual(rowText(dashboard, 'grid_import'), ['Unknown', 'Unavailable', 'Unavailable']);
  assert.deepEqual(rowText(dashboard, 'ess_charge'), ['0.00 kW (Last optimizer)', '2.00 kW', '+1.50 kW (charging)']);

  await dashboard.poll({ export_limit: 8, battery_power_kw: 6 });
  for (const key of ['grid_export', 'grid_import', 'ess_charge']) {
    assert.deepEqual(rowText(dashboard, key), ['Unknown', 'Unavailable', 'Unavailable']);
  }
});
