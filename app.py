from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

DATA_PATH = "data"

CATEGORY_MAP = {
    "🏠 日常": "daily",
    "🌍 自然・身体": "nature",
    "⏰ 時間・数": "time",
    "🧩 文法": "grammar",
    "💬 表現": "expression"
}

LEVEL_MAP = {
    "基礎": "basic",
    "応用": "applied",
    "実践": "practical"
}

user_state = {}

# ------------------------
# データ読み込み
# ------------------------

def load_words(category, level):
    file_path = os.path.join(DATA_PATH, category, f"{level}.json")

    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# ------------------------
# LINE送信
# ------------------------

def send_reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    body = {
        "replyToken": reply_token,
        "messages": messages
    }

    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(body)
    )

# ------------------------
# 問題生成
# ------------------------

def create_question(user_id):
    state = user_state[user_id]

    if state["index"] >= len(state["words"]):
        return {
            "type": "text",
            "text": f"🎉 セット終了！\n正解数：{state['correct']} / {len(state['words'])}"
        }

    word = state["words"][state["index"]]

    correct = word["jp"]
    wrong_pool = [w["jp"] for w in state["words"] if w["jp"] != correct]

    choices = random.sample(wrong_pool, min(3, len(wrong_pool)))
    choices.append(correct)
    random.shuffle(choices)

    state["correct_answer"] = correct
    state["choices"] = choices

    return {
        "type": "text",
        "text": f"『{word['kr']}』の意味は？\n\n" + "\n".join(choices)
    }

# ------------------------
# Webhook
# ------------------------

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] != "message":
            continue

        if event["message"]["type"] != "text":
            continue

        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = event["message"]["text"]

        # ------------------
        # カテゴリ選択
        # ------------------

        if text in CATEGORY_MAP:
            user_state[user_id] = {
                "category": CATEGORY_MAP[text]
            }
            send_reply(reply_token, [{
                "type": "text",
                "text": "レベルを選んでください\n基礎 / 応用 / 実践"
            }])
            return "OK"

        # ------------------
        # レベル選択
        # ------------------

        if text in LEVEL_MAP and user_id in user_state:
            category = user_state[user_id]["category"]
            level = LEVEL_MAP[text]

            words = load_words(category, level)

            if not words:
                send_reply(reply_token, [{
                    "type": "text",
                    "text": "まだ単語が登録されていません。"
                }])
                return "OK"

            random.shuffle(words)

            user_state[user_id].update({
                "level": level,
                "words": words,
                "index": 0,
                "correct": 0,
                "correct_answer": "",
                "choices": []
            })

            question = create_question(user_id)
            send_reply(reply_token, [question])
            return "OK"

        # ------------------
        # 回答処理
        # ------------------

        if user_id in user_state and "correct_answer" in user_state[user_id]:

            state = user_state[user_id]

            if text == state["correct_answer"]:
                state["correct"] += 1
                result = "正解！🔥"
            else:
                result = f"違います。正解は {state['correct_answer']}"

            state["index"] += 1

            next_question = create_question(user_id)

            send_reply(reply_token, [
                {"type": "text", "text": result},
                next_question
            ])
            return "OK"

        # ------------------
        # 初期表示
        # ------------------

        send_reply(reply_token, [{
            "type": "text",
            "text": "カテゴリを選んでください\n🏠 日常"
        }])

    return "OK"


if __name__ == "__main__":
    app.run()
