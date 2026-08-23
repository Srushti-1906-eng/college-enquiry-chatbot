from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import joblib
from spellchecker import SpellChecker
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from flask_session import Session

from database import get_connection


app = Flask(__name__)

spell = SpellChecker()

app.secret_key = "college_chatbot_secret"

app.config["SESSION_TYPE"] = "filesystem"
Session(app)

stemmer = PorterStemmer()


# =========================================================
# SAVE CHAT
# =========================================================

def save_chat(user_message, bot_reply):

    connection = get_connection()

    if connection is None:
        return

    cursor = connection.cursor()

    sql = """
    INSERT INTO chat_history (user_message, bot_reply)
    VALUES (%s, %s)
    """

    cursor.execute(sql, (user_message, bot_reply))
    connection.commit()

    cursor.close()
    connection.close()

# =========================================================
# LOAD AI MODEL
# =========================================================

model = joblib.load("model/model.pkl")
vectorizer = joblib.load("model/vectorizer.pkl")
encoder = joblib.load("model/label_encoder.pkl")


# =========================================================
# LOAD INTENTS
# =========================================================

with open("intents.json", "r") as file:
    intents = json.load(file)


# =========================================================
# SPELLING CORRECTION
# =========================================================

def correct_spelling(text):

    words = text.split()

    corrected = [
        spell.correction(word) or word
        for word in words
    ]

    return " ".join(corrected)


# =========================================================
# CHATBOT RESPONSE
# =========================================================

def get_response(user_input):

    # Convert input to lowercase
    user_input = user_input.strip().lower()


    # -----------------------------------------------------
    # HANDLE GREETINGS
    # -----------------------------------------------------

    greetings = {

        "hi":
        "Hi! Welcome to ACPCE. What would you like to know?",

        "hii":
        "Hi! Welcome to ACPCE. What would you like to know?",

        "hiii":
        "Hi! Welcome to ACPCE. What would you like to know?",

        "hello":
        "Hello! Welcome to the A. C. Patil College of Engineering enquiry chatbot. How can I help you?",

        "hey":
        "Hey! Welcome to the ACPCE enquiry chatbot. Ask me about admissions, courses, fees, location, facilities or placements."
    }


    if user_input in greetings:

        return greetings[user_input]


    # -----------------------------------------------------
    # SPELLING CORRECTION
    # -----------------------------------------------------

    corrected_input = correct_spelling(user_input)

    print("Original:", user_input)
    print("Corrected:", corrected_input)


    # -----------------------------------------------------
    # TOKENIZATION + STEMMING
    # -----------------------------------------------------

    words = word_tokenize(corrected_input.lower())

    words = [
        stemmer.stem(word)
        for word in words
        if word.isalnum()
    ]

    processed_text = " ".join(words)

    print("Processed:", processed_text)


    # -----------------------------------------------------
    # AI PREDICTION
    # -----------------------------------------------------

    X = vectorizer.transform([processed_text])

    prediction = model.predict(X)[0]

    tag = encoder.inverse_transform([prediction])[0]

    print("Predicted Tag:", tag)


    # -----------------------------------------------------
    # FIND INTENT
    # -----------------------------------------------------

    for intent in intents["intents"]:

        if intent["tag"] == tag:

            return intent["response"]


    return "Sorry, I couldn't understand your question."


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]


        connection = get_connection()

        if connection is None:
            return "Database connection failed."


        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO students(name, email, password)
            VALUES(%s,%s,%s)
            """,
            (name, email, password)
        )

        connection.commit()

        cursor.close()
        connection.close()


        return redirect(url_for("login"))


    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]


        connection = get_connection()

        if connection is None:
            return "Database connection failed."


        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT * FROM students
            WHERE email=%s AND password=%s
            """,
            (email, password)
        )

        student = cursor.fetchone()


        cursor.close()
        connection.close()


        if student:

            session["student_id"] = student["id"]

            session["student_name"] = student["name"]

            return redirect(url_for("chatbot"))

        else:

            return "Invalid Email or Password"


    return render_template("login.html")


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]


        connection = get_connection()

        if connection is None:
            return "Database connection failed."


        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT * FROM admin
            WHERE username=%s AND password=%s
            """,
            (username, password)
        )

        admin = cursor.fetchone()


        cursor.close()
        connection.close()


        if admin:

            session["admin"] = admin["username"]

            return redirect(url_for("admin_dashboard"))

        else:

            return "Invalid Admin Login"


    return render_template("admin_login.html")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:

        return redirect(url_for("admin_login"))


    search = request.args.get("search")


    connection = get_connection()

    if connection is None:
        return "Database connection failed."


    cursor = connection.cursor(dictionary=True)


    # -----------------------------------------------------
    # SEARCH CHATS
    # -----------------------------------------------------

    if search:

        cursor.execute(
            """
            SELECT * FROM chat_history
            WHERE question LIKE %s
            ORDER BY id DESC
            """,
            ("%" + search + "%",)
        )

    else:

        cursor.execute(
            """
            SELECT * FROM chat_history
            ORDER BY id DESC
            """
        )


    chats = cursor.fetchall()


    # -----------------------------------------------------
    # DASHBOARD STATISTICS
    # -----------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) AS total_students FROM students"
    )

    total_students = cursor.fetchone()["total_students"]


    cursor.execute(
        "SELECT COUNT(*) AS total_chats FROM chat_history"
    )

    total_chats = cursor.fetchone()["total_chats"]


    cursor.close()
    connection.close()


    return render_template(
        "admin_dashboard.html",
        chats=chats,
        total_students=total_students,
        total_chats=total_chats
    )


# =========================================================
# NOTICE
# =========================================================

@app.route("/notice")
def notice():

    connection = get_connection()

    if connection is None:
        return "Database connection failed."


    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT * FROM notices
        ORDER BY notice_date DESC
        """
    )

    notices = cursor.fetchall()


    cursor.close()
    connection.close()


    return render_template(
        "notice.html",
        notices=notices
    )


# =========================================================
# CHATBOT PAGE
# =========================================================

@app.route("/chatbot")
def chatbot():

    if "student_id" not in session:

        return redirect(url_for("login"))


    return render_template("chatbot.html")


# =========================================================
# ADD NOTICE
# =========================================================

@app.route("/add_notice", methods=["GET", "POST"])
def add_notice():

    if "admin" not in session:

        return redirect(url_for("admin_login"))


    if request.method == "POST":

        title = request.form["title"]

        description = request.form["description"]

        notice_date = request.form["notice_date"]


        connection = get_connection()

        if connection is None:
            return "Database connection failed."


        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO notices
            (title, description, notice_date)
            VALUES (%s,%s,%s)
            """,
            (
                title,
                description,
                notice_date
            )
        )

        connection.commit()


        cursor.close()
        connection.close()


        return redirect(url_for("notice"))


    return render_template("add_notice.html")


# =========================================================
# DELETE CHAT
# =========================================================

@app.route("/delete_chat/<int:id>")
def delete_chat(id):

    if "admin" not in session:

        return redirect(url_for("admin_login"))


    connection = get_connection()

    if connection is None:
        return "Database connection failed."


    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM chat_history
        WHERE id=%s
        """,
        (id,)
    )

    connection.commit()


    cursor.close()
    connection.close()


    return redirect(url_for("admin_dashboard"))


# =========================================================
# FEEDBACK
# =========================================================

@app.route("/feedback", methods=["GET", "POST"])
def feedback():

    if "student_id" not in session:

        return redirect(url_for("login"))


    if request.method == "POST":

        rating = request.form["rating"]

        comment = request.form["comment"]


        connection = get_connection()

        if connection is None:
            return "Database connection failed."


        cursor = connection.cursor()


        cursor.execute(
            """
            INSERT INTO feedback
            (student_id, rating, comment)
            VALUES(%s,%s,%s)
            """,
            (
                session["student_id"],
                rating,
                comment
            )
        )


        connection.commit()


        cursor.close()
        connection.close()


        return "Feedback Submitted Successfully!"


    return render_template("feedback.html")


# =========================================================
# ADD FAQ
# =========================================================

@app.route("/add_faq", methods=["GET", "POST"])
def add_faq():

    if "admin" not in session:

        return redirect(url_for("admin_login"))


    if request.method == "POST":

        category = request.form["category"]

        question = request.form["question"]

        answer = request.form["answer"]


        connection = get_connection()

        if connection is None:
            return "Database connection failed."


        cursor = connection.cursor()


        cursor.execute(
            """
            INSERT INTO faqs
            (category, question, answer)
            VALUES(%s,%s,%s)
            """,
            (
                category,
                question,
                answer
            )
        )


        connection.commit()


        cursor.close()
        connection.close()


        return redirect(url_for("admin_dashboard"))


    return render_template("add_faq.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# NOTICES
# =========================================================

@app.route("/notices")
def notices():

    connection = get_connection()

    if connection is None:
        return "Database connection failed."


    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT * FROM notices
        ORDER BY notice_date DESC
        """
    )

    all_notices = cursor.fetchall()


    cursor.close()
    connection.close()


    return render_template(
        "notices.html",
        notices=all_notices
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# CHAT API
# =========================================================

@app.route("/chat", methods=["POST"])
def chat():

    user_message = request.json["message"]

    bot_reply = get_response(user_message)


    save_chat(
        user_message,
        bot_reply
    )


    return jsonify({
        "response": bot_reply
    })


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)