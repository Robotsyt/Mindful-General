import os
from dotenv import load_dotenv
# pip install python-dotenv

import google.generativeai as genai
# pip install -q -U google-generative

load_dotenv()

model = genai.GenerativeModel("gemini-pro")
GENERATIVE_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GENERATIVE_API_KEY)

def prompt():
    user_input = "How are you today?"
    response = model.generate_content(user_input)
    print(response.text)
    return response

#https://google.dev/tutorials/python_quickstart

if __name__ == "__main__":
    prompt()