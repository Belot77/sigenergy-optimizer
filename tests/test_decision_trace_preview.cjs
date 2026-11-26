'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { Script } = require('node:vm');

const template = readFileSync(join(__dirname, '../templates/index.html'), 'utf8');
const scripts = [...template.matchAll(/^<script>\r?\n([\s\S]*?)^<\/script>/gm)].map(([, source]) => source);
const state = scripts.find(source => source.startsWith('// ------ State'));
const dashboard = scripts.find(source => source.includes('async function loadDecisionTrace('));
assert.ok(state && dashboard, 'Expected dashboard state and trace scripts');
const startup = dashboard.lastIndexOf('\ninitTheme();');
assert.notEqual(startup, -1, 'Expected dashboard startup block');
const script = new Script(state + dashboard.slice(0, startup), { filename: 'templates/index.html' });

const PREVIEW = './api/decision_trace/preview';
const COPY_500 = './api/decision_trace?limit=500&as_array=true';
const LOGS_500 = './api/logs?n=500';

function summaryRow(index, overrides = {}) {
  return {
    ts: '2026-11-26T05:40:09+00:00',
    ems_mode: 'Maximum Self Consumption',
    outcome_reason: 'decision ' + index + ' summary',
    export_limit_kw: 0,
    ess_charge_limit_kw: 12.5,
    application_status: 'applied',
    solar_provider_state: 'VALID',
    solar_provider_reason: 'provider_success_verified',
    solar_provider_verified_polled: '2026-11-26T05:40:06+00:00',
    solar_provider_deadline: '2026-11-26T08:40:06+00:00',
    ...overrides,
  };
}

function preview(rows) {
  return { ok: true, json: async () => ({ rows }) };
}

function deferred() {
  let resolve;
  const pending = new Promise(resolvePromise => { resolve = resolvePromise; });
  return { pending, resolve };
}

function openDashboard(handleRequest, { clipboard = true, clipboardRejects = false, allowLegacyCopy = () => true } = {}) {
  const elements = new Map(Object.entries({
    logContent: { innerHTML: 'Original view' },
    logMeta: { textContent: '' },
    logLineLimit: { value: '500' },
    logLevelFilter: { value: 'info' },
    uiApiKey: { value: '', addEventListener() {} },
  }));
  const requests = [];
  const writes = [];
  const timers = new Map();
  const fields = new Set();
  let selected;
  let nextTimer = 0;

  function getElementById(id) {
    if (!elements.has(id)) {
      elements.set(id, { textContent: '', innerHTML: '', hidden: false, classList: { add() {}, remove() {} } });
    }
    return elements.get(id);
  }

  const context = {
    document: {
      getElementById,
      querySelectorAll: () => [],
      createElement(tag) {
        assert.equal(tag, 'textarea');
        return {
          value: '', style: {},
          setAttribute() {},
          select() { selected = this; },
          remove() { fields.delete(this); },
        };
      },
      body: {
        appendChild(element) { fields.add(element); return element; },
        removeChild(element) { fields.delete(element); return element; },
      },
      execCommand(command) {
        assert.equal(command, 'copy');
        assert.ok(fields.has(selected));
        if (!allowLegacyCopy()) return false;
        writes.push(selected.value);
        return true;
      },
    },
    window: { location: { href: 'http://test.invalid/', protocol: 'http:' } },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return handleRequest(url, options);
    },
    navigator: clipboard ? { clipboard: {
      async writeText(value) {
        if (clipboardRejects) throw new Error('Clipboard permission denied');
        writes.push(value);
      },
    } } : {},
    sessionStorage: { getItem: () => 'test-api-key' },
    AbortController,
    URL,
    setTimeout(callback) {
      const id = ++nextTimer;
      timers.set(id, callback);
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
  };
  context.window.fetch = context.fetch;
  script.runInNewContext(context);

  return {
    context, elements, requests, writes, timers, fields,
    expireNextRequest() {
      assert.equal(timers.size, 1);
      const [id, callback] = timers.entries().next().value;
      timers.delete(id);
      callback();
    },
    text() {
      return [...elements.values()].map(element => [element.textContent, element.innerHTML].join(' ')).join(' ');
    },
  };
}

test('Decision Trace opens a bounded summary and shows the latest Solcast status', async () => {
  const rows = Array.from({ length: 20 }, (_, index) => summaryRow(index));
  rows[0] = summaryRow(0, { outcome_reason: '<img src=x onerror=example()>' });
  const ui = openDashboard((url) => {
    assert.equal(url, PREVIEW);
    return preview(rows);
  });

  await ui.context.loadDecisionTrace();

  assert.deepEqual(ui.requests.map(({ url }) => url), [PREVIEW]);
  assert.equal(ui.requests[0].options.headers['x-api-key'], 'test-api-key');
  assert.match(ui.text(), /Solcast Verified/);
  assert.match(ui.text(), /poll/i);
  assert.match(ui.text(), /expir|deadline/i);
  assert.match(ui.text(), /decision 19 summary/);
  const content = ui.elements.get('logContent').innerHTML;
  assert.doesNotMatch(content, /<img src=x onerror=example\(\)>/);
  assert.match(content, /&lt;img src=x onerror=example\(\)&gt;/);
  assert.ok(content.length < 20_000, '500-row selection must not expand preview markup');
  assert.equal(ui.timers.size, 0);
});

test('Copy Trace JSON requests all 500 original decisions only when clicked and never renders them', async () => {
  const payload = 'large raw diagnostic '.repeat(500);
  const trace = JSON.stringify(Array.from({ length: 500 }, (_, index) => ({
    index,
    values: { all_evidence: payload },
    application: { error: index === 499 ? 'last record retained' : null },
  })));
  const pending = deferred();
  const ui = openDashboard((url) => {
    assert.equal(url, COPY_500);
    return pending.pending;
  });
  const button = { disabled: false, textContent: 'Copy Trace JSON', focus() {} };

  assert.equal(ui.requests.length, 0);
  const copying = ui.context.copyDecisionTrace(button);
  assert.equal(button.disabled, true);
  pending.resolve({
    ok: true,
    text: async () => trace,
    json: async () => assert.fail('Full trace should be copied as raw response text'),
  });
  await copying;

  assert.deepEqual(ui.requests.map(({ url }) => url), [COPY_500]);
  assert.equal(ui.requests[0].options.headers['x-api-key'], 'test-api-key');
  assert.equal(ui.writes.length, 1);
  assert.equal(ui.writes[0], trace);
  const copied = JSON.parse(ui.writes[0]);
  assert.equal(copied.length, 500);
  assert.equal(copied[499].application.error, 'last record retained');
  assert.equal(ui.elements.get('logContent').innerHTML, 'Original view');
  assert.equal(button.disabled, false);
  assert.equal(ui.timers.size, 0);
});

test('Copy Trace JSON falls back to an offscreen textarea when browser clipboard rejects', async () => {
  const trace = '[{"values":{"detail":"keep exact bytes"}}]';
  const ui = openDashboard((url) => {
    assert.equal(url, COPY_500);
    return { ok: true, text: async () => trace };
  }, { clipboardRejects: true });
  const button = { disabled: false, textContent: 'Copy Trace JSON', focus() {} };

  await ui.context.copyDecisionTrace(button);

  assert.deepEqual(ui.writes, [trace]);
  assert.equal(ui.fields.size, 0);
  assert.equal(ui.elements.get('logContent').innerHTML, 'Original view');
  assert.equal(button.disabled, false);
});

test('A superseded preview cannot replace ordinary logs', async () => {
  const pending = deferred();
  const ui = openDashboard((url) => {
    if (url === PREVIEW) return pending.pending;
    assert.equal(url, LOGS_500);
    return { ok: true, text: async () => 'INFO ordinary optimizer log' };
  });

  const loadingPreview = ui.context.loadDecisionTrace();
  await ui.context.loadLogs();
  pending.resolve(preview([summaryRow(0, { outcome_reason: 'stale preview arrived late' })]));
  await loadingPreview;

  assert.deepEqual(ui.requests.map(({ url }) => url), [PREVIEW, LOGS_500]);
  assert.match(ui.elements.get('logContent').innerHTML, /ordinary optimizer log/);
  assert.doesNotMatch(ui.elements.get('logContent').innerHTML, /stale preview arrived late/);
  assert.equal(ui.timers.size, 0);
});

test('A stalled preview times out and can be reopened', async () => {
  let first = true;
  const ui = openDashboard((url, { signal }) => {
    assert.equal(url, PREVIEW);
    if (!first) return preview([summaryRow(0)]);
    first = false;
    return new Promise((resolve, reject) => {
      assert.ok(signal, 'Preview should send an abort signal');
      signal.addEventListener('abort', () => reject(signal.reason), { once: true });
    });
  });

  const stalled = ui.context.loadDecisionTrace();
  ui.expireNextRequest();
  await stalled;
  assert.match(ui.text(), /timed out|timeout/i);
  assert.equal(ui.timers.size, 0);

  await ui.context.loadDecisionTrace();
  assert.match(ui.elements.get('logContent').innerHTML, /decision 0 summary/);
  assert.equal(ui.timers.size, 0);
});


test('A stalled copy body times out, restores the control, and allows a retry', async () => {
  const trace = '[{"values":"complete"}]';
  const bodyStarted = deferred();
  let first = true;
  const ui = openDashboard((url, { signal }) => {
    assert.equal(url, COPY_500);
    if (!first) return { ok: true, text: async () => trace };
    first = false;
    return {
      ok: true,
      text: () => new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(signal.reason), { once: true });
        bodyStarted.resolve();
      }),
    };
  });
  const button = { disabled: false, textContent: 'Copy Trace JSON', focus() {} };

  const copying = ui.context.copyDecisionTrace(button);
  await bodyStarted.pending;
  assert.equal(button.disabled, true);
  ui.expireNextRequest();
  await copying;

  assert.match(ui.text(), /timed out|timeout/i);
  assert.equal(button.disabled, false);
  assert.equal(ui.writes.length, 0);
  assert.equal(ui.elements.get('logContent').innerHTML, 'Original view');

  await ui.context.copyDecisionTrace(button);

  assert.deepEqual(ui.writes, [trace]);
  assert.equal(button.disabled, false);
  assert.equal(ui.timers.size, 0);
});


test('A second click copies the prepared trace without another request', async () => {
  const trace = JSON.stringify(Array.from({ length: 500 }, (_, index) => ({
    index,
    values: { detail: 'original diagnostic ' + index },
  })));
  let permitLegacyCopy = false;
  const ui = openDashboard((url) => {
    assert.equal(url, COPY_500);
    return { ok: true, text: async () => trace };
  }, { clipboard: false, allowLegacyCopy: () => permitLegacyCopy });
  const button = { disabled: false, textContent: 'Copy Trace JSON', focus() {} };

  await ui.context.copyDecisionTrace(button);
  assert.equal(ui.writes.length, 0);
  assert.equal(button.disabled, false);
  assert.match(ui.text(), /click.*again|copy.*again|copy.*ready/i);

  permitLegacyCopy = true;
  const retry = ui.context.copyDecisionTrace(button);
  assert.deepEqual(ui.writes, [trace], 'The legacy copy runs in the second click before any await');
  await retry;

  assert.deepEqual(ui.requests.map(({ url }) => url), [COPY_500]);
  assert.equal(JSON.parse(ui.writes[0]).length, 500);
  assert.equal(ui.fields.size, 0);
  assert.equal(button.disabled, false);
  assert.equal(ui.elements.get('logContent').innerHTML, 'Original view');
});
