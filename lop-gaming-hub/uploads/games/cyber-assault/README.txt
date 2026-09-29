NexusPlay: Cyber Assault
==========================
A standalone HTML5 canvas browser game.

Controls:
WASD = move
Mouse = aim
Left click = shoot
Shift = dash
P / Escape = pause
Fullscreen button = browser fullscreen

Run:
Open index.html in a modern browser.

NexusPlay integration:
Copy the cyber-assault folder into:
static/games/cyber-assault/

Then serve it through your Flask app, for example:
@app.route("/play/cyber-assault")
def play_cyber_assault():
    return send_from_directory("static/games/cyber-assault", "index.html")

For a larger game library, give each game its own folder and create a database record containing its slug/path.
