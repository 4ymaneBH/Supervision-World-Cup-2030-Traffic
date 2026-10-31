import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../dist/vendor/three.module.js';
import {createVehicleFleet} from '../dist/vehicles.js';
import {ROUTES,createSimulation} from '../dist/simulation.js';

function setup(){
  const parent=new THREE.Group(),unitBox=new THREE.BoxGeometry(1,1,1);
  const curves=Object.fromEntries(Object.entries(ROUTES).map(([id,points])=>[id,new THREE.CatmullRomCurve3(points.map(([x,z])=>new THREE.Vector3(x,.19,z)),false,'centripetal')]));
  const cache=new Map();const material=color=>{if(!cache.has(color))cache.set(color,new THREE.MeshStandardMaterial({color}));return cache.get(color);};
  const fleet=createVehicleFleet(parent,curves,material,()=>.5,unitBox),simulation=createSimulation();
  const cleanup=()=>{fleet.dispose();unitBox.dispose();for(const m of cache.values())m.dispose();};
  return{parent,unitBox,curves,fleet,simulation,cleanup};
}
function body(fleet,mode='car'){return fleet.meshes.find(mesh=>mesh.name===`vehicle-${mode}-body`);}
function position(mesh,index=0){const matrix=new THREE.Matrix4();mesh.getMatrixAt(index,matrix);return new THREE.Vector3().setFromMatrixPosition(matrix);}

test('98 vehicles share one geometry and eleven instanced render batches',()=>{
  const {fleet,unitBox,cleanup}=setup();
  assert.equal(fleet.vehicleCount,98);assert.equal(fleet.meshes.length,11);
  assert.ok(fleet.meshes.every(mesh=>mesh.isInstancedMesh&&mesh.geometry===unitBox&&!mesh.castShadow));
  assert.ok(fleet.meshes.every(mesh=>mesh.instanceMatrix.usage===THREE.DynamicDrawUsage));cleanup();
});
test('motion follows the original route closely and pauses without changing matrices',()=>{
  const {fleet,curves,simulation,cleanup}=setup();fleet.update(0,simulation);
  const expected=curves.main.getPointAt(.25/20),tangent=curves.main.getTangentAt(.25/20);
  expected.add(new THREE.Vector3(-tangent.z*.6,.6,tangent.x*.6));
  const car=body(fleet);assert.ok(position(car).distanceTo(expected)<.08);
  fleet.update(1,simulation);const moving=position(car);assert.ok(moving.distanceTo(expected)>.5);
  simulation.togglePause();fleet.update(0,simulation);const version=car.instanceMatrix.version;
  assert.equal(fleet.update(1,simulation),false);assert.equal(car.instanceMatrix.version,version);
  assert.ok(position(car).distanceTo(moving)<.0001);cleanup();
});
test('phase changes reroute the shuttle even while paused; reset is reproducible',()=>{
  const {fleet,simulation,cleanup}=setup();simulation.togglePause();fleet.update(0,simulation);
  const before=position(body(fleet,'bus'));simulation.setPhase('resolved');
  assert.equal(fleet.update(0,simulation),true);assert.ok(position(body(fleet,'bus')).distanceTo(before)>1);
  simulation.reset();fleet.reset();fleet.update(0,simulation);const reset=position(body(fleet));
  fleet.update(5,simulation);fleet.reset();fleet.update(0,simulation);
  assert.ok(position(body(fleet)).distanceTo(reset)<.0001);cleanup();
});
test('mode filters hide and restore every part of a vehicle batch',()=>{
  const {fleet,simulation,cleanup}=setup();fleet.update(0,simulation);simulation.togglePause();
  simulation.toggleMode('tram');assert.equal(fleet.update(0,simulation),true);
  assert.ok(fleet.meshes.filter(mesh=>mesh.userData.mode==='tram').every(mesh=>!mesh.visible));
  simulation.toggleMode('tram');fleet.update(0,simulation);
  assert.ok(fleet.meshes.filter(mesh=>mesh.userData.mode==='tram').every(mesh=>mesh.visible));cleanup();
});
test('fixed culling bounds contain moving instances across the entire scenario',()=>{
  const {fleet,simulation,cleanup}=setup();
  for(const phase of ['normal','incident','resolved']){
    simulation.setPhase(phase);
    for(let step=0;step<30;step++){
      fleet.update(1,simulation);
      for(const mesh of fleet.meshes)for(let i=0;i<mesh.count;i++)assert.ok(mesh.boundingSphere.containsPoint(position(mesh,i)),mesh.name);
    }
  }
  cleanup();
});
test('hot-path updates use cached routes, and disposing releases batch objects safely',()=>{
  const {fleet,curves,parent,simulation,unitBox,cleanup}=setup();
  for(const curve of Object.values(curves)){curve.getPointAt=()=>{throw Error('Unexpected curve work per frame');};curve.getTangentAt=curve.getPointAt;}
  assert.doesNotThrow(()=>fleet.update(1/60,simulation));
  let geometryDisposed=false;unitBox.addEventListener('dispose',()=>geometryDisposed=true);
  fleet.dispose();fleet.dispose();assert.equal(parent.children.length,0);assert.equal(geometryDisposed,false);
  cleanup();assert.equal(geometryDisposed,true);
});
