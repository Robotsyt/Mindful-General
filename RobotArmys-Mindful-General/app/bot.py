from flask import Flask, render_template, request, jsonify
from flask import Flask, jsonify, request, send_file, send_from_directory
import json
import os
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI


app = Flask(__name__, template_folder="templates", static_folder="static")

# Configure the Gemini bot
os.environ["GOOGLE_API_KEY"] = "AIzaSyAQKWb8omb0RVV3QXeckS_TyBYqZlpfxVI"; 

@app.route("/")
def home():
    return send_file("templates/index.html")

@app.route("/api/generate", methods=["POST"])
def generate_api():
     if request.method == "POST":
        try:
            req_body = request.get_json()
            content = req_body.get("contents")
            model = ChatGoogleGenerativeAI(model=req_body.get("model"))
            message = HumanMessage(
                content=content
            )
            response = model.stream([message])
            def stream():
                for chunk in response:
                    yield 'data: %s\n\n' % json.dumps({ "text": chunk.content })

            return stream(), {'Content-Type': 'text/event-stream'}

        except Exception as e:
            return jsonify({ "error": str(e) })

# Defines a route to serve static files from the web directory for any given path.
# When a request matches the path, it sends the requested file from the web directory.
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('web', path)

# If the script is run directly, it starts the Flask app in debug mode.
if __name__ == '__main__':
    app.run(debug=True)
