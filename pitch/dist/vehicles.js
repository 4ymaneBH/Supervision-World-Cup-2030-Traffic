import * as THREE from './vendor/three.module.js';

const COLORS={car:0xd48b55,bus:0x216d51,tram:0xb16ab5,train:0x6c77b7};
const DEFINITIONS=[['car','main',20],['car','north',10],['car','avenue',15],['car','cross',11],['car','east',11],['car','coast',9],['car','west',7],['bus','main',5],['bus','north',3],['tram','tram',4],['train','rail',3]];
const SAMPLES=256;

// One shared cube, eleven instanced batches, and reusable matrices for all 98 vehicles.
// Curve evaluation happens once while loading, rather than allocating tangent vectors per frame.
export function createVehicleFleet(parent,curves,material,random,unitBox){
  const tables={};const routeBounds=new THREE.Box3();
  const point=new THREE.Vector3(),tangent=new THREE.Vector3();
  for(const [name,curve] of Object.entries(curves)){
    const positions=new Float32Array((SAMPLES+1)*3),directions=new Float32Array((SAMPLES+1)*3);
    for(let i=0;i<=SAMPLES;i++){
      curve.getPointAt(i/SAMPLES,point);curve.getTangentAt(i/SAMPLES,tangent);
      point.toArray(positions,i*3);tangent.toArray(directions,i*3);routeBounds.expandByPoint(point);
    }
    tables[name]={positions,directions,length:curve.getLength()};
  }
  // The fixed bounds include every interpolated route and each vehicle's full extent.
  // They remain valid as instances move, retaining safe frustum culling without per-frame scans.
  const bounds=routeBounds.expandByScalar(6).getBoundingSphere(new THREE.Sphere());
  const records=[],batches=[];
  const transform=new THREE.Object3D(),matrix=new THREE.Matrix4();
  const identity=new THREE.Quaternion();
  const glass=material(0xe8f0db),roofMaterial=material(0xf2efda);
  for(const mode of Object.keys(COLORS)){
    const definitions=DEFINITIONS.filter(item=>item[0]===mode);
    const count=definitions.reduce((total,item)=>total+item[2],0);
    const parts=[];
    const body=mode==='car'?[.9,.65,1.9]:mode==='bus'?[1.25,1,3.7]:mode==='tram'?[1.35,1,6]:[1.5,1.15,8];
    addPart('body',body,[0,mode==='car'?.6:.8,0],material(COLORS[mode]));
    addPart('roof',mode==='car'?[.72,.24,1]:[mode==='train'?1.3:1.1,.15,mode==='bus'?2.8:mode==='tram'?5.4:7.3],[0,mode==='car'?1.02:1.37,0],mode==='car'?glass:roofMaterial);
    if(mode!=='car')addPart('window',[mode==='train'?1.3:1.08,.43,.04],[0,.97,mode==='bus'?1.87:mode==='tram'?3.02:4.02],glass);
    const batch={mode,parts,visible:true};batches.push(batch);
    let index=0;
    for(const [,route,number] of definitions){
      for(let i=0;i<number;i++){
        records.push({mode,baseRoute:route,route,batch,index:index++,t:(i+.25)/number,direction:i%2===0?1:-1,speed:(mode==='car'?6.5:mode==='bus'?4.7:mode==='tram'?5.5:8.5)*(.85+random()*.3)});
      }
    }
    function addPart(name,size,offset,partMaterial){
      const mesh=new THREE.InstancedMesh(unitBox,partMaterial,count);
      mesh.name=`vehicle-${mode}-${name}`;mesh.userData.mode=mode;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.boundingSphere=bounds.clone();mesh.receiveShadow=true;
      // Moving vehicles never enter the cached static shadow map.
      mesh.castShadow=false;
      parent.add(mesh);
      parts.push({mesh,local:new THREE.Matrix4().compose(new THREE.Vector3(...offset),identity,new THREE.Vector3(...size))});
    }
  }
  let previousPhase=null,dirty=true,disposed=false;
  return{
    vehicleCount:records.length,
    meshes:batches.flatMap(batch=>batch.parts.map(part=>part.mesh)),
    update(dt,simulation){
      if(disposed)return false;
      const phaseChanged=previousPhase!==simulation.phase;previousPhase=simulation.phase;
      const modes=simulation.modes;let visibilityChanged=false;
      for(const batch of batches){
        if(batch.visible!==modes[batch.mode]){batch.visible=modes[batch.mode];visibilityChanged=true;}
        for(const part of batch.parts)part.mesh.visible=batch.visible;
      }
      if(simulation.paused&&!dirty&&!phaseChanged&&!visibilityChanged)return false;
      for(const vehicle of records){
        vehicle.route=vehicle.mode==='bus'&&vehicle.baseRoute==='main'&&simulation.phase==='resolved'?'west':vehicle.baseRoute;
        const route=tables[vehicle.route];
        if(!simulation.paused){
          const jam=vehicle.route==='main'&&vehicle.t>.25&&vehicle.t<.85;
          const slow=jam?(simulation.phase==='incident'?.15:simulation.phase==='resolved'?.65:1):1;
          vehicle.t=(vehicle.t+dt*simulation.speed*vehicle.speed/route.length*vehicle.direction*slow+1)%1;
        }
        if(!vehicle.batch.visible)continue;
        const sample=vehicle.t*SAMPLES,i=Math.floor(sample),a=i*3,b=(i+1)*3,f=sample-i;
        const x=route.positions[a]+(route.positions[b]-route.positions[a])*f;
        const y=route.positions[a+1]+(route.positions[b+1]-route.positions[a+1])*f;
        const z=route.positions[a+2]+(route.positions[b+2]-route.positions[a+2])*f;
        const dx=route.directions[a]+(route.directions[b]-route.directions[a])*f;
        const dz=route.directions[a+2]+(route.directions[b+2]-route.directions[a+2])*f;
        const offset=(vehicle.mode==='car'?.6:vehicle.mode==='bus'?.45:0)*vehicle.direction;
        transform.position.set(x-dz*offset,y,z+dx*offset);
        transform.rotation.y=Math.atan2(dx*vehicle.direction,dz*vehicle.direction);transform.updateMatrix();
        for(const part of vehicle.batch.parts){matrix.multiplyMatrices(transform.matrix,part.local);part.mesh.setMatrixAt(vehicle.index,matrix);}
      }
      for(const batch of batches)if(batch.visible)for(const part of batch.parts)part.mesh.instanceMatrix.needsUpdate=true;
      dirty=false;return true;
    },
    reset(){records.forEach((vehicle,i)=>vehicle.t=(i*.137+.03)%1);dirty=true;},
    dispose(){if(disposed)return;disposed=true;for(const batch of batches)for(const part of batch.parts){parent.remove(part.mesh);part.mesh.dispose();}},
  };
}
