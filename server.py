import os, re, json, shutil, tempfile, datetime, urllib.request
from flask import Flask, request, send_file, jsonify, after_this_request
import yt_dlp

app = Flask(__name__, static_folder=".", static_url_path="")
OK = re.compile(r"^https?://([\w-]+\.)*(tiktok\.com|youtube\.com|youtu\.be|instagram\.com)/")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
DAILY = int(os.environ.get("DAILY_LIMIT", "20"))
usage = {}

def user_id():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer ") or not SB_URL:
        return None
    req = urllib.request.Request(SB_URL + "/auth/v1/user",
                                 headers={"apikey": SB_KEY, "Authorization": h})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r).get("id")
    except Exception:
        return None

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/config")
def config():
    return jsonify(url=SB_URL, key=SB_KEY)

@app.route("/api/fetch")
def fetch():
    uid = user_id()
    if not uid:
        return jsonify(error="Faz login para continuar"), 401
    k = (uid, datetime.date.today().isoformat())
    if usage.get(k, 0) >= DAILY:
        return jsonify(error="Atingiste o limite diário de %d vídeos" % DAILY), 429
    url = request.args.get("url", "")
    if not OK.match(url):
        return jsonify(error="Link inválido (só TikTok, YouTube e Instagram)"), 400
    d = tempfile.mkdtemp()
    opts = {
        "outtmpl": d + "/v.%(ext)s",
        "format": "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "noplaylist": True, "quiet": True,
        "max_filesize": 150 * 1024 * 1024,
        "match_filter": yt_dlp.utils.match_filter_func("duration<=600"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
        f = os.path.join(d, os.listdir(d)[0])
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        return jsonify(error="Vídeo indisponível, privado ou demasiado grande"), 502
    usage[k] = usage.get(k, 0) + 1

    @after_this_request
    def clean(r):
        shutil.rmtree(d, ignore_errors=True)
        return r
    return send_file(f, mimetype="video/mp4")

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))
