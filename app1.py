
from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import sqlite3
import random
from functools import wraps

app = Flask(__name__)
app.secret_key = "trading_test_secret_2026"

DB = "trading.db"
ADMIN_PASSWORD = "123456"

STYLE = """
<style>
* {box-sizing:border-box}
body {
    margin:0; background:#07172e; color:#fff;
    font-family:Arial,sans-serif;
}
header {
    background:#102d55; padding:22px;
    text-align:center; border-bottom:2px solid #1685ff;
}
header h1 {margin:0;color:#55adff}
nav {margin-top:15px}
nav a {color:white;text-decoration:none;margin:8px}
.container {
    max-width:850px;margin:35px auto;padding:25px;
}
.card {
    background:#102b4d;padding:25px;
    border:1px solid #20548a;border-radius:15px;
    margin-bottom:20px;
}
h2 {color:#60b4ff}
input,select {
    width:100%;padding:14px;margin:9px 0;
    border:1px solid #3475ae;border-radius:8px;
    background:#071b35;color:white;font-size:16px;
}
button,.btn {
    display:inline-block;background:#087cff;
    color:white;border:0;padding:13px 22px;
    border-radius:8px;text-decoration:none;
    cursor:pointer;font-size:16px;margin-top:10px;
}
button:hover,.btn:hover {background:#005dcc}
.answer {
    display:block;background:#173e68;
    color:white;padding:17px;margin:12px 0;
    border-radius:9px;text-decoration:none;
    border:1px solid #3475ae;
}
.answer:hover {background:#087cff}
.muted {color:#a9c5e5}
.good {color:#48e59b}
.bad {color:#ff7777}
img.chart {width:100%;max-height:350px;object-fit:contain;
background:#07172e;border-radius:10px;margin-top:15px}
table {width:100%;border-collapse:collapse}
td,th {padding:12px;border-bottom:1px solid #3475ae;text-align:left}
@media(max-width:600px) {
 .container {padding:12px;margin:15px auto}
 .card {padding:17px}
 nav a {display:inline-block}
}
</style>
"""

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            question TEXT NOT NULL,
            image TEXT,
            a TEXT,
            b TEXT,
            c TEXT,
            correct TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            test_title TEXT,
            score INTEGER,
            total INTEGER,
            date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

def page(content, **kwargs):
    template = """
    <!DOCTYPE html>
    <html lang="uz">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Trading Test</title>
    """ + STYLE + """
    </head>
    <body>
    <header>
      <h1>📈 TRADING TEST</h1>
      <p>Bilimingizni sinab ko'ring</p>
      <nav>
        <a href="/">Bosh sahifa</a>
        <a href="/admin">Admin</a>
      </nav>
    </header>
    <div class="container">
    {% with messages = get_flashed_messages() %}
      {% for message in messages %}
        <div class="card">{{ message }}</div>
      {% endfor %}
    {% endwith %}
    """ + content + """
    </div>
    </body></html>
    """
    return render_template_string(template, **kwargs)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    con = db()
    tests = con.execute("""
        SELECT tests.*, COUNT(questions.id) AS count
        FROM tests LEFT JOIN questions
        ON tests.id=questions.test_id
        GROUP BY tests.id
    """).fetchall()
    con.close()

    content = """
    <div class="card" style="text-align:center">
      <h2>Trading bilimlaringizni sinang!</h2>
      <p class="muted">Grafiklarni tahlil qiling va to'g'ri javobni toping.</p>
      <h3>📊 TESTLAR</h3>
    </div>
    {% for t in tests %}
      <div class="card">
        <h2>{{t.title}}</h2>
        <p class="muted">{{t.count}} ta savol</p>
        {% if t.count > 0 %}
          <a class="btn" href="/test/{{t.id}}">Testga kirish</a>
        {% else %}
          <p class="muted">Hozircha savol yo'q</p>
        {% endif %}
      </div>
    {% else %}
      <div class="card">Hozircha test mavjud emas.</div>
    {% endfor %}
    """
    return page(content, tests=tests)

@app.route("/test/<int:test_id>", methods=["GET","POST"])
def start_test(test_id):
    con = db()
    test = con.execute(
        "SELECT * FROM tests WHERE id=?", (test_id,)
    ).fetchone()
    questions = con.execute(
        "SELECT id FROM questions WHERE test_id=?", (test_id,)
    ).fetchall()
    con.close()

    if not test or not questions:
        flash("Test topilmadi yoki savollar mavjud emas.")
        return redirect("/")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Ismingizni kiriting.")
            return redirect(url_for("start_test", test_id=test_id))

        ids = [q["id"] for q in questions]
        random.shuffle(ids)
        session["name"] = name
        session["test_id"] = test_id
        session["test_title"] = test["title"]
        session["ids"] = ids
        session["index"] = 0
        session["score"] = 0
        session["answers"] = []
        return redirect(url_for("question"))

    content = """
    <div class="card">
      <h2>{{test.title}}</h2>
      <p>Testni boshlash uchun ismingizni kiriting.</p>
      <form method="POST">
        <input name="name" placeholder="Ismingiz" required>
        <button type="submit">TESTNI BOSHLASH</button>
      </form>
    </div>
    """
    return page(content, test=test)

@app.route("/question")
def question():
    ids = session.get("ids")
    index = session.get("index", 0)

    if not ids or index >= len(ids):
        return redirect(url_for("result"))

    con = db()
    q = con.execute(
        "SELECT * FROM questions WHERE id=?", (ids[index],)
    ).fetchone()
    con.close()

    if not q:
        return redirect(url_for("result"))

    content = """
    <div class="card">
      <h2>{{title}}</h2>
      <p class="muted">O'quvchi: {{name}}</p>
      <p>Savol {{number}} / {{total}}</p>
      <div style="height:8px;background:#294768;border-radius:8px">
        <div style="height:8px;width:{{percent}}%;background:#1685ff;border-radius:8px"></div>
      </div>
      <h2>{{q.question}}</h2>
      {% if q.image %}
        <img class="chart" src="{{q.image}}" alt="Trading grafik">
      {% endif %}
      <form method="POST" action="/answer">
        {% for letter in ['A','B','C'] %}
          <button class="answer" style="width:100%;text-align:left"
                  name="answer" value="{{letter}}" type="submit">
            {{letter}}. {{q[letter.lower()]}}
          </button>
        {% endfor %}
      </form>
    </div>
    """
    return page(
        content, q=q, title=session.get("test_title"),
        name=session.get("name"), number=index+1,
        total=len(ids), percent=int((index/len(ids))*100)
    )

@app.route("/answer", methods=["POST"])
def answer():
    ids = session.get("ids")
    index = session.get("index", 0)
    if not ids or index >= len(ids):
        return redirect("/")

    selected = request.form.get("answer")
    con = db()
    q = con.execute(
        "SELECT correct FROM questions WHERE id=?", (ids[index],)
    ).fetchone()
    con.close()

    if q and selected == q["correct"]:
        session["score"] = session.get("score", 0) + 1

    session["index"] = index + 1

    if session["index"] >= len(ids):
        return redirect(url_for("result"))
    return redirect(url_for("question"))

@app.route("/result")
def result():
    ids = session.get("ids")
    if not ids:
        return redirect("/")

    name = session.get("name", "O'quvchi")
    title = session.get("test_title", "Test")
    score = session.get("score", 0)
    total = len(ids)
    percent = int(score / total * 100) if total else 0

    con = db()
    con.execute(
        "INSERT INTO results(name,test_title,score,total) VALUES(?,?,?,?)",
        (name, title, score, total)
    )
    con.commit()
    con.close()

    session.pop("ids", None)

    content = """
    <div class="card" style="text-align:center">
      <h2>🏆 TEST YAKUNLANDI!</h2>
      <h3>{{name}}</h3>
      <h1 style="font-size:55px;color:#55adff">{{percent}}%</h1>
      <h2>{{score}} / {{total}}</h2>
      {% if percent >= 60 %}
        <h2 class="good">Tabriklaymiz! Testdan o'tdingiz!</h2>
      {% else %}
        <h2 class="bad">Yana mashq qiling!</h2>
      {% endif %}
      <a class="btn" href="/">Bosh sahifa</a>
    </div>
    """
    return page(content, name=name, score=score,
                total=total, percent=percent)

@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/panel")
        flash("Admin kodi noto'g'ri!")

    content = """
    <div class="card">
      <h2>🔐 ADMIN KIRISH</h2>
      <form method="POST">
        <input type="password" name="password"
               placeholder="Admin kodi" required>
        <button>KIRISH</button>
      </form>
    </div>
    """
    return page(content)

@app.route("/admin/panel")
@admin_required
def admin_panel():
    con = db()
    tests = con.execute("SELECT * FROM tests ORDER BY id DESC").fetchall()
    questions = con.execute("""
        SELECT questions.*, tests.title AS test_title
        FROM questions JOIN tests ON tests.id=questions.test_id
        ORDER BY questions.id DESC
    """).fetchall()
    results = con.execute(
        "SELECT * FROM results ORDER BY id DESC LIMIT 50"
    ).fetchall()
    con.close()

    content = """
    <div class="card">
      <h2>Admin boshqaruv paneli</h2>
      <a class="btn" href="/admin/add-test">+ Yangi test yaratish</a>
      <a class="btn" href="/admin/add-question">+ Savol qo'shish</a>
      <a class="btn" href="/admin/results">Natijalar</a>
      <a class="btn" href="/admin/logout">Chiqish</a>
    </div>
    <div class="card">
      <h2>Mavjud testlar</h2>
      {% for t in tests %}
        <p>{{t.title}} — <a href="/admin/delete-test/{{t.id}}"
        onclick="return confirm('Testni o‘chirasizmi?')">O'chirish</a></p>
      {% else %}<p>Test yo'q</p>{% endfor %}
    </div>
    """
    return page(content, tests=tests, questions=questions, results=results)

@app.route("/admin/add-test", methods=["GET","POST"])
@admin_required
def add_test():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if title:
            con = db()
            con.execute("INSERT INTO tests(title) VALUES(?)", (title,))
            con.commit()
            con.close()
            flash("Yangi test yaratildi!")
            return redirect("/admin/panel")

    content = """
    <div class="card">
      <h2>Yangi test yaratish</h2>
      <form method="POST">
        <input name="title" placeholder="Masalan: BOS va CHOCH" required>
        <button>SAQLASH</button>
      </form>
    </div>
    """
    return page(content)

@app.route("/admin/add-question", methods=["GET","POST"])
@admin_required
def add_question():
    con = db()
    tests = con.execute("SELECT * FROM tests").fetchall()

    if request.method == "POST":
        test_id = request.form.get("test_id")
        question = request.form.get("question", "").strip()
        image = request.form.get("image", "").strip()
        a = request.form.get("a", "").strip()
        b = request.form.get("b", "").strip()
        c = request.form.get("c", "").strip()
        correct = request.form.get("correct")

        if test_id and question and a and b and c and correct:
            con.execute("""
                INSERT INTO questions(test_id,question,image,a,b,c,correct)
                VALUES(?,?,?,?,?,?,?)
            """, (test_id, question, image, a, b, c, correct))
            con.commit()
            con.close()
            flash("Savol saqlandi!")
            return redirect("/admin/panel")

    con.close()
    content = """
    <div class="card">
      <h2>Yangi savol qo'shish</h2>
      <form method="POST">
        <label>Testni tanlang</label>
        <select name="test_id" required>
          {% for t in tests %}
            <option value="{{t.id}}">{{t.title}}</option>
          {% endfor %}
        </select>
        <input name="question" placeholder="Savol matni" required>
        <input name="image" placeholder="Grafik rasmi URL (ixtiyoriy)">
        <input name="a" placeholder="A javobi" required>
        <input name="b" placeholder="B javobi" required>
        <input name="c" placeholder="C javobi" required>
        <label>To'g'ri javob</label>
        <select name="correct">
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
        </select>
        <button>SAVOLNI SAQLASH</button>
      </form>
    </div>
    """
    return page(content, tests=tests)

@app.route("/admin/results")
@admin_required
def admin_results():
    con = db()
    results = con.execute(
        "SELECT * FROM results ORDER BY id DESC"
    ).fetchall()
    con.close()

    content = """
    <div class="card">
      <h2>📊 O'quvchilar natijalari</h2>
      <table>
        <tr><th>Ism</th><th>Test</th><th>Natija</th><th>Vaqt</th></tr>
        {% for r in results %}
        <tr>
          <td>{{r.name}}</td>
          <td>{{r.test_title}}</td>
          <td>{{r.score}}/{{r.total}}</td>
          <td>{{r.date}}</td>
        </tr>
        {% endfor %}
      </table>
      <a class="btn" href="/admin/panel">Orqaga</a>
    </div>
    """
    return page(content, results=results)

@app.route("/admin/delete-test/<int:test_id>")
@admin_required
def delete_test(test_id):
    con = db()
    con.execute("DELETE FROM questions WHERE test_id=?", (test_id,))
    con.execute("DELETE FROM tests WHERE id=?", (test_id,))
    con.commit()
    con.close()
    flash("Test o'chirildi.")
    return redirect("/admin/panel")

@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
