/* Decorative flight layer: no pointer capture, audio, or data-feed changes. */
(()=>{
  const canvas=document.getElementById('spaceFlights'),ctx=canvas.getContext('2d');
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  if(!ctx)return;
  let width=0,height=0,ships=[],lasers=[],sparks=[],last=0,nextSolo=0,nextBattle=0,frame=0,activeTime=0;
  const random=(a,b)=>a+Math.random()*(b-a);
  function resize(){width=innerWidth;height=innerHeight;const dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);}
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
    ctx.save();ctx.translate(s.x,s.y);ctx.rotate(s.vx<0?Math.PI:0);ctx.scale(s.scale,s.scale);
    // Engine plume and swept wings, with a distinct red cockpit on pursuers.
    ctx.globalAlpha=.75;ctx.fillStyle=s.enemy?'#ff623c':'#58dfff';ctx.shadowColor=ctx.fillStyle;ctx.shadowBlur=9;
    ctx.beginPath();ctx.moveTo(-14,-3);ctx.lineTo(-random(24,34),0);ctx.lineTo(-14,3);ctx.fill();
    ctx.shadowBlur=0;ctx.fillStyle=s.enemy?'#697584':'#bccbd6';ctx.strokeStyle='#e6f3ff';ctx.lineWidth=.65;
    ctx.beginPath();ctx.moveTo(23,0);ctx.lineTo(0,-5);ctx.lineTo(-12,-15);ctx.lineTo(-9,-4);ctx.lineTo(-17,-3);ctx.lineTo(-17,3);ctx.lineTo(-9,4);ctx.lineTo(-12,15);ctx.lineTo(0,5);ctx.closePath();ctx.fill();ctx.stroke();
    ctx.fillStyle=s.enemy?'#ff3347':'#83efff';ctx.shadowColor=ctx.fillStyle;ctx.shadowBlur=7;ctx.beginPath();ctx.ellipse(6,0,5,2,0,0,Math.PI*2);ctx.fill();ctx.restore();
  }
  function burst(x,y){for(let i=0;i<9;i++){const angle=random(0,Math.PI*2),speed=random(18,65);sparks.push({x,y,vx:Math.cos(angle)*speed,vy:Math.sin(angle)*speed,life:random(.2,.5)});}}
  function tick(stamp){
    frame=0;if(document.hidden||motion.matches){last=0;return;}
    if(last&&stamp-last<1000/30){frame=requestAnimationFrame(tick);return;}
    const dt=last?Math.min((stamp-last)/1000,.06):0;last=stamp;activeTime+=dt;
    ctx.clearRect(0,0,width,height);
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
      ctx.save();ctx.globalAlpha=.85;ctx.strokeStyle='#ff3344';ctx.shadowColor='#ff142e';ctx.shadowBlur=8;ctx.lineWidth=1.7;
      ctx.beginPath();ctx.moveTo(l.x,l.y);ctx.lineTo(l.x-l.vx*.035,l.y-l.vy*.035);ctx.stroke();ctx.restore();
      if(Math.hypot(l.x-l.target.x,l.y-l.target.y)<15){burst(l.x,l.y);l.life=0;}
    }
    lasers=lasers.filter(l=>l.life>0);
    for(const p of sparks){p.x+=p.vx*dt;p.y+=p.vy*dt;p.life-=dt;ctx.globalAlpha=Math.max(0,p.life*1.7);ctx.fillStyle='#ff805c';ctx.fillRect(p.x,p.y,1.8,1.8);}
    ctx.globalAlpha=1;sparks=sparks.filter(p=>p.life>0);
    frame=requestAnimationFrame(tick);
  }
  function resume(){
    if(frame)cancelAnimationFrame(frame);frame=0;last=0;
    if(motion.matches){ships=[];lasers=[];sparks=[];ctx.clearRect(0,0,width,height);return;}
    if(!document.hidden)frame=requestAnimationFrame(tick);
  }
  resize();nextSolo=12;nextBattle=26;
  if(!motion.matches){
    spawn(false);ships[0].x=width*.22;
    const first=ships.length;spawn(true);
    const lead=ships[first];lead.x=width*.7;
    for(let i=first+1;i<ships.length;i++)ships[i].x=lead.x-Math.sign(lead.vx)*(135+(i-first-1)*80);
    for(const ship of ships)drawShip(ship);
  }
  window.addEventListener('resize',resize,{passive:true});document.addEventListener('visibilitychange',resume);motion.addEventListener('change',resume);resume();
})();
