import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)
application = app 

# Vercel Environment Variables இலிருந்து டேட்டாவை எடுக்கிறது
wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
phone = os.environ.get("PHONE_NUMBER")

model = genai.GenerativeModel(model_name="gemini-1.5-flash")
convo = model.start_chat(history=[])

def send(answer):
    # v25.0 லேட்டஸ்ட் URL
    url = f"https://graph.facebook.com/v25.0/{phone_id}/messages"
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

@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot is Running!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # v25.0 வெப்ஹூக் வெரிஃபிகேஷன்
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == "BOT":
            return str(challenge), 200 # Plain text ஆக ரிட்டர்ன் செய்கிறது
        else:
            return "Failed", 403
            
    elif request.method == "POST":
        try:
            body = request.get_json()
            print("\n📥 --- STEP 1: Meta Webhook Data ---")
            print(body)
            
            value = body["entry"][0]["changes"][0]["value"]
            if "messages" in value:
                data = value["messages"][0]
                
                if data["type"] == "text":
                    prompt = data["text"]["body"]
                    print(f"🤖 --- STEP 3: Prompt: {prompt}")
                    
                    convo.send_message(prompt)
                    reply = convo.last.text
                    print(f"✨ --- STEP 4: Gemini Reply: {reply}")
                    
                    send(reply)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"❌ Error: {e}")
            return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000)
