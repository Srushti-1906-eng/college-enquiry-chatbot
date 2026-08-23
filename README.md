# AI College Enquiry Chatbot

An AI-based College Enquiry Chatbot developed using Python, Flask, Machine Learning, and MySQL. The chatbot helps students get instant answers about admissions, courses, fees, placements, facilities, and notices of A. C. Patil College of Engineering.

## Features

- Student Login & Registration
- Admin Login
- AI-powered Question Answering
- Spell Correction
- College Notices
- Student Feedback
- Chat History Storage
- MySQL Database Integration

## Technologies Used

- Python
- Flask
- Scikit-learn
- NLTK
- MySQL
- HTML, CSS, JavaScript
- Bootstrap

## Project Structure

AI_College_Chatbot/
├── app.py
├── chatbot.py
├── database.py
├── config.py
├── intents.json
├── requirements.txt
├── database.sql
├── model/
├── templates/
└── static/

## Installation

1. Clone the repository

```bash
git clone https://github.com/Srushti-1906-eng/college-enquiry-chatbot.git
```

2. Install packages

```bash
pip install -r requirements.txt
```

3. Create MySQL database

```sql
SOURCE database.sql;
```

4. Create a `.env` file

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=college_chatbot
```

5. Run the application

```bash
python app.py
```

