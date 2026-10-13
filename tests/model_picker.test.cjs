const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
    let extension;
    const requests = [];
    const context = {
        app: { registerExtension(value) { extension = value; } },
        api: { fetchApi(url, options) {
            return new Promise((resolve) => requests.push({ url, options, resolve }));
        } },
        window: { prompt: () => 'custom-model' },
        AbortController, URLSearchParams,
        setTimeout: () => {},
    };
    const source = fs.readFileSync(path.join(__dirname, '../web/model_picker.js'), 'utf8')
        .replace(/^import .*;\r?\n/gm, '');
    vm.runInNewContext(source, context);
    function Node() {
        this.widgets = [
            { name: 'provider', value: 'Ollama' },
            { name: 'model', value: 'saved-model' },
            { name: 'base_url', value: '' },
        ];
    }
    Node.prototype.addWidget = function(type, name, value, callback, options = {}) {
        const widget = { type, name, value, callback, options };
        this.widgets.push(widget);
        return widget;
    };
    extension.beforeRegisterNodeDef(Node, { name: 'MiniMaxH3LLMProvider' });
    const node = new Node();
    node.onNodeCreated();
    return { node, requests, widget: (name) => node.widgets.find((w) => w.name === name) };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));
const response = (models) => ({ ok: true, json: async () => ({ models }) });

test('newer provider discovery wins even if an old request completes later', async () => {
    const { requests, widget } = setup();
    widget('provider').callback('Ollama');
    widget('provider').value = 'Claude';
    widget('provider').callback('Claude');
    assert.equal(requests[0].options.signal.aborted, true);
    requests[1].resolve(response(['new-model']));
    await flush();
    requests[0].resolve(response(['old-model']));
    await flush();
    assert.equal(widget('model').value, 'new-model');
});

test('endpoint refresh preserves a saved model and manual entry defeats pending discovery', async () => {
    const { requests, widget } = setup();
    widget('base_url').value = 'http://localhost:1234';
    widget('base_url').callback(widget('base_url').value);
    assert.match(requests[0].url, /base_url=http%3A%2F%2Flocalhost%3A1234/);
    requests[0].resolve(response(['discovered-model']));
    await flush();
    assert.equal(widget('model').value, 'saved-model');
    widget('refresh model list').callback();
    widget('enter model manually').callback();
    requests[1].resolve(response(['another-model']));
    await flush();
    assert.equal(widget('model').value, 'custom-model');
    assert.equal(widget('model').options.values.includes('custom-model'), true);
});
