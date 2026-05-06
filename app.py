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
                    "playing": False,
                    "answer": None,
                    "question_count": 0,
                    "correct_count": 0
                }

                message = f"{text}レベルを選択しました。\n「スタート」と送ってください。"

            # スタート
            elif text == "スタート":
                if user_id in user_state:
                    user_state[user_id]["playing"] = True
                    user_state[user_id]["question_count"] = 0
                    user_state[user_id]["correct_count"] = 0

                    level = user_state[user_id]["level"]
                    question = random.choice(words[level])
                    user_state[user_id]["answer"] = question["kr"]

                    message = f"第1問👇\n{question['jp']} は韓国語で？"
                else:
                    message = "まず「初級」または「中級」を選んでください。"

            # 終了
            elif text == "終了":
                if user_id in user_state:
                    user_state[user_id]["playing"] = False
                    message = "クイズを終了しました。"
                else:
                    message = "クイズは開始していません。"

            # 回答処理
            elif user_id in user_state and user_state[user_id].get("playing"):
                correct = user_state[user_id]["answer"]
                level = user_state[user_id]["level"]

                user_state[user_id]["question_count"] += 1

                if text == correct:
                    user_state[user_id]["correct_count"] += 1
                    result = "正解！🔥"
                else:
                    result = f"違います。正解は {correct}"

                # 5問終了判定
                if user_state[user_id]["question_count"] >= 5:
                    total = user_state[user_id]["question_count"]
                    correct_num = user_state[user_id]["correct_count"]
                    accuracy = int((correct_num / total) * 100)

                    message = (
                        f"{result}\n\n"
                        f"🎉 5問終了！\n"
                        f"正解数：{correct_num} / {total}\n"
                        f"正答率：{accuracy}%\n\n"
                        f"もう一度やる場合は「スタート」と送ってください。"
                    )

                    user_state[user_id]["playing"] = False

                else:
                    next_q_num = user_state[user_id]["question_count"] + 1
                    question = random.choice(words[level])
                    user_state[user_id]["answer"] = question["kr"]

                    message = (
                        f"{result}\n\n"
                        f"第{next_q_num}問👇\n"
                        f"{question['jp']} は韓国語で？"
                    )

            else:
                message = "「初級」または「中級」を送ってください。"

            data = {
                "replyToken": reply_token,
                "messages":[{"type":"text","text": message}]
            }

            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                data=json.dumps(data)
            )

    return "OK"
