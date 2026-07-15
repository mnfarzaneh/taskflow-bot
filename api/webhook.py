import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from bot.config import WEBHOOK_SECRET
from bot.handlers import handle_update

app = Flask(__name__)


@app.route("/api/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        incoming = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if incoming != WEBHOOK_SECRET:
            return jsonify({"ok": False}), 401

    update = request.get_json(force=True, silent=True) or {}
    try:
        handle_update(update)
    except Exception as e:
        print(f"[webhook] error handling update: {e}")

    return jsonify({"ok": True})


@app.route("/api/webhook", methods=["GET"])
def health():
    return jsonify({"status": "alive"})