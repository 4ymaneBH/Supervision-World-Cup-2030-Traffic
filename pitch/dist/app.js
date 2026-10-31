import { createSimulation } from './simulation.js';

const $=id=>document.getElementById(id);
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const simulation=createSimulation({reducedMotion});
let city=null,lastPhase=null,lastSecond=-1,lastPaused=null,lastSpeed=null,wasStory=false;
let previousTime=performance.now();
let hasInteracted=false;

function announce(text){$('announcer').textContent=text;}
function updateUI(){
  if(lastPhase!==simulation.phase){
    const data=simulation.data;lastPhase=simulation.phase;document.body.dataset.phase=simulation.phase;
    $('chapter').textContent=`0${data.number} / 03`;
    $('phase-title').textContent=data.title;$('phase-description').textContent=data.description;
    $('journey-minutes').textContent=data.minutes;$('journey-tag').textContent=data.tag;$('journey-change').textContent=data.change;
    $('flow-value').replaceChildren(document.createTextNode(data.flow),Object.assign(document.createElement('span'),{textContent:'%'}));
    $('supporters-value').textContent=data.supporters.toLocaleString('en');
    $('decision-label').textContent=data.label;$('decision-title').textContent=data.decision;$('decision-description').textContent=data.detail;
    $('scenario-action').replaceChildren(document.createTextNode(data.action),Object.assign(document.createElement('span'),{textContent:'↗'}));
    $('story-caption').textContent=data.caption;$('story-status').textContent=data.status;
    document.querySelectorAll('[data-phase]').forEach(button=>{const active=button.dataset.phase===simulation.phase;button.classList.toggle('selected',active);button.setAttribute('aria-pressed',String(active));});
    const callout=$('map-callout');callout.hidden=simulation.phase==='normal';callout.classList.toggle('resolved',simulation.phase==='resolved');
    $('callout-title').textContent=simulation.phase==='resolved'?'Alternative corridor active':'Match-day bottleneck';
    $('callout-description').textContent=simulation.phase==='resolved'?'West approach · scenario response':'Stadium access corridor · simulated';
    callout.querySelector('.callout-icon').textContent=simulation.phase==='resolved'?'↗':'!';
    if(hasInteracted)announce(`${data.title} Stadium journey ${data.minutes} minutes. ${data.detail}`);
  }
  const second=Math.floor(simulation.elapsed);
  if(second!==lastSecond){lastSecond=second;const total=17*3600+30*60+second*3;$('simulation-time').textContent=[Math.floor(total/3600)%24,Math.floor(total/60)%60,total%60].map(v=>String(v).padStart(2,'0')).join(':');}
  if(lastPaused!==simulation.paused){lastPaused=simulation.paused;$('pause-icon').textContent=simulation.paused?'▶':'Ⅱ';$('pause').setAttribute('aria-label',simulation.paused?'Resume simulation':'Pause simulation');$('pause').setAttribute('aria-pressed',String(simulation.paused));}
  if(lastSpeed!==simulation.speed){lastSpeed=simulation.speed;$('speed').textContent=`${simulation.speed}×`;$('speed').setAttribute('aria-label',`Simulation speed, currently ${simulation.speed} times`);}
  const playing=simulation.story!==null;
  if(playing){$('story-progress').style.width=`${simulation.story/60*100}%`;$('story-timing').textContent=`${Math.floor(simulation.story).toString().padStart(2,'0')} / 60 SEC`;}
  if(playing!==wasStory){
    $('play-story').classList.toggle('playing',playing);$('play-story').querySelector('span').textContent=playing?'Stop the story':'Play the 60-second story';
    if(!playing&&wasStory){$('story-progress').style.width=simulation.phase==='resolved'?'100%':'0%';$('story-timing').textContent=simulation.phase==='resolved'?'SCENARIO COMPLETE ✓':'EXPLORE THE DEMO ↗';}
    wasStory=playing;
  }
}
function setPhase(phase){hasInteracted=true;simulation.stopStory();simulation.setPhase(phase);updateUI();}
function reset(){hasInteracted=true;simulation.reset();city?.reset();city?.resetCamera();lastPhase=null;$('story-progress').style.width='0%';$('story-timing').textContent='EXPLORE THE DEMO ↗';document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed','true'));updateUI();announce('Scenario reset. Before the rush.');}

document.querySelectorAll('[data-phase]').forEach(button=>button.addEventListener('click',()=>setPhase(button.dataset.phase)));
$('scenario-action').addEventListener('click',()=>setPhase(simulation.phase==='normal'?'incident':simulation.phase==='incident'?'resolved':'normal'));
$('play-story').addEventListener('click',()=>{hasInteracted=true;if(simulation.story!==null){simulation.stopStory();}else{simulation.startStory();city?.reset();city?.resetCamera();announce('The 60-second story has started.');}updateUI();});
$('pause').addEventListener('click',()=>{simulation.togglePause();updateUI();});
$('speed').addEventListener('click',()=>{simulation.cycleSpeed();updateUI();});
$('reset').addEventListener('click',reset);
$('reset-camera').addEventListener('click',()=>city?.resetCamera());
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{const visible=simulation.toggleMode(button.dataset.mode);button.setAttribute('aria-pressed',String(visible));}));
document.querySelectorAll('[data-scroll]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.scroll).scrollIntoView({behavior:reducedMotion?'instant':'smooth',block:'start'})));

function toggleDisclosure(buttonId,panelId){const button=$(buttonId),panel=$(panelId);panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)panel.scrollIntoView({behavior:reducedMotion?'instant':'smooth',block:'nearest'});}
$('architecture-button').addEventListener('click',()=>toggleDisclosure('architecture-button','architecture'));
$('data-button').addEventListener('click',()=>toggleDisclosure('data-button','data-note'));
async function toggleFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();else announce('Use your browser fullscreen shortcut for presentation mode.');}catch{announce('Fullscreen is unavailable here. The demo works in this window.');}}
$('fullscreen').addEventListener('click',toggleFullscreen);
document.addEventListener('fullscreenchange',()=>{$('fullscreen').setAttribute('aria-label',document.fullscreenElement?'Exit fullscreen':'Toggle fullscreen');});
document.addEventListener('keydown',event=>{
  if(event.target.closest('button,a,input,textarea,select')||event.ctrlKey||event.metaKey||event.altKey)return;
  if(event.code==='Space'){event.preventDefault();simulation.togglePause();updateUI();}
  if(event.key.toLowerCase()==='r')reset();
  if(event.key.toLowerCase()==='f')toggleFullscreen();
});

updateUI();
try{
  const {createCity}=await import('./scene.js');
  city=createCity($('scene'),$('map-labels'),simulation);
  $('scene-loading').hidden=true;
  if(city.type==='2d'){$('map-hint').textContent='2D view · WebGL unavailable';$('reset-camera').hidden=true;}
}catch(error){
  $('scene-loading').replaceChildren(document.createTextNode('The city view could not load. Scenario controls are still available.'));
  console.error('City view unavailable:',error);
}

function frame(now){
  const dt=Math.min((now-previousTime)/1000,.1);previousTime=now;
  if(!document.hidden){simulation.tick(dt);city?.update(dt);updateUI();}
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
window.addEventListener('pagehide',()=>city?.dispose(),{once:true});
