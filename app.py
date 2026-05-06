from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

# 単語リスト（あとで増やせる）
words = [
    {"jp": "こんにちは", "kr": "안녕하세요"},
    {"jp": "ありがとう", "kr": "감사합니다"},
    {"jp": "さようなら", "kr": "안녕히 가세요"},
]

# ユーザーごとの正解を保存
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

            # スタートで問題出題
            if text == "スタート":
                question = random.choice(words)
                user_state[user_id] = question["kr"]

                data = {
                    "replyToken": reply_token,
                    "messages":[
                        {"type":"text",
                         "text": f"{question['jp']} は韓国語で？"}
                    ]
                }

            # 回答チェック
            elif user_id in user_state:
                correct = user_state[user_id]

                if text == correct:
                    message = "正解！🔥"
                else:
                    message = f"違います。正解は {correct}"

                data = {
                    "replyToken": reply_token,
                    "messages":[{"type":"text","text": message}]
                }

                # 問題リセット
                del user_state[user_id]

            else:
                data = {
                    "replyToken": reply_token,
                    "messages":[{"type":"text","text":"「スタート」と送ってください"}]
                }

            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                data=json.dumps(data)
            )

    return "OK"
