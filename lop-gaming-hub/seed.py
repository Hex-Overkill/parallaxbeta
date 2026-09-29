"""LoP Gaming Hub — development seed.

Creates the demo users, the global Lobby chatroom, six playable sample
games (packaged as zips and pushed through the *real* admin upload
pipeline), a few chat messages and historical play sessions so the
dashboard, leaderboards and activity feed look alive.

Run:  python seed.py   (idempotent — safe to re-run)
"""
import random
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path

from app import create_app
from extensions import db
from helpers import ingest_game_zip
from models import ChatMessage, ChatRoom, Game, GameSession, User, now_utc

SEED_PASSWORD = "gamer12345"

USERS = [
    ("gamer1", "gamer1@example.com", "gamer1pass123"),
    ("gamer2", "gamer2@example.com", "gamer2pass123"),
    ("gamer3", "gamer3@example.com", "gamer3pass123"),
]
EXPIRED_DEMO = ("expired_demo", "expired@example.com", "expired12345")
ADMIN = ("admin", "admin@lopgaming.local", "LoP-admin-2026!")

GAMES = [
    dict(
        title="Snake",
        category="Arcade",
        description="The classic. Eat the pixel fruit, grow longer, and don't bite yourself. Arrow keys or WASD to steer.",
        version="1.0",
        is_premium=False, is_multiplayer=False, is_featured=True,
        colors=("#22c55e", "#0d2b18"),
        html=r"""<!doctype html><html><head><meta charset="utf-8"><title>Snake</title><style>
body{margin:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;font-family:Verdana,sans-serif;color:#8fa3c4}
h1{font-size:18px;letter-spacing:4px;color:#22c55e;text-transform:uppercase;margin:0 0 8px}
#score{font-size:14px;margin-bottom:8px;color:#e8eefb}
canvas{background:#0d2b18;border:2px solid #22c55e;border-radius:8px;box-shadow:0 0 30px rgba(34,197,94,.25)}
#over{display:none;position:absolute;background:rgba(10,14,23,.92);padding:24px 40px;border-radius:12px;border:1px solid #22c55e;text-align:center}
#over h2{color:#22c55e;margin:0 0 10px;letter-spacing:2px}
#over button{margin-top:12px;padding:10px 26px;font-size:15px;background:#22c55e;border:0;border-radius:8px;cursor:pointer;color:#06210f;font-weight:bold}
</style></head><body>
<h1>Snake</h1><div id="score">Score 0</div>
<div style="position:relative"><canvas id="c" width="440" height="440"></canvas><div id="over"><h2>GAME OVER</h2><div style="color:#8fa3c4" id="fin"></div><button onclick="location.reload()">Play again</button></div></div>
<script>
var cv=document.getElementById('c'),ctx=cv.getContext('2d'),N=22,cell=cv.width/N,dir={x:1,y:0},q=[{x:9,y:10},{x:8,y:10},{x:7,y:10}],food,tick=0,acc=0,step=110,score=0,dead=false;
function placeFood(){while(true){var f={x:~~(Math.random()*N),y:~~(Math.random()*N)};if(!q.some(s=>s.x===f.x&&s.y===f.y)){food=f;return}}}
placeFood();
document.addEventListener('keydown',function(e){var k=e.key.toLowerCase();
 if((k==='arrowup'||k==='w')&&dir.y===0)dir={x:0,y:-1};
 if((k==='arrowdown'||k==='s')&&dir.y===0)dir={x:0,y:1};
 if((k==='arrowleft'||k==='a')&&dir.x===0)dir={x:-1,y:0};
 if((k==='arrowright'||k==='d')&&dir.x===0)dir={x:1,y:0};});
function frame(now){requestAnimationFrame(frame);if(dead)return;
 var dt=now-(acc||now);acc=now;tick+=dt;
 ctx.fillStyle='#0d2b18';ctx.fillRect(0,0,cv.width,cv.height);
 ctx.fillStyle='#ff4757';ctx.beginPath();ctx.arc(food.x*cell+cell/2,food.y*cell+cell/2,cell*.34,0,7);ctx.fill();
 q.forEach(function(s,i){ctx.fillStyle=i===0?'#8ff0b4':'#22c55e';ctx.fillRect(s.x*cell+1,s.y*cell+1,cell-2,cell-2);});
 if(tick>=step){tick=0;stepMove();}
 function stepMove(){
  var h={x:q[0].x+dir.x,y:q[0].y+dir.y};
  if(h.x<0||h.y<0||h.x>=N||h.y>=N||q.some(s=>s.x===h.x&&s.y===h.y)){gameOver();return}
  q.unshift(h);
  if(h.x===food.x&&h.y===food.y){score++;document.getElementById('score').textContent='Score '+score;placeFood();}
  else q.pop();
 }}
 function gameOver(){dead=true;document.getElementById('over').style.display='block';document.getElementById('fin').textContent='Final score: '+score;}
requestAnimationFrame(frame);
</script></body></html>""",
    ),
    dict(
        title="Neon Pong 2P",
        category="Multiplayer",
        description="Two-player table tennis in the arcade. Player 1 uses W/S, Player 2 uses the arrow keys. First to 5 wins.",
        version="1.2",
        is_premium=False, is_multiplayer=True, is_featured=True,
        colors=("#22d3ee", "#0b1f2b"),
        html=r"""<!doctype html><html><head><meta charset="utf-8"><title>Neon Pong 2P</title><style>
body{margin:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;min-height:100vh;font-family:Verdana,sans-serif;color:#8fa3c4}
h1{font-size:16px;letter-spacing:4px;color:#22d3ee;text-transform:uppercase;margin:14px 0 6px}
#keys{font-size:13px;color:#5c6f93;margin-bottom:10px}
canvas{background:#0b1f2b;border:2px solid #22d3ee;border-radius:8px;box-shadow:0 0 30px rgba(34,211,238,.22);display:block}
</style></head><body>
<h1>Neon Pong</h1><div id="keys">P1: W / S &nbsp;&nbsp;•&nbsp;&nbsp; P2: ↑ / ↓ &nbsp;&nbsp;•&nbsp;&nbsp; first to 5</div>
<canvas id="c" width="720" height="420"></canvas>
<script>
var cv=document.getElementById('c'),ctx=cv.getContext('2d'),W=cv.width,H=cv.height;
var pw=12,ph=80,lp={y:H/2-ph/2},rp={y:H/2-ph/2},ls=0,rs=0,ball={x:W/2,y:H/2,vx:5,vy:2.5},over=false;
var keys={};
document.addEventListener('keydown',function(e){keys[e.key]=true;if(e.key===' '&&over)location.reload();});
document.addEventListener('keyup',function(e){keys[e.key]=false;});
function reset(side){ball={x:W/2,y:H/2,vx:(side==='p2'?-1:1)*5,vy:(Math.random()*4-2)||2};}
function frame(){if(over)return;
 if(keys['w'])lp.y-=7;if(keys['s'])lp.y+=7;
 if(keys['ArrowUp'])rp.y-=7;if(keys['ArrowDown'])rp.y+=7;
 lp.y=Math.max(0,Math.min(H-ph,lp.y));rp.y=Math.max(0,Math.min(H-ph,rp.y));
 ball.x+=ball.vx;ball.y+=ball.vy;
 if(ball.y<0||ball.y>H){ball.vy*=-1;ball.y=Math.max(0,Math.min(H,ball.y));}
 function hit(p){return ball.x>p.x&&ball.x<p.x+pw&&ball.y>p.y&&ball.y<p.y+ph;}
 if(hit(lp)){ball.x=lp.x+pw;ball.vx*=-1.06;ball.vy=(ball.y-(lp.y+ph/2))/12;}
 else if(hit(rp)){ball.x=rp.x-pw;ball.vx*=-1.06;ball.vy=(ball.y-(rp.y+ph/2))/12;}
 if(ball.x<0){rs++;check('P2');}
 if(ball.x>W){ls++;check('P1');}
 ctx.fillStyle='#0b1f2b';ctx.fillRect(0,0,W,H);
 ctx.strokeStyle='rgba(34,211,238,.35)';ctx.setLineDash([8,10]);ctx.beginPath();ctx.moveTo(W/2,0);ctx.lineTo(W/2,H);ctx.stroke();ctx.setLineDash([]);
 ctx.fillStyle='#e8eefb';ctx.fillRect(0,lp.y,pw,ph);ctx.fillRect(W-pw,rp.y,pw,ph);
 ctx.fillStyle='#ffd76a';ctx.beginPath();ctx.arc(ball.x,ball.y,8,0,7);ctx.fill();
 ctx.fillStyle='#22d3ee';ctx.font='bold 22px Verdana';
 ctx.fillText(ls, W/2-70, 34);ctx.fillText(rs, W/2+50, 34);
 requestAnimationFrame(frame);
 function check(w){if(ls===5||rs===5){over=true;ctx.fillStyle='rgba(10,14,23,.9)';ctx.fillRect(0,H/2-50,W,100);ctx.fillStyle='#ffd76a';ctx.font='bold 30px Verdana';ctx.textAlign='center';ctx.fillText(w+' WINS — SPACE to replay',W/2,H/2+10);ctx.textAlign='left';}else reset(w);}
}
requestAnimationFrame(frame);
</script></body></html>""",
    ),
    dict(
        title="Memory Match",
        category="Puzzle",
        description="Flip the neon cards and pair up all 16 symbols. How few moves can you do it in?",
        version="1.0",
        is_premium=False, is_multiplayer=False, is_featured=False,
        colors=("#8b5cf6", "#151030"),
        html=r"""<!doctype html><html><head><meta charset="utf-8"><title>Memory Match</title><style>
body{margin:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;padding:24px;font-family:Verdana,sans-serif;color:#8fa3c4}
h1{font-size:16px;letter-spacing:4px;color:#8b5cf6;text-transform:uppercase;margin:0 0 8px}
#info{font-size:14px;color:#e8eefb;margin-bottom:16px}
#board{display:grid;grid-template-columns:repeat(4,84px);gap:10px}
.card{width:84px;height:84px;background:#1a1440;border:1px solid #4c3a9e;border-radius:10px;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:34px;user-select:none;transition:transform .15s}
.card.flip{background:#261b52;border-color:#8b5cf6}
.card.matched{background:rgba(139,92,246,.15);border-color:#22c55e;cursor:default}
.card:hover:not(.matched){transform:scale(1.05)}
#win{display:none;margin-top:14px;font-size:17px;color:#6fe9a0;font-weight:bold}
</style></head><body>
<h1>Memory Match</h1><div id="info">Moves: 0</div>
<div id="board"></div><div id="win">🎉 All matched in <span id="wm"></span> moves!</div>
<script>
var SYMS=['🚀','⚡','🔥','💎','🎧','🕹️','👾','💫'];
var deck=SYMS.concat(SYMS).sort(function(){return Math.random()-.5;});
var board=document.getElementById('board'),flipped=[],moves=0,locked=false,matched=0;
deck.forEach(function(s,i){var d=document.createElement('div');d.className='card';d.dataset.sym=s;d.dataset.i=i;d.textContent='?';
 d.addEventListener('click',function(){if(locked||d.classList.contains('flip')||d.classList.contains('matched'))return;
  d.textContent=s;d.classList.add('flip');flipped.push(d);
  if(flipped.length===2){locked=true;moves++;document.getElementById('info').textContent='Moves: '+moves;
   var a=flipped[0],b=flipped[1];
   if(a.dataset.sym===b.dataset.sym){a.classList.add('matched');b.classList.add('matched');matched+=2;
    if(matched===16){document.getElementById('win').style.display='block';document.getElementById('wm').textContent=moves;}}
   else setTimeout(function(){a.textContent='?';b.textContent='?';a.classList.remove('flip');b.classList.remove('flip');},650);
   flipped=[];setTimeout(function(){locked=false;},680);}});
 board.appendChild(d);});
</script></body></html>""",
    ),
    dict(
        title="Reflex Rush",
        category="Action",
        description="Premium adrenaline: hit the glowing nodes before they fade. 30 seconds, three lanes, one rule — react fast.",
        version="2.0",
        is_premium=True, is_multiplayer=False, is_featured=True,
        colors=("#f5b83d", "#2b1a06"),
        html=r"""<!doctype html><html><head><meta charset="utf-8"><title>Reflex Rush</title><style>
body{margin:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;padding:20px;font-family:Verdana,sans-serif;color:#8fa3c4}
h1{font-size:16px;letter-spacing:4px;color:#f5b83d;text-transform:uppercase;margin:0 0 8px}
#hud{display:flex;gap:28px;font-size:15px;color:#e8eefb;margin-bottom:10px}
#hud b{color:#f5b83d}
canvas{background:#2b1a06;border:2px solid #f5b83d;border-radius:8px;box-shadow:0 0 30px rgba(245,184,61,.2);cursor:crosshair}
</style></head><body>
<h1>Reflex Rush</h1><div id="hud"><span>Score <b id="sc">0</b></span><span>Time <b id="tm">30.0</b></span><span>Best <b id="hi">0</b></span></div>
<canvas id="c" width="600" height="400"></canvas>
<script>
var cv=document.getElementById('c'),ctx=cv.getContext('2d'),T=30,W=cv.width,H=cv.height;
var score=0,best=+(localStorage?localStorage.getItem('rr_best')||0:0),time=T,active=[],started=false;
document.getElementById('hi').textContent=best;
function spawn(){var x=40+Math.random()*(W-80),y=40+Math.random()*(H-80);
 active.push({x:x,y:y,r:26,born:performance.now()});}
cv.addEventListener('mousedown',function(e){var r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
 for(var i=active.length-1;i>=0;i--){var n=active[i];
  if(Math.hypot(mx-n.x,my-n.y)<n.r+8){score++;active.splice(i,1);document.getElementById('sc').textContent=score;return;}}});
setInterval(function(){if(!started){started=true;spawn();spawn();
 setInterval(function(){if(active.length<3)spawn();},900);return;}
 time=Math.max(0,time-.1);document.getElementById('tm').textContent=time.toFixed(1);
 if(time<=0){if(score>best){best=score;localStorage.setItem('rr_best',best);document.getElementById('hi').textContent=best;}
  ctx.fillStyle='rgba(10,14,23,.92)';ctx.fillRect(0,H/2-45,W,90);ctx.fillStyle='#ffd76a';ctx.font='bold 28px Verdana';ctx.textAlign='center';ctx.fillText('SCORE: '+score,W/2,H/2+10);ctx.textAlign='left';return;}
 active=active.filter(function(n){return performance.now()-n.born<800;});
 ctx.fillStyle='#2b1a06';ctx.fillRect(0,0,W,H);
 active.forEach(function(n){var a=1-(performance.now()-n.born)/800;ctx.globalAlpha=Math.max(0,a);ctx.fillStyle='#f5b83d';ctx.beginPath();ctx.arc(n.x,n.y,n.r,0,7);ctx.fill();ctx.fillStyle='#2b1a06';ctx.beginPath();ctx.arc(n.x,n.y,n.r*.55,0,7);ctx.fill();ctx.globalAlpha=1;});},100);
</script></body></html>""",
    ),
    dict(
        title="Space Dodger",
        category="Arcade",
        description="Premium + multiplayer chat lounge. Pilot your ship through an asteroid storm and survive as long as you can.",
        version="1.3",
        is_premium=True, is_multiplayer=True, is_featured=True,
        colors=("#4f7cff", "#0a1026"),
        html=r"""<!doctype html><html><head><meta charset="utf-8"><title>Space Dodger</title><style>
body{margin:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;padding:20px;font-family:Verdana,sans-serif;color:#8fa3c4}
h1{font-size:16px;letter-spacing:4px;color:#4f7cff;text-transform:uppercase;margin:0 0 8px}
#hud{display:flex;gap:26px;font-size:15px;color:#e8eefb;margin-bottom:10px}
#hud b{color:#4f7cff}
canvas{background:#0a1026;border:2px solid #4f7cff;border-radius:8px;box-shadow:0 0 30px rgba(79,124,255,.18)}
</style></head><body>
<h1>Space Dodger</h1><div id="hud"><span>Score <b id="sc">0</b></span><span>Survival <b id="tm">0s</b></span><span>Keys: ← ↑ ↓ →</span></div>
<canvas id="c" width="640" height="440"></canvas>
<script>
var cv=document.getElementById('c'),ctx=cv.getContext('2d'),W=cv.width,H=cv.height;
var ship={x:W/2,y:H-60,w:42,h:26},ast=[],score=0,alive=true,start=performance.now(),keys={};
function star(){return{x:Math.random()*W,y:-30,r:6+Math.random()*16,v:2.6+Math.random()*3.6};}
document.addEventListener('keydown',function(e){keys[e.key]=true;if(e.key===' '&&!alive)location.reload();});
document.addEventListener('keyup',function(e){keys[e.key]=false;});
setInterval(function(){ast.push(star());if(Math.random()<.4)ast.push(star());},600);
function frame(now){if(!alive)return;
 if(keys['ArrowLeft'])ship.x-=6;if(keys['ArrowRight'])ship.x+=6;
 if(keys['ArrowUp'])ship.y-=5;if(keys['ArrowDown'])ship.y+=5;
 ship.x=Math.max(15,Math.min(W-15,ship.x));ship.y=Math.max(15,Math.min(H-15,ship.y));
 ctx.fillStyle='#0a1026';ctx.fillRect(0,0,W,H);
 ast.forEach(function(a){a.y+=a.v;a.x+=Math.sin((now+a.y)/900)*.6;
  ctx.fillStyle='#4f5a74';ctx.beginPath();ctx.arc(a.x,a.y,a.r,0,7);ctx.fill();
  ctx.fillStyle='#1c2840';ctx.beginPath();ctx.arc(a.x-a.r*.2,a.y-a.r*.2,a.r*.5,0,7);ctx.fill();
  if(Math.abs(a.x-ship.x)<a.r+ship.w/2&&Math.abs(a.y-ship.y)<a.r+ship.h/2){alive=false;ctx.fillStyle='rgba(10,14,23,.92)';ctx.fillRect(0,H/2-45,W,90);ctx.fillStyle='#ffd76a';ctx.font='bold 26px Verdana';ctx.textAlign='center';ctx.fillText('CRASHED! SPACE to replay',W/2,H/2+10);ctx.textAlign='left';return;}});
 ast=ast.filter(function(a){return a.y<H+40;});
 ctx.fillStyle='#ffd76a';ctx.beginPath();ctx.moveTo(ship.x,ship.y-ship.h/2);ctx.lineTo(ship.x+ship.w/2,ship.y+ship.h/2);ctx.lineTo(ship.x-ship.w/2,ship.y+ship.h/2);ctx.closePath();ctx.fill();
 score++;document.getElementById('sc').textContent=Math.floor(score/4);
 document.getElementById('tm').textContent=Math.floor((now-start)/1000)+'s';
 requestAnimationFrame(frame);}
requestAnimationFrame(frame);
</script></body></html>""",
    ),
    dict(
        title="TicTacToe Arena",
        category="Puzzle",
        description="Online-style 2-player tic-tac-toe on one keyboard, with the full multiplayer lounge chat right next to it.",
        version="1.0",
        is_premium=False, is_multiplayer=True, is_featured=False,
        colors=("#ef4444", "#2b0f14"),
        html=r"""<!doctype html><html><head><meta charset="utf-8"><title>TicTacToe Arena</title><style>
body{margin:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;padding:24px;font-family:Verdana,sans-serif;color:#8fa3c4}
h1{font-size:16px;letter-spacing:4px;color:#ef4444;text-transform:uppercase;margin:0 0 8px}
#turn{font-size:16px;color:#e8eefb;margin-bottom:14px;min-height:22px}
#board{display:grid;grid-template-columns:repeat(3,110px);gap:8px}
.cell{width:110px;height:110px;background:#2b0f14;border:1px solid #8c2b2b;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:56px;font-weight:bold;cursor:pointer;user-select:none;color:#ffd76a}
.cell.x{color:#4f7cff}.cell.o{color:#ef4444}
#reset{margin-top:16px;padding:10px 26px;font-size:15px;background:#ef4444;border:0;border-radius:8px;cursor:pointer;color:#fff;font-weight:bold}
</style></head><body>
<h1>TicTacToe Arena</h1><div id="turn">X to move</div>
<div id="board"></div><button id="reset">New round</button>
<script>
var cells=[],turn='X',moves=0,over=false;
var WIN=[[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
var boardEl=document.getElementById('board'),turnEl=document.getElementById('turn');
function make(){
 cells=[];moves=0;over=false;turn='X';turnEl.textContent='X to move';
 boardEl.innerHTML='';
 for(var i=0;i<9;i++){var d=document.createElement('div');d.className='cell';d.dataset.i=i;
  d.addEventListener('click',function(){if(over||this.textContent)return;
   this.textContent=turn;this.classList.add(turn.toLowerCase());moves++;
   var w=winner();if(w){over=true;turnEl.textContent=w+' wins! 🎉';flash(w);}
   else if(moves===9){over=true;turnEl.textContent='Draw 🤝';}
   else{turn=turn==='X'?'O':'X';turnEl.textContent=turn+' to move';}});
  boardEl.appendChild(d);cells.push(d);}
}
function winner(){for(var i=0;i<WIN.length;i++){var a=WIN[i],x=cells[a[0]].textContent;
 if(x&&x===cells[a[1]].textContent&&x===cells[a[2]].textContent)return x;}return null;}
function flash(w){WIN.forEach(function(l){var ok=cells[l[0]].textContent===w&&cells[l[1]].textContent===w&&cells[l[2]].textContent===w;
 if(ok)l.forEach(function(i){cells[i].style.borderColor='#22c55e';});});}
document.getElementById('reset').addEventListener('click',make);
make();
</script></body></html>""",
    ),
]

TEMPLATE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="320" viewBox="0 0 512 320">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>
  </linearGradient></defs>
  <rect width="512" height="320" rx="18" fill="url(#g)"/>
  <rect x="8" y="8" width="496" height="304" rx="14" fill="none" stroke="rgba(255,255,255,.35)" stroke-width="2"/>
  <rect x="16" y="16" width="480" height="288" rx="12" fill="rgba(10,14,23,.55)"/>
  <text x="256" y="176" font-family="Verdana, sans-serif" font-size="34" font-weight="bold" fill="#ffffff" text-anchor="middle">{title}</text>
  <text x="256" y="212" font-family="Verdana, sans-serif" font-size="18" fill="rgba(232,238,251,.75)" text-anchor="middle">LoP Gaming Hub</text>
</svg>"""


def make_thumb(slug: str, title: str, colors: tuple) -> Path:
    from flask import current_app
    thumb_dir = current_app.config["THUMBNAIL_DIR"]
    thumb_dir.mkdir(parents=True, exist_ok=True)
    target = thumb_dir / f"{slug}-seed.svg"
    svg = TEMPLATE_SVG.format(title=title.upper(), c1=colors[0], c2=colors[1])
    target.write_text(svg, encoding="utf-8")
    return target


def seed_users() -> None:
    for username, email, password in USERS + [EXPIRED_DEMO]:
        if User.query.filter_by(username=username).first():
            continue
        user = User(
            username=username,
            email=email,
            role="user",
            trial_started_at=now_utc() - (
                timedelta(days=60) if username == "expired_demo" else timedelta(seconds=0)
            ),
        )
        user.set_password(password)
        db.session.add(user)

    if not User.query.filter_by(username=ADMIN[0]).first():
        admin = User(
            username=ADMIN[0],
            email=ADMIN[1],
            role="admin",
            trial_started_at=now_utc(),
        )
        admin.set_password(ADMIN[2])
        db.session.add(admin)
    db.session.commit()
    print(f"  users: {User.query.count()} total (admin {ADMIN[0]!r} / {ADMIN[2]!r})")


def seed_chat() -> None:
    lobby = ChatRoom.query.filter_by(name="Lobby").first()
    if lobby is None:
        lobby = ChatRoom(name="Lobby", slug="lobby", game_id=None)
        db.session.add(lobby)
        db.session.commit()
        print("  chatroom: Lobby created")
    if lobby.messages.count() == 0:
        g1 = User.query.filter_by(username="gamer1").first()
        g2 = User.query.filter_by(username="gamer2").first()
        g3 = User.query.filter_by(username="gamer3").first()
        for user, text in [
            (g1, "Yo! Anyone up for Neon Pong?"),
            (g2, "Space Dodger just dropped, it's clean 🔥"),
            (g3, "1v1 me in the lobby losers 😎"),
        ]:
            if user:
                db.session.add(
                    ChatMessage(room_id=lobby.id, user_id=user.id, content=text)
                )
        db.session.commit()
        print("  chat: 3 welcome messages in Lobby")


def seed_games() -> None:
    with tempfile.TemporaryDirectory(prefix="lop-seed-") as tmp:
        tmp_dir = Path(tmp)
        for spec in GAMES:
            if Game.query.filter_by(slug=spec["title"].lower().replace(" ", "-")).first():
                print(f"  game: {spec['title']} already exists, skipped")
                continue
            zip_path = tmp_dir / f"{spec['title']}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("index.html", spec["html"])
            thumb = make_thumb(
                spec["title"].lower().replace(" ", "-"), spec["title"], spec["colors"]
            )
            game = ingest_game_zip(
                zip_path,
                {
                    "title": spec["title"],
                    "description": spec["description"],
                    "category": spec["category"],
                    "version": spec["version"],
                    "is_premium": spec["is_premium"],
                    "is_multiplayer": spec["is_multiplayer"],
                    "is_featured": spec["is_featured"],
                    "uploaded_by_id": User.query.filter_by(username="admin").first().id,
                },
                extra_thumb_path=thumb,
            )
            print(f"  game: {game.title} -> /games/{game.slug}")
    print(f"  total games in library: {Game.query.count()}")


def seed_sessions() -> None:
    if GameSession.query.count() > 0:
        print("  sessions already seeded")
        return
    from helpers import recompute_game_stats
    rng = random.Random(42)
    users = User.query.filter_by(role="user").all()
    games = {g.slug: g for g in Game.query.filter_by(is_premium=False).all()}
    playable = [g["title"].lower().replace(" ", "-") for g in GAMES if not g["is_premium"]]
    for i in range(26):
        user = rng.choice(users[:3])
        slug = rng.choice(playable[:3])  # snake, pong, memory
        game = games.get(slug)
        if not game:
            continue
        started = now_utc() - timedelta(
            minutes=rng.randint(30, 60 * 24 * 12), seconds=rng.randint(0, 3600)
        )
        duration = rng.randint(60, 420)
        db.session.add(
            GameSession(
                user_id=user.id,
                game_id=game.id,
                started_at=started,
                duration_seconds=duration,
                is_active=False,
            )
        )
    db.session.commit()
    recompute_game_stats()
    print(f"  seeded {GameSession.query.count()} historical sessions")


def main() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        print("== LoP Gaming Hub seed ==")
        seed_users()
        seed_chat()
        seed_games()
        seed_sessions()
        print("Done! Run `python app.py` and open http://127.0.0.1:5000")


if __name__ == "__main__":
    main()