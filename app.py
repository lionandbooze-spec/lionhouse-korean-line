from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

BASE_PATH = "data"

user_state = {}

# ======================
# 共通：LINE送信
# ======================
def send_reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": messages
    }
    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(data)
    )

# ======================
# 単語読み込み
# ======================
def load_words(category, level):
    file_path = f"{BASE_PATH}/{category}/{level}.json"
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

# ======================
# カテゴリUI
# ======================
def category_menu():
    return {
        "type": "text",
        "text": "カテゴリを選択してください",
        "quickReply": {
            "items": [
                {"type": "action","action":{"type":"message","label":"🏠 日常","text":"daily"}},
                {"type": "action","action":{"type":"message","label":"🌍 自然・身体","text":"nature"}},
                {"type": "action","action":{"type":"message","label":"⏰ 時間・数","text":"time"}},
                {"type": "action","action":{"type":"message","label":"🧩 文法","text":"grammar"}},
                {"type": "action","action":{"type":"message","label":"💬 表現","text":"expression"}}
            ]
        }
    }

# ======================
# レベルUI
# ======================
def level_menu():
    return {
        "type": "text",
        "text": "レベルを選択してください",
        "quickReply": {
            "items": [
                {"type":"action","action":{"type":"message","label":"基礎","text":"basic"}},
                {"type":"action","action":{"type":"message","label":"応用","text":"applied"}},
                {"type":"action","action":{"type":"message","label":"実践","text":"practical"}}
            ]
        }
    }

# ======================
# クイズ作成
# ======================
def create_question(user_id):

    category = user_state[user_id]["category"]
    level = user_state[user_id]["level"]

    words = load_words(category, level)
    if not words:
        return {"type":"text","text":"データがありません"}

    random.shuffle(words)
    word = words[0]

    # --- 実践（会話） ---
    if level == "practical":

        prompt = f"『\n{word['kr']}\n』\n日本語訳は？"
        correct = word["jp"]

        wrong = [w["jp"] for w in words if w["jp"] != correct]
        wrong = random.sample(wrong, min(3, len(wrong)))
        choices = wrong + [correct]
        random.shuffle(choices)

    else:
        direction = random.choice(["kr_to_jp","jp_to_kr"])

        if direction == "kr_to_jp":
            prompt = f"『{word['kr']}』の意味は？"
            correct = word["jp"]
            wrong = [w["jp"] for w in words if w["jp"] != correct]
        else:
            prompt = f"『{word['jp']}』は韓国語で？"
            correct = word["kr"]
            wrong = [w["kr"] for w in words if w["kr"] != correct]

        wrong = random.sample(wrong, min(3, len(wrong)))
        choices = wrong + [correct]
        random.shuffle(choices)

    user_state[user_id]["current"] = {
        "correct": correct,
        "choices": choices
    }

    return build_quiz_flex(prompt, choices)

# ======================
# 4択UI
# ======================
def build_quiz_flex(prompt, choices):

    buttons = []
    colors = ["#6CC4A1","#5DA9E9","#F6BD60","#E76F51"]

    for i,choice in enumerate(choices):
        buttons.append({
            "type":"button",
            "action":{"type":"message","label":choice,"text":choice},
            "style":"primary",
            "color":colors[i % 4]
        })

    return {
        "type":"flex",
        "altText":"クイズ問題",
        "contents":{
            "type":"bubble",
            "body":{
                "type":"box",
                "layout":"vertical",
                "spacing":"md",
                "contents":[
                    {"type":"text","text":prompt,"wrap":True,"weight":"bold","size":"md"},
                    *buttons,
                    {
                        "type":"button",
                        "action":{"type":"message","label":"練習をやめる","text":"stop"},
                        "style":"secondary"
                    }
                ]
            }
        }
    }

# ======================
# Webhook
# ======================
@app.route("/callback", methods=["POST"])
def callback():

    body = request.get_json()
    events = body.get("events",[])

    for event in events:

        if event["type"] != "message":
            continue

        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = event["message"]["text"]

        # 初回
        if text == "start":
            send_reply(reply_token,[category_menu()])
            continue

        # カテゴリ選択
        if text in ["daily","nature","time","grammar","expression"]:
            user_state[user_id] = {"category":text}
            send_reply(reply_token,[level_menu()])
            continue

        # レベル選択
        if text in ["basic","applied","practical"] and user_id in user_state:
            user_state[user_id]["level"] = text
            user_state[user_id]["score"] = 0
            user_state[user_id]["count"] = 0
            question = create_question(user_id)
            send_reply(reply_token,[question])
            continue

        # 終了
        if text == "stop":
            send_reply(reply_token,[category_menu()])
            continue

        # 回答処理
        if user_id in user_state and "current" in user_state[user_id]:

            correct = user_state[user_id]["current"]["correct"]

            if text == correct:
                user_state[user_id]["score"] += 1
                result = "✅ 正解！"
            else:
                result = f"❌ 不正解\n正解：{correct}"

            user_state[user_id]["count"] += 1

            # 10問で終了
            if user_state[user_id]["count"] >= 10:

                score = user_state[user_id]["score"]

                send_reply(reply_token,[{
                    "type":"text",
                    "text":f"🎉 セット終了！\n\n正解数：{score} / 10"
                },
                {
                    "type":"text",
                    "text":"もう一度やりますか？",
                    "quickReply":{
                        "items":[
                            {"type":"action","action":{"type":"message","label":"同じ条件で続ける","text":"again"}},
                            {"type":"action","action":{"type":"message","label":"カテゴリへ戻る","text":"start"}}
                        ]
                    }
                }])
                continue

            question = create_question(user_id)
            send_reply(reply_token,[{"type":"text","text":result},question])
            continue

        if text == "again" and user_id in user_state:
            user_state[user_id]["score"] = 0
            user_state[user_id]["count"] = 0
            question = create_question(user_id)
            send_reply(reply_token,[question])
            continue

        send_reply(reply_token,[category_menu()])

    return "OK"

if __name__ == "__main__":
    app.run()
