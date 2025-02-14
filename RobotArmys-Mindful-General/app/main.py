from flask import Flask, render_template, request, jsonify
import json
import os
from difflib import get_close_matches

app = Flask(__name__, template_folder="templates", static_folder="static")

# Define the correct file path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Get the absolute path of 'app/'
KNOWLEDGE_BASE_FILE = os.path.join(BASE_DIR, "..", "knowledge_base.json")  # Access knowledge_base.json in the root dir

# Load knowledge base
def load_knowledge_base():
    try:
        with open(KNOWLEDGE_BASE_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"questions": []}  # Return empty structure if file is missing or corrupted

# Save knowledge base (in case you want to allow updates later)
def save_knowledge_base(data):
    with open(KNOWLEDGE_BASE_FILE, "w") as file:
        json.dump(data, file, indent=2)

knowledge_base = load_knowledge_base()

# Find best match for user question
def find_best_match(user_question, questions):
    matches = get_close_matches(user_question, questions, n=1, cutoff=0.6)
    return matches[0] if matches else None

# Get answer from knowledge base
def get_answer_for_question(question):
    for q in knowledge_base["questions"]:
        if q["question"].lower() == question.lower():
            return q["answer"]
    return "I don't know the answer, but you can teach me!"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    
    if not user_message:
        return jsonify({"response": "Please ask a question."})

    best_match = find_best_match(user_message, [q["question"] for q in knowledge_base["questions"]])
    
    if best_match:
        response = get_answer_for_question(best_match)
    else:
        response = "I don't know the answer, but you can teach me!"
    
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)

