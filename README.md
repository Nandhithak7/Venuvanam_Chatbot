# Venuvanam AI — Tamil Literary Assistant (Starter Project)

A separate Flask chatbot prototype for readers of [Venuvanam](https://venuvanam.com/). It is not embedded into the original site and does not require admin access.

## Features

- Responsive chat interface with Tamil-friendly fonts.
- Ask in Tamil, English, or Tanglish.
- Gemini-powered article-aware Q&A, word meaning, explanation, summary, and translation when an API key is configured.
- Basic local article retrieval and source links.
- Demo mode without an API key so the UI can still be shown.
- Optional polite public-page indexer (`crawl_site.py`) that checks `robots.txt`, limits requests, and stores short extracts only.

## Technology choices

- **Python + Flask**: simple backend and quick to run for a beginner.
- **Gemini API, model `gemini-3.8-flash`**: selected as a current stable Flash model for fast general conversation. You can change it in `.env` if access differs.
- **JSON local index + keyword retrieval**: intentionally simple for a starter project. For a production system, replace with semantic retrieval/embeddings, better metadata, evaluation, and caching.

## 1. Requirements

- Python 3.10+ recommended.
- Internet connection for Gemini API.
- A Gemini API key for AI-powered responses. Without a key, the app runs in demo mode.

## 2. Setup on Windows

Open Command Prompt or the VS Code terminal in this folder:

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` in a text editor and set your key:

```env
GEMINI_API_KEY=PASTE_YOUR_OWN_KEY_HERE
GEMINI_MODEL=gemini-3.8-flash
SITE_URL=https://venuvanam.com/
PORT=5000
```

Get a key from Google AI Studio: https://aistudio.google.com/apikey

**Never paste your API key into `app.py`, `static/app.js`, screenshots, or a public repository. Do not send the `.env` file to anyone.** Check applicable account, service, and billing limits before using the API.

## 3. Run the chatbot

```bat
python app.py
```

Open this address in your browser: http://127.0.0.1:5000

To check status: http://127.0.0.1:5000/api/health

## 4. Update the website article index

The starter index in `data/articles.json` contains only a few short homepage-derived records. It is **not** the complete Venuvanam archive.

Before crawling, confirm that automated access is permitted by the website owner and site rules. Then run:

```bat
python crawl_site.py
```

The crawler checks `robots.txt`, stays on `venuvanam.com`, visits at most 35 pages, waits between requests, and saves short extracts. If crawling is disallowed or the site blocks it, do not bypass that restriction; ask the site owner for an approved export/feed/API or a permitted content dataset.

Review the generated `data/articles.json` before using it. Some websites render content dynamically or paginate articles, so the crawler may miss pages. Re-run it when the website changes.

## 5. How it works

1. The browser sends a question to Flask's `/api/chat` endpoint.
2. Flask searches the local JSON index for keyword overlap.
3. If `GEMINI_API_KEY` is configured, relevant records are added as context to a Gemini Interactions API request.
4. The model is instructed not to invent Venuvanam-specific facts when context is missing.
5. The browser displays the answer and matching source links.

## Important limitations

- This is a starter/demo, not a production deployment.
- The local index is small until the site owner-approved content import is completed.
- Keyword search can miss semantically related articles; semantic embeddings/reranking should be the next improvement.
- An LLM can still make mistakes. Test Tamil script, Tanglish, article-specific questions, translation quality, and unsupported questions.
- Do not deploy publicly without rate limiting, logging/privacy review, error monitoring, stronger retrieval, and API cost controls.
- Article content remains the property of its respective rights holders. Use only content you are authorized to process and show.

## Suggested demo questions

- `Venuvanam enna website?`
- `செண்பகமே செண்பகமே article edha pathi?`
- `Explain this Tamil phrase in simple English: ...`
- `Translate this into English: வணக்கம், உங்கள் நாள் இனிதாக அமையட்டும்.`
- `Which article did you use?`

## Project structure

```text
venuvanam_ai_starter/
├── app.py
├── crawl_site.py
├── requirements.txt
├── .env.example
├── README.md
├── data/articles.json
├── templates/index.html
└── static/{style.css, app.js}
```
