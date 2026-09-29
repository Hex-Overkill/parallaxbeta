const canvas=document.getElementById("game"),ctx=canvas.getContext("2d");
const W=canvas.width,H=canvas.height;
const keys={}; let mouse={x:W/2,y:H/2,down:false};
let player,enemies,bullets,particles,score,wave,spawnLeft,spawnTimer,paused,gameOver,last,high=Number(localStorage.getItem("nexusHigh")||0);

function reset(){
  player={x:W/2,y:H/2,r:16,hp:100,speed:250,angle:0,dash:0,shoot:0};
  enemies=[];bullets=[];particles=[];score=0;wave=1;spawnLeft=6;spawnTimer=0;paused=false;gameOver=false;last=performance.now();
  document.getElementById("overlay").classList.add("hidden"); updateHUD();
}
function updateHUD(){
  hp.textContent=Math.max(0,Math.ceil(player?.hp||0));scoreEl.textContent=score;waveEl.textContent=wave;enemiesEl.textContent=enemies.length+spawnLeft;
}
const hp=document.getElementById("hp"),scoreEl=document.getElementById("score"),waveEl=document.getElementById("wave"),enemiesEl=document.getElementById("enemies");
function rand(a,b){return Math.random()*(b-a)+a}
function spawnEnemy(){
  const side=Math.floor(Math.random()*4);let x,y;
  if(side===0){x=rand(20,W-20);y=-25}else if(side===1){x=W+25;y=rand(20,H-20)}else if(side===2){x=rand(20,W-20);y=H+25}else{x=-25;y=rand(20,H-20)}
  const type=Math.random()<.16+wave*.01?"fast":"normal";
  enemies.push({x,y,r:type==="fast"?12:15,hp:type==="fast"?28+wave*3:45+wave*6,max:type==="fast"?28+wave*3:45+wave*6,speed:type==="fast"?125+wave*3:70+wave*2,hit:0,type});
}
function shoot(){
  if(player.shoot>0||paused||gameOver)return;
  player.shoot=.12;
  const a=player.angle,spd=620;
  bullets.push({x:player.x+Math.cos(a)*24,y:player.y+Math.sin(a)*24,vx:Math.cos(a)*spd,vy:Math.sin(a)*spd,r:4,life:1});
}
function burst(x,y,n=8,life=.5){
  for(let i=0;i<n;i++){const a=rand(0,Math.PI*2),s=rand(30,180);particles.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life,max:life,r:rand(1,4)})}
}
function damageEnemy(e,d){
  e.hp-=d;e.hit=.08;burst(e.x,e.y,3,.25);
  if(e.hp<=0){score+=e.type==="fast"?150:100;burst(e.x,e.y,15,.55);enemies=enemies.filter(x=>x!==e)}
}
function update(dt){
  if(paused||gameOver)return;
  let dx=(keys.KeyD?1:0)-(keys.KeyA?1:0),dy=(keys.KeyS?1:0)-(keys.KeyW?1:0),len=Math.hypot(dx,dy)||1;
  let sp=player.speed*(player.dash>0?2.7:1);
  player.x=Math.max(22,Math.min(W-22,player.x+dx/len*sp*dt));
  player.y=Math.max(22,Math.min(H-22,player.y+dy/len*sp*dt));
  player.angle=Math.atan2(mouse.y-player.y,mouse.x-player.x);
  player.shoot=Math.max(0,player.shoot-dt);player.dash=Math.max(0,player.dash-dt);
  if(mouse.down)shoot();

  spawnTimer-=dt;
  if(spawnLeft>0&&spawnTimer<=0){spawnEnemy();spawnLeft--;spawnTimer=Math.max(.22,.75-wave*.035)}
  if(spawnLeft===0&&enemies.length===0){wave++;spawnLeft=Math.min(6+wave*2,22);score+=250;burst(player.x,player.y,30,.9)}

  for(const b of bullets){b.x+=b.vx*dt;b.y+=b.vy*dt;b.life-=dt}
  bullets=bullets.filter(b=>b.life>0&&b.x>-20&&b.x<W+20&&b.y>-20&&b.y<H+20);

  for(const e of enemies){
    const a=Math.atan2(player.y-e.y,player.x-e.x),d=Math.hypot(player.x-e.x,player.y-e.y);
    e.x+=Math.cos(a)*e.speed*dt;e.y+=Math.sin(a)*e.speed*dt;e.hit=Math.max(0,e.hit-dt);
    if(d<e.r+player.r){player.hp-= (e.type==="fast"?22:14)*dt; if(player.hp<=0){endGame();}}
  }
  for(const b of bullets){for(const e of [...enemies]){if(Math.hypot(b.x-e.x,b.y-e.y)<b.r+e.r){damageEnemy(e,25);b.life=0;break}}}
  for(const p of particles){p.x+=p.vx*dt;p.y+=p.vy*dt;p.life-=dt;p.vx*=.96;p.vy*=.96}
  particles=particles.filter(p=>p.life>0);updateHUD();
}
function endGame(){
  gameOver=true;high=Math.max(high,score);localStorage.setItem("nexusHigh",high);
  document.getElementById("overlayTitle").textContent="SYSTEM DOWN";
  document.getElementById("overlayText").textContent=`Score: ${score}  •  Best: ${high}  •  Wave: ${wave}`;
  document.getElementById("overlay").classList.remove("hidden");
}
function draw(){
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle="#080b16";ctx.fillRect(0,0,W,H);
  // grid
  ctx.strokeStyle="#12203a";ctx.lineWidth=1;
  for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke()}
  for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke()}
  // arena accents
  ctx.strokeStyle="#00d9ff44";ctx.lineWidth=3;ctx.strokeRect(15,15,W-30,H-30);
  ctx.strokeStyle="#a855f744";ctx.lineWidth=2;ctx.strokeRect(45,45,W-90,H-90);
  // obstacles
  for(let i=0;i<9;i++){let x=90+(i*137)%850,y=90+(i*83)%430;ctx.fillStyle="#111a2b";ctx.fillRect(x,y,55,32);ctx.strokeStyle="#00a8cc55";ctx.strokeRect(x,y,55,32)}
  // bullets
  for(const b of bullets){ctx.fillStyle="#ffd166";ctx.shadowBlur=15;ctx.shadowColor="#ffb703";ctx.beginPath();ctx.arc(b.x,b.y,b.r,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0}
  // particles
  for(const p of particles){ctx.globalAlpha=Math.max(0,p.life/p.max);ctx.fillStyle="#ff3b81";ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fill()}ctx.globalAlpha=1;
  // enemies
  for(const e of enemies){ctx.save();ctx.translate(e.x,e.y);ctx.rotate(Math.atan2(player.y-e.y,player.x-e.x));ctx.shadowBlur=15;ctx.shadowColor="#ff1744";ctx.fillStyle=e.hit?"#fff":"#a71945";ctx.beginPath();ctx.arc(0,0,e.r,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#ff1744";ctx.lineWidth=3;ctx.stroke();ctx.fillStyle="#111";ctx.fillRect(2,-4,10,8);ctx.restore();
    ctx.fillStyle="#2a1020";ctx.fillRect(e.x-18,e.y-e.r-10,36,4);ctx.fillStyle="#ff1744";ctx.fillRect(e.x-18,e.y-e.r-10,36*Math.max(0,e.hp/e.max),4)}
  // player
  ctx.save();ctx.translate(player.x,player.y);ctx.rotate(player.angle);ctx.shadowBlur=20;ctx.shadowColor="#00e5ff";ctx.fillStyle="#00b8d4";ctx.beginPath();ctx.arc(0,0,player.r,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#dffcff";ctx.lineWidth=2;ctx.stroke();ctx.fillStyle="#07111d";ctx.fillRect(0,-5,28,10);ctx.fillStyle="#a855f7";ctx.fillRect(-9,-9,10,18);ctx.restore();
  // HP bar
  ctx.fillStyle="#07111d";ctx.fillRect(25,25,220,18);ctx.fillStyle="#ff3b61";ctx.fillRect(25,25,220*Math.max(0,player.hp/100),18);ctx.strokeStyle="#00d9ff88";ctx.strokeRect(25,25,220,18);
}
function loop(t){const dt=Math.min(.033,(t-last)/1000);last=t;update(dt);draw();requestAnimationFrame(loop)}
window.addEventListener("keydown",e=>{keys[e.code]=true;if(e.code==="ShiftLeft"||e.code==="ShiftRight"){if(player&&player.dash<=0){player.dash=.18;burst(player.x,player.y,8,.3)}}if(e.code==="KeyP"||e.code==="Escape")paused=!paused});
window.addEventListener("keyup",e=>keys[e.code]=false);
canvas.addEventListener("mousemove",e=>{const r=canvas.getBoundingClientRect();mouse.x=(e.clientX-r.left)*W/r.width;mouse.y=(e.clientY-r.top)*H/r.height});
canvas.addEventListener("mousedown",()=>mouse.down=true);window.addEventListener("mouseup",()=>mouse.down=false);
document.getElementById("restart").onclick=reset;
document.getElementById("fullscreen").onclick=()=>document.querySelector(".game-wrap").requestFullscreen?.();
reset();requestAnimationFrame(loop);
