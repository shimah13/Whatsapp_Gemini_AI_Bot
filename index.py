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
            print("Incoming Webhook Body:", body) # மெட்டாவிலிருந்து வரும் மொத்த டேட்டாவையும் லாக்ஸில் காட்டும்
            
            # மெசேஜ் உள்ளே இருக்கிறதா என்று பாதுகாப்பாக சரிபார்க்கும் லாஜிக்
            if body.get("entry") and body["entry"][0].get("changes") and body["entry"][0]["changes"][0].get("value") and "messages" in body["entry"][0]["changes"][0]["value"]:
                
                data = body["entry"][0]["changes"][0]["value"]["messages"][0]
                
                # 1. டெக்ஸ்ட் மெசேஜாக இருந்தால்:
                if data.get("type") == "text":
                    prompt = data["text"]["body"]
                    convo.send_message(prompt)
                    send(convo.last.text)
                    print("Text reply processed successfully.")
                
                # 2. மீடியா மெசேஜாக இருந்தால் (ஆடியோ/இமேஜ்/டாக்குமெண்ட்):
                else:
                    media_type = data.get("type")
                    media_url_endpoint = f'https://graph.facebook.com/v18.0/{data[media_type]["id"]}/'
                    headers = {'Authorization': f'Bearer {wa_token}'}
                    media_response = requests.get(media_url_endpoint, headers=headers)
                    media_url = media_response.json().get("url")
                    
                    if not media_url:
                        print("Failed to fetch media URL from Meta.")
                        return jsonify({"status": "media_url_error"}), 200
                        
                    media_download_response = requests.get(media_url, headers=headers)
                    
                    # PDF டாக்குமெண்ட் சரிபார்ப்பு
                    if media_type == "document" and data["document"].get("mime_type") == "application/pdf":
                        doc = fitz.open(stream=media_download_response.content, filetype="pdf")
                        for _, page in enumerate(doc):
                            destination = "/tmp/temp_image.jpg"
                            pix = page.get_pixmap()
                            pix.save(destination)
                            file = genai.upload_file(path=destination, display_name="tempfile")
                            response = model.generate_content(["What is this", file])
                            answer = response._result.candidates[0].content.parts[0].text
                            convo.send_message(f"PDF content: {answer}")
                            send(convo.last.text)
                            remove(destination)
                    
                    # இமேஜ் அல்லது ஆடியோ சரிபார்ப்பு
                    elif media_type in ["audio", "image"]:
                        filename = "/tmp/temp_audio.mp3" if media_type == "audio" else "/tmp/temp_image.jpg"
                        with open(filename, "wb") as temp_media:
                            temp_media.write(media_download_response.content)
                            
                        file = genai.upload_file(path=filename, display_name="tempfile")
                        response = model.generate_content(["What is this", file])
                        answer = response._result.candidates[0].content.parts[0].text
                        remove("/tmp/temp_image.jpg", "/tmp/temp_audio.mp3")
                        convo.send_message(f"Media transcription: {answer}")
                        send(convo.last.text)
                        
                        files = genai.list_files()
                        for f in files:
                            f.delete()
                    else:
                        send("This format is not Supported by the bot ☹")
            else:
                print("Webhook received, but it is a status update (delivery/read receipt), not a new message.")
                
            return jsonify({"status": "ok"}), 200
            
        except Exception as e:
            print(f"Error occurred in Webhook: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000)
