from flask import Flask, request
import requests
import json
import os
import random

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

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

# 🔊 韓国語 → mp3ファイル名マッピング
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

        # レベル選択で即スタート
        if text in words.keys():
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

        # 音声再生ボタン
        elif text == "音声再生" and user_id in user_state and user_state[user_id].get("last_audio"):
            audio_url = user_state[user_id]["last_audio"]
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
        elif user_id in user_state and user_state[user_id].get("playing") and text in user_state[user_id]["choices"]:

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

                data = {
                    "replyToken": reply_token,
                    "messages": (
                        [{"type": "text", "text": result_text}]
                        + next_question
                        if isinstance(next_question, list)
                        else [{"type": "text", "text": result_text}, next_question]
                    )
                }

                requests.post(
                    "https://api.line.me/v2/bot/message/reply",
                    headers=headers,
                    data=json.dumps(data)
                )
                continue

        else:
            message = level_menu()

        data = {
            "replyToken": reply_token,
            "messages": message if isinstance(message, list) else [message]
        }

        requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=headers,
            data=json.dumps(data)
        )

    return "OK"


def level_menu(text="レベルを選んでください。"):
    return {
        "type": "text",
        "text": text,
        "quickReply": level_buttons()
    }


def level_buttons():
    return {
        "items": [
            {
                "type": "action",
                "action": {"type": "message", "label": "初級", "text": "初級"}
            },
            {
                "type": "action",
                "action": {"type": "message", "label": "中級", "text": "中級"}
            }
        ]
    }


def create_question(user_id):
    level = user_state[user_id]["level"]
    question = random.choice(words[level])

    direction = random.choice(["jp_to_kr", "kr_to_jp"])
    audio_message = None

    if direction == "jp_to_kr":
        prompt = f"『{question['jp']}』は韓国語で？"
        correct = question["kr"]
        wrong = [w["kr"] for w in words[level] if w["kr"] != correct]

    else:
        prompt = f"『{question['kr']}』は日本語で？"
        correct = question["jp"]
        wrong = [w["jp"] for w in words[level] if w["jp"] != correct]

        audio_file = filename_map.get(question["kr"])
        audio_url = f"https://lionhouse-korean-line.onrender.com/static/{audio_file}"

        audio_message = {
            "type": "audio",
            "originalContentUrl": audio_url,
            "duration": 2000
        }

        user_state[user_id]["last_audio"] = audio_url

    choices = random.sample(wrong, 3) + [correct]
    random.shuffle(choices)

    user_state[user_id]["correct_answer"] = correct
    user_state[user_id]["choices"] = choices

    rows = []
    for i in range(0, 4, 2):
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                build_button(choices[i]),
                build_button(choices[i+1])
            ]
        })

    flex = {
        "type": "flex",
        "altText": "クイズ問題",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "text",
                        "text": prompt,
                        "weight": "bold",
                        "size": "lg"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "message",
                            "label": "🔊 もう一度聞く",
                            "text": "音声再生"
                        },
                        "style": "secondary"
                    }
                ] + rows + [
                    {
                        "type": "button",
                        "action": {
                            "type": "message",
                            "label": "やめる",
                            "text": "やめる"
                        },
                        "style": "link"
                    }
                ]
            }
        }
    }

    return [audio_message, flex] if audio_message else [flex]


def build_button(text):
    return {
        "type": "button",
        "action": {
            "type": "message",
            "label": text,
            "text": text
        },
        "style": "primary",
        "color": "#6CC4A1",
        "flex": 1
    }
