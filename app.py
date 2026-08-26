from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import joblib
import time

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


# =========================================================
# LOAD SPELL CHECKER
# =========================================================

start_time = time.time()

spell = SpellChecker()

# College-specific words
# These words should NOT be changed by SpellChecker.
PROTECTED_WORDS = {
    "acpce",
    "patil",
    "kharghar",
    "navi",
    "mumbai",
    "maharashtra",
    "engineering",
    "college",
    "admission",
    "admissions",
    "placement",
    "placements",
    "hostel",
    "hostels",
    "btech",
    "mca",
    "mba",
    "station",
    "railway",
    "campus",
    "fees",
    "fee",
    "courses",
    "course",
    "department",
    "departments",
    "canteen",
    "library",
    "scholarship",
    "scholarships"
}

spell.word_frequency.load_words(list(PROTECTED_WORDS))

print("SpellChecker loaded:", time.time() - start_time, "seconds")


# =========================================================
# LOAD AI MODEL
# =========================================================

model = joblib.load("model/model.pkl")

vectorizer = joblib.load("model/vectorizer.pkl")

encoder = joblib.load("model/label_encoder.pkl")

print("Models loaded:", time.time() - start_time, "seconds")


# =========================================================
# STEMMER
# =========================================================

stemmer = PorterStemmer()


# =========================================================
# LOAD INTENTS
# =========================================================

with open("intents.json", "r", encoding="utf-8") as file:
    intents = json.load(file)


# =========================================================
# DATABASE HELPERS
# =========================================================

def save_chat(conversation_id, user_message, bot_reply):

    conn = get_connection()

    if conn is None:
        return False

    cursor = conn.cursor()

    try:

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

        return True

    except Exception as e:

        conn.rollback()

        print("Error saving chat:", e)

        return False

    finally:

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

    try:

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

        return conversation_id

    except Exception as e:

        conn.rollback()

        print("Error creating conversation:", e)

        return None

    finally:

        cursor.close()
        conn.close()


# =========================================================
# GET ALL CONVERSATIONS
# =========================================================

def get_conversations(student_id):

    conn = get_connection()

    if conn is None:
        return []

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM conversations
            WHERE student_id=%s
            ORDER BY created_at DESC
            """,
            (student_id,)
        )

        return cursor.fetchall()

    except Exception as e:

        print("Error getting conversations:", e)

        return []

    finally:

        cursor.close()
        conn.close()


# =========================================================
# GET MESSAGES OF ONE CONVERSATION
# =========================================================

def get_messages(conversation_id):

    conn = get_connection()

    if conn is None:
        return []

    cursor = conn.cursor(dictionary=True)

    try:

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

        return cursor.fetchall()

    except Exception as e:

        print("Error getting messages:", e)

        return []

    finally:

        cursor.close()
        conn.close()


# =========================================================
# CHECK CONVERSATION BELONGS TO STUDENT
# =========================================================

def conversation_belongs_to_student(conversation_id, student_id):

    conn = get_connection()

    if conn is None:
        return False

    cursor = conn.cursor()

    try:

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

        return result is not None

    except Exception as e:

        print("Error checking conversation:", e)

        return False

    finally:

        cursor.close()
        conn.close()


# =========================================================
# SPELLING CORRECTION
# =========================================================

def correct_spelling(text):

    words = text.split()

    corrected = []

    for word in words:

        # Keep punctuation separate
        clean_word = word.lower().strip(".,?!:;()[]{}\"'")

        if not clean_word:
            corrected.append(word)
            continue

        # Never correct college-specific words
        if clean_word in PROTECTED_WORDS:

            corrected.append(word)

        else:

            corrected_word = spell.correction(clean_word)

            if corrected_word:
                corrected.append(corrected_word)
            else:
                corrected.append(word)

    return " ".join(corrected)


# =========================================================
# PREPROCESS TEXT
# =========================================================
#
# IMPORTANT:
# ACPCE must NOT become "acpc".
#
# Normal words are stemmed.
# College-specific words are kept unchanged.
# =========================================================

def preprocess_text(text):

    words = word_tokenize(text.lower())

    processed = []

    for word in words:

        if not word.isalnum():
            continue

        # Keep protected college terms unchanged
        if word in PROTECTED_WORDS:

            processed.append(word)

        else:

            processed.append(
                stemmer.stem(word)
            )

    return " ".join(processed)


# =========================================================
# NORMALIZE INPUT
# =========================================================

def normalize_text(text):

    text = text.lower().strip()

    replacements = {
        "a. c. patil": "acpce",
        "a c patil": "acpce",
        "a.c. patil": "acpce",
        "a. c patil": "acpce",
        "a c. patil": "acpce",
        "a c patil college": "acpce",
        "a. c. patil college": "acpce",
        "a c patil college of engineering": "acpce",
        "a. c. patil college of engineering": "acpce",
        "a.c.p.c.e": "acpce",
        "a.c.p.c.e.": "acpce"
    }

    for old, new in replacements.items():

        text = text.replace(old, new)

    return text


# =========================================================
# DIRECT COLLEGE LOCATION HANDLER
# =========================================================
#
# This handles common location questions directly.
# It prevents the ML model from incorrectly predicting
# "general" for questions such as:
#
# Where is ACPCE located?
# What is the address of ACPCE?
# Is ACPCE walking distance from Kharghar station?
# How far is ACPCE from Kharghar station?
# =========================================================

def get_location_response(user_input):

    text = normalize_text(user_input)

    # -----------------------------------------------------
    # LOCATION / ADDRESS
    # -----------------------------------------------------

    location_keywords = [
        "where is",
        "location",
        "located",
        "address",
        "where can i find",
        "which area",
        "which place"
    ]

    college_keywords = [
        "acpce",
        "college",
        "patil"
    ]

    has_location_word = any(
        keyword in text
        for keyword in location_keywords
    )

    has_college_word = any(
        keyword in text
        for keyword in college_keywords
    )

    if has_location_word and has_college_word:

        return (
            "A. C. Patil College of Engineering (ACPCE) "
            "is located in Kharghar, Navi Mumbai, Maharashtra."
        )


    # -----------------------------------------------------
    # KHARGHAR STATION QUESTIONS
    # -----------------------------------------------------

    station_keywords = [
        "kharghar station",
        "kharghar railway station",
        "railway station",
        "railway",
        "station"
    ]

    distance_keywords = [
        "walking distance",
        "walk",
        "walking",
        "near",
        "nearby",
        "how far",
        "distance",
        "far",
        "close",
        "reach",
        "get to",
        "travel"
    ]

    has_station_word = any(
        keyword in text
        for keyword in station_keywords
    )

    has_distance_word = any(
        keyword in text
        for keyword in distance_keywords
    )

    if (
        "acpce" in text
        and
        has_station_word
        and
        (
            has_distance_word
            or "kharghar" in text
        )
    ):

        return (
            "ACPCE is located in Kharghar, Navi Mumbai, "
            "near Kharghar Railway Station. "
            "The exact walking distance can vary depending "
            "on the route and campus entrance."
        )


    # -----------------------------------------------------
    # IS KHARGHAR STATION NEAR ACPCE?
    # -----------------------------------------------------

    if (
        "acpce" in text
        and
        (
            "near kharghar" in text
            or "near station" in text
            or "station near" in text
        )
    ):

        return (
            "Yes. A. C. Patil College of Engineering (ACPCE) "
            "is in Kharghar, Navi Mumbai, near Kharghar Railway Station."
        )


    return None


# =========================================================
# GREETING HANDLER
# =========================================================

def get_greeting_response(user_input):

    greetings = {

        "hi":
            "Hi! Welcome to ACPCE. What would you like to know?",

        "hii":
            "Hi! Welcome to ACPCE. What would you like to know?",

        "hiii":
            "Hi! Welcome to ACPCE. What would you like to know?",

        "hello":
            (
                "Hello! Welcome to the A. C. Patil College "
                "of Engineering enquiry chatbot. How can I help you?"
            ),

        "hey":
            (
                "Hey! Welcome to the ACPCE enquiry chatbot. "
                "Ask me about admissions, courses, fees, "
                "location, facilities or placements."
            )
    }

    return greetings.get(user_input)


# =========================================================
# CHATBOT RESPONSE
# =========================================================

def get_response(user_input):

    if not user_input:
        return "Please enter a question."


    # -----------------------------------------------------
    # ORIGINAL INPUT
    # -----------------------------------------------------

    original_input = user_input.strip().lower()


    # -----------------------------------------------------
    # GREETINGS
    # -----------------------------------------------------

    greeting_response = get_greeting_response(
        original_input
    )

    if greeting_response:

        return greeting_response


    # -----------------------------------------------------
    # NORMALIZE
    # -----------------------------------------------------

    normalized_input = normalize_text(
        original_input
    )


    # -----------------------------------------------------
    # DIRECT LOCATION HANDLER
    # -----------------------------------------------------
    #
    # This runs BEFORE spell correction and ML prediction.
    # Therefore ACPCE location questions don't get lost.
    # -----------------------------------------------------

    location_response = get_location_response(
        normalized_input
    )

    if location_response:

        print("Direct Location Match")

        return location_response


    # -----------------------------------------------------
    # SPELLING CORRECTION
    # -----------------------------------------------------

    corrected_input = correct_spelling(
        normalized_input
    )

    print("Original:", original_input)

    print("Corrected:", corrected_input)


    # -----------------------------------------------------
    # PREPROCESSING
    # -----------------------------------------------------

    processed_text = preprocess_text(
        corrected_input
    )

    print("Processed:", processed_text)


    # -----------------------------------------------------
    # AI PREDICTION
    # -----------------------------------------------------

    try:

        X = vectorizer.transform([
            processed_text
        ])

        prediction = model.predict(X)[0]

        tag = encoder.inverse_transform([
            prediction
        ])[0]

        print("Predicted Tag:", tag)

    except Exception as e:

        print("Model prediction error:", e)

        return (
            "Sorry, I couldn't process your question. "
            "Please try asking about admissions, courses, "
            "fees, location, hostel, placements or facilities."
        )


    # -----------------------------------------------------
    # FIND INTENT RESPONSE
    # -----------------------------------------------------

    for intent in intents.get("intents", []):

        if intent.get("tag") == tag:

            responses = intent.get("response", [])

            # If response is a list
            if isinstance(responses, list):

                if responses:
                    return responses[0]

            # If response is a string
            elif isinstance(responses, str):

                return responses


    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    return (
        "Sorry, I couldn't understand your question. "
        "Please try asking about admissions, courses, "
        "fees, location, hostel, placements or facilities."
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()

        email = request.form.get("email", "").strip()

        password = request.form.get("password", "")


        if not name or not email or not password:

            return "Please fill all fields."


        connection = get_connection()

        if connection is None:

            return "Database connection failed."


        cursor = connection.cursor()

        try:

            # Check if email already exists
            cursor.execute(
                """
                SELECT id
                FROM students
                WHERE email=%s
                """,
                (email,)
            )

            existing_student = cursor.fetchone()

            if existing_student:

                return "Email already registered."


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

        except Exception as e:

            connection.rollback()

            print("Registration error:", e)

            return "Registration failed."

        finally:

            cursor.close()
            connection.close()


        return redirect(
            url_for("login")
        )


    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if not email or not password:

            return "Please enter email and password."


        connection = get_connection()

        if connection is None:

            return "Database connection failed."


        cursor = connection.cursor(
            dictionary=True
        )

        try:

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

        except Exception as e:

            print("Login error:", e)

            student = None

        finally:

            cursor.close()
            connection.close()


        if student:

            session["student_id"] = student["id"]

            session["student_name"] = student["name"]

            # Start a fresh active conversation
            session.pop(
                "conversation_id",
                None
            )

            return redirect(
                url_for("chatbot")
            )


        return "Invalid Email or Password"


    return render_template(
        "login.html"
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin_login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if not username or not password:

            return "Please enter username and password."


        connection = get_connection()

        if connection is None:

            return "Database connection failed."


        cursor = connection.cursor(
            dictionary=True
        )

        try:

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

        except Exception as e:

            print("Admin login error:", e)

            admin = None

        finally:

            cursor.close()
            connection.close()


        if admin:

            session["admin"] = admin["username"]

            return redirect(
                url_for("admin_dashboard")
            )


        return "Invalid Admin Login"


    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    search = request.args.get(
        "search",
        ""
    ).strip()


    connection = get_connection()

    if connection is None:

        return "Database connection failed."


    cursor = connection.cursor(
        dictionary=True
    )


    try:

        # -------------------------------------------------
        # SEARCH CHAT HISTORY
        # -------------------------------------------------

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
                ORDER BY id DESC
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
                ORDER BY id DESC
                """
            )


        chats = cursor.fetchall()


        # -------------------------------------------------
        # TOTAL STUDENTS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total_students
            FROM students
            """
        )

        total_students = cursor.fetchone()[
            "total_students"
        ]


        # -------------------------------------------------
        # TOTAL CHATS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total_chats
            FROM chat_history
            """
        )

        total_chats = cursor.fetchone()[
            "total_chats"
        ]


        # -------------------------------------------------
        # TOTAL CONVERSATIONS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total_conversations
            FROM conversations
            """
        )

        total_conversations = cursor.fetchone()[
            "total_conversations"
        ]


    except Exception as e:

        print("Admin dashboard error:", e)

        chats = []

        total_students = 0

        total_chats = 0

        total_conversations = 0

    finally:

        cursor.close()
        connection.close()


    return render_template(
        "admin_dashboard.html",
        chats=chats,
        total_students=total_students,
        total_chats=total_chats,
        total_conversations=total_conversations
    )


# =========================================================
# STUDENT NOTICES
# =========================================================

@app.route("/notices")
@app.route("/notice")
def notices():

    connection = get_connection()

    if connection is None:

        return "Database connection failed."


    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT *
            FROM notices
            ORDER BY notice_date DESC
            """
        )

        all_notices = cursor.fetchall()

    except Exception as e:

        print("Notice error:", e)

        all_notices = []

    finally:

        cursor.close()
        connection.close()


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

        return redirect(
            url_for("login")
        )


    student_id = session["student_id"]


    # -----------------------------------------------------
    # CHECK ACTIVE CONVERSATION
    # -----------------------------------------------------

    if "conversation_id" not in session:

        conversation_id = create_conversation(
            student_id
        )

        if conversation_id is None:

            return "Unable to create new conversation."

        session["conversation_id"] = conversation_id


    else:

        current_id = session[
            "conversation_id"
        ]


        # Make sure conversation belongs
        # to logged-in student

        if not conversation_belongs_to_student(
            current_id,
            student_id
        ):

            conversation_id = create_conversation(
                student_id
            )

            if conversation_id is None:

                return "Unable to create new conversation."

            session["conversation_id"] = conversation_id


    # -----------------------------------------------------
    # GET CURRENT MESSAGES
    # -----------------------------------------------------

    messages = get_messages(
        session["conversation_id"]
    )


    # -----------------------------------------------------
    # GET CONVERSATION HISTORY
    # -----------------------------------------------------

    conversations = get_conversations(
        student_id
    )


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

        return redirect(
            url_for("login")
        )


    conversation_id = create_conversation(
        session["student_id"]
    )


    if conversation_id is None:

        return "Unable to create new conversation."


    session["conversation_id"] = conversation_id


    return redirect(
        url_for("chatbot")
    )


# =========================================================
# OPEN OLD CONVERSATION
# =========================================================

@app.route("/conversation/<int:id>")
def open_conversation(id):

    if "student_id" not in session:

        return redirect(
            url_for("login")
        )


    # Student can only open their own conversation

    if not conversation_belongs_to_student(
        id,
        session["student_id"]
    ):

        return redirect(
            url_for("chatbot")
        )


    session["conversation_id"] = id


    return redirect(
        url_for("chatbot")
    )


# =========================================================
# DELETE STUDENT CONVERSATION
# =========================================================

@app.route(
    "/delete_conversation/<int:id>",
    methods=["POST", "GET"]
)
def delete_conversation(id):

    if "student_id" not in session:

        return redirect(
            url_for("login")
        )


    student_id = session[
        "student_id"
    ]


    if not conversation_belongs_to_student(
        id,
        student_id
    ):

        return redirect(
            url_for("chatbot")
        )


    connection = get_connection()

    if connection is None:

        return "Database connection failed."


    cursor = connection.cursor()

    try:

        # Delete chat messages first
        cursor.execute(
            """
            DELETE FROM chat_history
            WHERE conversation_id=%s
            """,
            (id,)
        )


        # Delete conversation
        cursor.execute(
            """
            DELETE FROM conversations
            WHERE id=%s AND student_id=%s
            """,
            (
                id,
                student_id
            )
        )

        connection.commit()


    except Exception as e:

        connection.rollback()

        print("Delete conversation error:", e)

    finally:

        cursor.close()
        connection.close()


    # If deleted conversation was active,
    # create a new one.

    if session.get(
        "conversation_id"
    ) == id:

        session.pop(
            "conversation_id",
            None
        )


    return redirect(
        url_for("chatbot")
    )


# =========================================================
# ADD NOTICE
# =========================================================

@app.route(
    "/add_notice",
    methods=["GET", "POST"]
)
def add_notice():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        notice_date = request.form.get(
            "notice_date",
            ""
        )


        if not title or not description or not notice_date:

            return "Please fill all notice fields."


        connection = get_connection()

        if connection is None:

            return "Database connection failed."


        cursor = connection.cursor()

        try:

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

        except Exception as e:

            connection.rollback()

            print("Add notice error:", e)

            return "Unable to add notice."

        finally:

            cursor.close()
            connection.close()


        return redirect(
            url_for("admin_dashboard")
        )


    return render_template(
        "add_notice.html"
    )


# =========================================================
# DELETE CHAT
# =========================================================

@app.route(
    "/delete_chat/<int:id>",
    methods=["POST", "GET"]
)
def delete_chat(id):

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    connection = get_connection()

    if connection is None:

        return "Database connection failed."


    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            DELETE FROM chat_history
            WHERE id=%s
            """,
            (id,)
        )

        connection.commit()

    except Exception as e:

        connection.rollback()

        print("Delete chat error:", e)

    finally:

        cursor.close()
        connection.close()


    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# FEEDBACK
# =========================================================

@app.route(
    "/feedback",
    methods=["GET", "POST"]
)
def feedback():

    if "student_id" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        rating = request.form.get(
            "rating"
        )

        comment = request.form.get(
            "comment",
            ""
        ).strip()


        if not rating:

            return "Please select a rating."


        connection = get_connection()

        if connection is None:

            return "Database connection failed."


        cursor = connection.cursor()

        try:

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

        except Exception as e:

            connection.rollback()

            print("Feedback error:", e)

            return "Unable to submit feedback."

        finally:

            cursor.close()
            connection.close()


        return "Feedback Submitted Successfully!"


    return render_template(
        "feedback.html"
    )


# =========================================================
# ADD FAQ
# =========================================================

@app.route(
    "/add_faq",
    methods=["GET", "POST"]
)
def add_faq():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        question = request.form.get(
            "question",
            ""
        ).strip()

        answer = request.form.get(
            "answer",
            ""
        ).strip()


        if not category or not question or not answer:

            return "Please fill all FAQ fields."


        connection = get_connection()

        if connection is None:

            return "Database connection failed."


        cursor = connection.cursor()

        try:

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

        except Exception as e:

            connection.rollback()

            print("Add FAQ error:", e)

            return "Unable to add FAQ."

        finally:

            cursor.close()
            connection.close()


        return redirect(
            url_for("admin_dashboard")
        )


    return render_template(
        "add_faq.html"
    )


# =========================================================
# ADMIN FEEDBACK
# =========================================================

@app.route("/admin_feedback")
def admin_feedback():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    connection = get_connection()

    if connection is None:

        return "Database connection failed."


    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
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
            """
        )

        feedbacks = cursor.fetchall()

    except Exception as e:

        print("Admin feedback error:", e)

        feedbacks = []

    finally:

        cursor.close()
        connection.close()


    return render_template(
        "admin_feedback.html",
        feedbacks=feedbacks
    )


# =========================================================
# CHAT API
# =========================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    if "student_id" not in session:

        return jsonify({
            "response": "Please login first."
        }), 401


    # -----------------------------------------------------
    # MAKE SURE CONVERSATION EXISTS
    # -----------------------------------------------------

    if "conversation_id" not in session:

        conversation_id = create_conversation(
            session["student_id"]
        )

        if conversation_id is None:

            return jsonify({
                "response":
                    "Unable to create conversation."
            }), 500

        session["conversation_id"] = conversation_id


    # -----------------------------------------------------
    # VERIFY CURRENT CONVERSATION
    # -----------------------------------------------------

    if not conversation_belongs_to_student(
        session["conversation_id"],
        session["student_id"]
    ):

        conversation_id = create_conversation(
            session["student_id"]
        )

        if conversation_id is None:

            return jsonify({
                "response":
                    "Unable to create conversation."
            }), 500

        session["conversation_id"] = conversation_id


    # -----------------------------------------------------
    # READ JSON
    # -----------------------------------------------------

    data = request.get_json(
        silent=True
    )


    if not data or "message" not in data:

        return jsonify({
            "response": "Please enter a message."
        }), 400


    user_message = str(
        data["message"]
    ).strip()


    if not user_message:

        return jsonify({
            "response": "Please enter a message."
        }), 400


    # -----------------------------------------------------
    # GET BOT RESPONSE
    # -----------------------------------------------------

    bot_reply = get_response(
        user_message
    )


    # -----------------------------------------------------
    # SAVE CHAT
    # -----------------------------------------------------

    save_chat(
        session["conversation_id"],
        user_message,
        bot_reply
    )


    # -----------------------------------------------------
    # RETURN RESPONSE
    # -----------------------------------------------------

    return jsonify({
        "response": bot_reply
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin_logout")
def admin_logout():

    session.pop(
        "admin",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        use_reloader=False
    )