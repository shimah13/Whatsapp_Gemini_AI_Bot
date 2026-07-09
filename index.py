import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os
import fitz

# Vercel-க்குத் தேவையான Flask Instance
app = Flask(__name__)
application = app 

wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
phone = os.environ.get("PHONE_NUMBER")

name = "Your name or nickname" 
bot_name = "Give a name to your bot" 
model_name = "gemini-1.5-flash" 

generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 0,
  "max_output_tokens": 8192,
}

safety_settings = [
  {"category": "HARM_CATEGORY_HARASSMENT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
  {"category": "HARM_CATEGORY_HATE_SPEECH","threshold": "BLOCK_MEDIUM_AND_ABOVE"},  
  {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
  {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

convo = model.start_chat(history=[])

def send(answer):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
          "messaging_product": "whatsapp", 
          "to": f"{phone}", 
          "type": "text",
          "text": {"body": f"{answer}"},
    }
    response = requests.post(url, headers=headers, json=data)
    print("Meta API Response:", response.json()) 
    return response

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)

@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot is Running Successfully!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        else:
            return "Failed", 403
            
    elif request.method == "POST":
        try:
            body = request.get_json()
            print("\n📥 --- STEP 1: Meta-விலிருந்து வந்த மொத்த டேட்டா ---")
            print(body)
            
            # மெசேஜ் இருக்கா இல்லையான்னு செக் பண்றோம்
            value = body["entry"][0]["changes"][0]["value"]
            if "messages" in value:
                data = value["messages"][0]
                print("\n💬 --- STEP 2: மெசேஜ் டேட்டா பிரித்தெடுக்கப்பட்டது ---")
                print(data)
                
                if data["type"] == "text":
                    prompt = data["text"]["body"]
                    print(f"\n🤖 --- STEP 3: ஜெமினிக்கு அனுப்பும் கேள்வி: {prompt}")
                    
                    convo.send_message(prompt)
                    reply = convo.last.text
                    print(f"\n✨ --- STEP 4: ஜெமினி கொடுத்த பதில்: {reply}")
                    
                    # உங்கள் ஒரிஜினல் send பங்க்ஷனை கூப்பிடுகிறோம்
                    res = send(reply)
                    print("\n🚀 --- STEP 5: வாட்ஸ்அப் செண்ட் ஸ்டேட்டஸ் ---")
                    print(res.json())
            else:
                print("\nℹ️ --- INFO: இது புது மெசேஜ் இல்லை (Delivery/Read Receipt) ---")
                
            return jsonify({"status": "ok"}), 200
            
        except Exception as e:
            print(f"\n❌ --- ERROR: கோட் இங்கே தான் ஸ்டக் ஆகியுள்ளது! ---")
            print(f"காரணம்: {e}")
            return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000)
