from flask import Flask, request
import requests
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

# ----------------------------
# 単語データ
# ----------------------------
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
# LINE返信（デバッグ付き）
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

    print("=== LINE Reply ===")
    print(res.status_code)
    print(res.text)
    print("==================")

# ----------------------------
# PDF風ボタン
# ----------------------------
def build_pdf_button(text, highlight=False):
    bg = "#B7E2EE" if highlight else "#CDEBF3"

    return {
        "type": "box",
        "layout": "vertical",
        "paddingAll": "16px",
        "backgroundColor": bg,
        "cornerRadius": "18px",
        "flex": 1,
        "action": {
            "type": "message",
            "label": text,
            "text": text
        },
        "contents": [
            {
                "type": "text",
                "text": text,
                "align": "center",
                "color": "#3A4A63",
                "weight": "bold"
            }
        ]
    }

# ----------------------------
# レベル選択画面
# ----------------------------
def level_menu():
    return {
        "type": "flex",
        "altText": "レベル選択",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "backgroundColor": "#EAF6FB",
                "contents": [
                    {
                        "type": "text",
                        "text": "レベルを選んでください",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#3A4A63"
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "spacing": "md",
                        "contents": [
                            build_pdf_button("初級"),
                            build_pdf_button("中級")
                        ]
                    }
                ]
            }
        }
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

    highlight = user_state[user_id].get("just_correct", False)
    user_state[user_id]["just_correct"] = False

    contents = [
        {
            "type": "text",
            "text": prompt,
            "weight": "bold",
            "size": "lg",
            "color": "#3A4A63"
        }
    ]

    for i in range(0, len(choices), 2):
        row = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "md",
            "contents": []
        }

        row["contents"].append(build_pdf_button(choices[i], highlight))

        if i + 1 < len(choices):
            row["contents"].append(build_pdf_button(choices[i + 1], highlight))

        contents.append(row)

    contents.append({
        "type": "box",
        "layout": "vertical",
        "paddingAll": "14px",
        "backgroundColor": "#CDEBF3",
        "cornerRadius": "18px",
        "action": {
            "type": "message",
            "label": "練習をやめる",
            "text": "やめる"
        },
        "contents": [
            {
                "type": "text",
                "text": "練習をやめる",
                "align": "center",
                "color": "#3A4A63"
            }
        ]
    })

    return {
        "type": "flex",
        "altText": "クイズ",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "backgroundColor": "#EAF6FB",
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

        # レベル選択
        if text in words:
            user_state[user_id] = {
                "level": text,
                "playing": True,
                "count": 0,
                "score": 0,
                "just_correct": False
            }

            reply(reply_token, [create_question(user_id)])
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
                    user_state[user_id]["just_correct"] = True
                    result = "正解！🔥"
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

                reply(reply_token, [
                    {"type": "text", "text": result},
                    create_question(user_id)
                ])
                continue

        # 何を送ってもレベル選択表示
        reply(reply_token, [level_menu()])

    return "OK"


if __name__ == "__main__":
    app.run()
