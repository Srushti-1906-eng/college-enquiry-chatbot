from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import joblib
from spellchecker import SpellChecker
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from flask_session import Session

from database import get_connection


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = "college_chatbot_secret"

app.config["SESSION_TYPE"] = "filesystem"

Session(app)

import time

start_time = time.time()

spell = SpellChecker()

print("SpellChecker loaded:", time.time() - start_time, "seconds")

encoder = joblib.load("model/label_encoder.pkl")

print("Models loaded:", time.time() - start_time, "seconds")

stemmer = PorterStemmer()


# =========================================================
# SAVE CHAT
# =========================================================

def save_chat(conversation_id, user_message, bot_reply):

    conn = get_connection()

    if conn is None:
        return

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_history
        (conversation_id, user_message, bot_reply)
        VALUES (%s, %s, %s)
        """,
        (
            conversation_id,
            user_message,
            bot_reply
        )
    )

    # Change "New Chat" into first question
    cursor.execute(
        """
        UPDATE conversations
        SET title=%s
        WHERE id=%s AND title='New Chat'
        """,
        (
            user_message[:30],
            conversation_id
        )
    )

    conn.commit()

    cursor.close()
    conn.close()


# =========================================================
# CREATE NEW CONVERSATION
# =========================================================

def create_conversation(student_id):

    conn = get_connection()

    if conn is None:
        return None

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO conversations
        (student_id, title)
        VALUES (%s, %s)
        """,
        (
            student_id,
            "New Chat"
        )
    )

    conn.commit()

    conversation_id = cursor.lastrowid

    cursor.close()
    conn.close()

    return conversation_id


# =========================================================
# GET ALL CONVERSATIONS
# =========================================================

def get_conversations(student_id):

    conn = get_connection()

    if conn is None:
        return []

    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM conversations
        WHERE student_id=%s
        ORDER BY created_at DESC
        """,
        (student_id,)
    )

    conversations = cursor.fetchall()

    cursor.close()
    conn.close()

    return conversations


# =========================================================
# GET MESSAGES OF ONE CONVERSATION
# =========================================================

def get_messages(conversation_id):

    conn = get_connection()

    if conn is None:
        return []

    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            user_message AS question,
            bot_reply AS answer,
            created_at
        FROM chat_history
        WHERE conversation_id=%s
        ORDER BY id ASC
        """,
        (conversation_id,)
    )

    messages = cursor.fetchall()

    cursor.close()
    conn.close()

    return messages


# =========================================================
# CHECK CONVERSATION BELONGS TO STUDENT
# =========================================================

def conversation_belongs_to_student(conversation_id, student_id):

    conn = get_connection()

    if conn is None:
        return False

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM conversations
        WHERE id=%s AND student_id=%s
        """,
        (
            conversation_id,
            student_id
        )
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result is not None


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

    user_input = user_input.strip().lower()


    # -----------------------------------------------------
    # GREETINGS
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
            INSERT INTO students
            (name, email, password)
            VALUES (%s, %s, %s)
            """,
            (
                name,
                email,
                password
            )
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
            SELECT *
            FROM students
            WHERE email=%s AND password=%s
            """,
            (
                email,
                password
            )
        )

        student = cursor.fetchone()

        cursor.close()

        connection.close()


        if student:

            session["student_id"] = student["id"]

            session["student_name"] = student["name"]

            session.pop("conversation_id", None)

            return redirect(url_for("chatbot"))


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
            SELECT *
            FROM admin
            WHERE username=%s AND password=%s
            """,
            (
                username,
                password
            )
        )

        admin = cursor.fetchone()

        cursor.close()

        connection.close()


        if admin:

            session["admin"] = admin["username"]

            return redirect(url_for("admin_dashboard"))


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
    # SEARCH CHAT HISTORY
    # -----------------------------------------------------

    if search:

        cursor.execute(
            """
            SELECT
                id,
                conversation_id,
                user_message AS question,
                bot_reply AS answer,
                created_at
            FROM chat_history
            WHERE user_message LIKE %s
            ORDER BY id ASC
            """,
            (
                "%" + search + "%",
            )
        )

    else:

        cursor.execute(
            """
            SELECT
                id,
                conversation_id,
                user_message AS question,
                bot_reply AS answer,
                created_at
            FROM chat_history
            ORDER BY id ASC
            """
        )


    chats = cursor.fetchall()


    # -----------------------------------------------------
    # DASHBOARD STATISTICS
    # -----------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total_students
        FROM students
        """
    )

    total_students = cursor.fetchone()["total_students"]


    cursor.execute(
        """
        SELECT COUNT(*) AS total_chats
        FROM chat_history
        """
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
# STUDENT NOTICES
# IMPORTANT:
# ONLY ONE notices() FUNCTION
# =========================================================

@app.route("/notices")
@app.route("/notice")
def notices():

    connection = get_connection()

    if connection is None:

        return "Database connection failed."


    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM notices
        ORDER BY notice_date DESC
        """
    )

    all_notices = cursor.fetchall()

    cursor.close()

    connection.close()


    # Your actual file is:
    # templates/notice.html

    return render_template(
        "notice.html",
        notices=all_notices
    )


# =========================================================
# CHATBOT PAGE
# =========================================================

@app.route("/chatbot")
def chatbot():

    if "student_id" not in session:
        return redirect(url_for("login"))

    student_id = session["student_id"]

    # Get all previous conversations for this student
    conversations = get_conversations(student_id)

    # -----------------------------------------------------
    # CREATE A NEW CHAT IF THERE IS NO ACTIVE CHAT
    # -----------------------------------------------------

    if "conversation_id" not in session:

        conversation_id = create_conversation(student_id)

        if conversation_id is None:
            return "Unable to create new conversation."

        session["conversation_id"] = conversation_id

    else:

        current_id = session["conversation_id"]

        # Make sure current conversation belongs to logged-in student
        if not conversation_belongs_to_student(
            current_id,
            student_id
        ):

            conversation_id = create_conversation(student_id)

            if conversation_id is None:
                return "Unable to create new conversation."

            session["conversation_id"] = conversation_id


    # -----------------------------------------------------
    # GET MESSAGES OF CURRENT CHAT
    # -----------------------------------------------------

    messages = get_messages(
        session["conversation_id"]
    )


    # Refresh conversation history
    conversations = get_conversations(student_id)


    return render_template(
        "chatbot.html",
        conversations=conversations,
        messages=messages
    )


    # -----------------------------------------------------
    # GET CURRENT CHAT MESSAGES
    # -----------------------------------------------------

    messages = get_messages(
        session["conversation_id"]
    )


    # Refresh conversation list

    conversations = get_conversations(student_id)


    return render_template(
        "chatbot.html",
        conversations=conversations,
        messages=messages
    )


# =========================================================
# NEW CHAT
# =========================================================

@app.route("/new_chat")
def new_chat():

    if "student_id" not in session:

        return redirect(url_for("login"))


    conversation_id = create_conversation(
        session["student_id"]
    )


    session["conversation_id"] = conversation_id


    return redirect(url_for("chatbot"))


# =========================================================
# OPEN OLD CONVERSATION
# =========================================================

@app.route("/conversation/<int:id>")
def open_conversation(id):

    if "student_id" not in session:

        return redirect(url_for("login"))


    # Student can only open their own conversations

    if not conversation_belongs_to_student(
        id,
        session["student_id"]
    ):

        return redirect(url_for("chatbot"))


    session["conversation_id"] = id


    return redirect(url_for("chatbot"))


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
            VALUES (%s, %s, %s)
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


        # Go to admin notice page

        return redirect(url_for("chatbot"))


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
            VALUES (%s, %s, %s)
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
            VALUES (%s, %s, %s)
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

    if "student_id" not in session:

        return jsonify({
            "response": "Please login first."
        }), 401


    # Make sure conversation exists

    if "conversation_id" not in session:

        session["conversation_id"] = create_conversation(
            session["student_id"]
        )


    data = request.get_json()


    if not data or "message" not in data:

        return jsonify({
            "response": "Please enter a message."
        }), 400


    user_message = data["message"].strip()


    if not user_message:

        return jsonify({
            "response": "Please enter a message."
        }), 400


    # Get AI response

    bot_reply = get_response(user_message)


    # Save message to current conversation

    save_chat(
        session["conversation_id"],
        user_message,
        bot_reply
    )


    return jsonify({
        "response": bot_reply
    })

# =========================================================
# ADMIN FEEDBACK
# =========================================================

@app.route("/admin_feedback")
def admin_feedback():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    connection = get_connection()

    if connection is None:
        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            feedback.id,
            students.name AS student_name,
            students.email AS student_email,
            feedback.rating,
            feedback.comment
        FROM feedback
        JOIN students
            ON feedback.student_id = students.id
        ORDER BY feedback.id DESC
    """)

    feedbacks = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_feedback.html",
        feedbacks=feedbacks
    )

# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        use_reloader=False
    )