import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { ROUTES, LANDMARKS, project } from './simulation.js';
import { landmarkText, text } from './i18n.js';
import { createVehicleFleet } from './vehicles.js';

const PALETTE={car:0xd48b55,bus:0x216d51,tram:0xb16ab5,train:0x6c77b7};

export function createCity(host, labelsHost, simulation, language='en') {
  let renderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});}
  catch{return createFallback(host,labelsHost,simulation,language);}
  const seedRandom=(()=>{let seed=2030;return()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};})();
  const materials=new Map();
  const material=(color,extra={})=>{const key=color+JSON.stringify(extra);if(!materials.has(key))materials.set(key,new THREE.MeshStandardMaterial({color,roughness:.93,...extra}));return materials.get(key);};
  const unitBox=new THREE.BoxGeometry(1,1,1);
  let needsRender=true,labelsDirty=true,disposed=false,viewWidth=0,viewHeight=0;
  const markCameraDirty=()=>{needsRender=true;labelsDirty=true;};
  renderer.setClearColor(0xe4eadb);
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.05;
  host.appendChild(renderer.domElement);
  renderer.domElement.setAttribute('aria-hidden','true');
  const scene=new THREE.Scene();
  const camera=new THREE.OrthographicCamera(-150,150,105,-105,.1,900);
  const target=new THREE.Vector3(-2,0,10);
  const home=new THREE.Vector3(133,182,179);
  camera.position.copy(home);camera.lookAt(target);
  const controls=new OrbitControls(camera,renderer.domElement);
  controls.target.copy(target);controls.enableDamping=true;controls.dampingFactor=.08;
  controls.minPolarAngle=.18;controls.maxPolarAngle=Math.PI/2.6;controls.minZoom=.7;controls.maxZoom=2.5;
  controls.enablePan=false;controls.rotateSpeed=.55;controls.zoomSpeed=.7;
  controls.addEventListener('change',markCameraDirty);
  scene.add(new THREE.HemisphereLight(0xfff9e8,0x8b9a81,2.5));
  const sun=new THREE.DirectionalLight(0xfff5de,3);sun.position.set(-70,130,-45);
  sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);
  Object.assign(sun.shadow.camera,{left:-140,right:140,top:140,bottom:-140,near:10,far:400});
  sun.shadow.bias=-.001;sun.shadow.normalBias=.12;scene.add(sun);

  const city=new THREE.Group();scene.add(city);
  const ground=new THREE.Mesh(new THREE.BoxGeometry(211,2.5,211),[
    material(0xb7c6a6),material(0xb7c6a6),material(0xd7e1c8),material(0xb7c6a6),material(0xc4d0b2),material(0xc4d0b2),
  ]);ground.position.set(0,-1.45,9);ground.receiveShadow=true;city.add(ground);
  const underlay=new THREE.Mesh(new THREE.PlaneGeometry(2000,2000),material(0xe4eadb));underlay.rotation.x=-Math.PI/2;underlay.position.y=-3;underlay.receiveShadow=true;scene.add(underlay);
  const roadSamples=[];const curves={};const routeMeshes={};
  for(const [id,points] of Object.entries(ROUTES)){
    curves[id]=new THREE.CatmullRomCurve3(points.map(([x,z])=>new THREE.Vector3(x,.19,z)),false,'centripetal');
    roadSamples.push(...curves[id].getPoints(100));
    if(id==='rail'||id==='tram') continue;
    ribbon(curves[id],3.2,.01,0xb6c3a8);
    ribbon(curves[id],2.5,.04,0xf3f2df);
    const lane=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curves[id].getPoints(120).map(p=>p.clone().setY(.09))),new THREE.LineDashedMaterial({color:0xb2bba7,dashSize:1.3,gapSize:1.6,transparent:true,opacity:.8}));lane.computeLineDistances();city.add(lane);
  }

  // A simplified Atlantic edge and Bouregreg estuary establish Rabat's geography.
  polygon([[-105,-96],[-24,-96],[-34,-72],[-45,-50],[-55,-22],[-65,6],[-73,45],[-80,90],[-89,114],[-105,114]],0xa8cebf,.12);
  const river=new THREE.CatmullRomCurve3([[55,-96],[57,-84],[63,-72],[74,-61],[86,-52],[105,-47]].map(([x,z])=>new THREE.Vector3(x,0,z)));
  ribbon(river,10,.14,0xa8cebf);ribbon(river,11.5,.11,0xe7e5ca);
  const wavePoints=[];
  for(let i=0;i<10;i++)wavePoints.push(new THREE.Vector3(-96+i*.9,.19,-69+i*13),new THREE.Vector3(-83+i*.3,.19,-72+i*13));
  city.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(wavePoints),new THREE.LineBasicMaterial({color:0xcce0d0,transparent:true,opacity:.65})));
  const parkZones=[{x:-29,z:-37,rx:15,rz:12},{x:28,z:29,rx:13,rz:17},{x:-42,z:61,rx:7,rz:10},{x:53,z:-28,rx:9,rz:12}];
  const parkGeometry=new THREE.CircleGeometry(1,40);
  for(const p of parkZones){const park=new THREE.Mesh(parkGeometry,material(0xb7cc9e));park.rotation.x=-Math.PI/2;park.scale.set(p.rx,p.rz,1);park.position.set(p.x,.12,p.z);park.receiveShadow=true;city.add(park);}

  // Buildings are seeded decorative massing, not real building footprints.
  const buildingData=[];const landmarkPoints=LANDMARKS.filter(p=>p.kind!=='water').map(p=>({...project(p.lat,p.lon),kind:p.kind}));
  for(let z=-78;z<99;z+=7.4){for(let x=-83;x<86;x+=7.4){
    const bx=x+(seedRandom()-.5)*1.8,bz=z+(seedRandom()-.5)*1.8;
    if(bx<(-24-(bz+96)*.32)+6)continue;
    if(bz<-48&&bx>48)continue;
    if(roadSamples.some(p=>(p.x-bx)**2+(p.z-bz)**2<18))continue;
    if(landmarkPoints.some(p=>(p.x-bx)**2+(p.z-bz)**2<(p.kind==='stadium'?320:100)))continue;
    if(parkZones.some(p=>((bx-p.x)/p.rx)**2+((bz-p.z)/p.rz)**2<1))continue;
    buildingData.push({x:bx,z:bz,w:2.5+seedRandom()*2.7,d:2.4+seedRandom()*2.8,h:1.5+seedRandom()*4.2,c:Math.floor(seedRandom()*3)});
  }}
  const buildingColors=[0xecebd9,0xe0e2cd,0xcbd6b9];
  const dummy=new THREE.Object3D();
  buildingColors.forEach((color,i)=>{
    const subset=buildingData.filter(b=>b.c===i);
    const mesh=new THREE.InstancedMesh(unitBox,material(color),subset.length);mesh.castShadow=true;mesh.receiveShadow=true;
    subset.forEach((b,j)=>{dummy.position.set(b.x,b.h/2+.1,b.z);dummy.scale.set(b.w,b.h,b.d);dummy.rotation.y=(seedRandom()-.5)*.08;dummy.updateMatrix();mesh.setMatrixAt(j,dummy.matrix);});city.add(mesh);
  });
  const trees=[];
  for(let i=0;i<190;i++){
    const park=parkZones[i%parkZones.length];const angle=seedRandom()*Math.PI*2;const r=Math.sqrt(seedRandom())*.9;
    trees.push({x:park.x+Math.cos(angle)*park.rx*r,z:park.z+Math.sin(angle)*park.rz*r,h:1.3+seedRandom()*1.1});
  }
  const foliage=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),material(0x809c70),trees.length);foliage.castShadow=true;
  trees.forEach((p,i)=>{dummy.position.set(p.x,p.h,p.z);dummy.rotation.set(0,seedRandom()*3,0);dummy.scale.set(.85,p.h*.65,.85);dummy.updateMatrix();foliage.setMatrixAt(i,dummy.matrix);});city.add(foliage);

  const railMeshes=[];
  for(const id of ['rail','tram']){
    const matColor=id==='rail'?0x9197a5:0xb58bb1;
    railMeshes.push(ribbon(curves[id],id==='rail'?2.4:1.6,.19,id==='rail'?0xc2c7ba:0xd3bdca));
    for(const offset of [-.35,.35]){
      const pts=curves[id].getPoints(200).map((p,i,arr)=>{
        const tangent=curves[id].getTangent(i/(arr.length-1));return p.clone().add(new THREE.Vector3(-tangent.z*offset,.09,tangent.x*offset));
      });const track=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineBasicMaterial({color:matColor}));city.add(track);railMeshes.push(track);
    }
  }
  routeMeshes.main=ribbon(curves.main,.35,.23,0xd48b55);
  // Phase highlighting must not recolor the shared vehicle material.
  routeMeshes.main.material=routeMeshes.main.material.clone();
  routeMeshes.west=ribbon(curves.west,.65,.26,0x397857);routeMeshes.west.visible=false;

  makeStation(-3,17,1.1);makeStation(35,-36,1);
  makeStadium();makeHassan();
  const stadiumMarker=new THREE.Mesh(new THREE.TorusGeometry(19,.23,6,90),new THREE.MeshBasicMaterial({color:0x4e8156,transparent:true,opacity:.55}));stadiumMarker.rotation.x=-Math.PI/2;stadiumMarker.scale.y=.78;stadiumMarker.position.set(-56,.25,85);city.add(stadiumMarker);
  const incidentPoint=curves.main.getPoint(.58);
  const incidentRing=new THREE.Mesh(new THREE.TorusGeometry(5,.5,8,48),new THREE.MeshBasicMaterial({color:0xd77d50,transparent:true,opacity:.8}));incidentRing.rotation.x=-Math.PI/2;incidentRing.position.copy(incidentPoint).setY(.65);incidentRing.visible=false;city.add(incidentRing);
  const fleet=createVehicleFleet(city,curves,material,seedRandom,unitBox);
  // Only static buildings and landmarks cast shadows, so their map can be cached.
  renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
  city.traverse(object=>{if(object!==incidentRing){object.updateMatrix();object.matrixAutoUpdate=false;}});
  underlay.updateMatrix();underlay.matrixAutoUpdate=false;
  const labels=LANDMARKS.map(mark=>{
    const el=document.createElement('div');el.className=`map-label ${mark.kind}`;
    const translated=landmarkText(language,mark);
    const name=document.createElement('span');name.textContent=translated.name;el.append(name);
    if(mark.sub){const sub=document.createElement('small');sub.textContent=translated.sub;el.append(sub);}
    labelsHost.append(el);const p=project(mark.lat,mark.lon);return{el,mark,point:new THREE.Vector3(p.x,mark.kind==='stadium'?7:mark.id==='hassan'?12:5,p.z)};
  });
  const resize=()=>{
    const w=host.clientWidth,h=host.clientHeight;
    if(!w||!h)return;
    viewWidth=w;viewHeight=h;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,w<600?1.25:1.65));
    markCameraDirty();
    const height=w<600?235:206;
    camera.left=-height*w/h/2;camera.right=height*w/h/2;camera.top=height/2;camera.bottom=-height/2;camera.updateProjectionMatrix();renderer.setSize(w,h,false);
  };
  const observer=new ResizeObserver(resize);observer.observe(host);resize();
  let previousPhase=null;
  const projectedLabel=new THREE.Vector3();
  return {
    type:'3d',
    setLanguage(value){language=value;labels.forEach(({el,mark})=>{const translated=landmarkText(language,mark);el.querySelector('span').textContent=translated.name;const sub=el.querySelector('small');if(sub)sub.textContent=translated.sub;});markCameraDirty();},
    resetCamera(){camera.position.copy(home);camera.zoom=1;controls.target.copy(target);camera.updateProjectionMatrix();controls.update();markCameraDirty();},
    update(dt){
      if(disposed)return;
      controls.update();
      if(previousPhase!==simulation.phase){
        previousPhase=simulation.phase;needsRender=true;
        incidentRing.visible=simulation.phase==='incident';routeMeshes.west.visible=simulation.phase==='resolved';
        routeMeshes.main.material.color.setHex(simulation.phase==='incident'?0xc86541:simulation.phase==='resolved'?0xb4a17a:0xd48b55);
      }
      const fleetChanged=fleet.update(dt,simulation);
      if(simulation.paused&&!fleetChanged&&!needsRender&&!labelsDirty)return;
      if(!simulation.paused)incidentRing.scale.setScalar(1+Math.sin(simulation.elapsed*2)*.13);
      if(labelsDirty){
        camera.updateMatrixWorld();
        for(const {el,point} of labels){
          const p=projectedLabel.copy(point).project(camera);
          el.style.left=`${(p.x*.5+.5)*viewWidth}px`;el.style.top=`${(-p.y*.5+.5)*viewHeight}px`;
          el.style.opacity=p.z>1||p.x<-1.1||p.x>1.1||p.y<-1.1||p.y>1.1?'0':'1';
        }
        labelsDirty=false;
      }
      renderer.render(scene,camera);needsRender=false;
    },
    getDiagnostics(){return {threeRevision:THREE.REVISION,vehicles:fleet.vehicleCount,vehicleBatchMeshes:fleet.meshes.length,renderCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures,staticShadowsCached:!renderer.shadowMap.autoUpdate};},
    reset(){fleet.reset();needsRender=true;},
    dispose(){
      if(disposed)return;disposed=true;observer.disconnect();controls.removeEventListener('change',markCameraDirty);controls.dispose();
      const geometries=new Set(),allMaterials=new Set(materials.values());
      scene.traverse(object=>{if(object.geometry)geometries.add(object.geometry);if(object.material)for(const m of Array.isArray(object.material)?object.material:[object.material])allMaterials.add(m);if(object.isInstancedMesh)object.dispose();});
      for(const geometry of geometries)geometry.dispose();for(const m of allMaterials)m.dispose();
      sun.shadow.dispose();renderer.dispose();renderer.domElement.remove();labelsHost.replaceChildren();
    },
  };

  function polygon(points,color,y){
    const shape=new THREE.Shape(points.map(([x,z])=>new THREE.Vector2(x,-z)));
    const mesh=new THREE.Mesh(new THREE.ShapeGeometry(shape),material(color));mesh.rotation.x=-Math.PI/2;mesh.position.y=y;mesh.receiveShadow=true;city.add(mesh);return mesh;
  }
  function ribbon(curve,width,y,color){
    const pts=curve.getPoints(110);const positions=[];const indices=[];
    pts.forEach((p,i)=>{const tangent=curve.getTangent(i/(pts.length-1));const nx=-tangent.z*width/2,nz=tangent.x*width/2;positions.push(p.x+nx,y,p.z+nz,p.x-nx,y,p.z-nz);if(i<pts.length-1){const n=i*2;indices.push(n,n+2,n+1,n+1,n+2,n+3);}});
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setIndex(indices);geometry.computeVertexNormals();
    const mesh=new THREE.Mesh(geometry,material(color,{side:THREE.DoubleSide}));mesh.receiveShadow=true;city.add(mesh);return mesh;
  }
  function box(w,h,d,color,x,y,z,parent=city){const mesh=new THREE.Mesh(unitBox,material(color));mesh.scale.set(w,h,d);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;}
  function makeStation(x,z,scale){const g=new THREE.Group();g.position.set(x,0,z);g.rotation.y=-.58;g.scale.setScalar(scale);city.add(g);box(9,.5,15,0xd2d8c4,0,.4,0,g);box(7.5,2.2,5,0xecebdc,0,1.7,0,g);box(10,.4,7,0x8d9b86,0,3,0,g);for(let j=-1;j<=1;j++)box(.2,2.5,5,0xb9c3af,j*3,1.7,0,g);}
  function makeHassan(){const g=new THREE.Group();g.position.set(55,0,-58);city.add(g);box(9,.4,9,0xdcc9a9,0,.3,0,g);box(2.4,11,2.4,0xcbb18c,0,5.8,0,g);box(2.9,.5,2.9,0xe4c9a4,0,11.4,0,g);for(let i=0;i<4;i++)box(.25,9,.25,0xd8c19e,i%2?1.24:-1.24,5.8,i>1?1.24:-1.24,g);}
  function makeStadium(){
    const group=new THREE.Group();group.position.set(-56,0,85);group.rotation.y=-.3;city.add(group);
    const shape=new THREE.Shape();shape.absellipse(0,0,14,10,0,Math.PI*2,false);
    const hole=new THREE.Path();hole.absellipse(0,0,9.5,5.8,0,Math.PI*2,true);shape.holes.push(hole);
    const stands=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:3,bevelEnabled:true,bevelSize:.5,bevelThickness:.4,bevelSegments:1,steps:1}),material(0xece8d2));stands.rotation.x=-Math.PI/2;stands.position.y=.5;stands.castShadow=true;group.add(stands);
    box(18,.2,10,0x7f9f68,0,.6,0,group);
    const fieldPoints=[[-8,-4],[8,-4],[8,4],[-8,4],[-8,-4]].map(([x,z])=>new THREE.Vector3(x,.73,z));group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(fieldPoints),new THREE.LineBasicMaterial({color:0xdde5ca})));
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,.74,-4),new THREE.Vector3(0,.74,4)]),new THREE.LineBasicMaterial({color:0xdde5ca})));
    const circle=new THREE.Mesh(new THREE.RingGeometry(1.6,1.7,40),new THREE.MeshBasicMaterial({color:0xdde5ca,side:THREE.DoubleSide}));circle.rotation.x=-Math.PI/2;circle.position.y=.74;group.add(circle);
    for(let i=0;i<8;i++){const a=i*Math.PI/4;const x=Math.cos(a)*15,z=Math.sin(a)*11;box(.2,5,.2,0x7c8a70,x,2.6,z,group);box(1,.4,.6,0xf1edcd,x,5.2,z,group);}
  }
}

function createFallback(host,labelsHost,simulation,language){
  // A functional schematic still supports the pitch on machines without WebGL.
  labelsHost.hidden=true;
  const paths=Object.entries(ROUTES).map(([id,points])=>`<polyline data-route="${id}" points="${points.map(([x,z])=>`${x},${z}`).join(' ')}" fill="none" stroke="${id==='rail'?'#6c77b7':id==='tram'?'#b16ab5':id==='west'?'#397857':'#f6f3df'}" stroke-width="${id==='rail'||id==='tram'?1.1:2.5}"/>`).join('');
  host.innerHTML=`<svg class="fallback-svg" viewBox="-108 -100 216 220" role="img" aria-label="Two dimensional Rabat simulation"><rect x="-108" y="-100" width="216" height="220" fill="#d7e1c8"/><path d="M-108-100H-24L-80 114H-108Z" fill="#a8cebf"/>${paths}<ellipse cx="-56" cy="85" rx="14" ry="10" fill="#ebe6cf" stroke="#7c946b" stroke-width="2"/><rect x="-64" y="81" width="16" height="8" fill="#7f9f68"/><g id="fallback-vehicles"></g><g font-family="Arial" font-size="5" fill="#18392d"><text x="-14" y="11">Rabat Agdal</text><text x="24" y="-42">Rabat Ville</text><text x="-79" y="104">Prince Moulay Abdellah</text></g></svg>`;
  const setLanguage=value=>{language=value;host.querySelector('svg').setAttribute('aria-label',text(language,'fallbackScene'));};
  setLanguage(language);
  const list=[];const container=host.querySelector('#fallback-vehicles');
  Object.entries({car:26,bus:5,tram:3,train:2}).forEach(([mode,count])=>{for(let i=0;i<count;i++){const el=document.createElementNS('http://www.w3.org/2000/svg','circle');el.setAttribute('r',mode==='car'?1:1.8);el.setAttribute('fill',`#${PALETTE[mode].toString(16).padStart(6,'0')}`);container.append(el);list.push({el,mode,t:i/count,route:mode==='train'?'rail':mode==='tram'?'tram':'main'});}});
  return{type:'2d',setLanguage,resetCamera(){},reset(){list.forEach((v,i)=>v.t=(i*.137)%1);},dispose(){},update(dt){const modes=simulation.modes;for(const v of list){if(!simulation.paused)v.t=(v.t+dt*simulation.speed*(simulation.phase==='incident'&&v.route==='main'?.008:.025))%1;const pts=ROUTES[simulation.phase==='resolved'&&v.mode==='bus'?'west':v.route];const index=v.t*(pts.length-1),i=Math.floor(index),a=pts[i],b=pts[Math.min(i+1,pts.length-1)],f=index-i;v.el.setAttribute('cx',a[0]+(b[0]-a[0])*f);v.el.setAttribute('cy',a[1]+(b[1]-a[1])*f);v.el.style.display=modes[v.mode]?'':'none';}host.querySelector('[data-route=west]').setAttribute('opacity',simulation.phase==='resolved'?'1':'.2');}};
}
