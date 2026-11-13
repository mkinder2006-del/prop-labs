/* Decorative flight layer: no pointer capture, audio, or data-feed changes. */
(()=>{
  const canvas=document.getElementById('spaceFlights');let artwork=[];
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  if(!canvas)return;
  let width=0,height=0,ships=[],lasers=[],sparks=[],last=0,nextSolo=0,nextBattle=0,frame=0,activeTime=0;
  const random=(a,b)=>a+Math.random()*(b-a);
  function resize(){width=innerWidth;height=innerHeight;canvas.setAttribute('viewBox',`0 0 ${width} ${height}`);}
  function spawn(battle){
    if(ships.length>4)return;
    const direction=Math.random()<.5?1:-1,speed=random(70,110),y=random(height*.13,height*.85),start=direction>0?-210:width+210;
    const leader={x:start,y,baseY:y,vx:speed*direction,age:0,phase:random(0,6),scale:random(.65,1),enemy:false,battle,shotAt:random(.7,1.3)};
    ships.push(leader);
    if(battle){
      ships.push({x:start-direction*135,y:y+35,baseY:y+35,vx:speed*direction,age:0,phase:leader.phase+.2,scale:leader.scale*.9,enemy:true,battle:true,target:leader,shotAt:.7});
      if(width>700&&Math.random()<.5)ships.push({x:start-direction*215,y:y-32,baseY:y-32,vx:speed*direction,age:0,phase:leader.phase+.5,scale:leader.scale*.8,enemy:true,battle:true,target:leader,shotAt:1.2});
    }
  }
  function drawShip(s){
    artwork.push(`<g class="flying-ship" transform="translate(${s.x} ${s.y}) rotate(${s.vx<0?180:0}) scale(${s.scale})"><path d="M-14 -3 L-${random(24,34)} 0 L-14 3Z" fill="${s.enemy?'#ff623c':'#58dfff'}"/><path d="M23 0 L0 -5 L-12 -15 L-9 -4 L-17 -3 L-17 3 L-9 4 L-12 15 L0 5Z" fill="${s.enemy?'#697584':'#bccbd6'}" stroke="#e6f3ff" stroke-width=".7"/><ellipse cx="6" cy="0" rx="5" ry="2" fill="${s.enemy?'#ff3347':'#83efff'}"/></g>`);
  }
  function burst(x,y){for(let i=0;i<9;i++){const angle=random(0,Math.PI*2),speed=random(18,65);sparks.push({x,y,vx:Math.cos(angle)*speed,vy:Math.sin(angle)*speed,life:random(.2,.5)});}}
  function tick(stamp){
    frame=0;if(document.hidden||motion.matches){last=0;return;}
    if(last&&stamp-last<1000/30){frame=requestAnimationFrame(tick);return;}
    const dt=last?Math.min((stamp-last)/1000,.06):0;last=stamp;activeTime+=dt;
    artwork=[];
    if(activeTime>=nextSolo){spawn(false);nextSolo=activeTime+random(9,15);}
    if(activeTime>=nextBattle){spawn(true);nextBattle=activeTime+random(23,32);}
    for(const s of ships){
      s.age+=dt;s.x+=s.vx*dt;s.y=s.baseY+Math.sin(s.age*(s.battle?1.9:.7)+s.phase)*(s.battle?17:7);
      if(s.enemy&&s.target&&s.age>=s.shotAt&&s.x>0&&s.x<width&&s.target.x>0&&s.target.x<width){
        const dx=s.target.x-s.x,dy=s.target.y-s.y,dist=Math.hypot(dx,dy)||1;
        lasers.push({x:s.x,y:s.y,vx:dx/dist*560,vy:dy/dist*560,life:.9,target:s.target});s.shotAt=s.age+random(.85,1.6);
      }
      drawShip(s);
    }
    ships=ships.filter(s=>s.vx>0?s.x<width+260:s.x>-260);
    for(const l of lasers){
      l.x+=l.vx*dt;l.y+=l.vy*dt;l.life-=dt;
      artwork.push(`<line class="red-laser" x1="${l.x}" y1="${l.y}" x2="${l.x-l.vx*.035}" y2="${l.y-l.vy*.035}" stroke="#ff3344" stroke-width="2" stroke-linecap="round"/>`);
      if(Math.hypot(l.x-l.target.x,l.y-l.target.y)<15){burst(l.x,l.y);l.life=0;}
    }
    lasers=lasers.filter(l=>l.life>0);
    for(const p of sparks){p.x+=p.vx*dt;p.y+=p.vy*dt;p.life-=dt;artwork.push(`<circle cx="${p.x}" cy="${p.y}" r="1.4" fill="#ff805c" opacity="${Math.max(0,p.life*1.7)}"/>`);}
    sparks=sparks.filter(p=>p.life>0);canvas.innerHTML=artwork.join('');
    frame=requestAnimationFrame(tick);
  }
  function resume(){
    if(frame)cancelAnimationFrame(frame);frame=0;last=0;
    if(motion.matches){ships=[];lasers=[];sparks=[];artwork=[];canvas.innerHTML='';return;}
    if(!document.hidden)frame=requestAnimationFrame(tick);
  }
  resize();nextSolo=12;nextBattle=26;
  if(!motion.matches){
    spawn(false);ships[0].x=width*.22;
    const first=ships.length;spawn(true);
    const lead=ships[first];lead.x=width*.7;
    for(let i=first+1;i<ships.length;i++)ships[i].x=lead.x-Math.sign(lead.vx)*(135+(i-first-1)*80);
    for(const ship of ships)drawShip(ship);canvas.innerHTML=artwork.join('');
  }
  window.addEventListener('resize',resize,{passive:true});document.addEventListener('visibilitychange',resume);motion.addEventListener('change',resume);resume();
})();
