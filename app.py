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
        audio_url = f"https://lionhouse-korean-line.onrender.com/static/{audio_file}"

        audio_message = {
            "type": "audio",
            "originalContentUrl": audio_url,
            "duration": 2000
        }

        user_state[user_id]["last_audio"] = audio_url
        show_audio_button = True

    choices = random.sample(wrong, 3) + [correct]
    random.shuffle(choices)

    user_state[user_id]["correct_answer"] = correct
    user_state[user_id]["choices"] = choices

    contents = [
        {
            "type": "text",
            "text": prompt,
            "weight": "bold",
            "size": "lg"
        }
    ]

    # 🔊 韓→日のときだけ表示
    if show_audio_button:
        contents.append({
            "type": "button",
            "action": {
                "type": "message",
                "label": "🔊 もう一度聞く",
                "text": "音声再生"
            },
            "style": "secondary"
        })

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

    contents.extend(rows)

    contents.append({
        "type": "button",
        "action": {
            "type": "message",
            "label": "やめる",
            "text": "やめる"
        },
        "style": "link"
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
                "contents": contents
            }
        }
    }

    return [audio_message, flex] if audio_message else [flex]
