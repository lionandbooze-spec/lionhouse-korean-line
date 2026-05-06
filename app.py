from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

# ======================
# words.json 読み込み
# ======================
with open("words.json", "r", encoding="utf-8") as f:
    words = json.load(f)

user_state = {}
user_progress = {}

# ======================
# LINE返信
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
# カテゴリUI（縦並び）
# ======================
def category_menu():

    buttons = []

    for cat in words.keys():
        buttons.append({
            "type": "button",
            "action": {
                "type": "message",
                "label": cat,
                "text": cat
            },
            "style": "primary",
            "color": "#6CC4A1",
            "margin": "md"
        })

    return {
        "type": "flex",
        "altText": "カテゴリ選択",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "カテゴリを選んでください",
                        "weight": "bold",
                        "size": "lg"
                    }
                ] + buttons
            }
        }
    }

# ======================
# レベルUI（縦並び）
# ======================
def level_menu(category):

    buttons = []

    for level in words[category].keys():
        buttons.append({
            "type": "button",
            "action": {
                "type": "message",
                "label": level,
                "text": level
            },
            "style": "primary",
            "color": "#4C8BF5",
            "margin": "md"
        })

    return {
        "type": "flex",
        "altText": "レベル選択",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{category} のレベルを選んでください",
                        "weight": "bold",
                        "size": "lg"
                    }
                ] + buttons
            }
        }
    }

# ======================
# セット生成（70/20/10）
# ======================
def build_question_set(user_id, category, level):
    all_words = words[category][level]

    if user_id not in user_progress:
        user_progress[user_id] = {}

    if category not in user_progress[user_id]:
        user_progress[user_id][category] = {}

    if level not in user_progress[user_id][category]:
        user_progress[user_id][category][level] = {}

    progress = user_progress[user_id][category][level]

    group1, group2, group3 = [], [], []

    for w in all_words:
        key = w["kr"]
        streak = progress.get(key, 0)

        if streak <= 1:
            group1.append(w)
        elif 2 <= streak < 5:
            group2.append(w)
        else:
            group3.append(w)

    selected = []
    selected += random.sample(group1, min(7, len(group1)))
    selected += random.sample(group2, min(2, len(group2)))
    selected += random.sample(group3, min(1, len(group3)))

    while len(selected) < 10 and len(selected) < len(all_words):
        candidate = random.choice(all_words)
        if candidate not in selected:
            selected.append(candidate)

    random.shuffle(selected)
    return selected

# ======================
# 問題生成
# ======================
def create_question(user_id):
    state = user_state[user_id]
    question = state["current_set"][state["index"]]

    direction = random.choice(["jp_to_kr", "kr_to_jp"])

    if direction == "jp_to_kr":
        prompt = f"『{question['jp']}』は韓国語で？"
        correct = question["kr"]
        pool = [w["kr"] for w in words[state["category"]][state["level"]]]
    else:
        prompt = f"『{question['kr']}』は日本語で？"
        correct = question["jp"]
        pool = [w["jp"] for w in words[state["category"]][state["level"]]]

    pool = list(set(pool))
    pool.remove(correct)

    choices = random.sample(pool, min(3, len(pool)))
    choices.append(correct)
    random.shuffle(choices)

    state["correct"] = correct
    state["choices"] = choices

    quick_items = [{
        "type": "action",
        "action": {
            "type": "message",
            "label": c,
            "text": c
        }
    } for c in choices]

    return {
        "type": "text",
        "text": prompt,
        "quickReply": {"items": quick_items}
    }

# ======================
# Webhook
# ======================
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

        if text in words:
            user_state[user_id] = {"category": text}
            send_reply(reply_token, [level_menu(text)])
            continue

        if user_id in user_state and "category" in user_state[user_id]:
            category = user_state[user_id]["category"]

            if text in words[category]:
                user_state[user_id]["level"] = text
                user_state[user_id]["current_set"] = build_question_set(user_id, category, text)
                user_state[user_id]["index"] = 0
                send_reply(reply_token, [create_question(user_id)])
                continue

        if user_id in user_state and "current_set" in user_state[user_id]:
            state = user_state[user_id]

            if text in state.get("choices", []):
                correct = state["correct"]
                category = state["category"]
                level = state["level"]
                question = state["current_set"][state["index"]]

                key = question["kr"]
                progress = user_progress[user_id][category][level]
                streak = progress.get(key, 0)

                if text == correct:
                    streak += 1
                    result = "正解！🔥"
                else:
                    streak = max(0, streak - 2)
                    result = f"違います。正解は {correct}"

                progress[key] = streak
                state["index"] += 1

                if state["index"] >= 10:
                    mastered = sum(1 for v in progress.values() if v >= 5)
                    total = len(words[category][level])
                    percent = int((mastered / total) * 100) if total > 0 else 0

                    send_reply(reply_token, [{
                        "type": "text",
                        "text": f"{result}\n\n📊 習熟度：{percent}%\n（{mastered}/{total}習得）"
                    }, category_menu()])
                    del user_state[user_id]
                    continue

                send_reply(reply_token, [
                    {"type": "text", "text": result},
                    create_question(user_id)
                ])
                continue

        send_reply(reply_token, [category_menu()])

    return "OK"

if __name__ == "__main__":
    app.run()
