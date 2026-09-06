// T1 referee helper: run the tape page's own JS under a minimal DOM shim and
// report whether it survives load. Usage: node research/t1_referee_pagejs.js
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'tape', 'omen-tape.html'), 'utf8');

function grabScript(id) {
  const re = new RegExp('<script id="' + id + '" type="application/json">([\\s\\S]*?)</script>');
  const m = html.match(re);
  return m ? m[1] : null;
}
const dataText = grabScript('data');
const fillarmText = grabScript('fillarmdata');

// the last <script> block is the page engine
const j = html.lastIndexOf('<script>');
const js = html.slice(j + '<script>'.length, html.indexOf('</script>', j));

function mkEl() {
  const el = {
    innerHTML: '', textContent: '', value: '', checked: false, style: {},
    children: [], classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {}, appendChild() {}, setAttribute() {}, getAttribute() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; },
    closest() { return null; },
  };
  return el;
}
const store = {};
global.document = {
  getElementById(id) {
    if (id === 'data') return { textContent: dataText };
    if (id === 'fillarmdata') return { textContent: fillarmText };
    if (!store[id]) store[id] = mkEl();
    return store[id];
  },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  createElement() { return mkEl(); },
  body: mkEl(),
};
global.window = { addEventListener() {}, location: { hash: '' } };
global.Set = Set;

try {
  eval(js);
  console.log('PAGE_JS_RESULT: ran to completion without throwing');
} catch (e) {
  console.log('PAGE_JS_RESULT: THREW ' + e.constructor.name + ': ' + e.message);
  const line = (e.stack || '').split('\n').slice(0, 4).join(' | ');
  console.log('PAGE_JS_STACK: ' + line);
}
