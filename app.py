import os
import random
import sqlite3
import time
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, request, redirect, url_for, session, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = os.environ.get("DATABASE_PATH", "trading.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "535157")
UPLOAD_DIR = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

STYLE = """
<style>
*{box-sizing:border-box}body{margin:0;background:#07172e;color:#fff;font-family:Arial,sans-serif}
header{background:#102d55;padding:20px;text-align:center;border-bottom:2px solid #1685ff}
header h1{margin:0;color:#55adff}nav{margin-top:14px}nav a{color:white;text-decoration:none;margin:8px}
.container{max-width:900px;margin:28px auto;padding:18px}.card{background:#102b4d;padding:22px;border:1px solid #20548a;border-radius:14px;margin-bottom:18px;overflow-wrap:anywhere}
h2{color:#60b4ff}input,select,textarea{width:100%;padding:13px;margin:8px 0;border:1px solid #3475ae;border-radius:8px;background:#071b35;color:white;font-size:16px}
button,.btn{display:inline-block;background:#087cff;color:white;border:0;padding:12px 20px;border-radius:8px;text-decoration:none;cursor:pointer;font-size:16px;margin:7px 5px 5px 0}
button:hover,.btn:hover{background:#005dcc}.answer{display:block;width:100%;text-align:left;background:#173e68;color:white;padding:16px;margin:11px 0;border-radius:9px;border:1px solid #3475ae}
.muted{color:#a9c5e5}.good{color:#48e59b}.bad{color:#ff7777}.chart{width:100%;max-height:420px;object-fit:contain;background:#07172e;border-radius:10px;margin-top:15px}
table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #3475ae;text-align:left}
.small{font-size:13px;color:#a9c5e5}.timer{font-size:22px;font-weight:bold;color:#ffd166}
@media(max-width:600px){.container{padding:10px;margin:12px auto}.card{padding:15px}nav a{display:inline-block}table{font-size:12px}td,th{padding:6px 3px}}
</style>
"""

def db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def columns(con, table):
    return [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS tests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL)""")
    if "published" not in columns(con, "tests"):
        con.execute("ALTER TABLE tests ADD COLUMN published INTEGER NOT NULL DEFAULT 1")
    if "duration_minutes" not in columns(con, "tests"):
        con.execute("ALTER TABLE tests ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 20")
    con.execute("""CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,test_id INTEGER,question TEXT NOT NULL,
        image TEXT,a TEXT,b TEXT,c TEXT,correct TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS results(
        id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,test_title TEXT,
        score INTEGER,total INTEGER,date TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS answer_details(
        id INTEGER PRIMARY KEY AUTOINCREMENT,result_id INTEGER,question_text TEXT,
        selected TEXT,correct TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,full_name TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)""")
    con.execute("""CREATE TABLE IF NOT EXISTS test_permissions(
        student_id INTEGER NOT NULL,test_id INTEGER NOT NULL,allowed_attempts INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(student_id,test_id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS attempts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER NOT NULL,test_id INTEGER NOT NULL,
        started_at REAL NOT NULL,ends_at REAL NOT NULL,status TEXT NOT NULL DEFAULT 'in_progress',
        score INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,
        result_date TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS attempt_questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,attempt_id INTEGER NOT NULL,question_id INTEGER NOT NULL,
        position INTEGER NOT NULL,selected TEXT,answered INTEGER NOT NULL DEFAULT 0)""")
    con.commit()
    con.close()

def page(content, **kwargs):
    template = """<!DOCTYPE html><html lang="uz"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>Trading Test</title>""" + STYLE + """
    </head><body><header><h1>📈 TRADING TEST</h1><p>Bilimingizni sinab ko'ring</p>
    <nav><a href="/">Bosh sahifa</a><a href="/login">O'quvchi kirishi</a><a href="/admin">Admin</a></nav>
    </header><div class="container">{% with messages=get_flashed_messages() %}{% for message in messages %}
    <div class="card">{{message}}</div>{% endfor %}{% endwith %}""" + content + """</div></body></html>"""
    return render_template_string(template, **kwargs)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin"))
        return fn(*args, **kwargs)
    return wrapper

def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("student_id"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def finish_attempt(con, attempt_id):
    attempt = con.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    if not attempt or attempt["status"] != "in_progress":
        return
    rows = con.execute("""SELECT aq.id,aq.selected,q.correct FROM attempt_questions aq
        JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=?""", (attempt_id,)).fetchall()
    score = sum(1 for r in rows if r["selected"] == r["correct"])
    con.execute("UPDATE attempts SET status='finished',score=?,total=? WHERE id=?",
                (score, len(rows), attempt_id))
    con.commit()

def get_current_attempt(con):
    aid = session.get("attempt_id")
    if not aid:
        return None
    a = con.execute("SELECT * FROM attempts WHERE id=? AND student_id=?",
                    (aid, session.get("student_id"))).fetchone()
    if not a:
        return None
    if a["status"] == "in_progress" and time.time() >= a["ends_at"]:
        finish_attempt(con, aid)
        a = con.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
    return a

@app.route("/")
def home():
    con = db()
    tests = con.execute("""SELECT t.*,COUNT(q.id) AS count FROM tests t
        LEFT JOIN questions q ON q.test_id=t.id WHERE t.published=1
        GROUP BY t.id ORDER BY t.id DESC""").fetchall()
    con.close()
    content = """<div class="card"><h2>Trading bilimlaringizni sinang!</h2>
    <p class="muted">Testni ishlash uchun o'quvchi login-paroli bilan kiring.</p></div>
    {% for t in tests %}<div class="card"><h2>{{t.title}}</h2>
    <p>{{t.count}} ta savol · {{t.duration_minutes}} daqiqa</p>
    {% if t.count %}<a class="btn" href="/login">Kirish va testni ishlash</a>{% endif %}</div>
    {% else %}<div class="card">Hozircha test yo'q.</div>{% endfor %}"""
    return page(content, tests=tests)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        con = db()
        student = con.execute("SELECT * FROM students WHERE username=? AND active=1",
                              (username,)).fetchone()
        con.close()
        if student and check_password_hash(student["password_hash"], password):
            session.clear()
            session["student_id"] = student["id"]
            session["student_name"] = student["full_name"]
            return redirect(request.args.get("next") or url_for("student_home"))
        flash("Login yoki parol noto'g'ri.")
    return page("""<div class="card"><h2>O'quvchi kirishi</h2><form method="POST">
    <input name="username" placeholder="Login" required>
    <input type="password" name="password" placeholder="Parol" required>
    <button>KIRISH</button></form></div>""")

@app.route("/logout")
def student_logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/student")
@student_required
def student_home():
    con = db()
    tests = con.execute("""SELECT t.*,COUNT(q.id) count FROM tests t LEFT JOIN questions q
        ON q.test_id=t.id WHERE t.published=1 GROUP BY t.id ORDER BY t.id DESC""").fetchall()
    history = con.execute("""SELECT a.*,t.title FROM attempts a JOIN tests t ON t.id=a.test_id
        WHERE a.student_id=? ORDER BY a.id DESC""", (session["student_id"],)).fetchall()
    con.close()
    content = """<div class="card"><h2>Salom, {{name}}!</h2><a class="btn" href="/logout">Chiqish</a></div>
    <div class="card"><h2>Mavjud testlar</h2>{% for t in tests %}<p><b>{{t.title}}</b> —
    {{t.count}} savol, {{t.duration_minutes}} daqiqa
    {% if t.count %}<a class="btn" href="/test/{{t.id}}">Testni ochish</a>{% endif %}</p>
    {% else %}<p>Hozircha test yo'q.</p>{% endfor %}</div>
    <div class="card"><h2>Mening natijalarim</h2>{% for h in history %}
    <p>{{h.title}} — {% if h.status=='finished' %}{{h.score}}/{{h.total}} ·
    <a href="/my-result/{{h.id}}">Natijani ko'rish</a>{% else %}Jarayonda{% endif %}</p>
    {% else %}<p>Hali natija yo'q.</p>{% endfor %}</div>"""
    return page(content, name=session["student_name"], tests=tests, history=history)

@app.route("/test/<int:test_id>", methods=["GET", "POST"])
@student_required
def start_test(test_id):
    con = db()
    test = con.execute("SELECT * FROM tests WHERE id=? AND published=1", (test_id,)).fetchone()
    questions = con.execute("SELECT id FROM questions WHERE test_id=?", (test_id,)).fetchall()
    if not test or not questions:
        con.close()
        flash("Test topilmadi yoki savollar yo'q.")
        return redirect(url_for("student_home"))
    sid = session["student_id"]
    perm = con.execute("SELECT allowed_attempts FROM test_permissions WHERE student_id=? AND test_id=?",
                       (sid, test_id)).fetchone()
    allowed = perm["allowed_attempts"] if perm else 1
    used = con.execute("SELECT COUNT(*) FROM attempts WHERE student_id=? AND test_id=?",
                       (sid, test_id)).fetchone()[0]
    active = con.execute("""SELECT id FROM attempts WHERE student_id=? AND test_id=?
        AND status='in_progress' ORDER BY id DESC LIMIT 1""", (sid, test_id)).fetchone()
    if request.method == "POST":
        if active:
            con.close()
            session["attempt_id"] = active["id"]
            return redirect(url_for("take_question"))
        if used >= allowed:
            con.close()
            flash("Bu testni ishlash imkoniyatingiz tugagan. Admindan qayta ruxsat so'rang.")
            return redirect(url_for("student_home"))
        now = time.time()
        ends = now + int(test["duration_minutes"]) * 60
        cur = con.execute("""INSERT INTO attempts(student_id,test_id,started_at,ends_at,total)
            VALUES(?,?,?,?,?)""", (sid, test_id, now, ends, len(questions)))
        aid = cur.lastrowid
        qids = [q["id"] for q in questions]
        random.shuffle(qids)
        for pos, qid in enumerate(qids):
            con.execute("INSERT INTO attempt_questions(attempt_id,question_id,position) VALUES(?,?,?)",
                        (aid, qid, pos))
        con.commit()
        con.close()
        session["attempt_id"] = aid
        return redirect(url_for("take_question"))
    con.close()
    content = """<div class="card"><h2>{{test.title}}</h2><p>Vaqt: {{test.duration_minutes}} daqiqa.
    Savollar: {{count}} ta.</p><p>Testni boshlaganingizdan keyin vaqt yuradi. Bir marta topshirasiz.</p>
    <form method="POST"><button>TESTNI BOSHLASH</button></form></div>"""
    return page(content, test=test, count=len(questions))

@app.route("/question", methods=["GET", "POST"])
@student_required
def take_question():
    con = db()
    attempt = get_current_attempt(con)
    if not attempt:
        con.close()
        session.pop("attempt_id", None)
        return redirect(url_for("student_home"))
    if attempt["status"] == "finished":
        aid = attempt["id"]
        con.close()
        return redirect(url_for("my_result", attempt_id=aid))
    row = con.execute("""SELECT aq.*,q.question,q.image,q.a,q.b,q.c FROM attempt_questions aq
        JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=? AND aq.answered=0
        ORDER BY aq.position LIMIT 1""", (attempt["id"],)).fetchone()
    total = attempt["total"]
    answered = con.execute("SELECT COUNT(*) FROM attempt_questions WHERE attempt_id=? AND answered=1",
                           (attempt["id"],)).fetchone()[0]
    if not row:
        finish_attempt(con, attempt["id"])
        con.close()
        return redirect(url_for("my_result", attempt_id=attempt["id"]))
    if request.method == "POST":
        choice = request.form.get("answer")
        if choice not in ("A", "B", "C"):
            con.close()
            flash("Javobni tanlang.")
            return redirect(url_for("take_question"))
        con.execute("UPDATE attempt_questions SET selected=?,answered=1 WHERE id=? AND answered=0",
                    (choice, row["id"]))
        con.commit()
        remaining = con.execute("SELECT COUNT(*) FROM attempt_questions WHERE attempt_id=? AND answered=0",
                                 (attempt["id"],)).fetchone()[0]
        if remaining == 0:
            finish_attempt(con, attempt["id"])
            con.close()
            return redirect(url_for("my_result", attempt_id=attempt["id"]))
        con.close()
        return redirect(url_for("take_question"))
    con.close()
    seconds = max(0, int(attempt["ends_at"] - time.time()))
    content = """<div class="card"><h2>{{title}}</h2><p>O'quvchi: {{name}}</p>
    <p>Savol {{number}} / {{total}}</p><p class="timer">Qolgan vaqt: <span id="clock"></span></p>
    <div style="height:8px;background:#294768;border-radius:8px"><div style="height:8px;width:{{percent}}%;background:#1685ff;border-radius:8px"></div></div>
    <h2>{{q.question}}</h2>{% if q.image %}<img class="chart" src="{{q.image}}" alt="Savol rasmi">{% endif %}
    <form method="POST" id="answerForm">{% for letter in ['A','B','C'] %}
    <button class="answer" name="answer" value="{{letter}}" type="submit">{{letter}}. {{q[letter.lower()]}}</button>
    {% endfor %}</form></div>
    <script>
    let left={{seconds}};
    function tick(){let m=Math.floor(left/60),s=left%60;
    document.getElementById('clock').textContent=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
    if(left<=0){window.location.reload();return;}left--;setTimeout(tick,1000);}tick();
    </script>"""
    return page(content, title="Test", name=session["student_name"], number=answered+1,
                total=total, percent=int(answered/total*100) if total else 0,
                q=row, seconds=seconds)

@app.route("/my-result/<int:attempt_id>")
@student_required
def my_result(attempt_id):
    con = db()
    attempt = con.execute("""SELECT a.*,t.title FROM attempts a JOIN tests t ON t.id=a.test_id
        WHERE a.id=? AND a.student_id=?""", (attempt_id, session["student_id"])).fetchone()
    if not attempt:
        con.close()
        return redirect(url_for("student_home"))
    if attempt["status"] == "in_progress":
        con.close()
        session["attempt_id"] = attempt_id
        return redirect(url_for("take_question"))
    details = con.execute("""SELECT q.question,q.image,aq.selected,q.correct,q.a,q.b,q.c
        FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id
        WHERE aq.attempt_id=? ORDER BY aq.position""", (attempt_id,)).fetchall()
    con.close()
    pct = int(attempt["score"] / attempt["total"] * 100) if attempt["total"] else 0
    content = """<div class="card"><h2>Test yakunlandi</h2><h3>{{name}} — {{attempt.title}}</h3>
    <h1 style="font-size:48px;color:#55adff">{{pct}}%</h1><h2>{{attempt.score}} / {{attempt.total}}</h2>
    <p>Natija saqlangan. Uni o'zgartirib bo'lmaydi.</p></div>
    {% for d in details %}<div class="card"><b>{{loop.index}}. {{d.question}}</b>
    {% if d.image %}<img class="chart" src="{{d.image}}">{% endif %}
    <p>Sizning javobingiz: <b>{{d.selected}}</b></p>
    {% if d.selected==d.correct %}<p class="good">To'g'ri</p>{% else %}
    <p class="bad">Noto'g'ri. To'g'ri javob: {{d.correct}} — {{d[d.correct|lower]}}</p>{% endif %}
    </div>{% endfor %}<a class="btn" href="/student">Orqaga</a>"""
    return page(content, name=session["student_name"], attempt=attempt, details=details, pct=pct)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD:
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        flash("Admin kodi noto'g'ri.")
    return page("""<div class="card"><h2>Admin kirish</h2><form method="POST">
    <input type="password" name="password" placeholder="Admin kodi" required><button>KIRISH</button></form></div>""")

@app.route("/admin/panel")
@admin_required
def admin_panel():
    con = db()
    tests = con.execute("""SELECT t.*,COUNT(q.id) count FROM tests t LEFT JOIN questions q
        ON q.test_id=t.id GROUP BY t.id ORDER BY t.id DESC""").fetchall()
    students = con.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    pending = con.execute("""SELECT a.*,s.full_name,s.username,t.title FROM attempts a
        JOIN students s ON s.id=a.student_id JOIN tests t ON t.id=a.test_id
        WHERE a.status='finished' ORDER BY a.id DESC LIMIT 30""").fetchall()
    con.close()
    content = """<div class="card"><h2>Admin panel</h2>
    <a class="btn" href="/admin/add-student">+ O'quvchi yaratish</a>
    <a class="btn" href="/admin/add-test">+ Test yaratish</a>
    <a class="btn" href="/admin/add-question">+ Savol qo'shish</a>
    <a class="btn" href="/admin/results">Natijalar</a><a class="btn" href="/admin/logout">Chiqish</a></div>
    <div class="card"><h2>Testlar</h2>{% for t in tests %}<p><b>{{t.title}}</b> · {{t.count}} savol ·
    {{t.duration_minutes}} daqiqa · {% if t.published %}Ochiq{% else %}Yashirin{% endif %}
    <a href="/admin/publish/{{t.id}}/{{0 if t.published else 1}}">{{'Yashirish' if t.published else 'Chiqarish'}}</a></p>
    {% else %}<p>Test yo'q.</p>{% endfor %}</div>
    <div class="card"><h2>O'quvchilar</h2>{% for s in students %}<p>{{s.full_name}} ({{s.username}})
    — {% if s.active %}Faol{% else %}Bloklangan{% endif %}
    <a href="/admin/student/{{s.id}}">Boshqarish</a></p>{% else %}<p>O'quvchi yo'q.</p>{% endfor %}</div>
    <div class="card"><h2>Oxirgi topshirilgan testlar</h2>{% for a in pending %}
    <p>{{a.full_name}} — {{a.title}} — {{a.score}}/{{a.total}} ·
    <a href="/admin/student/{{a.student_id}}">Qayta ruxsat berish</a></p>{% endfor %}</div>"""
    return page(content, tests=tests, students=students, pending=pending)

@app.route("/admin/add-student", methods=["GET", "POST"])
@admin_required
def add_student():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        if not username or len(password) < 4 or not full_name:
            flash("Ism, login va kamida 4 belgili parol kiriting.")
        else:
            con = db()
            try:
                con.execute("INSERT INTO students(username,password_hash,full_name) VALUES(?,?,?)",
                            (username, generate_password_hash(password), full_name))
                con.commit()
                flash("O'quvchi yaratildi. Login-parolni o'quvchiga bering.")
                con.close()
                return redirect(url_for("admin_panel"))
            except sqlite3.IntegrityError:
                con.close()
                flash("Bu login band. Boshqa login tanlang.")
    return page("""<div class="card"><h2>O'quvchi yaratish</h2><form method="POST">
    <input name="full_name" placeholder="Ism-familiya" required>
    <input name="username" placeholder="Login" required>
    <input type="text" name="password" placeholder="Parol (kamida 4 belgi)" required>
    <button>O'QUVCHINI SAQLASH</button></form><a class="btn" href="/admin/panel">Orqaga</a></div>""")

@app.route("/admin/student/<int:student_id>", methods=["GET", "POST"])
@admin_required
def manage_student(student_id):
    con = db()
    student = con.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        con.close()
        return redirect(url_for("admin_panel"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "grant":
            test_id = int(request.form.get("test_id", "0"))
            con.execute("""INSERT INTO test_permissions(student_id,test_id,allowed_attempts)
                VALUES(?,?,2) ON CONFLICT(student_id,test_id)
                DO UPDATE SET allowed_attempts=allowed_attempts+1""", (student_id, test_id))
            con.commit()
            flash("O'quvchiga shu testni yana bir marta ishlash ruxsati berildi.")
        elif action == "toggle":
            con.execute("UPDATE students SET active=1-active WHERE id=?", (student_id,))
            con.commit()
        elif action == "password":
            new_password = request.form.get("new_password", "")
            if len(new_password) >= 4:
                con.execute("UPDATE students SET password_hash=? WHERE id=?",
                            (generate_password_hash(new_password), student_id))
                con.commit()
                flash("Parol yangilandi.")
        con.close()
        return redirect(url_for("manage_student", student_id=student_id))
    tests = con.execute("SELECT * FROM tests ORDER BY id DESC").fetchall()
    attempts = con.execute("""SELECT a.*,t.title FROM attempts a JOIN tests t ON t.id=a.test_id
        WHERE a.student_id=? ORDER BY a.id DESC""", (student_id,)).fetchall()
    con.close()
    content = """<div class="card"><h2>{{s.full_name}}</h2><p>Login: {{s.username}}</p>
    <form method="POST"><input type="hidden" name="action" value="toggle">
    <button>{{'Blokdan chiqarish' if not s.active else 'Bloklash'}}</button></form>
    <h3>Qayta test ishlashga ruxsat</h3><form method="POST"><input type="hidden" name="action" value="grant">
    <select name="test_id">{% for t in tests %}<option value="{{t.id}}">{{t.title}}</option>{% endfor %}</select>
    <button>YANA 1 MARTA RUXSAT BERISH</button></form>
    <h3>Parolni almashtirish</h3><form method="POST"><input type="hidden" name="action" value="password">
    <input name="new_password" placeholder="Yangi parol" required><button>PAROLNI SAQLASH</button></form></div>
    <div class="card"><h3>Test urinishlari</h3>{% for a in attempts %}
    <p>{{a.title}} — {{a.status}} — {{a.score}}/{{a.total}} — {{a.result_date}}</p>
    {% else %}<p>Urinish yo'q.</p>{% endfor %}</div><a class="btn" href="/admin/panel">Orqaga</a>"""
    return page(content, s=student, tests=tests, attempts=attempts)

@app.route("/admin/add-test", methods=["GET", "POST"])
@admin_required
def add_test():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        try:
            minutes = max(1, min(300, int(request.form.get("duration_minutes", "20"))))
        except ValueError:
            minutes = 20
        if title:
            con = db()
            con.execute("INSERT INTO tests(title,published,duration_minutes) VALUES(?,0,?)",
                        (title, minutes))
            con.commit()
            con.close()
            flash("Test saqlandi. Savollarni qo'shing, keyin testni o'quvchilarga chiqaring.")
            return redirect(url_for("admin_panel"))
    return page("""<div class="card"><h2>Yangi test</h2><form method="POST">
    <input name="title" placeholder="Test nomi" required>
    <label>Test vaqti (daqiqada)</label><input type="number" name="duration_minutes" value="20" min="1" max="300" required>
    <button>SAQLASH</button></form></div>""")

@app.route("/admin/add-question", methods=["GET", "POST"])
@admin_required
def add_question():
    con = db()
    tests = con.execute("SELECT * FROM tests ORDER BY id DESC").fetchall()
    if request.method == "POST":
        try:
            test_id = int(request.form.get("test_id", "0"))
        except ValueError:
            test_id = 0
        question = request.form.get("question", "").strip()
        a, b, c = [request.form.get(k, "").strip() for k in ("a", "b", "c")]
        correct = request.form.get("correct")
        image_url = request.form.get("image_url", "").strip()
        upload = request.files.get("image_file")
        image = image_url
        if upload and upload.filename:
            if allowed_image(upload.filename):
                filename = secure_filename(upload.filename)
                unique = f"{int(time.time()*1000)}_{filename}"
                upload.save(os.path.join(UPLOAD_DIR, unique))
                image = "/" + os.path.join(UPLOAD_DIR, unique).replace("\\", "/")
            else:
                flash("Rasm formati PNG, JPG, JPEG, GIF yoki WEBP bo'lishi kerak.")
                con.close()
                return redirect(url_for("add_question"))
        valid_test = con.execute("SELECT id FROM tests WHERE id=?", (test_id,)).fetchone()
        if valid_test and question and a and b and c and correct in ("A", "B", "C"):
            con.execute("""INSERT INTO questions(test_id,question,image,a,b,c,correct)
                VALUES(?,?,?,?,?,?,?)""", (test_id, question, image, a, b, c, correct))
            con.commit()
            con.close()
            flash("Savol saqlandi.")
            return redirect(url_for("admin_panel"))
        flash("Maydonlarni to'g'ri to'ldiring.")
    con.close()
    return page("""<div class="card"><h2>Savol qo'shish</h2>{% if tests %}<form method="POST"
    enctype="multipart/form-data"><label>Test</label><select name="test_id" required>
    {% for t in tests %}<option value="{{t.id}}">{{t.title}}</option>{% endfor %}</select>
    <textarea name="question" placeholder="Savol matni" required></textarea>
    <label>Kompyuterdan rasm yuklash</label><input type="file" name="image_file" accept="image/*">
    <p class="small">Yoki rasm internetda bo'lsa, uning URL manzilini kiriting:</p>
    <input name="image_url" placeholder="Rasm URL (ixtiyoriy)">
    <input name="a" placeholder="A javobi" required><input name="b" placeholder="B javobi" required>
    <input name="c" placeholder="C javobi" required><label>To'g'ri javob</label>
    <select name="correct"><option>A</option><option>B</option><option>C</option></select>
    <button>SAVOLNI SAQLASH</button></form>{% else %}<p>Avval test yarating.</p>{% endif %}</div>""", tests=tests)

@app.route("/admin/publish/<int:test_id>/<int:state>")
@admin_required
def publish_test(test_id, state):
    con = db()
    count = con.execute("SELECT COUNT(*) FROM questions WHERE test_id=?", (test_id,)).fetchone()[0]
    if state == 1 and count == 0:
        flash("Testni chiqarishdan oldin kamida bitta savol qo'shing.")
    else:
        con.execute("UPDATE tests SET published=? WHERE id=?", (1 if state else 0, test_id))
        con.commit()
        flash("Test holati o'zgartirildi.")
    con.close()
    return redirect(url_for("admin_panel"))

@app.route("/admin/results")
@admin_required
def admin_results():
    con = db()
    rows = con.execute("""SELECT a.*,s.full_name,s.username,t.title FROM attempts a
        JOIN students s ON s.id=a.student_id JOIN tests t ON t.id=a.test_id
        WHERE a.status='finished' ORDER BY a.id DESC""").fetchall()
    con.close()
    return page("""<div class="card"><h2>O'quvchilar natijalari</h2><table><tr><th>O'quvchi</th>
    <th>Test</th><th>Natija</th><th>Sana</th></tr>{% for r in rows %}<tr><td>{{r.full_name}}</td>
    <td>{{r.title}}</td><td>{{r.score}}/{{r.total}}</td><td>{{r.result_date}}</td></tr>
    {% else %}<tr><td colspan="4">Natija yo'q.</td></tr>{% endfor %}</table></div>""", rows=rows)

@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.errorhandler(413)
def too_large(_):
    return page("<div class='card'>Rasm hajmi 5 MB dan oshmasligi kerak.</div>"), 413

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
