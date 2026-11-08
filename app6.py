
import os
import sqlite3
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "trading_test_secret_2026")

DB = os.environ.get("DATABASE_PATH", "trading.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "535157")


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = connect()
    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            published INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            a TEXT NOT NULL,
            b TEXT NOT NULL,
            c TEXT NOT NULL,
            d TEXT NOT NULL,
            correct TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS answer_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            selected TEXT,
            correct TEXT NOT NULL,
            selected_text TEXT,
            correct_text TEXT
        )
    """)

    # Eski bazada published ustuni bo‘lmasa, qo‘shiladi.
    columns = [
        r["name"] for r in
        cur.execute("PRAGMA table_info(tests)").fetchall()
    ]

    if "published" not in columns:
        cur.execute(
            "ALTER TABLE tests ADD COLUMN published INTEGER NOT NULL DEFAULT 1"
        )

    db.commit()
    db.close()


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


BASE = """
<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradingTest</title>
<style>
* { box-sizing:border-box }
body {
    margin:0;
    background:#0b1220;
    color:#e8eefc;
    font-family:Arial,sans-serif;
}
.wrap { max-width:950px; margin:28px auto; padding:16px }
.card {
    background:#151f32;
    border:1px solid #263653;
    border-radius:14px;
    padding:18px;
    margin:12px 0;
}
h1,h2,h3 { color:white }
a { color:#8fc5ff; text-decoration:none }
input,textarea,select {
    width:100%;
    padding:12px;
    margin:7px 0 14px;
    border-radius:8px;
    border:1px solid #40516e;
    background:#0d1728;
    color:white;
}
button,.btn {
    display:inline-block;
    background:#2674df;
    color:white;
    border:0;
    border-radius:8px;
    padding:10px 15px;
    cursor:pointer;
    margin:4px 3px;
}
.secondary { background:#46546b }
.green { background:#16834b }
.red { background:#b63838 }
.muted { color:#aab8ce }
.option {
    display:block;
    padding:9px;
    background:#0d1728;
    border-radius:8px;
    margin:7px 0;
}
table { width:100%; border-collapse:collapse }
td,th {
    padding:10px;
    border-bottom:1px solid #34445f;
    text-align:left;
    vertical-align:top;
}
.flash {
    background:#493d1d;
    padding:10px;
    border-radius:8px;
    margin:8px 0;
}
</style>
</head>
<body>
<div class="wrap">
{% with messages = get_flashed_messages() %}
{% for m in messages %}
<div class="flash">{{m}}</div>
{% endfor %}
{% endwith %}
{{content|safe}}
</div>
</body>
</html>
"""


def page(content, **context):
    return render_template_string(
        BASE,
        content=render_template_string(content, **context)
    )


@app.route("/")
def home():
    db = connect()
    tests = db.execute(
        "SELECT * FROM tests WHERE published=1 ORDER BY id DESC"
    ).fetchall()
    db.close()

    return page("""
    <h1>TradingTest</h1>
    <div class="card">
        <h2>O‘quvchi bo‘limi</h2>
        {% if tests %}
            {% for t in tests %}
            <div class="card">
                <h3>{{t.title}}</h3>
                <a class="btn" href="{{url_for('take_test',test_id=t.id)}}">
                    Testni boshlash
                </a>
            </div>
            {% endfor %}
        {% else %}
            <p class="muted">Hozircha ochiq test yo‘q.</p>
        {% endif %}
    </div>
    <p><a href="{{url_for('admin_login')}}">Admin kirishi</a></p>
    """, tests=tests)


@app.route("/admin", methods=["GET", "POST"])
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        flash("Parol noto‘g‘ri!")

    return page("""
    <h1>Admin kirish</h1>
    <div class="card">
        <form method="post">
            <label>Admin paroli</label>
            <input type="password" name="password" required>
            <button>Kirish</button>
        </form>
    </div>
    <a href="/">Bosh sahifa</a>
    """)


@app.route("/admin/panel")
@admin_required
def admin_panel():
    db = connect()
    tests = db.execute("""
        SELECT t.*,
        (SELECT COUNT(*) FROM questions q WHERE q.test_id=t.id) AS qcount
        FROM tests t ORDER BY t.id DESC
    """).fetchall()
    db.close()

    return page("""
    <h1>Admin panel</h1>

    <p>
        <a class="btn green" href="{{url_for('add_test')}}">
            + Yangi test yaratish
        </a>
        <a class="btn secondary" href="{{url_for('all_results')}}">
            Natijalarni ko‘rish
        </a>
        <a class="btn red" href="{{url_for('admin_logout')}}">
            Chiqish
        </a>
    </p>

    {% for t in tests %}
    <div class="card">
        <h2>{{t.title}}</h2>
        <p>{{t.qcount}} ta savol</p>

        {% if t.published %}
            <b style="color:#65dc9b">O‘quvchilarga ochiq</b>
            <a class="btn red"
               href="{{url_for('publish_test',test_id=t.id,state=0)}}">
                Yashirish
            </a>
        {% else %}
            <b style="color:#ffce72">Yashirin</b>
            <a class="btn green"
               href="{{url_for('publish_test',test_id=t.id,state=1)}}">
                O‘quvchilarga chiqarish
            </a>
        {% endif %}

        <a class="btn" href="{{url_for('add_question',test_id=t.id)}}">
            Savol qo‘shish
        </a>
        <a class="btn secondary"
           href="{{url_for('test_results',test_id=t.id)}}">
            Natijalar
        </a>
    </div>
    {% else %}
        <p>Testlar hali yo‘q.</p>
    {% endfor %}
    """, tests=tests)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


@app.route("/admin/add-test", methods=["GET", "POST"])
@admin_required
def add_test():
    if request.method == "POST":
        title = request.form.get("title", "").strip()

        if title:
            db = connect()
            db.execute(
                "INSERT INTO tests(title,published) VALUES(?,0)",
                (title,)
            )
            db.commit()
            db.close()

            flash("Test saqlandi. Hozircha o‘quvchilarga ko‘rinmaydi.")
            return redirect(url_for("admin_panel"))

        flash("Test nomini kiriting.")

    return page("""
    <h1>Yangi test yaratish</h1>
    <div class="card">
        <form method="post">
            <label>Test nomi</label>
            <input name="title" required>
            <button>Saqlash</button>
        </form>
    </div>
    <a href="{{url_for('admin_panel')}}">Orqaga</a>
    """)


@app.route("/admin/add-question/<int:test_id>", methods=["GET", "POST"])
@admin_required
def add_question(test_id):
    db = connect()
    test = db.execute(
        "SELECT * FROM tests WHERE id=?",
        (test_id,)
    ).fetchone()

    if not test:
        db.close()
        return "Test topilmadi", 404

    if request.method == "POST":
        vals = [
            request.form.get(x, "").strip()
            for x in ("question", "a", "b", "c", "d", "correct")
        ]

        if all(vals) and vals[5] in ("A", "B", "C", "D"):
            db.execute("""
                INSERT INTO questions
                (test_id,question,a,b,c,d,correct)
                VALUES(?,?,?,?,?,?,?)
            """, (test_id, *vals))

            db.commit()
            db.close()

            flash("Savol saqlandi.")
            return redirect(url_for("add_question", test_id=test_id))

        flash("Barcha joylarni to‘ldiring va to‘g‘ri javobni tanlang.")

    questions = db.execute(
        "SELECT * FROM questions WHERE test_id=? ORDER BY id",
        (test_id,)
    ).fetchall()
    db.close()

    return page("""
    <h1>{{test.title}}</h1>

    <div class="card">
        <h2>Yangi savol</h2>
        <form method="post">
            <label>Savol</label>
            <textarea name="question" required></textarea>

            {% for key in ['a','b','c','d'] %}
                <label>{{key|upper}} javob</label>
                <input name="{{key}}" required>
            {% endfor %}

            <label>To‘g‘ri javob</label>
            <select name="correct">
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
            </select>

            <button>Saqlash</button>
        </form>
    </div>

    <h2>Qo‘shilgan savollar ({{questions|length}})</h2>

    {% for q in questions %}
    <div class="card">
        <b>{{loop.index}}. {{q.question}}</b>
        <p class="muted">To‘g‘ri javob: {{q.correct}}</p>
    </div>
    {% endfor %}

    <a href="{{url_for('admin_panel')}}">Admin panelga qaytish</a>
    """, test=test, questions=questions)


@app.route("/admin/publish/<int:test_id>/<int:state>")
@admin_required
def publish_test(test_id, state):
    db = connect()
    db.execute(
        "UPDATE tests SET published=? WHERE id=?",
        (1 if state else 0, test_id)
    )
    db.commit()
    db.close()

    flash("Test holati o‘zgartirildi.")
    return redirect(url_for("admin_panel"))


@app.route("/test/<int:test_id>", methods=["GET", "POST"])
def take_test(test_id):
    db = connect()

    test = db.execute(
        "SELECT * FROM tests WHERE id=? AND published=1",
        (test_id,)
    ).fetchone()

    if not test:
        db.close()
        return "Bu test mavjud emas yoki admin tomonidan ochilmagan.", 404

    questions = db.execute(
        "SELECT * FROM questions WHERE test_id=? ORDER BY id",
        (test_id,)
    ).fetchall()
    db.close()

    if not questions:
        return "Bu testda hali savollar yo‘q."

    if request.method == "POST":
        name = request.form.get("student_name", "").strip()

        if not name:
            flash("Ismingizni kiriting.")
            return redirect(url_for("take_test", test_id=test_id))

        answers = {}
        score = 0

        for q in questions:
            selected = request.form.get(str(q["id"]), "")
            answers[q["id"]] = selected

            if selected == q["correct"]:
                score += 1

        db = connect()

        cur = db.execute("""
            INSERT INTO results(test_id,student_name,score,total)
            VALUES(?,?,?,?)
        """, (test_id, name, score, len(questions)))

        result_id = cur.lastrowid

        for q in questions:
            selected = answers.get(q["id"], "")

            selected_text = (
                q[selected.lower()]
                if selected in ("A", "B", "C", "D")
                else ""
            )

            correct_text = q[q["correct"].lower()]

            db.execute("""
                INSERT INTO answer_details
                (result_id,question_id,question_text,selected,
                 correct,selected_text,correct_text)
                VALUES(?,?,?,?,?,?,?)
            """, (
                result_id,
                q["id"],
                q["question"],
                selected,
                q["correct"],
                selected_text,
                correct_text
            ))

        db.commit()
        db.close()

        return redirect(
            url_for("student_result", result_id=result_id)
        )

    return page("""
    <h1>{{test.title}}</h1>

    <div class="card">
        <form method="post">
            <label>Ismingiz</label>
            <input name="student_name" required>

            {% for q in questions %}
            <div class="card">
                <h3>{{loop.index}}. {{q.question}}</h3>

                {% for key in ['A','B','C','D'] %}
                <label class="option">
                    <input
                        style="width:auto;margin:0 8px 0 0"
                        type="radio"
                        name="{{q.id}}"
                        value="{{key}}">
                    {{key}}) {{q[key|lower]}}
                </label>
                {% endfor %}
            </div>
            {% endfor %}

            <button type="submit">Testni yakunlash</button>
        </form>
    </div>
    """, test=test, questions=questions)


@app.route("/student-result/<int:result_id>")
def student_result(result_id):
    db = connect()

    result = db.execute("""
        SELECT r.*, t.title
        FROM results r
        JOIN tests t ON t.id=r.test_id
        WHERE r.id=?
    """, (result_id,)).fetchone()

    db.close()

    if not result:
        return "Natija topilmadi", 404

    return page("""
    <div class="card">
        <h1>Test yakunlandi</h1>
        <h2>{{result.student_name}}</h2>
        <h3>{{result.title}}</h3>
        <p>Natija: <b>{{result.score}} / {{result.total}}</b></p>
        <a class="btn" href="/">Bosh sahifa</a>
    </div>
    """, result=result)


@app.route("/admin/results")
@admin_required
def all_results():
    db = connect()

    results = db.execute("""
        SELECT r.*, t.title
        FROM results r
        LEFT JOIN tests t ON t.id=r.test_id
        ORDER BY r.id DESC
    """).fetchall()

    db.close()

    return page("""
    <h1>Barcha natijalar</h1>

    <div class="card">
        <table>
            <tr>
                <th>O‘quvchi</th>
                <th>Test</th>
                <th>Ball</th>
                <th>Sana</th>
                <th></th>
            </tr>

            {% for r in results %}
            <tr>
                <td>{{r.student_name}}</td>
                <td>{{r.title or 'Test'}}</td>
                <td>{{r.score}}/{{r.total}}</td>
                <td>{{r.created_at or ''}}</td>
                <td>
                    <a href="{{url_for('result_detail',result_id=r.id)}}">
                        Javoblarni ko‘rish
                    </a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <a href="{{url_for('admin_panel')}}">Orqaga</a>
    """, results=results)


@app.route("/admin/results/<int:test_id>")
@admin_required
def test_results(test_id):
    db = connect()

    results = db.execute("""
        SELECT r.*,t.title
        FROM results r
        LEFT JOIN tests t ON t.id=r.test_id
        WHERE r.test_id=?
        ORDER BY r.id DESC
    """, (test_id,)).fetchall()

    db.close()

    return page("""
    <h1>{{results[0].title if results else 'Test natijalari'}}</h1>

    <div class="card">
        <table>
            <tr>
                <th>O‘quvchi</th>
                <th>Ball</th>
                <th>Sana</th>
                <th></th>
            </tr>

            {% for r in results %}
            <tr>
                <td>{{r.student_name}}</td>
                <td>{{r.score}}/{{r.total}}</td>
                <td>{{r.created_at or ''}}</td>
                <td>
                    <a href="{{url_for('result_detail',result_id=r.id)}}">
                        Javoblari
                    </a>
                </td>
            </tr>
            {% endfor %}
        </table>

        {% if not results %}
            <p>Hali natija yo‘q.</p>
        {% endif %}
    </div>

    <a href="{{url_for('admin_panel')}}">Orqaga</a>
    """, results=results)


@app.route("/admin/result/<int:result_id>")
@admin_required
def result_detail(result_id):
    db = connect()

    result = db.execute("""
        SELECT r.*,t.title
        FROM results r
        LEFT JOIN tests t ON t.id=r.test_id
        WHERE r.id=?
    """, (result_id,)).fetchone()

    details = db.execute("""
        SELECT * FROM answer_details
        WHERE result_id=?
        ORDER BY id
    """, (result_id,)).fetchall()

    db.close()

    if not result:
        return "Natija topilmadi", 404

    return page("""
    <h1>O‘quvchi javoblari</h1>

    <div class="card">
        <h2>{{result.student_name}}</h2>
        <p>{{result.title}} — {{result.score}}/{{result.total}}</p>
    </div>

    {% for d in details %}
    <div class="card">
        <h3>{{loop.index}}. {{d.question_text}}</h3>

        <p>
            O‘quvchi javobi:
            <b>{{d.selected or 'Javob berilmagan'}}</b>
            {% if d.selected_text %}
                — {{d.selected_text}}
            {% endif %}
        </p>

        <p>
            To‘g‘ri javob:
            <b>{{d.correct}}</b> — {{d.correct_text}}
        </p>

        {% if d.selected == d.correct %}
            <b style="color:#65dc9b">To‘g‘ri</b>
        {% else %}
            <b style="color:#ff7777">Noto‘g‘ri</b>
        {% endif %}
    </div>
    {% endfor %}

    <a href="{{url_for('all_results')}}">Natijalarga qaytish</a>
    """, result=result, details=details)


if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
