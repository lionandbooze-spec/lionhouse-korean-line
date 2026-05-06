from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

# レベル別単語リスト
words = {
    "初級": [
        {"jp": "こんにちは", "kr": "안녕하세요"},
        {"jp": "ありがとう", "kr": "감사합니다"},
        {"jp": "さようなら", "kr": "안녕히 가세요"},
    ],
    "中級": [
        {"jp": "約束", "kr": "약속"},
        {"jp": "経験", "kr": "경험"},
        {"jp": "理由", "kr": "이유"},
    ]
}

# ユーザー状態管理
user_state = {}

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] == "message":
            user_id = event["source"]["userId"]
            reply_token = event["replyToken"]
            text = event["message"]["text"]

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ACCESS_TOKEN}"
            }

            # レベル選択
            if text in words.keys():
                user_state[user_id] = {
                    "level": text,
                    "answer": None
                }

                data = {
                    "replyToken": reply_token,
                    "messages":[
                        {"type":"text",
                         "text": f"{text}レベルを選択しました。\n「スタート」と送ってください。"}
                    ]
                }

            # スタートで出題
            elif text == "スタート":
                if user_id in user_state and user_state[user_id]["level"]:
                    level = user_state[user_id]["level"]
                    question = random.choice(words[level])
                    user_state[user_id]["answer"] = question["kr"]

                    data = {
                        "replyToken": reply_token,
                        "messages":[
                            {"type":"text",
                             "text": f"{question['jp']} は韓国語で？"}
                        ]
                    }
                else:
                    data = {
                        "replyToken": reply_token,
                        "messages":[
                            {"type":"text",
                             "text": "まず「初級」または「中級」を選んでください。"}
                        ]
                    }

            # 回答チェック
            elif user_id in user_state and user_state[user_id]["answer"]:
                correct = user_state[user_id]["answer"]

                if text == correct:
                    message = "正解！🔥"
                else:
                    message = f"違います。正解は {correct}"

                user_state[user_id]["answer"] = None

                data = {
                    "replyToken": reply_token,
                    "messages":[{"type":"text","text": message}]
                }

            else:
                data = {
                    "replyToken": reply_token,
                    "messages":[
                        {"type":"text",
                         "text": "「初級」または「中級」を送ってください。"}
                    ]
                }

            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                data=json.dumps(data)
            )

    return "OK"
