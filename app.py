from flask import Flask, request
import requests
import json
import os
import random
from urllib.parse import quote

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

BASE_AUDIO_URL = "https://raw.githubusercontent.com/lionandbooze-spec/lionhouse-korean-line/main/audio/"

# ---------------------
# 単語
# ---------------------
words = {
    "初級": [
        {"jp": "こんにちは", "kr": "안녕하세요"},
        {"jp": "ありがとう", "kr": "감사합니다"},
        {"jp": "さようなら", "kr": "안녕히 가세요"},
        {"jp": "はい", "kr": "네"},
        {"jp": "いいえ", "kr": "아니요"},
    ],
    "中級": [
        {"jp": "約束", "kr": "약속"},
        {"jp": "経験", "kr": "경험"},
        {"jp": "理由", "kr": "이유"},
        {"jp": "準備", "kr": "준비"},
        {"jp": "選択", "kr": "선택"},
    ]
}

filename_map = {
    w["kr"]: f"{w['kr']}.mp3"
    for level in words.values()
    for w in level
}

user_state = {}

# ---------------------
# LINE reply
# ---------------------
def reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps({
            "replyToken": reply_token,
            "messages": messages
        })
    )

# ---------------------
# LINE push audio
# ---------------------
def push_audio(user_id, audio_url):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        data=json.dumps({
            "to": user_id,
            "messages": [{
                "type": "audio",
                "originalContentUrl": audio_url,
                "duration": 1000
            }]
        })
    )

# ---------------------
# レベルメニュー
# ---------------------
def level_menu():
    return {
        "type": "text",
        "text": "レベルを選んでください",
        "quickReply": {
            "items": [
                {"type": "action",
                 "action": {"type": "message", "label": "初級", "text": "初級"}},
                {"type": "action",
                 "action": {"type": "message", "label": "中級", "text": "中級"}}
            ]
        }
    }

# ---------------------
# 問題生成
# ---------------------
def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])
    direction = random.choice(["jp_to_kr", "kr_to_jp"])

    if direction == "jp_to_kr":
        prompt = f"{question['jp']} は韓国語で？"
        correct = question["kr"]
        wrong = [w["kr"] for w in words[level] if w["kr"] != correct]
        user_state[user_id]["last_audio"] = None
    else:
        prompt = f"{question['kr']} は日本語で？"
        correct = question["jp"]
        wrong = [w["jp"] for w in words[level] if w["jp"] != correct]

        encoded = quote(filename_map[question["kr"]])
        user_state[user_id]["last_audio"] = BASE_AUDIO_URL + encoded

    choices = random.sample(wrong, min(3, len(wrong)))
    choices.append(correct)
    random.shuffle(choices)

    user_state[user_id]["correct"] = correct
    user_state[user_id]["choices"] = choices

    return {
        "type": "text",
        "text": prompt + "\n\n" + "\n".join(choices)
    }

# ---------------------
# Webhook
# ---------------------
@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:

        # message以外は無視
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text")
        if not text:
            continue

        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]

        # レベル選択
        if text in words:
            user_state[user_id] = {
                "level": text,
                "playing": True,
                "count": 0,
                "score": 0,
                "last_audio": None
            }
            q = create_question(user_id)
            reply(reply_token, [q])

            audio = user_state[user_id].get("last_audio")
            if audio:
                push_audio(user_id, audio)
            continue

        # 音声再生
        if text == "音声再生" and user_id in user_state:
            audio = user_state[user_id].get("last_audio")
            if audio:
                push_audio(user_id, audio)
            continue

        # 回答処理
        if user_id in user_state and user_state[user_id]["playing"]:
            if text in user_state[user_id]["choices"]:
                user_state[user_id]["count"] += 1

                if text == user_state[user_id]["correct"]:
                    user_state[user_id]["score"] += 1
                    msg = "正解！"
                else:
                    msg = f"違います。正解は {user_state[user_id]['correct']}"

                if user_state[user_id]["count"] >= 5:
                    score = user_state[user_id]["score"]
                    total = user_state[user_id]["count"]
                    user_state[user_id]["playing"] = False

                    reply(reply_token, [{
                        "type": "text",
                        "text": f"{msg}\n\n5問終了\n{score}/{total}"
                    }, level_menu()])
                    continue

                q = create_question(user_id)
                reply(reply_token, [
                    {"type": "text", "text": msg},
                    q
                ])

                audio = user_state[user_id].get("last_audio")
                if audio:
                    push_audio(user_id, audio)

    return "OK"
