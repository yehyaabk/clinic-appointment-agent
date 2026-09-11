from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from pyngrok import ngrok
from dotenv import load_dotenv
from threading import Thread

load_dotenv()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text})
    print(response.text)

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    print("Webhook hit! Raw data:", request.get_json())
    data = request.get_json()
    chat_id = data['message']['chat']['id']
    incoming_message = data['message']['text']
    reply_text = incoming_message
    print(chat_id)
    send_telegram_message(chat_id, reply_text)
    return "OK", 200


@app.route('/webhook/twilio', methods=['POST'])
def twilio_webhook():
    incoming_message = request.form.get('Body', '')
    from_number = request.form.get('From', '').replace('whatsapp:', '')

    reply_text = incoming_message  #

    resp = MessagingResponse()
    resp.message(reply_text + from_number)
    return Response(str(resp), mimetype="application/xml")



def run_flask():
    app.run(host="0.0.0.0", port=5000)


if __name__ == '__main__':
    # Start Flask in a separate thread so the main thread stays free
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    public_url = ngrok.connect(5000).public_url
    print(f"Tunnel running at: {public_url}")

    response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
                json={"url": f"{public_url}/webhook/telegram"}
            )

    print("Set webhook response:", response.status_code, response.text)

    flask_thread.join()  # keep the main thread alive so the program doesn't exit

