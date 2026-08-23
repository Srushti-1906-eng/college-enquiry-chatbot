import json
import nltk
import joblib

from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder

# Download NLTK data (only first time)
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')

stemmer = PorterStemmer()

# Load intents
with open("intents.json", "r") as file:
    data = json.load(file)

patterns = []
tags = []

# Process data
for intent in data["intents"]:
    for pattern in intent["patterns"]:
        words = word_tokenize(pattern.lower())
        words = [stemmer.stem(word) for word in words if word.isalnum()]
        patterns.append(" ".join(words))
        tags.append(intent["tag"])

# Convert text to numbers
vectorizer = TfidfVectorizer(stop_words="english")
X = vectorizer.fit_transform(patterns)

# Encode labels
encoder = LabelEncoder()
y = encoder.fit_transform(tags)

# Train model
model = LogisticRegression(max_iter=1000)
model.fit(X, y)

# Save model
joblib.dump(model, "model/model.pkl")
joblib.dump(vectorizer, "model/vectorizer.pkl")
joblib.dump(encoder, "model/label_encoder.pkl")

print("✅ AI Model Trained Successfully!")