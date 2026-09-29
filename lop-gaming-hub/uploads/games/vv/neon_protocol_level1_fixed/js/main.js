(function(){
"use strict";
var game;
function $(id){return document.getElementById(id)}
function show(id){
  ["boot","mainMenu","story","complete","dead"].forEach(function(x){var e=$(x);if(e)e.classList.add("hidden")});
  var target=$(id); if(target) target.classList.remove("hidden");
}
function boot(){
  try{
    game=new LevelOne($("game"));
    show("mainMenu");
  }catch(err){
    console.error(err);
    var b=$("boot");
    b.classList.remove("hidden");
    b.innerHTML='<div class="storybox"><div class="kicker">BOOT ERROR</div><h1>NEON PROTOCOL</h1><p>Game startup failed. Reload the page after extracting the complete ZIP folder.</p><p style="font-size:12px;color:#ff6b8a">'+String(err.message||err)+'</p></div>';
  }
}
$("start").onclick=function(){show("story")};
$("enter").onclick=function(){show("mainMenu");$("mainMenu").classList.add("hidden");game.start()};
$("returnMenu").onclick=function(){if(game){game.running=false;game.reset()}show("mainMenu")};
$("retry").onclick=function(){show("mainMenu");$("mainMenu").classList.add("hidden");game.start()};
$("deadMenu").onclick=function(){if(game){game.running=false;game.reset()}show("mainMenu")};

document.addEventListener("keydown",function(e){
  if(e.key!=="Escape")return;
  if(game && game.running){game.running=false;game.reset();show("mainMenu");}
  else if($("complete") && !$("complete").classList.contains("hidden")){if(game)game.reset();show("mainMenu");}
  else if($("dead") && !$("dead").classList.contains("hidden")){if(game)game.reset();show("mainMenu");}
});
document.querySelectorAll("#touch button").forEach(function(b){
 var k=b.dataset.key,code=k==="left"?"KeyA":k==="right"?"KeyD":"Space";
 function down(e){e.preventDefault();if(k==="fire")game.mouse=true;else if(k==="use")game.use();else game.keys[code]=true}
 function up(e){e.preventDefault();if(k==="fire")game.mouse=false;else game.keys[code]=false}
 b.addEventListener("touchstart",down,{passive:false});b.addEventListener("touchend",up,{passive:false});
 b.addEventListener("mousedown",down);b.addEventListener("mouseup",up);
});
window.addEventListener("load",function(){setTimeout(boot,100)});
setTimeout(function(){if($("boot")&&!$("boot").classList.contains("hidden"))show("mainMenu")},2500);
})();