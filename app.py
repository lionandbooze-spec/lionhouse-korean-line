from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

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
# 習熟度計算
# ======================
def calculate_mastery(user_id, category, level):
    if user_id not in user_progress:
        return 0
    if category not in user_progress[user_id]:
        return 0
    if level not in user_progress[user_id][category]:
        return 0

    progress = user_progress[user_id][category][level]
    total_words = len(words[category][level])
    if total_words == 0:
        return 0

    mastered = 0
    for w in words[category][level]:
        if progress.get(w["kr"], 0) >= 5:
            mastered += 1

    return int((mastered / total_words) * 100)

# ======================
# カテゴリUI
# ======================
def category_menu():
    buttons = []
    for cat in words.keys():
        buttons.append({
            "type": "button",
            "action": {"type": "message", "label": cat, "text": cat},
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
                    {"type": "text", "text": "カテゴリを選んでください", "weight": "bold", "size": "lg"}
                ] + buttons
            }
        }
    }

# ======================
# レベルUI
# ======================
def level_menu(category):
    buttons = []
    for level in words[category].keys():
        buttons.append({
            "type": "button",
            "action": {"type": "message", "label": level, "text": level},
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
                    {"type": "text", "text": f"{category} のレベルを選んでください", "weight": "bold", "size": "lg"}
                ] + buttons
            }
        }
    }

# ======================
# セット生成
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
    if group1:
        selected += random.sample(group1, min(7, len(group1)))
    if group2:
        selected += random.sample(group2, min(2, len(group2)))
    if group3:
        selected += random.sample(group3, min(1, len(group3)))

    while len(selected) < 10 and len(selected) < len(all_words):
        candidate = random.choice(all_words)
        if candidate not in selected:
            selected.append(candidate)

    random.shuffle(selected)
    return selected

# ======================
# 教材ブロック
# ======================
def build_learning_block(word, level, streak):
    if streak < 2:
        return ""

    text_block = "\n\n"

    if word["type"] == "verb":
        conj = word.get("conjugation", {})
        if level == "基礎":
            section = conj.get("basic", {})
        elif level == "応用":
            section = conj.get("intermediate", {})
        else:
            section = conj.get("advanced", {})

        if section:
            text_block += "🔄 表現\n"
            for key, value in section.items():
                if key == "conversation":
                    text_block += "\n💬 会話\n"
                    for line in value:
                        text_block += f"{line}\n"
                else:
                    text_block += f"{value[0]}（{value[1]}）\n"

    elif word["type"] in ["noun", "adjective"]:
        example = word.get("example", {})
        section = example.get(
            "basic" if level == "基礎"
            else "intermediate" if level == "応用"
            else "advanced",
            {}
        )

        if section:
            text_block += "📘 例文\n"
            text_block += f"{section['kr']}\n"
            text_block += f"（{section['jp']}）\n"

    return text_block

# ======================
# 結果UI
# ======================
def result_menu(result_text):
    return {
        "type": "flex",
        "altText": "結果",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": result_text, "wrap": True},
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "▶ 次の問題へ", "text": "次へ"},
                        "style": "primary",
                        "margin": "lg"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "やめる", "text": "やめる"},
                        "style": "secondary"
                    }
                ]
            }
        }
    }

# ======================
# セット終了UI
# ======================
def end_set_menu(category, level, correct_count, total, mastery):
    return {
        "type": "flex",
        "altText": "セット終了",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {"type": "text", "text": "🎉 セット終了！", "weight": "bold", "size": "xl"},
                    {"type": "text", "text": f"正解数：{correct_count} / {total}"},
                    {"type": "text", "text": f"習熟度：{mastery}%"},
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#6CC4A1",
                        "action": {"type": "message", "label": "▶ 同じ条件でもう一度やる", "text": "もう一度"}
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "margin": "md",
                        "action": {"type": "message", "label": "▶ カテゴリ・レベルを選び直す", "text": "最初から"}
                    }
                ]
            }
        }
    }

# ======================
# 問題生成
# ======================
def create_question(user_id):
    state = user_state[user_id]

    if state["index"] >= len(state["current_set"]):
        state["index"] = 0

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
    if correct in pool:
        pool.remove(correct)

    choices = random.sample(pool, min(3, len(pool)))
    choices.append(correct)
    random.shuffle(choices)

    state["correct"] = correct
    state["choices"] = choices

    colors = ["#4C8BF5", "#6CC4A1", "#F6B26B", "#C27BA0"]

    rows = []
    for i in range(0, len(choices), 2):
        row = {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": []}
        for j in range(2):
            if i + j < len(choices):
                idx = i + j
                row["contents"].append({
                    "type": "button",
                    "action": {"type": "message", "label": choices[idx], "text": choices[idx]},
                    "style": "primary",
                    "color": colors[idx],
                    "flex": 1
                })
        rows.append(row)

    return {
        "type": "flex",
        "altText": "クイズ問題",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {"type": "text", "text": prompt, "weight": "bold", "size": "xl", "wrap": True}
                ] + rows
            }
        }
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

        # やめる
        if text == "やめる":
            user_state.pop(user_id, None)
            send_reply(reply_token, [category_menu()])
            continue

        # 次へ
        if text == "次へ" and user_id in user_state:
            state = user_state[user_id]
            state["index"] += 1

            if state["index"] >= len(state["current_set"]):
                category = state["category"]
                level = state["level"]
                correct_count = state["correct_count"]
                total = len(state["current_set"])
                mastery = calculate_mastery(user_id, category, level)

                send_reply(reply_token, [
                    end_set_menu(category, level, correct_count, total, mastery)
                ])
                continue

            send_reply(reply_token, [create_question(user_id)])
            continue

        # もう一度
        if text == "もう一度" and user_id in user_state:
            state = user_state[user_id]
            category = state["category"]
            level = state["level"]

            state["current_set"] = build_question_set(user_id, category, level)
            state["index"] = 0
            state["correct_count"] = 0

            send_reply(reply_token, [create_question(user_id)])
            continue

        # 最初から
        if text == "最初から":
            user_state.pop(user_id, None)
            send_reply(reply_token, [category_menu()])
            continue

        # カテゴリ選択
        if text in words:
            user_state[user_id] = {"category": text}
            send_reply(reply_token, [level_menu(text)])
            continue

        # レベル選択
        if user_id in user_state and "category" in user_state[user_id]:
            category = user_state[user_id]["category"]
            if text in words[category]:
                user_state[user_id]["level"] = text
                user_state[user_id]["current_set"] = build_question_set(user_id, category, text)
                user_state[user_id]["index"] = 0
                user_state[user_id]["correct_count"] = 0
                send_reply(reply_token, [create_question(user_id)])
                continue

        # 回答処理
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
                    state["correct_count"] += 1
                    result = "正解！🔥"
                else:
                    streak = max(0, streak - 2)
                    result = f"違います。正解は {correct}"

                progress[key] = streak

                fire = "🔥" * streak
                remain = max(0, 5 - streak)

                if streak >= 5:
                    streak_text = "\n\n🔥🔥🔥🔥🔥 (5 / 5)\n習熟達成！🎉"
                else:
                    streak_text = f"\n\n{fire} ({streak} / 5)\nあと{remain}回で習熟！"

                result += streak_text
                result += build_learning_block(question, level, streak)

                send_reply(reply_token, [result_menu(result)])
                continue

        send_reply(reply_token, [category_menu()])

    return "OK"

if __name__ == "__main__":
    app.run()
