from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

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

user_state = {}

# ----------------------------
# LINE返信
# ----------------------------
def reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    res = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        json={
            "replyToken": reply_token,
            "messages": messages
        }
    )

    print("Reply status:", res.status_code)
    print("Reply body:", res.text)

# ----------------------------
# レベル選択（安全版）
# ----------------------------
def level_menu():
    return {
        "type": "text",
        "text": "レベルを選んでください\n\n初級\n中級"
    }

# ----------------------------
# 問題生成（安全Flex）
# ----------------------------
def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])
    direction = random.choice(["jp_to_kr", "kr_to_jp"])

    if direction == "jp_to_kr":
        prompt = f"{question['jp']} は韓国語で？"
        correct = question["kr"]
        wrong = [w["kr"] for w in words[level] if w["kr"] != correct]
    else:
        prompt = f"{question['kr']} は日本語で？"
        correct = question["jp"]
        wrong = [w["jp"] for w in words[level] if w["jp"] != correct]

    choices = random.sample(wrong, min(3, len(wrong)))
    choices.append(correct)
    random.shuffle(choices)

    user_state[user_id]["correct"] = correct
    user_state[user_id]["choices"] = choices

    # ボタンを縦並び（最も安全）
    contents = [
        {
            "type": "text",
            "text": prompt,
            "weight": "bold",
            "size": "lg"
        }
    ]

    for c in choices:
        contents.append({
            "type": "button",
            "action": {
                "type": "message",
                "label": c,
                "text": c
            }
        })

    contents.append({
        "type": "button",
        "action": {
            "type": "message",
            "label": "やめる",
            "text": "やめる"
        }
    })

    return {
        "type": "flex",
        "altText": "クイズ",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": contents
            }
        }
    }

# ----------------------------
# Webhook
# ----------------------------
@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:

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

        print("Received:", text)

        if text in words:
            user_state[user_id] = {
                "level": text,
                "playing": True,
                "count": 0,
                "score": 0
            }

            flex = create_question(user_id)
            reply(reply_token, [flex])
            continue

        if text == "やめる" and user_id in user_state:
            user_state[user_id]["playing"] = False
            reply(reply_token, [level_menu()])
            continue

        if user_id in user_state and user_state[user_id].get("playing"):

            if text in user_state[user_id]["choices"]:

                user_state[user_id]["count"] += 1

                if text == user_state[user_id]["correct"]:
                    user_state[user_id]["score"] += 1
                    result = "正解！"
                else:
                    result = f"違います。正解は {user_state[user_id]['correct']}"

                if user_state[user_id]["count"] >= 5:
                    score = user_state[user_id]["score"]
                    total = user_state[user_id]["count"]
                    user_state[user_id]["playing"] = False

                    reply(reply_token, [
                        {"type": "text", "text": f"{result}\n\n5問終了 {score}/{total}"},
                        level_menu()
                    ])
                    continue

                flex = create_question(user_id)

                reply(reply_token, [
                    {"type": "text", "text": result},
                    flex
                ])

    return "OK"
