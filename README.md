# AI StudyMate
#Ai lab project By TANUJ SINGH - 2402221530129, Under the guidance of Ms. ANJALI SRIVASTAVA Ma'am.

**Learn Smarter. Prepare Better.** A local-first study assistant that turns a PDF or text document into a summary, topic list, study questions, quiz and personalized review suggestions.

## Objective and features

Students often have lengthy notes but little time to turn them into useful revision. StudyMate extracts readable text, asks a language model to create grounded study material, and lets the student check understanding in an interactive quiz.

- PDF and TXT upload (10 MB limit), including OCR analysis for scanned PDFs.
- Short and detailed summaries, key points, 5–8 important topics and open-ended questions.
- Ten MCQs with four options, answer key, explanation, difficulty and topic label.
- Interactive quiz with previous/next navigation, score, performance level, weak topics and revision guidance.
- Live AI mode through a server-side Gemini key; clearly labeled source-based results when no key is configured or AI is unavailable.
- Sample Introduction to AI material at `backend/sample_material.txt`.
- Uploaded files are held in memory for the request and are not saved on the server.

## Technology and layout

React, Vite, JavaScript, Tailwind CSS utilities/custom CSS; Python, Flask REST API, pypdf, PyMuPDF; Gemini content generation through backend-only HTTPS requests (`gemini-3.5-flash-lite` by default). There is no database; the current session lives in React state.

```text
ai-studymate/
├── backend/app.py
├── backend/services/documents.py      # PDF/TXT validation and extraction
├── backend/services/ai_service.py     # chunking, AI prompts, validation, fallback, scoring
├── backend/sample_material.txt
├── backend/requirements.txt
├── frontend/src/App.jsx               # screens and interactions
├── frontend/src/services/api.js       # REST client
├── frontend/src/styles.css
├── frontend/package.json
└── README.md
```

## Requirements

- Python 3.10+
- Node.js 20.19+ (or 22.12+; required by the current Vite release)
- Gemini API key for live AI mode (optional; source-based mode works without one)

## Setup and run

### One-click Windows launch

Double-click `Start-StudyMate.cmd` in File Explorer, or use the **StudyMate** shortcut on your desktop. Each time you click it, the launcher checks whether the backend and frontend are running, starts any that are stopped, and opens `http://127.0.0.1:5173` in your browser. After the first setup, use this same shortcut after restarting your computer.

The first launch can take a few minutes to install dependencies. Python 3.10+ and Node.js 20.19+ with npm must be installed.

You can also start it from PowerShell in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\Open-StudyMate.ps1
```
To stop the background servers later, run `powershell -ExecutionPolicy Bypass -File .\Stop-StudyMate.ps1` from the project folder.

Open two PowerShell terminals in `ai-studymate`.

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Set values in `backend/.env` (keep this private; `.env` is ignored by git):

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
PORT=5000
```

Leave the key empty for offline mode. Then run:

```powershell
python app.py
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (`http://127.0.0.1:5174`). Flask health check: `http://127.0.0.1:5000/api/health`.

## Example workflow

1. Open the workspace and upload a PDF/TXT, or select **Use sample notes**.
2. Review the summary and topic cards.
3. Browse open-ended questions or start the quiz.
4. Submit answers and review the score, missed topics and recommendations.

## API

- `GET /api/health` — service status and whether AI is configured (never returns the key).
- `POST /api/analyze` — multipart `file`; returns summary, topics, questions, MCQs and mode label.
- `POST /api/evaluate` — JSON `{ "analysis": ..., "answers": {"0": 1} }`; returns score and revision feedback.

## AI Implementation

- **NLP:** Input is normalized, split into readable passages and analyzed for concepts, questions and relationships. Offline mode extracts frequent terms and source sentences as a limited fallback.
- **LLM:** Flask calls Gemini from the backend using `GEMINI_API_KEY`; the key is never sent to React. Prompts request source-grounded content in a fixed JSON schema.
- **Summarization and chunking:** Long documents are split into passages of about 10,000 characters. Representative source sentences are selected before one structured analysis request, keeping requests bounded.
- **Question generation:** The model is asked for 8 open-ended questions and at least 10 MCQs, each tied to a topic and grounded in the upload. The backend validates required fields, four-option MCQs and answer indices.
- **Evaluation:** MCQ answer indices are compared with the answer key. Missed question topics are aggregated into weak-topic priorities. This version uses deterministic quiz scoring, not semantic similarity.
- **AI feedback:** In live mode, missed questions and explanations are sent for tailored advice. Without a key or after API failure, rule-based advice is clearly labeled. Sentence Transformers are not used in this version; semantic short-answer evaluation is future scope.
- **Limitations:** Model availability, usage limits and pricing depend on your Google AI account settings. LLMs can make mistakes, so verify high-stakes material. Offline prompts are source-based practice questions.

## Viva notes

1. **Problem:** converting notes into revision resources takes time.
2. **AI use:** summary, topic identification, question generation and (when enabled) personalized feedback.
3. **NLP:** methods that help computers process human language.
4. **LLM:** a model trained on large text collections that generates or transforms language from instructions and context.
5. **PDF processing:** pypdf extracts selectable text; PyMuPDF renders scanned pages locally and Gemini reads the scanned page images.
6. **Question generation:** extracted text is passed with grounding instructions and a fixed JSON schema.
7. **Performance:** answer indices are checked against the answer key; missed topic labels drive recommendations.
8. **Pre-trained model:** makes language understanding practical without training a model from scratch.
9. **Limitations:** free model request limits, changing model availability, possible model errors, extraction limits and no persistent history.
10. **Future scope:** Sentence Transformers for semantic evaluation, flashcards, multiple languages, adaptive difficulty, progress history, authentication and a mobile app.

## Future scope

Voice-based learning, personalized learning paths, multiple languages, flashcards, an AI tutor, progress tracking, Firebase authentication, student history, adaptive difficulty and mobile support.

## Troubleshooting

- **Could not reach server:** start Flask and check that port 5000 is available.
- **AI fallback/401:** check the key in `backend/.env`, then restart Flask. The app remains usable offline.
- **Scanned PDF / too little text:** use a clear scan; the app sends rendered page images to Gemini for text extraction.
- **CORS/network error:** use Vite on port 5174 and Flask on port 5000.
- **Python dependencies:** activate the backend virtual environment and rerun `pip install -r requirements.txt`.
- **Frontend dependencies:** use Node 20.19+ or 22.12+ and rerun `npm install`.

## Verification checklist

- [ ] Health endpoint responds without exposing secrets.
- [ ] Upload a TXT and text-based PDF; inspect empty/scanned PDF and unsupported extension handling.
- [ ] With a valid key, confirm AI mode and check results against source material.
- [ ] Without a key, confirm results are labeled offline/demo.
- [ ] Complete quiz, navigate, and verify score and weak topics.
- [ ] Check phone and desktop layouts.
