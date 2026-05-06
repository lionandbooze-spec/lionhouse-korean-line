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
