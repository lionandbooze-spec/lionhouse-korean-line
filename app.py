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
# LINE返信（デバッグ出力あり）
# ----------------------------
def reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    response = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        json={
            "replyToken": reply_token,
            "messages": messages
        }
    )

    print("=== LINE Reply ===")
    print("Status:", response.status_code)
    print("Body:", response.text)
    print("==================")

# ----------------------------
# レベル選択
# ----------------------------
def level_menu():
    return {
        "type": "text",
        "text": "レベルを選んでください",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "初級",
                        "text": "初級"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "中級",
                        "text": "中級"
                    }
                }
            ]
        }
    }

# ----------------------------
# ボタン作成
# ----------------------------
def build_button(text):
    return {
        "type": "button",
        "action": {
            "type": "message",
            "label": text,
            "text": text
        },
        "style": "primary",
        "color": "#6CC4A1"
    }

# ----------------------------
# 問題生成
# ----------------------------
def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])

    direction = random.choice(["jp_to_kr", "kr_to_jp"])

    if direction == "jp_to_kr":
        prompt = f"『{question['jp']}』は韓国語で？"
        correct = question["kr"]
        wrong = [w["kr"] for w in words[level] if w["kr"] != correct]
    else:
        prompt = f"『{question['kr']}』は日本語で？"
        correct = question["jp"]
        wrong = [w["jp"] for w in words[level] if w["jp"] != correct]

    choices = random.sample(wrong, min(3, len(wrong)))
    choices.append(correct)
    random.shuffle(choices)

    user_state[user_id]["correct"] = correct
    user_state[user_id]["choices"] = choices

    contents = [
        {"type": "text", "text": prompt, "weight": "bold", "size": "lg"}
    ]

    for choice in choices:
        contents.append(build_button(choice))

    contents.append({
        "type": "button",
        "action": {
            "type": "message",
            "label": "やめる",
            "text": "やめる"
        },
        "style": "secondary"
    })

    return {
        "type": "flex",
        "altText": "クイズ問題",
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

        print("Received text:", text)

        # レベル選択
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

        # やめる
        if text == "やめる" and user_id in user_state:
            user_state[user_id]["playing"] = False
            reply(reply_token, [level_menu()])
            continue

        # 回答処理
        if user_id in user_state and user_state[user_id].get("playing"):

            if text in user_state[user_id]["choices"]:

                user_state[user_id]["count"] += 1

                if text == user_state[user_id]["correct"]:
                    user_state[user_id]["score"] += 1
                    result = "正解！🔥"
                else:
                    result = f"違います。正解は {user_state[user_id]['correct']}"

                if user_state[user_id]["count"] >= 5:
                    score = user_state[user_id]["score"]
                    total = user_state[user_id]["count"]
                    user_state[user_id]["playing"] = False

                    reply(reply_token, [
                        {"type": "text", "text": f"{result}\n\n5問終了\n{score}/{total}"},
                        level_menu()
                    ])
                    continue

                flex = create_question(user_id)

                reply(reply_token, [
                    {"type": "text", "text": result},
                    flex
                ])

    return "OK"
