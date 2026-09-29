class LevelOne{
 constructor(canvas){this.canvas=canvas;this.ctx=canvas.getContext("2d");this.running=false;this.paused=false;this.keys={};this.mouse=false;this.time=0;this.camera=0;this.reset();this.bind();this.resize();addEventListener("resize",()=>this.resize())}
 reset(){this.p={...LEVEL_01.start,w:30,h:46,vx:0,vy:0,hp:100,cash:0,face:1,onGround:false,weapon:"pistol",cool:0,inv:900};this.enemies=LEVEL_01.enemies.map(e=>({x:e.x,y:e.y,w:e.type==="guardian"?50:32,h:e.type==="guardian"?60:42,type:e.type,hp:e.type==="guardian"?180:e.type==="ranged"?55:45,max:e.type==="guardian"?180:e.type==="ranged"?55:45,vx:0,vy:0,cool:Math.random()*700,dead:false,hitFlash:0}));this.platforms=LEVEL_01.platforms.map(x=>({...x}));this.pickups=LEVEL_01.pickups.map(x=>({...x,w:x.type==="weapon"?28:20,h:x.type==="weapon"?28:20}));this.bullets=[];this.enemyBullets=[];this.complete=false}
 bind(){addEventListener("keydown",e=>{this.keys[e.code]=true;if(["ArrowLeft","ArrowRight","ArrowUp","Space"].includes(e.code))e.preventDefault();if(e.code==="KeyE")this.use()});addEventListener("keyup",e=>this.keys[e.code]=false);addEventListener("mousedown",e=>{if(e.button===0)this.mouse=true});addEventListener("mouseup",e=>{if(e.button===0)this.mouse=false})}
 resize(){this.canvas.width=innerWidth*devicePixelRatio;this.canvas.height=innerHeight*devicePixelRatio;this.canvas.style.width=innerWidth+"px";this.canvas.style.height=innerHeight+"px";this.ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
 start(){this.reset();this.running=true;this.paused=false;this.canvas.classList.remove("hidden");document.getElementById("hud").classList.remove("hidden");document.getElementById("touch").classList.remove("hidden");this.last=performance.now();requestAnimationFrame(t=>this.loop(t))}
 stop(){this.running=false}
 rect(a){return{x:a.x,y:a.y,w:a.w,h:a.h}}
 hit(a,b){return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y}
 sweptHit(b,e){
   // Test the bullet's movement segment against the enemy rectangle.
   // Also keep a small radius so very fast bullets cannot visually skip targets.
   const r=3;
   const minX=e.x-r,maxX=e.x+e.w+r,minY=e.y-r,maxY=e.y+e.h+r;
   const x0=b.px, y0=b.py, x1=b.x, y1=b.y;
   if(x0>=minX&&x0<=maxX&&y0>=minY&&y0<=maxY)return true;
   if(x1>=minX&&x1<=maxX&&y1>=minY&&y1<=maxY)return true;
   const dx=x1-x0,dy=y1-y0;
   let t0=0,t1=1;
   for(const [p,q] of [[-dx,x0-minX],[dx,maxX-x0],[-dy,y0-minY],[dy,maxY-y0]]){
     if(p===0){if(q<0)return false;continue}
     const t=q/p;
     if(p<0){if(t>t1)return false;if(t>t0)t0=t}
     else{if(t<t0)return false;if(t<t1)t1=t}
   }
   return true;
 }
 fire(){let w=WEAPONS[this.p.weapon];if(this.p.cool>0)return;this.p.cool=w.rate;let angle=(Math.random()-.5)*w.spread;this.bullets.push({x:this.p.x+this.p.w/2,y:this.p.y+18,px:this.p.x+this.p.w/2,py:this.p.y+18,vx:Math.cos(angle)*w.speed*this.p.face,vy:Math.sin(angle)*w.speed,dmg:w.damage,life:1200})}
 use(){if(!this.running)return;let near=Math.abs(this.p.x-(LEVEL_01.tower.x+50))<100&&Math.abs(this.p.y-LEVEL_01.tower.y)<160;if(near&&this.enemies.every(e=>e.dead)){this.complete=true;this.running=false;document.getElementById("hud").classList.add("hidden");document.getElementById("touch").classList.add("hidden");document.getElementById("game").classList.add("hidden");document.getElementById("complete").classList.remove("hidden")}}
 update(dt){let k=this.keys,p=this.p,move=(k.KeyD||k.ArrowRight?1:0)-(k.KeyA||k.ArrowLeft?1:0);p.vx=move*285;if(move)p.face=move;if((k.Space||k.KeyW||k.ArrowUp)&&p.onGround){p.vy=-610;p.onGround=false}p.vy+=1600*dt/1000;p.x+=p.vx*dt/1000;p.y+=p.vy*dt/1000;p.x=Math.max(0,Math.min(LEVEL_01.width-p.w,p.x));p.onGround=false;
  for(const q of this.platforms){if(p.x+p.w>q.x&&p.x<q.x+q.w&&p.y+p.h>=q.y&&p.y+p.h<=q.y+32&&p.vy>=0){p.y=q.y-p.h;p.vy=0;p.onGround=true}}
  p.cool-=dt;p.inv-=dt;if(this.mouse||k.KeyJ||k.KeyK)this.fire();
  for(const b of this.bullets){b.px=b.x;b.py=b.y;b.x+=b.vx*dt/1000;b.y+=b.vy*dt/1000;b.life-=dt;for(const e of this.enemies)if(!e.dead&&this.sweptHit(b,e)){e.hp-=b.dmg;e.hitFlash=110;b.life=0;if(e.hp<=0){e.dead=true;p.cash+=e.type==="guardian"?100:15}break}}
  this.bullets=this.bullets.filter(b=>b.life>0&&b.x>-100&&b.x<LEVEL_01.width+100&&b.y>-100&&b.y<LEVEL_01.height+100);
  for(const e of this.enemies){if(e.dead)continue;e.hitFlash=Math.max(0,e.hitFlash-dt);let dx=p.x-e.x,dy=p.y-e.y,d=Math.hypot(dx,dy)||1;e.cool-=dt;if(e.type==="ranged"||e.type==="guardian"){e.vx=Math.abs(dx)<700?Math.sign(dx)*55:0;if(d<760&&e.cool<=0){this.enemyFire(e);e.cool=e.type==="guardian"?800:1250}}else e.vx=Math.sign(dx)*70;
    e.vy+=1600*dt/1000;e.x+=e.vx*dt/1000;e.y+=e.vy*dt/1000;for(const q of this.platforms)if(e.x+e.w>q.x&&e.x<q.x+q.w&&e.y+e.h>=q.y&&e.y+e.h<=q.y+32&&e.vy>=0){e.y=q.y-e.h;e.vy=0}
    if(this.hit(e,p)&&p.inv<=0){p.hp-=e.type==="guardian"?16:9;p.inv=700}
  }
  for(const b of this.enemyBullets){b.x+=b.vx*dt/1000;b.y+=b.vy*dt/1000;b.life-=dt;if(this.hit(b,p)&&p.inv<=0){p.hp-=b.dmg;b.life=0;p.inv=700}}
  this.enemyBullets=this.enemyBullets.filter(b=>b.life>0);
  this.pickups=this.pickups.filter(q=>{if(this.hit(q,p)){if(q.type==="cash")p.cash+=q.value;if(q.type==="med")p.hp=Math.min(100,p.hp+q.value);if(q.type==="weapon"){p.weapon=q.id}return false}return true});
  if(p.y>LEVEL_01.height+120)p.hp=0;if(p.hp<=0){this.running=false;document.getElementById("hud").classList.add("hidden");document.getElementById("touch").classList.add("hidden");document.getElementById("game").classList.add("hidden");document.getElementById("dead").classList.remove("hidden")}
  this.camera=Math.max(0,Math.min(LEVEL_01.width-innerWidth,p.x-innerWidth*.42));this.hud()
 }
 enemyFire(e){let dx=this.p.x-(e.x+e.w/2),dy=this.p.y+18-(e.y+e.h/2),d=Math.hypot(dx,dy)||1;this.enemyBullets.push({x:e.x+e.w/2,y:e.y+20,vx:dx/d*430,vy:dy/d*430,dmg:e.type==="guardian"?13:8,life:2200})}
 hud(){document.getElementById("hp").textContent=Math.max(0,Math.ceil(this.p.hp));document.getElementById("cash").textContent=this.p.cash;document.getElementById("weapon").textContent=WEAPONS[this.p.weapon].name.toUpperCase();document.getElementById("hpFill").style.width=Math.max(0,this.p.hp)+"%";let left=this.enemies.filter(e=>!e.dead).length;document.getElementById("mission").textContent=left?`HOSTILES REMAINING: ${left}  •  REACH THE SIGNAL TOWER`:"ALL HOSTILES CLEARED  •  PRESS E AT THE SIGNAL TOWER";let near=Math.abs(this.p.x-(LEVEL_01.tower.x+50))<110&&Math.abs(this.p.y-LEVEL_01.tower.y)<170;document.getElementById("prompt").textContent=near&&left===0?"PRESS E — RECOVER TRANSMISSION":""}
 loop(t){
   if(!this.running)return;
   try{
     let dt=Math.min(34,t-this.last);this.last=t;
     this.update(dt);this.draw();
     requestAnimationFrame(tt=>this.loop(tt));
   }catch(err){
     this.running=false;
     console.error(err);
     const box=document.getElementById("prompt");
     if(box){
       box.textContent="GAME ERROR — RELOAD LEVEL";
       box.style.color="#ff456c";
     }
   }
 }
 draw(){let c=this.ctx,w=innerWidth,h=innerHeight,cam=this.camera;let g=c.createLinearGradient(0,0,0,h);g.addColorStop(0,"#081727");g.addColorStop(1,"#020307");c.fillStyle=g;c.fillRect(0,0,w,h);c.save();c.translate(-cam,0);
   c.fillStyle="#11304a";c.globalAlpha=.45;for(let i=0;i<40;i++)c.fillRect(i*150,180-(i%5)*18,80+(i%4)*20,470);c.globalAlpha=1;
   for(const q of this.platforms){c.fillStyle="#0c1824";c.fillRect(q.x,q.y,q.w,q.h);c.fillStyle="#20d8ff";c.fillRect(q.x,q.y,q.w,2)}
   // tower
   c.fillStyle="#12192a";c.fillRect(LEVEL_01.tower.x,LEVEL_01.tower.y,LEVEL_01.tower.w,220);c.strokeStyle="#ff3bd4";c.lineWidth=2;c.strokeRect(LEVEL_01.tower.x,LEVEL_01.tower.y,LEVEL_01.tower.w,220);c.fillStyle="#20d8ff";c.fillRect(LEVEL_01.tower.x+25,LEVEL_01.tower.y+35,70,25);c.fillStyle="#ff3bd4";c.fillRect(LEVEL_01.tower.x+55,LEVEL_01.tower.y-25,10,25);
   for(const q of this.pickups){c.fillStyle=q.type==="cash"?"#ffe45c":q.type==="med"?"#ff3bd4":"#20d8ff";c.shadowBlur=12;c.shadowColor=c.fillStyle;c.fillRect(q.x,q.y,q.w,q.h);c.shadowBlur=0}
   for(const b of this.bullets){c.fillStyle="#20d8ff";c.fillRect(b.x-2,b.y-2,17,5)}for(const b of this.enemyBullets){c.fillStyle="#ff456c";c.fillRect(b.x,b.y,8,4)}
   for(const e of this.enemies)if(!e.dead){c.fillStyle=e.hitFlash>0?"#ffffff":e.type==="guardian"?"#ff3bd4":e.type==="ranged"?"#a96cff":"#ff5b5b";c.fillRect(e.x,e.y,e.w,e.h);c.fillStyle="#080b12";c.fillRect(e.x,e.y-8,e.w,4);c.fillStyle="#ff3bd4";c.fillRect(e.x,e.y-8,e.w*(e.hp/e.max),4)}
   c.fillStyle=this.p.inv>0?"#fff":"#20d8ff";c.fillRect(this.p.x,this.p.y,this.p.w,this.p.h);c.fillStyle="#ff3bd4";c.fillRect(this.p.face>0?this.p.x+this.p.w-4:this.p.x,this.p.y+10,4,5);
   c.strokeStyle="#20d8ff";c.strokeRect(LEVEL_01.exit.x,LEVEL_01.exit.y,LEVEL_01.exit.w,LEVEL_01.exit.h);c.fillStyle="#20d8ff";c.fillText("SIGNAL",LEVEL_01.exit.x+12,LEVEL_01.exit.y+75);c.restore()
 }
}
