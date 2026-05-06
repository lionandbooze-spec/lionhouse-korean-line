from flask import Flask, request
import requests
import json
import os
import random
from urllib.parse import quote

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

# ----------------------
# 単語データ
# ----------------------
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

# ----------------------
# 音声ファイル対応
# ----------------------
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

BASE_AUDIO_URL = "https://raw.githubusercontent.com/lionandbooze-spec/lionhouse-korean-line/main/audio/"

user_state = {}

# ----------------------
# LINE reply
# ----------------------
def send_reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    data = {
        "replyToken": reply_token,
        "messages": messages
    }

    res = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(data)
    )

    print("Reply:", res.status_code)
    print(res.text)


# ----------------------
# LINE push（音声）
# ----------------------
def push_audio(user_id, audio_url):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    data = {
        "to": user_id,
        "messages": [
            {
                "type": "audio",
                "originalContentUrl": audio_url,
                "duration": 1000
            }
        ]
    }

    res = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        data=json.dumps(data)
    )

    print("Push:", res.status_code)
    print(res.text)


# ----------------------
# レベルメニュー
# ----------------------
def level_menu(text="レベルを選んでください。"):
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "message", "label": "初級", "text": "初級"}},
                {"type": "action", "action": {"type": "message", "label": "中級", "text": "中級"}}
            ]
        }
    }


# ----------------------
# ボタン生成
# ----------------------
def build_button(text):
    return {
        "type": "button",
        "action": {"type": "message", "label": text, "text": text},
        "style": "primary",
        "color": "#6CC4A1",
        "flex": 1
    }


# ----------------------
# 問題生成
# ----------------------
def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])
    direction = random.choice(["jp_to_kr", "kr_to_jp"])

    if direction == "jp_to_kr":
        prompt = f"『{question['jp']}』は韓国語で？"
        correct = question["kr"]
        wrong = [w["kr"] for w in words[level] if w["kr"] != correct]
        user_state[user_id]["last_audio"] = None

    else:
        prompt = f"『{question['kr']}』は日本語で？"
        correct = question["jp"]
        wrong = [w["jp"] for w in words[level] if w["jp"] != correct]

        audio_file = filename_map.get(question["kr"])
        if audio_file:
            encoded_file = quote(audio_file)
            audio_url = BASE_AUDIO_URL + encoded_file
            user_state[user_id]["last_audio"] = audio_url

    wrong = list(set(wrong))
    choices = random.sample(wrong, min(3, len(wrong)))
    choices.append(correct)
    random.shuffle(choices)

    user_state[user_id]["correct_answer"] = correct
    user_state[user_id]["choices"] = choices

    contents = [
        {"type": "text", "text": prompt, "weight": "bold", "size": "lg"}
    ]

    # 韓→日の時だけ音声ボタン
    if user_state[user_id].get("last_audio"):
        contents.append({
            "type": "button",
            "action": {"type": "message", "label": "🔊 もう一度聞く", "text": "音声再生"},
            "style": "secondary"
        })

    # 選択肢ボタン
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
        contents.append(row)

    # やめるボタン
    contents.append({
        "type": "button",
        "action": {"type": "message", "label": "やめる", "text": "やめる"},
        "style": "link"
    })

    return {
        "type": "flex",
        "altText": "クイズ問題",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": contents
            }
        }
    }


# ----------------------
# Webhook
# ----------------------
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

            flex = create_question(user_id)
            send_reply(reply_token, [flex])

            # 音声があればpush
            audio_url = user_state[user_id].get("last_audio")
            if audio_url:
                push_audio(user_id, audio_url)
            continue

        # 音声再生
        if text == "音声再生" and user_id in user_state:
            audio_url = user_state[user_id].get("last_audio")
            if audio_url:
                push_audio(user_id, audio_url)
            continue

        # やめる
        if text == "やめる" and user_id in user_state:
            user_state[user_id]["playing"] = False
            send_reply(reply_token, [level_menu("クイズを終了しました。")])
            continue

        # 回答処理
        if user_id in user_state and user_state[user_id].get("playing"):
            if text in user_state[user_id]["choices"]:

                correct = user_state[user_id]["correct_answer"]
                user_state[user_id]["question_count"] += 1

                if text == correct:
                    user_state[user_id]["correct_count"] += 1
                    result_text = "正解！🔥"
                else:
                    result_text = f"違います。正解は {correct}"

                if user_state[user_id]["question_count"] >= 5:
                    total = user_state[user_id]["question_count"]
                    correct_num = user_state[user_id]["correct_count"]
                    accuracy = int((correct_num / total) * 100)
                    user_state[user_id]["playing"] = False

                    send_reply(reply_token, [{
                        "type": "text",
                        "text": (
                            f"{result_text}\n\n"
                            f"🎉 5問終了！\n"
                            f"正解数：{correct_num} / {total}\n"
                            f"正答率：{accuracy}%"
                        )
                    }, level_menu()])
                    continue

                flex = create_question(user_id)
                send_reply(reply_token, [
                    {"type": "text", "text": result_text},
                    flex
                ])

                audio_url = user_state[user_id].get("last_audio")
                if audio_url:
                    push_audio(user_id, audio_url)

    return "OK"


if __name__ == "__main__":
    app.run()
