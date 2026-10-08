"""AI analysis with a grounded extractive fallback for local demos."""
import base64
import json
import os
import re
from collections import Counter

from openai import OpenAI

MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
STOPWORDS = set("""
 a an the and or but if then than so because as at by for from in into of on onto to up with
 is are was were be been being do does did can could should would will may might this that these
 those it its they them their we you your i he she his her our not no very more most some any all
 each other another such also only just about over under between through during after before use used
 using based called known include includes including make makes made help helps learn learned learn
 example examples material document notes study according key point points important main describe
 system systems field branch type types part parts thing things process processes method methods
""".split())
LOW_VALUE_TOPICS = {"ai", "data", "learning", "human", "intelligence", "language", "artificial", "patterns", "systems", "system", "model", "models", "examples", "tasks", "these tasks", "ai can", "process", "processes", "method", "methods", "computer", "computer science", "notes"}


def chunks(text, limit=10000):
    """Split text at sentence/paragraph boundaries and hard-cap unusually long lines."""
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    output, current = [], ""
    for piece in pieces:
        if len(piece) > limit:
            if current.strip():
                output.append(current.strip())
                current = ""
            output.extend(piece[i:i + limit] for i in range(0, len(piece), limit))
            continue
        if len(current) + len(piece) + 1 > limit and current:
            output.append(current.strip())
            current = ""
        current += piece + " "
    if current.strip():
        output.append(current.strip())
    return output or [text[:limit]]


def _llm_json(instruction, material):
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    response = OpenAI(
        api_key=key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={"HTTP-Referer": "http://127.0.0.1:5173", "X-OpenRouter-Title": "AI StudyMate"},
        timeout=90,
        max_retries=0,
    ).chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a careful study assistant. Use only facts supported by the supplied study material. Return valid JSON matching the requested schema. If the source is insufficient, say so rather than inventing facts."},
            {"role": "user", "content": instruction + "\n\nSTUDY MATERIAL:\n" + material},
        ],
        temperature=0.25,
    )
    return json.loads(response.choices[0].message.content)


def openrouter_error_message(error):
    details = str(error).lower()
    if "401" in details or "invalid_api_key" in details or "authentication" in details:
        return "OpenRouter rejected the configured key. Check backend/.env."
    if "403" in details or "permission" in details:
        return f"OpenRouter denied access to {MODEL}. Check this key's access."
    if "404" in details or "model_not_found" in details:
        return f"OpenRouter does not recognize model {MODEL}. Update OPENROUTER_MODEL in backend/.env."
    if "402" in details or "payment required" in details:
        return "OpenRouter says this request requires credits. The app is set to its free-model router; check the account's free access."
    if "400" in details or "badrequesterror" in details:
        return "OpenRouter could not process this request. Try a smaller or clearer PDF."
    if "429" in details or "rate limit" in details:
        return "OpenRouter's free-model request limit may have been reached. Wait and try again later."
    if "connection" in details or "timeout" in details:
        return "Could not reach OpenRouter. Check the internet connection and try again."
    return "OpenRouter could not complete this request. Check the key and try again."


def analyze_pdf_file(pdf_bytes, filename):
    """Render scanned PDF pages locally, OCR them with OpenRouter vision, then analyze the text."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Scanned-PDF support is missing. Install backend requirements and restart the app.") from exc
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OpenRouter is not configured. Add OPENROUTER_API_KEY to backend/.env, then restart the app.")
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        if document.page_count == 0:
            raise RuntimeError("This PDF has no pages.")
        client = OpenAI(
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={"HTTP-Referer": "http://127.0.0.1:5173", "X-OpenRouter-Title": "AI StudyMate"},
            timeout=120,
            max_retries=0,
        )
        extracted = []
        # Small batches keep image OCR requests compatible across free providers.
        for start in range(0, document.page_count, 3):
            content = [{"type": "text", "text": "Read the visible text in each page image in order. Preserve headings, formulas, and meaningful labels. Return only the extracted text, separated by page headings. Do not summarize or guess unreadable text."}]
            for page_index in range(start, min(start + 3, document.page_count)):
                page = document.load_page(page_index)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
                image_data = base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=65)).decode("ascii")
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}})
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": content}],
                max_tokens=6000,
                temperature=0,
            )
            extracted.append(response.choices[0].message.content or "")
        document.close()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(openrouter_error_message(exc)) from exc
    extracted_text = "\n\n".join(extracted).strip()
    if len(re.sub(r"\W", "", extracted_text)) < 80:
        raise RuntimeError("OpenRouter could not read enough text in this PDF. Try a clearer scan or a PDF with selectable text.")
    try:
        result = analyze(extracted_text)
        result["notice"] = f"{result['notice']} Scanned PDF text was read from its page images."
        result["character_count"] = len(extracted_text)
        return result
    except Exception as exc:
        raise RuntimeError(openrouter_error_message(exc)) from exc


def _sentences(text):
    values = [re.sub(r"\s+", " ", s).strip(" \t-•") for s in re.split(r"(?<=[.!?])\s+|\n+", text)]
    return [s for s in values if len(re.findall(r"[A-Za-z]{2,}", s)) >= 5]


def _rank_sentences(sentences):
    words_by_sentence = [
        [w for w in re.findall(r"[a-zA-Z][a-zA-Z-]{1,}", sentence.lower()) if w not in STOPWORDS]
        for sentence in sentences
    ]
    frequency = Counter(word for words in words_by_sentence for word in set(words))
    scored = []
    for index, (sentence, words) in enumerate(zip(sentences, words_by_sentence)):
        if not words:
            continue
        # Weight distinctive words and avoid letting long sentences dominate.
        score = sum(frequency[word] for word in set(words)) / (len(words) ** 0.5)
        scored.append((score, index, sentence))
    return [sentence for _, _, sentence in sorted(scored, reverse=True)]


def _topics(text, sentences):
    unigram_counts = Counter()
    phrase_counts = Counter()
    for sentence in sentences:
        tokens = re.findall(r"[a-zA-Z][a-zA-Z-]{1,}", sentence.lower())
        unigram_counts.update(token for token in tokens if token not in STOPWORDS)
        phrase_counts.update(
            f"{left} {right}"
            for left, right in zip(tokens, tokens[1:])
            if left not in STOPWORDS and right not in STOPWORDS and left != right
        )
    # Prefer noun phrases that introduce a concept: "Machine learning is...",
    # "In supervised learning,...", or "A neural network is...".
    introduced = Counter()
    subject_pattern = re.compile(
        r"^(?:(?:a|an|the)\s+)?([a-z][a-z-]*(?:\s+[a-z][a-z-]*){0,2})"
        r"(?:\s+\([^)]{1,16}\))?\s+(?:is|are|helps?|enables?|uses?|trains?|learns?|contains?|considers?|supports?|includes?|can)\b"
    )
    prep_pattern = re.compile(r"^(?:in|for|about|during|within)\s+([a-z][a-z-]*(?:\s+[a-z][a-z-]*){0,2}),")
    for sentence in sentences:
        lowered = sentence.lower()
        match = prep_pattern.search(lowered) or subject_pattern.search(lowered)
        if match:
            phrase = " ".join(word for word in match.group(1).split() if word not in {"a", "an", "the"})
            if len(phrase.split()) >= 2 and phrase not in LOW_VALUE_TOPICS and not phrase.startswith(("these ", "this ", "that ")) and not phrase.endswith(" can"):
                introduced[phrase] += 1

    candidates = []
    for name in set(introduced) | set(phrase_counts):
        if name not in LOW_VALUE_TOPICS:
            score = phrase_counts[name] + introduced[name] * 2
            candidates.append((name, score, 1 if introduced[name] else 0))
    candidates.extend((name, count, 0) for name, count in unigram_counts.items() if count >= 3 and name not in LOW_VALUE_TOPICS)
    candidates.sort(key=lambda item: (-(item[1] + item[2] * 2), -item[2], -len(item[0].split()), item[0]))
    selected = []
    for name, count, _is_phrase in candidates:
        if any(name in prior or prior in name for prior in selected):
            continue
        selected.append(name)
        if len(selected) == 10:
            break

    result = []
    for index, name in enumerate(selected):
        matching = [sentence for sentence in sentences if name in sentence.lower()]
        explanation = matching[0] if matching else f"Review how {name} is used in the document."
        result.append({
            "name": name.title(),
            "explanation": explanation,
            "importance": "High" if index < 3 else "Medium" if index < 6 else "Low",
        })
    return result


def _offline_analysis(text):
    """Build transparent, source-based study prompts when live AI is unavailable."""
    sentences = _sentences(text)
    if not sentences:
        sentences = [text[:500].strip() or "No readable content was found."]
    ranked = _rank_sentences(sentences)
    if not ranked:
        ranked = sentences
    summary_sentences = ranked[:min(8, len(ranked))]
    key_points = ranked[:min(6, len(ranked))]
    topics = _topics(text, sentences)
    if not topics:
        topics = [{"name": "Main ideas", "explanation": sentences[0], "importance": "High"}]

    questions = []
    for index in range(8):
        topic = topics[index % len(topics)]
        support = next((s for s in sentences if topic["name"].lower() in s.lower()), sentences[index % len(sentences)])
        questions.append({
            "question": f"Explain {topic['name']} using the information in your notes.",
            "expected_answer": support,
            "explanation": f"This answer is taken from the section about {topic['name']}.",
            "difficulty": "Easy" if index < 3 else "Medium" if index < 6 else "Hard",
            "topic": topic["name"],
        })

    unique_sentences = list(dict.fromkeys(sentences))
    mcqs = []
    question_stems = ["Which statement best describes", "According to the notes, what is true about", "Which detail is associated with"]
    for index in range(10):
        topic = topics[index % len(topics)]
        support = next((s for s in unique_sentences if topic["name"].lower() in s.lower()), unique_sentences[index % len(unique_sentences)])
        choices = [support]
        for candidate in unique_sentences:
            if candidate != support and candidate not in choices:
                choices.append(candidate)
            if len(choices) == 4:
                break
        fillers = [
            "The document does not state this.",
            "This detail is not mentioned in the notes.",
            "This conclusion cannot be drawn from the material.",
        ]
        for filler in fillers:
            if len(choices) == 4:
                break
            choices.append(filler)
        correct_index = index % 4
        choices[0], choices[correct_index] = choices[correct_index], choices[0]
        mcqs.append({
            "question": f"{question_stems[index % len(question_stems)]} {topic['name']}?",
            "options": choices,
            "answer": correct_index,
            "explanation": support,
            "difficulty": "Easy" if index < 4 else "Medium" if index < 8 else "Hard",
            "topic": topic["name"],
        })

    return {
        "summary_short": " ".join(summary_sentences[:3]),
        "summary_detailed": " ".join(summary_sentences),
        "key_points": key_points,
        "topics": topics,
        "questions": questions,
        "mcqs": mcqs,
    }


def _fallback_notice(error):
    details = str(error).lower()
    if "insufficient_quota" in details or "credit_balance_exhausted" in details or "no credits remaining" in details:
        return "OpenRouter is temporarily unavailable. Showing source-based study mode for this document."
    if "429" in details or "rate limit" in details:
        return "The AI service is temporarily rate limited. Showing source-based study mode for this document."
    return "OpenRouter could not complete this request. Showing source-based study mode for this document."


def analyze(text):
    instruction = "Analyze this study material. Return JSON with summary_short (2-3 plain-language sentences), summary_detailed (4-6 concise sentences), key_points (array of strings), topics (array of 5-8 objects {name, explanation, importance: High|Medium|Low}), questions (array of 8 objects {question, expected_answer, explanation, difficulty: Easy|Medium|Hard, topic}), mcqs (array of 10 objects {question, options: exactly 4 strings, answer: integer 0-3, explanation, difficulty: Easy|Medium|Hard, topic}). Keep the brief summary exact. Questions and correct answers must be explicitly grounded in this material."
    try:
        parts = chunks(text)
        if len(parts) == 1:
            source = text
        else:
            # Extract a few representative sentences per chunk, then make one
            # bounded model request instead of spending a request per chunk.
            evidence = []
            for part in parts:
                sentences = _sentences(part)
                evidence.extend(_rank_sentences(sentences)[:3])
            source = "\n".join(evidence)[:24000]
        result = _llm_json(instruction, source[:30000])
        if not result:
            return {
                **_offline_analysis(text),
                "mode": "offline",
                "notice": "OpenRouter is not configured. Showing source-based study mode for this document.",
            }
        _validate_analysis(result)
        return {**result, "mode": "ai", "notice": f"Generated with {MODEL} from your study material."}
    except Exception as exc:
        return {**_offline_analysis(text), "mode": "offline", "notice": _fallback_notice(exc)}


def _validate_analysis(data):
    required = ("summary_short", "summary_detailed", "key_points", "topics", "questions", "mcqs")
    if not isinstance(data, dict) or any(key not in data for key in required):
        raise ValueError("Missing analysis fields")
    if not isinstance(data["summary_short"], str) or not isinstance(data["summary_detailed"], str):
        raise ValueError("Invalid summary")
    if any(not isinstance(data[key], list) for key in ("key_points", "topics", "questions", "mcqs")):
        raise ValueError("Invalid analysis lists")
    if not data["topics"] or len(data["mcqs"]) < 10:
        raise ValueError("At least ten MCQs are required")
    for topic in data["topics"]:
        if not isinstance(topic, dict) or not all(isinstance(topic.get(key), str) for key in ("name", "explanation", "importance")):
            raise ValueError("Invalid topic")
    for question in data["questions"]:
        if not isinstance(question, dict) or not all(isinstance(question.get(key), str) for key in ("question", "expected_answer", "explanation", "difficulty", "topic")):
            raise ValueError("Invalid study question")
    for question in data["mcqs"]:
        if not isinstance(question, dict) or not all(isinstance(question.get(key), str) for key in ("question", "explanation", "difficulty", "topic")):
            raise ValueError("Invalid MCQ fields")
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4 or not all(isinstance(option, str) for option in options) or question.get("answer") not in range(4):
            raise ValueError("Invalid MCQ")


def evaluate(analysis, answers):
    questions = analysis["mcqs"]
    correct = sum(1 for index, question in enumerate(questions) if answers.get(str(index)) == question["answer"])
    missed = [question for index, question in enumerate(questions) if answers.get(str(index)) != question["answer"]]
    weak = Counter(question.get("topic", "Key ideas") for question in missed)
    weak_topics = sorted(weak.items(), key=lambda item: -item[1])
    percent = correct / max(len(questions), 1)
    feedback = f"You got {correct} of {len(questions)} correct. " + (
        "Strong work—keep building on these concepts." if percent >= .8 else "Review the topics below, then try again."
    )
    recommendations = [f"Review {topic}: reread its explanation and answer one study question from memory." for topic, _ in weak_topics[:4]]
    mode = "offline"
    if os.getenv("OPENROUTER_API_KEY", "").strip() and missed:
        try:
            context = json.dumps({
                "score": f"{correct}/{len(questions)}",
                "missed": [{"question": q["question"], "topic": q.get("topic"), "explanation": q["explanation"]} for q in missed],
            })
            result = _llm_json("Return JSON {feedback: string, recommendations: array of strings}. Give specific, supportive revision advice based only on these missed questions.", context)
            if result:
                feedback = result.get("feedback", feedback)
                recommendations = result.get("recommendations", recommendations)
                mode = "ai"
        except Exception:
            pass
    return {
        "total": len(questions), "correct": correct, "incorrect": len(questions) - correct,
        "percentage": round(percent * 100),
        "performance": "Excellent" if percent >= .9 else "Good" if percent >= .7 else "Keep practicing",
        "weak_topics": [{"name": name, "priority": "High" if count >= 3 else "Medium" if count == 2 else "Low"} for name, count in weak_topics],
        "feedback": feedback, "recommendations": recommendations, "mode": mode,
    }
