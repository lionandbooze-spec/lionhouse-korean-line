from flask import Flask, request, send_from_directory
import requests
import json
import os
import random

app = Flask(__name__, static_url_path='/static')

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

# --- 単語データ ---
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

# --- 音声ファイル対応表（staticフォルダ内に置く）---
filename_map = {
    "안녕하세요": "안녕하세요.mp3",
    "감사합니다": "감사합니다.mp3",
    "안녕히 가세요": "안녕히 가세요.mp3",
    "네": "네.mp3",
    "아니요": "아니요.mp3",
    "약속": "약속.mp3",
    "경험": "경험.mp3",
    "이유": "이유.mp3",
    "준비": "준비.mp3",
    "선택": "선택.mp3",
}

user_state = {}

# --- static公開 ---
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# --- Webhook ---
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

        message = None

        # レベル選択
        if text in words:
            user_state[user_id] = {
                "level": text,
                "playing": True,
                "question_count": 0,
                "correct_count": 0,
                "correct_answer": None,
                "choices": [],
                "last_audio": None
            }
            message = create_question(user_id)

        # 音声再生
        elif text == "音声再生" and user_id in user_state:
            audio_url = user_state[user_id].get("last_audio")
            if audio_url:
                message = {
                    "type": "audio",
                    "originalContentUrl": audio_url,
                    "duration": 2000
                }

        # やめる
        elif text == "やめる" and user_id in user_state:
            user_state[user_id]["playing"] = False
            message = level_menu("クイズを終了しました。")

        # 回答処理
        elif user_id in user_state and user_state[user_id].get("playing"):
            if text in user_state[user_id]["choices"]:

                correct = user_state[user_id]["correct_answer"]
                user_state[user_id]["question_count"] += 1

                if text == correct:
                    user_state[user_id]["correct_count"] += 1
                    result_text = "正解！🔥"
                else:
                    result_text = f"違います。正解は {correct}"

                # 5問終了
                if user_state[user_id]["question_count"] >= 5:
                    total = user_state[user_id]["question_count"]
                    correct_num = user_state[user_id]["correct_count"]
                    accuracy = int((correct_num / total) * 100)

                    user_state[user_id]["playing"] = False

                    message = {
                        "type": "text",
                        "text": (
                            f"{result_text}\n\n"
                            f"🎉 5問終了！\n"
                            f"正解数：{correct_num} / {total}\n"
                            f"正答率：{accuracy}%"
                        ),
                        "quickReply": level_buttons()
                    }

                else:
                    next_question = create_question(user_id)

                    messages = [{"type": "text", "text": result_text}]
                    if isinstance(next_question, list):
                        messages.extend(next_question)
                    else:
                        messages.append(next_question)

                    send_reply(reply_token, messages, headers)
                    continue

        if not message:
            message = level_menu()

        if isinstance(message, list):
            messages = message
        else:
            messages = [message]

        send_reply(reply_token, messages, headers)

    return "OK"

# --- LINE送信 ---
def send_reply(reply_token, messages, headers):
    data = {
        "replyToken": reply_token,
        "messages": messages
    }

    response = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(data)
    )

    print(response.status_code)
    print(response.text)

# --- レベルメニュー ---
def level_menu(text="レベルを選んでください。"):
    return {
        "type": "text",
        "text": text,
        "quickReply": level_buttons()
    }

def level_buttons():
    return {
        "items": [
            {"type": "action", "action": {"type": "message", "label": "初級", "text": "初級"}},
            {"type": "action", "action": {"type": "message", "label": "中級", "text": "中級"}}
        ]
    }

# --- 問題生成 ---
def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])

    direction = random.choice(["jp_to_kr", "kr_to_jp"])
    audio_message = None
    show_audio_button = False

    if direction == "jp_to_kr":
        prompt = f"『{question['jp']}』は韓国語で？"
        correct = question["kr"]
        wrong = [w["kr"] for w in words[level] if w["kr"] != correct]

    else:
        prompt = f"『{question['kr']}』は日本語で？"
        correct = question["jp"]
        wrong = [w["jp"] for w in words[level] if w["jp"] != correct]

        audio_file = filename_map.get(question["kr"])
        if audio_file:
            audio_url = f"https://lionhouse-korean-line.onrender.com/static/{audio_file}"
            user_state[user_id]["last_audio"] = audio_url
            audio_message = {
                "type": "audio",
                "originalContentUrl": audio_url,
                "duration": 2000
            }
            show_audio_button = True

    wrong = list(set(wrong))
    if len(wrong) >= 3:
        choices = random.sample(wrong, 3)
    else:
        choices = wrong.copy()

    choices.append(correct)
    random.shuffle(choices)

    user_state[user_id]["correct_answer"] = correct
    user_state[user_id]["choices"] = choices

    contents = [
        {"type": "text", "text": prompt, "weight": "bold", "size": "lg"}
    ]

    if show_audio_button:
        contents.append({
            "type": "button",
            "action": {"type": "message", "label": "🔊 もう一度聞く", "text": "音声再生"},
            "style": "secondary"
        })

    rows = []
    for i in range(0, len(choices), 2):
        row = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": []
        }

        row["contents"].append(build_button(choices[i]))
        if i + 1 < len(choices):
            row["contents"].append(build_button(choices[i+1]))

        rows.append(row)

    contents.extend(rows)

    contents.append({
        "type": "button",
        "action": {"type": "message", "label": "やめる", "text": "やめる"},
        "style": "link"
    })

    flex = {
        "type": "flex",
        "altText": "クイズ問題",
        "contents": {
            "type": "bubble",
            "body": {"type": "box", "layout": "vertical", "spacing": "lg", "contents": contents}
        }
    }

    # 🔥 Flex → Audio の順で送る（LINE仕様対策）
    if audio_message:
        return [flex, audio_message]
    else:
        return [flex]

def build_button(text):
    return {
        "type": "button",
        "action": {"type": "message", "label": text, "text": text},
        "style": "primary",
        "color": "#6CC4A1",
        "flex": 1
    }

if __name__ == "__main__":
    app.run()
