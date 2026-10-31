import { createSimulation } from './simulation.js';
import { applyTranslations, selectLanguage, phaseText, text, TEXT } from './i18n.js';

const $=id=>document.getElementById(id);
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const simulation=createSimulation({reducedMotion});
let savedLanguage=null;
try{savedLanguage=window.localStorage?.getItem('rabat-flow-language');}catch{/* Storage is optional. */}
let language=selectLanguage(window.location?.search,savedLanguage);
const t=(key,values)=>text(language,key,values);
let city=null,lastPhase=null,lastSecond=-1,lastPaused=null,lastSpeed=null;
let previousTime=performance.now();
let uiElapsed=0;
let hasInteracted=false;
let cityFailed=false;

function announce(message){$('announcer').textContent=message;}
function updateUI(){
  const phaseKey=`${language}:${simulation.phase}`;
  if(lastPhase!==phaseKey){
    const data=phaseText(language,simulation.phase);lastPhase=phaseKey;document.body.dataset.phase=simulation.phase;
    $('chapter').textContent=`0${data.number} / 03`;
    $('phase-title').textContent=data.title;$('phase-description').textContent=data.description;
    $('journey-minutes').textContent=data.minutes;$('journey-tag').textContent=data.tag;$('journey-change').textContent=data.change;
    $('flow-value').replaceChildren(document.createTextNode(data.flow),Object.assign(document.createElement('span'),{textContent:'%'}));
    $('supporters-value').textContent=data.supporters.toLocaleString(language);
    $('decision-label').textContent=data.label;$('decision-title').textContent=data.decision;$('decision-description').textContent=data.detail;
    $('scenario-action').replaceChildren(document.createTextNode(data.action),Object.assign(document.createElement('span'),{textContent:'↗'}));
    $('story-caption').textContent=data.caption;$('story-status').textContent=data.status;
    document.querySelectorAll('.scenario-tabs [data-phase]').forEach(button=>{const active=button.dataset.phase===simulation.phase;button.classList.toggle('selected',active);button.setAttribute('aria-pressed',String(active));});
    const callout=$('map-callout');const resolved=simulation.phase==='resolved';callout.hidden=simulation.phase==='normal';callout.classList.toggle('resolved',resolved);
    $('callout-title').textContent=t(resolved?'resolvedTitle':'incidentTitle');$('callout-description').textContent=t(resolved?'resolvedDetail':'incidentDetail');
    callout.querySelector('.callout-icon').textContent=resolved?'↗':'!';
    if(hasInteracted)announce(t('phaseAnnouncement',{title:data.title,minutes:data.minutes,detail:data.detail}));
  }
  const second=Math.floor(simulation.elapsed);
  if(second!==lastSecond){lastSecond=second;const total=17*3600+30*60+second*3;$('simulation-time').textContent=[Math.floor(total/3600)%24,Math.floor(total/60)%60,total%60].map(v=>String(v).padStart(2,'0')).join(':');}
  const pauseKey=`${language}:${simulation.paused}`;
  if(lastPaused!==pauseKey){lastPaused=pauseKey;$('pause-icon').textContent=simulation.paused?'▶':'Ⅱ';$('pause').setAttribute('aria-label',t(simulation.paused?'resume':'pause'));$('pause').setAttribute('aria-pressed',String(simulation.paused));}
  const speedKey=`${language}:${simulation.speed}`;
  if(lastSpeed!==speedKey){lastSpeed=speedKey;$('speed').textContent=`${simulation.speed}×`;$('speed').setAttribute('aria-label',t('speed',{speed:simulation.speed}));}
  const playing=simulation.story!==null;
  $('play-story').classList.toggle('playing',playing);
  const storyLabel=t(playing?'stopStory':'playStory');
  if($('play-story').querySelector('span').textContent!==storyLabel)$('play-story').querySelector('span').textContent=storyLabel;
  $('story-progress').style.width=playing?`${simulation.story/60*100}%`:simulation.phase==='resolved'?'100%':simulation.phase==='incident'?'35%':'0%';
  $('story-timing').textContent=playing?`${Math.floor(simulation.story).toString().padStart(2,'0')} / 60 SEC`:t(simulation.phase==='resolved'?'complete':'explore');
}
function setLanguage(value){
  if(!TEXT[value])return;
  language=value;applyTranslations(document,language);
  document.querySelectorAll('[data-language]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.language===language)));
  city?.setLanguage(language);
  $('map-hint').textContent=t(city?.type==='2d'?'fallbackHint':'mapHint');
  $('fullscreen').setAttribute('aria-label',t(document.fullscreenElement?'exitFullscreen':'fullscreen'));
  if(cityFailed)$('scene-loading').textContent=t('loadError');
  updateUI();
  try{window.localStorage?.setItem('rabat-flow-language',language);}catch{/* Switching still works without storage. */}
  try{const url=new URL(window.location.href);url.searchParams.set('lang',language);window.history.replaceState(null,'',url);}catch{/* Embedded previews may restrict history. */}
}
function setPhase(phase){hasInteracted=true;simulation.stopStory();simulation.setPhase(phase);updateUI();}
function reset(){hasInteracted=true;simulation.reset();city?.reset();city?.resetCamera();lastPhase=null;document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed','true'));updateUI();announce(t('scenarioReset'));}

document.querySelectorAll('[data-language]').forEach(button=>button.addEventListener('click',()=>setLanguage(button.dataset.language)));
document.querySelectorAll('.scenario-tabs [data-phase]').forEach(button=>button.addEventListener('click',()=>setPhase(button.dataset.phase)));
$('scenario-action').addEventListener('click',()=>simulation.phase==='resolved'?reset():setPhase(simulation.phase==='normal'?'incident':'resolved'));
$('play-story').addEventListener('click',()=>{hasInteracted=true;if(simulation.story!==null){simulation.stopStory();}else{simulation.startStory();city?.reset();city?.resetCamera();announce(t('storyStarted'));}updateUI();});
$('pause').addEventListener('click',()=>{simulation.togglePause();updateUI();});
$('speed').addEventListener('click',()=>{simulation.cycleSpeed();updateUI();});
$('reset').addEventListener('click',reset);
$('reset-camera').addEventListener('click',()=>city?.resetCamera());
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{const visible=simulation.toggleMode(button.dataset.mode);button.setAttribute('aria-pressed',String(visible));}));
document.querySelectorAll('[data-scroll]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.scroll).scrollIntoView({behavior:reducedMotion?'instant':'smooth',block:'start'})));

function toggleDisclosure(buttonId,panelId){const button=$(buttonId),panel=$(panelId);panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)panel.scrollIntoView({behavior:reducedMotion?'instant':'smooth',block:'nearest'});}
$('architecture-button').addEventListener('click',()=>toggleDisclosure('architecture-button','architecture'));
$('data-button').addEventListener('click',()=>toggleDisclosure('data-button','data-note'));
$('presenter-button').addEventListener('click',()=>toggleDisclosure('presenter-button','presenter-notes'));
async function toggleFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();else announce(t('fullscreenShortcut'));}catch{announce(t('fullscreenUnavailable'));}}
$('fullscreen').addEventListener('click',toggleFullscreen);
document.addEventListener('fullscreenchange',()=>{$('fullscreen').setAttribute('aria-label',t(document.fullscreenElement?'exitFullscreen':'fullscreen'));});
document.addEventListener('keydown',event=>{
  if(event.target.closest('button,a,input,textarea,select')||event.ctrlKey||event.metaKey||event.altKey)return;
  if(event.code==='Space'){event.preventDefault();simulation.togglePause();updateUI();}
  if(event.key.toLowerCase()==='r')reset();
  if(event.key.toLowerCase()==='f')toggleFullscreen();
});

setLanguage(language);
try{
  const {createCity}=await import('./scene.js');
  city=createCity($('scene'),$('map-labels'),simulation,language);
  if(new URLSearchParams(window.location?.search).has('perf'))window.rabatFlowPerformance=()=>city.getDiagnostics?.()??{renderMode:'2d'};
  $('scene-loading').hidden=true;
  if(city.type==='2d'){$('map-hint').textContent=t('fallbackHint');$('reset-camera').hidden=true;}
}catch(error){cityFailed=true;$('scene-loading').replaceChildren(document.createTextNode(t('loadError')));console.error('City view unavailable:',error);}
function frame(now){
  const dt=Math.min((now-previousTime)/1000,.1);previousTime=now;
  if(!document.hidden){
    simulation.tick(dt);city?.update(dt);uiElapsed+=dt;
    if(uiElapsed>=.1||lastPhase!==`${language}:${simulation.phase}`){updateUI();uiElapsed=0;}
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
window.addEventListener('pagehide',event=>{if(!event.persisted)city?.dispose();});
