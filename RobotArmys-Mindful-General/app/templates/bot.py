import google.generativeai as genai
import gradio as gr
import os
key = "AIzaSyAQKWb8omb0RVV3QXeckS_TyBYqZlpfxVI"
genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-pro")
def chatbot(user_input):
    try:
        response = model.generate_content(user_input)
        return response.text
    except Exception as e:
        return f"Error: {e}"
    
iface = gr.Interface(
fn=chatbot,
inputs="text",
outputs="text",
title="Mental Health bot",
description="welcome to our Mental health bot",
theme="default",
)

iface.launch(share = True, pwa=True)