import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createSimulation, PHASES, ROUTES, LANDMARKS, project } from '../dist/simulation.js';

test('guided pitch transitions at 18 and 39 seconds and finishes at 60',()=>{
  const sim=createSimulation();sim.startStory();sim.tick(17);assert.equal(sim.phase,'normal');
  sim.tick(1);assert.equal(sim.phase,'incident');sim.tick(21);assert.equal(sim.phase,'resolved');
  sim.tick(21);assert.equal(sim.story,null);assert.equal(sim.phase,'resolved');
});
test('pause holds movement and story; speed changes movement without shortening the pitch',()=>{
  const sim=createSimulation();sim.startStory();sim.cycleSpeed();sim.tick(10);
  assert.equal(sim.elapsed,20);assert.equal(sim.story,10);sim.togglePause();sim.tick(15);
  assert.equal(sim.story,10);assert.equal(sim.elapsed,20);sim.togglePause();sim.tick(8);assert.equal(sim.phase,'incident');
});
test('reset restores phase, speed, mode visibility and reduced-motion preference',()=>{
  const sim=createSimulation({reducedMotion:true});assert.equal(sim.paused,true);sim.startStory();
  sim.setPhase('resolved');sim.cycleSpeed();sim.toggleMode('tram');sim.reset();
  assert.equal(sim.phase,'normal');assert.equal(sim.paused,true);assert.equal(sim.speed,1);assert.equal(sim.modes.tram,true);assert.equal(sim.story,null);
});
test('rejects invalid state and time; mode copies cannot mutate internal state',()=>{
  const sim=createSimulation();assert.throws(()=>sim.setPhase('bad'));assert.throws(()=>sim.toggleMode('bad'));
  assert.throws(()=>sim.tick(-1));assert.throws(()=>sim.tick(NaN));assert.throws(()=>sim.tick(Infinity));
  const modes=sim.modes;modes.car=false;assert.equal(sim.modes.car,true);
});
test('scenario estimates remain explicit and geographically bounded',()=>{
  assert.equal(PHASES.incident.minutes-PHASES.resolved.minutes,13);
  for(const route of Object.values(ROUTES))for(const point of route)assert.equal(point.length,2);
  for(const mark of LANDMARKS){const p=project(mark.lat,mark.lon);assert.ok(Math.abs(p.x)<110&&Math.abs(p.z)<110);}
});
test('all local HTML assets and module imports exist; controls have matching markup',()=>{
  const root=resolve(dirname(fileURLToPath(import.meta.url)),'../dist');
  const html=readFileSync(resolve(root,'index.html'),'utf8');
  for(const match of html.matchAll(/(?:src|href)="(\.\/[^"#]+)"/g))assert.ok(existsSync(resolve(root,match[1])),match[1]);
  const app=readFileSync(resolve(root,'app.js'),'utf8');const ids=new Set([...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
  for(const match of app.matchAll(/\$\('([^']+)'\)/g))assert.ok(ids.has(match[1]),`Missing control ${match[1]}`);
  for(const file of ['app.js','scene.js'])for(const match of readFileSync(resolve(root,file),'utf8').matchAll(/(?:from\s*|import\()['"](\.\/[^'"]+)['"]/g))assert.ok(existsSync(resolve(root,match[1])),match[1]);
});
