import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS
from services.documents import extract_document, is_readable_pdf_text
from services.ai_service import analyze, analyze_pdf_file, evaluate

app = Flask(__name__)
# Leave room for multipart boundaries; extract_document enforces the 10 MB file limit.
app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "ai_configured": bool(os.getenv("OPENROUTER_API_KEY"))})

@app.post("/api/analyze")
def upload_and_analyze():
    if "file" not in request.files:
        return jsonify({"error": "Choose a PDF or TXT file first."}), 400
    try:
        file = request.files["file"]
        text = extract_document(file)
        extension = (file.filename or "").rsplit(".", 1)[-1].lower()
        if extension == "pdf":
            file.stream.seek(0)
            pdf_bytes = file.stream.read()
            result = analyze(text) if is_readable_pdf_text(text) else analyze_pdf_file(pdf_bytes, file.filename)
        else:
            result = analyze(text)
        result["document_name"] = file.filename
        result.setdefault("character_count", len(text))
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        app.logger.exception("Analysis failed")
        return jsonify({"error": "We could not analyze this document. Please try again."}), 500

@app.post("/api/evaluate")
def score_quiz():
    payload = request.get_json(silent=True) or {}
    analysis = payload.get("analysis")
    answers = payload.get("answers")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("mcqs"), list) or not isinstance(answers, dict):
        return jsonify({"error": "Quiz answers could not be evaluated."}), 400
    try:
        return jsonify(evaluate(analysis, answers))
    except Exception:
        return jsonify({"error": "Could not calculate your result. Please try again."}), 500

@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Files must be 10 MB or smaller."}), 413

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
