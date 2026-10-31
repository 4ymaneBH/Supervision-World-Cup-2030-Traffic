import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {TEXT, selectLanguage, text, phaseText, landmarkText} from '../dist/i18n.js';
import {LANDMARKS, PHASES} from '../dist/simulation.js';

test('French is the default; explicit links override saved language',()=>{
  assert.equal(selectLanguage(),'fr');assert.equal(selectLanguage('?lang=en','fr'),'en');
  assert.equal(selectLanguage('?lang=fr','en'),'fr');assert.equal(selectLanguage('?lang=bad','en'),'en');
  assert.equal(selectLanguage('','bad'),'fr');
});
test('French and English cover every marked UI label with matching placeholders',()=>{
  assert.deepEqual(Object.keys(TEXT.fr).sort(),Object.keys(TEXT.en).sort());
  for(const key of Object.keys(TEXT.en)){
    assert.ok(TEXT.fr[key].trim(),key);
    const placeholders=value=>[...value.matchAll(/\{(\w+)\}/g)].map(m=>m[1]).sort();
    assert.deepEqual(placeholders(TEXT.fr[key]),placeholders(TEXT.en[key]),key);
  }
  const html=readFileSync(new URL('../dist/index.html',import.meta.url),'utf8');
  for(const match of html.matchAll(/data-i18n(?:-aria|-title)?="([^"]+)"/g)){
    assert.ok(TEXT.en[match[1]],match[1]);assert.ok(TEXT.fr[match[1]],match[1]);
  }
});
test('all three French phases preserve the same numerical assumptions',()=>{
  for(const phase of ['normal','incident','resolved']){
    const fr=phaseText('fr',phase);const en=phaseText('en',phase);
    for(const field of ['number','minutes','flow','supporters'])assert.equal(fr[field],en[field]);
    assert.notEqual(fr.title,en.title);assert.notEqual(fr.detail,en.detail);
  }
  assert.equal(PHASES.normal.title,'Before the rush');
});
test('labels, fallbacks and accessibility messages are localized',()=>{
  assert.equal(landmarkText('fr',LANDMARKS.find(m=>m.id==='hassan')).name,'Tour Hassan');
  assert.match(landmarkText('fr',LANDMARKS.find(m=>m.id==='agdal')).sub,/Correspondance/);
  assert.equal(text('fr','speed',{speed:2}),'Vitesse de simulation : 2 fois');
  assert.throws(()=>text('fr','missing'));
});
