'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { Script } = require('node:vm');

const template = readFileSync(join(__dirname, '../templates/index.html'), 'utf8');
const scripts = [...template.matchAll(/^<script>\r?\n([\s\S]*?)^<\/script>/gm)].map(([, source]) => source);
const state = scripts.find(source => source.startsWith('// ------ State'));
const settings = scripts.find(source => source.includes('async function loadConfig()'));
assert.ok(state && settings, 'Expected the dashboard state and Settings scripts');
const startup = settings.lastIndexOf('\ninitTheme();');
assert.notEqual(startup, -1, 'Expected the dashboard startup block');
const script = new Script(state + settings.slice(0, startup), { filename: 'templates/index.html' });

const EXPORT = 'export_pricing_caps';
const IMPORT = 'import_pricing_caps';
const DUMP = 'morning_dump';
const BOOST = 'evening_boost';
const setting = (section, key) => `cfg_${section}_${key}`;

function element(id, initialValue = '') {
  const listeners = new Map();
  let value = initialValue;
  return {
    id,
    get value() { return value; },
    set value(next) { value = String(next); },
    addEventListener(type, handler) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(handler);
    },
    dispatch(type, target = this) {
      for (const handler of listeners.get(type) || []) handler({ target, currentTarget: this });
    },
    classList: { add() {}, remove() {}, toggle() {} },
    style: {},
  };
}

async function openDashboard() {
  const config = {
    export_threshold_low: 0.01, export_threshold_medium: 0.1, export_threshold_high: 0.1234567,
    export_limit_low: 3, export_limit_medium: 5, export_limit_high: 10,
    import_threshold_low: 0.05, import_threshold_medium: 0, import_threshold_high: -0.05,
    import_limit_low: 3, import_limit_medium: 5, import_limit_high: 10,
    battery_export_min_soc_low: 100, battery_export_min_soc_medium: 40,
    battery_export_min_soc_high: 20, battery_export_min_soc_spike: 10,
    export_spike_threshold: 0, export_spike_min_soc: 0, export_spike_full_power: false,
    allow_low_medium_export_positive_fit: false, allow_positive_fit_battery_discharging: false,
    morning_dump_enabled: true, morning_dump_hours_before_sunrise: 2, morning_dump_min_soc: 15,
    evening_boost_enabled: true, evening_boost_min_feedin_price: 0.01,
    evening_aggressive_floor: 80, evening_boost_forecast_safety: 1.2,
    evening_boost_min_tomorrow_forecast_kwh: 100,
    notification_service: '01', auto_enable_ha_control: true,
    ems_mode_select: 'select.example_ems',
  };
  const elements = new Map([...template.matchAll(/\bid="(t(?:Exp|Imp)\w+)"/g)]
    .map(([, id]) => [id, element(id)]));
  const content = element('cfgContent');
  const doc = element('document');
  Object.defineProperty(content, 'innerHTML', {
    set(markup) {
      for (const id of elements.keys()) if (id.startsWith('cfg_')) elements.delete(id);
      for (const [, tag] of markup.matchAll(/(<input\b[^>]*>)/g)) {
        const id = tag.match(/\bid="([^"]+)"/)?.[1];
        if (id?.startsWith('cfg_')) elements.set(id, element(id, tag.match(/\bvalue="([^"]*)"/)?.[1] ?? ''));
      }
      for (const [, id, options] of markup.matchAll(/<select id="([^"]+)">([\s\S]*?)<\/select>/g)) {
        if (!id.startsWith('cfg_')) continue;
        const selected = options.match(/<option value="([^"]*)"\s+selected\b/)?.[1];
        elements.set(id, element(id, selected ?? options.match(/<option value="([^"]*)"/)?.[1] ?? ''));
      }
    },
  });
  elements.set(content.id, content);
  const requests = [];
  const errors = [];
  let pause;
  let pauseLoad;
  let rejectSave = false;
  const context = {
    document: Object.assign(doc, {
      getElementById: id => elements.get(id) ?? null,
      querySelectorAll: selector => selector === '.thresh-input'
        ? [...elements.values()].filter(input => /^t(?:Exp|Imp)/.test(input.id)) : [],
    }),
    sessionStorage: { getItem: () => null },
    setTimeout() {},
    console: { error: (...args) => errors.push(args.join(' ')) },
    fetch: async (url, options) => {
      if (url === './api/config' && !options.method) {
        const snapshot = { ...config };
        if (pauseLoad) {
          const pending = pauseLoad;
          pauseLoad = undefined;
          await pending;
        }
        return { ok: true, json: async () => snapshot };
      }
      assert.equal(url, './api/config/batch');
      assert.equal(options.method, 'POST');
      const { updates, persist } = JSON.parse(options.body);
      assert.equal(persist, true);
      const updated = Object.fromEntries(updates.map(({ key, value }) => [key, value]));
      requests.push(updated);
      if (pause) {
        const pending = pause;
        pause = undefined;
        await pending;
      }
      if (rejectSave) {
        rejectSave = false;
        return { ok: false, statusText: 'Save rejected', json: async () => ({ detail: 'Save rejected' }) };
      }
      Object.assign(config, updated);
      return { ok: true, json: async () => ({ ok: true, updated }) };
    },
  };
  context.window = context;
  script.runInNewContext(context);
  await context.loadConfig();
  assert.equal(elements.get('tExpHighLimit').value, '10');
  assert.equal(elements.get(setting(EXPORT, 'export_limit_high')).value, '10');
  const attemptSave = async section => {
    const button = element('apply');
    if (section) await context.applyConfigSection(button, section);
    else await context.applyThresholds(button);
    return button;
  };
  const save = async section => {
    const button = await attemptSave(section);
    assert.deepEqual(errors, []);
    assert.notEqual(button.textContent, 'Error');
  };
  return {
    config, requests, save, attemptSave, reload: () => context.loadConfig(),
    remove: id => elements.delete(id),
    rejectNextSave: () => { rejectSave = true; },
    value: id => elements.get(id).value,
    edit(id, value) {
      const input = elements.get(id);
      input.value = value;
      input.dispatch('input');
      content.dispatch('input', input);
      doc.dispatch('input', input);
    },
    pauseNextSave() {
      let resume;
      pause = new Promise(resolve => { resume = resolve; });
      return resume;
    },
    pauseNextLoad() {
      let resume;
      pauseLoad = new Promise(resolve => { resume = resolve; });
      return resume;
    },
  };
}

test('Settings export cap survives a subsequent dashboard import-only save', async () => {
  const ui = await openDashboard();
  ui.edit(setting(EXPORT, 'export_limit_high'), '12');
  await ui.save(EXPORT);
  const dashboardExportAfterSave = ui.value('tExpHighLimit');
  ui.edit('tImpLowLimit', '4');
  await ui.save();

  assert.equal(ui.config.export_limit_high, 12);
  assert.deepEqual(ui.requests, [{ export_limit_high: 12 }, { import_limit_low: 4 }]);
  assert.equal(dashboardExportAfterSave, '12');
});

test('A stale config reload cannot undo an acknowledged pricing save', async () => {
  const ui = await openDashboard();
  const settingsExport = setting(EXPORT, 'export_limit_high');
  const settingsSpike = setting(EXPORT, 'export_spike_full_power');
  assert.equal(ui.value(settingsSpike), 'false');
  const resume = ui.pauseNextLoad();
  const reload = ui.reload();
  ui.edit(settingsExport, '12');
  ui.edit(settingsSpike, 'true');
  await ui.save(EXPORT);
  resume();
  await reload;

  assert.equal(ui.value('tExpHighLimit'), '12');
  assert.equal(ui.value(settingsExport), '12');
  assert.equal(ui.value(settingsSpike), 'true');
  assert.deepEqual(ui.requests, [{ export_limit_high: 12, export_spike_full_power: true }]);
});

test('Dashboard import cap survives a Settings price-only save without rounding untouched prices', async () => {
  const ui = await openDashboard();
  ui.edit('tImpHighLimit', '12');
  await ui.save();
  const settingsImportAfterSave = ui.value(setting(IMPORT, 'import_limit_high'));
  ui.edit(setting(IMPORT, 'import_threshold_medium'), '-0.02');
  await ui.save(IMPORT);

  assert.equal(ui.config.import_limit_high, 12);
  assert.equal(ui.config.export_threshold_high, 0.1234567);
  assert.deepEqual(ui.requests, [{ import_limit_high: 12 }, { import_threshold_medium: -0.02 }]);
  assert.equal(settingsImportAfterSave, '12');
  assert.equal(Number(ui.value('tImpMedPrice')), -2);
});

test('A save preserves the other editor’s draft for the same field and an unrelated draft', async () => {
  const ui = await openDashboard();
  const settingsExport = setting(EXPORT, 'export_limit_high');
  const settingsImport = setting(IMPORT, 'import_limit_low');
  ui.edit(settingsExport, '13');
  ui.edit(settingsImport, '4');
  ui.edit('tExpHighLimit', '12');
  await ui.save();

  assert.equal(ui.value(settingsExport), '13');
  assert.equal(ui.value(settingsImport), '4');
  await ui.save(EXPORT);
  assert.equal(ui.value('tExpHighLimit'), '13');
  assert.deepEqual(ui.requests, [{ export_limit_high: 12 }, { export_limit_high: 13 }]);
  assert.equal(ui.value(settingsImport), '4');
});

test('Acknowledging a save preserves a newer edit made while the request is pending', async () => {
  const ui = await openDashboard();
  const settingsExport = setting(EXPORT, 'export_limit_high');
  const resume = ui.pauseNextSave();
  ui.edit(settingsExport, '12');
  const pending = ui.save(EXPORT);
  ui.edit(settingsExport, '13');
  resume();
  await pending;

  assert.equal(ui.value(settingsExport), '13');
  assert.equal(ui.value('tExpHighLimit'), '12');
  await ui.save(EXPORT);
  assert.deepEqual(ui.requests, [{ export_limit_high: 12 }, { export_limit_high: 13 }]);
  assert.equal(ui.value('tExpHighLimit'), '13');
});

test('A Morning Dump duration edit omits an untouched floor changed by another client', async () => {
  const ui = await openDashboard();
  ui.config.morning_dump_min_soc = 20;
  ui.edit(setting(DUMP, 'morning_dump_hours_before_sunrise'), '1.5');
  await ui.save(DUMP);

  assert.deepEqual(ui.requests, [{ morning_dump_hours_before_sunrise: 1.5 }]);
  assert.equal(ui.config.morning_dump_min_soc, 20);
});

for (const invalid of ['', '   ', 'Infinity', 'NaN']) {
  test(`A blank or nonfinite Morning Dump floor ${JSON.stringify(invalid)} is rejected before saving`, async () => {
    const ui = await openDashboard();
    const floor = setting(DUMP, 'morning_dump_min_soc');
    ui.edit(floor, invalid);
    const button = await ui.attemptSave(DUMP);

    assert.equal(button.textContent, 'Error');
    assert.deepEqual(ui.requests, []);
    assert.equal(ui.config.morning_dump_min_soc, 15);
    assert.equal(ui.value(floor), invalid);
  });
}

test('An explicit zero and false remain intentional Settings edits', async () => {
  const ui = await openDashboard();
  ui.edit(setting(DUMP, 'morning_dump_min_soc'), '0');
  ui.edit(setting(DUMP, 'morning_dump_enabled'), 'false');
  await ui.save(DUMP);

  assert.deepEqual(ui.requests, [{ morning_dump_enabled: false, morning_dump_min_soc: 0 }]);
});

test('An unchanged section sends no request, including equivalent numeric formatting', async () => {
  const ui = await openDashboard();
  ui.edit(setting(DUMP, 'morning_dump_min_soc'), '15.00');
  await ui.save(DUMP);
  await ui.save(BOOST);

  assert.deepEqual(ui.requests, []);
});

test('Text Settings use exact values and preserve an intentional empty string', async () => {
  const ui = await openDashboard();
  const service = setting('control_notifications', 'notification_service');
  ui.edit(service, '1');
  await ui.save('control_notifications');
  ui.edit(service, '');
  await ui.save('control_notifications');

  assert.deepEqual(ui.requests, [{ notification_service: '1' }, { notification_service: '' }]);
});

test('An entity binding edit omits untouched bindings and a missing input', async () => {
  const ui = await openDashboard();
  ui.edit(setting('ems_limits', 'ems_mode_select'), 'select.replacement_ems');
  ui.remove(setting('ems_limits', 'grid_export_limit'));
  await ui.save('ems_limits');

  assert.deepEqual(ui.requests, [{ ems_mode_select: 'select.replacement_ems' }]);
});

test('Reload preserves drafts across non-pricing sections and refreshes untouched fields', async () => {
  const ui = await openDashboard();
  const duration = setting(DUMP, 'morning_dump_hours_before_sunrise');
  const forecast = setting(BOOST, 'evening_boost_min_tomorrow_forecast_kwh');
  ui.edit(duration, '1.5');
  ui.edit(forecast, '80');
  ui.config.morning_dump_min_soc = 20;
  await ui.reload();

  assert.equal(ui.value(duration), '1.5');
  assert.equal(ui.value(forecast), '80');
  assert.equal(ui.value(setting(DUMP, 'morning_dump_min_soc')), '20');
  await ui.save(DUMP);
  await ui.save(BOOST);
  assert.deepEqual(ui.requests, [
    { morning_dump_hours_before_sunrise: 1.5 },
    { evening_boost_min_tomorrow_forecast_kwh: 80 },
  ]);
});

test('A stale reload cannot undo an acknowledged non-pricing save', async () => {
  const ui = await openDashboard();
  const floor = setting(DUMP, 'morning_dump_min_soc');
  const resume = ui.pauseNextLoad();
  const reload = ui.reload();
  ui.edit(floor, '20');
  await ui.save(DUMP);
  resume();
  await reload;

  assert.equal(ui.value(floor), '20');
  await ui.save(DUMP);
  assert.deepEqual(ui.requests, [{ morning_dump_min_soc: 20 }]);
});

test('A non-pricing save acknowledges only its submitted draft and preserves newer edits', async () => {
  const ui = await openDashboard();
  const floor = setting(DUMP, 'morning_dump_min_soc');
  const resume = ui.pauseNextSave();
  ui.edit(floor, '20');
  const pending = ui.save(DUMP);
  ui.edit(floor, '25');
  resume();
  await pending;

  assert.equal(ui.value(floor), '25');
  await ui.save(DUMP);
  assert.deepEqual(ui.requests, [{ morning_dump_min_soc: 20 }, { morning_dump_min_soc: 25 }]);
});

test('A rejected non-pricing save preserves a newer draft for retry', async () => {
  const ui = await openDashboard();
  const floor = setting(DUMP, 'morning_dump_min_soc');
  const resume = ui.pauseNextSave();
  ui.rejectNextSave();
  ui.edit(floor, '20');
  const pending = ui.attemptSave(DUMP);
  ui.edit(floor, '25');
  resume();
  const button = await pending;

  assert.equal(button.textContent, 'Error');
  assert.equal(ui.config.morning_dump_min_soc, 15);
  assert.equal(ui.value(floor), '25');
});
