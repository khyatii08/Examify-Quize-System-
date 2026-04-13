from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import pdfkit
from flask import make_response

app = Flask(__name__)
app.secret_key = "exam_secret_key"

# ================= DATABASE CONNECTION =================
def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="exam_db",
        cursorclass=pymysql.cursors.DictCursor
    )

# ================= HOME PAGE =================
@app.route('/')
def home():
    return render_template("home.html")

# ================= ABOUT PAGE =================
@app.route('/about')
def about():
    return render_template("about.html")

# ================= CONTACT PAGE =================
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contact_messages (name, email, message)
            VALUES (%s, %s, %s)
        """, (request.form['name'], request.form['email'], request.form['message']))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Message sent successfully!", "success")
        return redirect(url_for('contact'))
    return render_template("contact.html")

# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already registered", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('register'))

        cursor.execute("""
            INSERT INTO users (username, email, password, is_verified)
            VALUES (%s,%s,%s,1)
        """, (username, email, password))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration Successful! Please Login.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE username=%s AND password=%s
        """, (username, password))

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Credentials", "danger")

    return render_template("login.html")

# ================= DASHBOARD =================
@app.route('/dashboard')
@app.route('/dashboard/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("dashboard.html", subjects=subjects)

# ================= START EXAM =================
@app.route('/start_exam/<int:subject_id>')
def start_exam(subject_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM subjects WHERE id=%s", (subject_id,))
    subject = cursor.fetchone()

    if not subject:
        cursor.close()
        conn.close()
        return "Subject not found!"

    cursor.execute("SELECT * FROM questions WHERE subject_id=%s", (subject_id,))
    questions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("exam.html", subject=subject, questions=questions)

# ================= SUBMIT EXAM =================
@app.route('/submit_exam', methods=['POST'])
def submit_exam():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    subject_id = request.form['subject_id']
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions WHERE subject_id=%s", (subject_id,))
    questions = cursor.fetchall()

    score = 0
    for question in questions:
        selected = request.form.get(f"q{question['id']}")
        correct = question['correct_answer']

        if selected and correct:
            if selected.strip().lower() == correct.strip().lower():
                score += 1

    total = len(questions)
    percentage = round((score / total) * 100, 2) if total > 0 else 0

    cursor.execute("""
        INSERT INTO results (user_id, subject_id, score, total, percentage, exam_date)
        VALUES (%s,%s,%s,%s,%s,NOW())
    """, (user_id, subject_id, score, total, percentage))

    conn.commit()
    result_id = cursor.lastrowid

    cursor.close()
    conn.close()

    return redirect(url_for('result_page', result_id=result_id))

# ================= RESULT PAGE =================
@app.route('/result/<int:result_id>')
def result_page(result_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, s.subject_name
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        WHERE r.id=%s AND r.user_id=%s
    """, (result_id, session['user_id']))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return "Result not found!"

    return render_template("result.html", result=result)

# ================= HISTORY PAGE =================
@app.route('/history')
def history():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, s.subject_name
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        WHERE r.user_id=%s
        ORDER BY r.exam_date DESC
    """, (session['user_id'],))

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("history.html", results=results)

# ================= CLIENT CERTIFICATE =================
@app.route('/certificate/<int:result_id>')
def certificate(result_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, u.username, s.subject_name
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN subjects s ON r.subject_id = s.id
        WHERE r.id=%s AND r.user_id=%s
    """, (result_id, session['user_id']))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return "Result not found!"

    return render_template("certificate.html", result=result, role="client")

# ================= CERTIFICATE PDF VIEW =================
@app.route('/certificate/pdf/<int:result_id>')
def certificate_pdf(result_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, u.username, s.subject_name
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN subjects s ON r.subject_id = s.id
        WHERE r.id=%s AND r.user_id=%s
    """, (result_id, session['user_id']))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return "Result not found!"

    rendered = render_template("certificate.html", result=result, role="client")

    config = pdfkit.configuration(
        wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    )

    pdf = pdfkit.from_string(rendered, False, configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=certificate.pdf'

    return response
# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))

# ================= ADMIN ROUTES =================

# ================= ADMIN LOGIN =================
@app.route('/admin', methods=['GET', 'POST'])
@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM admin
            WHERE username=%s AND password=%s
        """, (request.form['username'], request.form['password']))

        admin_user = cursor.fetchone()
        cursor.close()
        conn.close()

        if admin_user:
            session['admin'] = admin_user['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid Admin Login")

    return render_template("admin/admin_login.html")


# ADMIN DASHBOARD
@app.route("/admin/admin_dashboard")
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM subjects")
    total_subjects = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM questions")
    total_questions = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM contact_messages")
    total_contacts = cursor.fetchone()['total']

    cursor.close()
    conn.close()

    return render_template(
        "admin/admin_dashboard.html",
        total_users=total_users,
        total_subjects=total_subjects,
        total_questions=total_questions,
        total_contacts=total_contacts
    )


#  MANAGE USERS 
@app.route('/admin/manage_users')
def manage_users():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users ORDER BY id DESC")
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/manage_users.html", users=users)


@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE users SET username=%s, email=%s WHERE id=%s
        """, (request.form['username'], request.form['email'], user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('manage_users'))

    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/edit_user.html", user=user)


@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('manage_users'))


#  MANAGE SUBJECTS 
@app.route('/admin/manage_subjects', methods=['GET', 'POST'])
def manage_subjects():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute(
            "INSERT INTO subjects (subject_name) VALUES (%s)",
            (request.form['subject_name'],)
        )
        conn.commit()

    cursor.execute("SELECT * FROM subjects ORDER BY id DESC")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/manage_subjects.html", subjects=subjects)


@app.route('/admin/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute(
            "UPDATE subjects SET subject_name=%s WHERE id=%s",
            (request.form['subject_name'], subject_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('manage_subjects'))

    cursor.execute("SELECT * FROM subjects WHERE id=%s", (subject_id,))
    subject = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/edit_subject.html", subject=subject)


@app.route('/admin/delete_subject/<int:subject_id>')
def delete_subject(subject_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM subjects WHERE id=%s", (subject_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('manage_subjects'))

# MANAGE QUESTIONS 
@app.route('/admin/manage_questions', methods=['GET', 'POST'])
def manage_questions():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # ADD QUESTION
    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO questions
            (subject_id, question, option1, option2, option3, option4, correct_answer)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form['subject_id'],
            request.form['question'],
            request.form['option1'],
            request.form['option2'],
            request.form['option3'],
            request.form['option4'],
            request.form['correct_answer']
        ))
        conn.commit()

    # GET ALL QUESTIONS
    cursor.execute("""
        SELECT q.*, s.subject_name
        FROM questions q
        JOIN subjects s ON q.subject_id = s.id
        ORDER BY q.id DESC
    """)
    questions = cursor.fetchall()

    # GET ALL SUBJECTS
    cursor.execute("SELECT * FROM subjects ORDER BY id DESC")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/manage_questions.html",
        questions=questions,
        subjects=subjects
    )


#  EDIT QUESTION 
@app.route("/admin/edit_question/<int:question_id>", methods=["GET", "POST"])
def edit_question(question_id):

    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        cursor.execute("""
            UPDATE questions
            SET subject_id=%s,
                question=%s,
                option1=%s,
                option2=%s,
                option3=%s,
                option4=%s,
                correct_answer=%s
            WHERE id=%s
        """, (
            request.form["subject_id"],
            request.form["question"],
            request.form["option1"],
            request.form["option2"],
            request.form["option3"],
            request.form["option4"],
            request.form["correct_answer"],
            question_id
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("manage_questions"))

    # LOAD QUESTION
    cursor.execute("SELECT * FROM questions WHERE id=%s", (question_id,))
    question = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/edit_question.html", question=question)


#  DELETE QUESTION 
@app.route('/admin/delete_question/<int:question_id>')
def delete_question(question_id):

    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM questions WHERE id=%s", (question_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('manage_questions'))


# ================= MANAGE CONTACTS =================
@app.route('/admin/manage_contacts')
def manage_contacts():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM contact_messages ORDER BY id DESC")
    contacts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/manage_contacts.html", contacts=contacts)


# ================= DELETE CONTACT =================
@app.route('/admin/delete_contact/<int:contact_id>')
def delete_contact(contact_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM contact_messages WHERE id=%s", (contact_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Message deleted successfully!", "success")
    return redirect(url_for('manage_contacts'))


# ================= REPLY CONTACT =================
@app.route("/admin/reply_contact/<int:contact_id>", methods=["POST"])
def reply_contact(contact_id):

    if 'admin' not in session:
        return redirect(url_for('admin'))

    subject = request.form["subject"]
    message_body = request.form["message"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM contact_messages WHERE id=%s", (contact_id,))
    contact = cursor.fetchone()

    if not contact:
        flash("Contact not found!", "danger")
        return redirect(url_for("manage_contacts"))

    # ===== EMAIL CONFIGURATION =====
    sender_email = "ashokbhaichauhan086@gmail.com"
    sender_password = "iqmirucfwuwffytp"  

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = contact["email"]
        msg["Subject"] = subject

        msg.attach(MIMEText(message_body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()

        flash("Reply sent successfully!", "success")

    except Exception as e:
        flash("Error sending email: " + str(e), "danger")

    cursor.close()
    conn.close()

    return redirect(url_for("manage_contacts"))

# ================= ADMIN VIEW ALL RESULTS =================
@app.route('/admin/manage_results')
def manage_results():

    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT r.*, u.username, s.subject_name
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN subjects s ON r.subject_id = s.id
        ORDER BY r.exam_date DESC
    """)

    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/manage_results.html", results=results)
# ================= EDIT RESULTS =================
@app.route('/admin/result/edit/<int:result_id>', methods=['GET', 'POST'])
def edit_result(result_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == 'POST':
        # Get data from the form
        user_id = request.form['user_id']
        subject_id = request.form['subject_id']
        score = request.form['score']
        total = request.form['total']
        
        # Update logic using raw SQL
        cursor.execute("""
            UPDATE results 
            SET user_id = %s, subject_id = %s, score = %s, total = %s 
            WHERE id = %s
        """, (user_id, subject_id, score, total, result_id))
        
        conn.commit()
        cursor.close()
        conn.close()

        flash("Result updated successfully", "success")
        return redirect(url_for('manage_results'))

    # GET request: Fetch the specific result to pre-fill the form
    cursor.execute("SELECT * FROM results WHERE id = %s", (result_id,))
    result = cursor.fetchone()

    # Fetch users and subjects for the dropdown menus (like in add_result)
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT id, subject_name FROM subjects")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/edit_result.html', result=result, users=users, subjects=subjects)# ================= ADMIN DELETE RESULT =================

    @app.route('/admin/delete_result/<int:result_id>')
    def delete_result(result_id):

        if 'admin' not in session:
          return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM results WHERE id=%s", (result_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Result deleted successfully!", "success")

    return redirect(url_for('manage_results'))

# ================= ADD NEW RESULT =================
@app.route('/admin/result/add', methods=['GET', 'POST'])
def add_result():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == 'POST':
        user_id = request.form['user_id']
        subject_id = request.form['subject_id']
        score = request.form['score']
        total = request.form['total']
        exam_date = request.form['exam_date']

        cursor.execute("""
            INSERT INTO results (user_id, subject_id, score, total, exam_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, subject_id, score, total, exam_date))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Result added successfully!", "success")
        return redirect(url_for('manage_results'))

    # Fetch users and subjects for the form dropdown
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT id, subject_name FROM subjects")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/add_result.html', users=users, subjects=subjects)

@app.route('/admin/certificate/<int:result_id>')
def admin_certificate(result_id):

    if 'admin' not in session:
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, u.username, s.subject_name
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN subjects s ON r.subject_id = s.id
        WHERE r.id=%s
    """, (result_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return "Result not found!"

    return render_template("admin/admin_certificate.html", result=result)

# ================= ADMIN LOGOUT =================
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin'))


# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)
    