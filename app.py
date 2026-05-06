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

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] != "message":
            continue

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
                "question_count": 0,
                "correct_count": 0,
                "correct_answer": None,
                "choices": []
            }

            message = {
                "type": "text",
                "text": f"{text}レベルを選択しました。\n「スタート」と送ってください。"
            }

        # スタート
        elif text == "スタート":
            if user_id in user_state:
                user_state[user_id]["playing"] = True
                user_state[user_id]["question_count"] = 0
                user_state[user_id]["correct_count"] = 0
                message = create_question(user_id)
            else:
                message = {
                    "type": "text",
                    "text": "まず「初級」または「中級」を選んでください。"
                }

        # 回答処理
        elif user_id in user_state and user_state[user_id].get("playing"):

            correct = user_state[user_id]["correct_answer"]
            level = user_state[user_id]["level"]

            if text in user_state[user_id]["choices"]:
                user_state[user_id]["question_count"] += 1

                if text == correct:
                    user_state[user_id]["correct_count"] += 1
                    result = "正解！🔥"
                else:
                    result = f"違います。正解は {correct}"

                # 5問終了
                if user_state[user_id]["question_count"] >= 5:
                    total = user_state[user_id]["question_count"]
                    correct_num = user_state[user_id]["correct_count"]
                    accuracy = int((correct_num / total) * 100)

                    user_state[user_id]["playing"] = False

                    message = {
                        "type": "text",
                        "text": (
                            f"{result}\n\n"
                            f"🎉 5問終了！\n"
                            f"正解数：{correct_num} / {total}\n"
                            f"正答率：{accuracy}%\n\n"
                            f"もう一度やる場合は「スタート」と送ってください。"
                        )
                    }

                else:
                    next_question = create_question(user_id)
                    message = {
                        "type": "text",
                        "text": result
                    }

                    # 2メッセージ送る（結果＋次の問題）
                    data = {
                        "replyToken": reply_token,
                        "messages": [
                            message,
                            next_question
                        ]
                    }

                    requests.post(
                        "https://api.line.me/v2/bot/message/reply",
                        headers=headers,
                        data=json.dumps(data)
                    )
                    continue

            else:
                message = {
                    "type": "text",
                    "text": "下のボタンから選んでください。"
                }

        else:
            message = {
                "type": "text",
                "text": "「初級」または「中級」を送ってください。"
            }

        data = {
            "replyToken": reply_token,
            "messages": [message]
        }

        requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=headers,
            data=json.dumps(data)
        )

    return "OK"


def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])
    correct = question["kr"]

    wrong = [w["kr"] for w in words[level] if w["kr"] != correct]
    choices = random.sample(wrong, 3) + [correct]
    random.shuffle(choices)

    user_state[user_id]["correct_answer"] = correct
    user_state[user_id]["choices"] = choices

    return {
        "type": "text",
        "text": f"{question['jp']} は韓国語で？",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": c,
                        "text": c
                    }
                } for c in choices
            ]
        }
    }
