import json
import joblib
import nltk

from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

nltk.download("punkt")
nltk.download("punkt_tab")

stemmer = PorterStemmer()

# Load AI model
model = joblib.load("model/model.pkl")
vectorizer = joblib.load("model/vectorizer.pkl")
encoder = joblib.load("model/label_encoder.pkl")

# Load intents
with open("intents.json", "r", encoding="utf-8") as file:
    intents = json.load(file)

print("🤖 College Enquiry Chatbot")
print("Type 'exit' to quit.\n")


# Greetings
greetings = {
    "hi": "Hi! Welcome to ACPCE. What would you like to know?",
    "hii": "Hi! Welcome to ACPCE. What would you like to know?",
    "hiii": "Hi! Welcome to ACPCE. What would you like to know?",
    "hello": "Hello! Welcome to the A. C. Patil College of Engineering enquiry chatbot. How can I help you?",
    "hey": "Hey! Welcome to the ACPCE enquiry chatbot. Ask me about admissions, courses, fees, location, facilities or placements."
}


while True:

    user_input = input("You: ").strip()

    if user_input == "":
        print("Bot: Please enter a question.")
        continue

    # Exit
    if user_input.lower() == "exit":
        print("Bot: Thank you! Have a nice day.")
        break

    # Convert input to lowercase
    clean_input = user_input.lower()

    # Direct greeting check
    if clean_input in greetings:
        print("Bot:", greetings[clean_input])
        continue

    # Tokenize and stem
    words = word_tokenize(clean_input)

    words = [
        stemmer.stem(word)
        for word in words
        if word.isalnum()
    ]

    processed_text = " ".join(words)

    print("Processed:", processed_text)

    # Convert text into vector
    X = vectorizer.transform([processed_text])

    # Predict intent
    prediction = model.predict(X)[0]

    tag = encoder.inverse_transform([prediction])[0]

    print("Predicted Tag:", tag)

    found = False

    # Find matching tag
    for intent in intents["intents"]:

        if intent["tag"] == tag:

            # Your JSON uses questions -> question -> answer
            for item in intent["questions"]:

                question = item["question"].lower()

                # For greeting tag, return first answer
                if tag == "greetings":
                    print("Bot:", item["answer"])
                    found = True
                    break

            if found:
                break

    if not found:
        print("Bot: Sorry, I couldn't understand your question.")