// Predefined illustrative states, not observed traffic or a predictive model.
export const PHASES = Object.freeze({
  normal: { number:1, title:'Before the rush', description:'Rabat is moving. Rail, tram and bus routes bring supporters toward the stadium.', minutes:18, flow:82, supporters:2400, tag:'BASELINE', change:'corridor estimate', label:'CITY PULSE', decision:'Every connection counts.', detail:'Watch vehicles move across the city. Then introduce a match-day surge to see what changes.', action:'Trigger match-day surge', caption:'The last kilometre can change the whole experience.', status:'YOUR CITY, IN SYNC' },
  incident: { number:2, title:'The city feels it.', description:'A match-day surge slows the stadium access corridor. The road bottleneck puts onward connections at risk.', minutes:34, flow:31, supporters:4800, tag:'BOTTLENECK', change:'+16 min vs baseline', label:'RECOMMENDATION', decision:'Open another way in.', detail:'Shift the demo shuttle to the west approach. Keep the rail-to-bus connection at Agdal, and spread arrivals across two corridors.', action:'Apply the alternative route', caption:'One bottleneck. Several modes. One coordinated response.', status:'DISRUPTION DETECTED' },
  resolved: { number:3, title:'A better way in.', description:'The demo shuttle takes the west approach. Supporters keep moving as pressure eases on the main corridor.', minutes:21, flow:68, supporters:4800, tag:'ALTERNATIVE', change:'13 min saved in scenario', label:'SCENARIO RESPONSE', decision:'Keep the match within reach.', detail:'The alternative reduces the scenario estimate from 34 to 21 minutes. This illustrates a decision, with no live dispatch or measured outcome.', action:'Replay the scenario', caption:'13 minutes recovered in this illustrative scenario.', status:'ALTERNATIVE ROUTE ACTIVE' },
});

export function createSimulation({ reducedMotion = false } = {}) {
  let phase = 'normal';
  let elapsed = 0;
  let paused = reducedMotion;
  let speed = 1;
  let story = null;
  const modes = { car:true, bus:true, tram:true, train:true };
  return {
    get phase(){return phase;}, get data(){return PHASES[phase];},
    get elapsed(){return elapsed;}, get paused(){return paused;}, get speed(){return speed;},
    get story(){return story;}, get modes(){return {...modes};},
    setPhase(value){ if(!PHASES[value]) throw new RangeError('Unknown scenario phase'); phase=value; },
    togglePause(){paused=!paused;return paused;},
    cycleSpeed(){speed=speed===1?2:speed===2?4:1;return speed;},
    toggleMode(mode){if(!(mode in modes)) throw new RangeError('Unknown mode');modes[mode]=!modes[mode];return modes[mode];},
    startStory(){phase='normal';elapsed=0;paused=false;speed=1;story=0;},
    stopStory(){story=null;},
    reset(){phase='normal';elapsed=0;paused=reducedMotion;speed=1;story=null;Object.keys(modes).forEach(key=>modes[key]=true);},
    tick(delta){
      if(!Number.isFinite(delta)||delta<0) throw new RangeError('Delta must be nonnegative');
      if(paused) return;
      elapsed+=delta*speed;
      if(story!==null){
        story=Math.min(60,story+delta);
        phase=story<18?'normal':story<39?'incident':'resolved';
        if(story>=60) story=null;
      }
    },
  };
}

export const LANDMARKS = [
  {id:'stadium',name:'Prince Moulay Abdellah',sub:'Stadium · scenario destination',lat:33.9595,lon:-6.889,kind:'stadium'},
  {id:'agdal',name:'Rabat Agdal',sub:'Rail → shuttle connection',lat:33.9905,lon:-6.856,kind:'station'},
  {id:'ville',name:'Rabat Ville',sub:'City rail station',lat:34.0139,lon:-6.8344,kind:'station'},
  {id:'hassan',name:'Hassan Tower',sub:'',lat:34.024,lon:-6.822,kind:'landmark'},
  {id:'tram',name:'Tram corridor',sub:'Illustrative connection',lat:34.002,lon:-6.859,kind:'tram'},
  {id:'atlantic',name:'ATLANTIC OCEAN',sub:'',lat:34.022,lon:-6.892,kind:'water'},
  {id:'river',name:'BOUREGREG',sub:'',lat:34.025,lon:-6.798,kind:'water'},
];

export function project(lat,lon){return {x:(lon+6.855)*1660,z:(33.998-lat)*2220};}

// Deliberately simplified paths. These are not operator route geometries.
export const ROUTES = {
  main: [[-3,17],[-9,27],[-17,35],[-24,44],[-26,58],[-39,73],[-56,85]],
  west: [[-3,17],[-19,19],[-36,23],[-48,34],[-59,49],[-66,66],[-56,85]],
  north: [[35,-36],[28,-23],[13,-10],[2,2],[-3,17]],
  rail: [[61,-71],[46,-54],[35,-36],[22,-21],[8,-3],[-3,17],[-8,37],[-14,58],[-21,83],[-29,101]],
  tram: [[72,-64],[53,-54],[35,-36],[14,-26],[-7,-18],[-20,-9],[-25,7],[-25,23],[-32,40]],
  avenue: [[-69,-27],[-49,-12],[-26,1],[-3,17],[19,33],[43,49],[70,64]],
  coast: [[-24,-79],[-33,-55],[-42,-31],[-51,-3],[-60,25],[-68,58]],
  cross: [[-74,1],[-52,5],[-25,7],[0,7],[25,8],[48,9],[79,13]],
  east: [[35,-36],[41,-15],[48,9],[39,33],[31,54],[15,77],[-5,97]],
};
