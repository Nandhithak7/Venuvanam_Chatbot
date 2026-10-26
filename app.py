
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai

# --------------------------------------------------
# APP CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024

SITE_URL = os.getenv("SITE_URL", "https://venuvanam.com/")

# Use the model ID, not "models/model-id".
MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
).strip().removeprefix("models/")

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# HTTP timeout is configured in milliseconds.
client = (
    genai.Client(
        api_key=API_KEY,
        http_options={"timeout": 120000}
    )
    if API_KEY
    else None
)


# --------------------------------------------------
# LOAD LOCAL ARTICLE INDEX
# --------------------------------------------------

def load_articles():
    path = BASE_DIR / "data" / "articles.json"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    except (OSError, json.JSONDecodeError):
        app.logger.exception("Could not load articles.json")
        return []


# --------------------------------------------------
# TEXT PROCESSING AND ARTICLE RETRIEVAL
# --------------------------------------------------

def words(text):
    return set(
        re.findall(
            r"[\w\u0B80-\u0BFF]+",
            (text or "").lower()
        )
    )


def retrieve_articles(question, articles, limit=5):
    query_words = words(question)
    q = question.lower()

    author_terms = [
        "author",
        "who wrote",
        "writer",
        "founder",
        "யார் எழுதியது",
        "ஆசிரியர்",
        "எழுத்தாளர்",
        "யாருடையது",
        "யார்"
    ]

    about_terms = [
        "what is venuvanam",
        "about venuvanam",
        "tell me about venuvanam",
        "வேணுவனம் என்றால் என்ன",
        "வேணுவனம் பற்றி",
        "வேணுவனம்"
    ]

    if any(term in q for term in author_terms):
        author_articles = [
            article
            for article in articles
            if (
                "author" in " ".join(
                    article.get("tags", [])
                ).lower()
                or "author name" in article.get(
                    "content", ""
                ).lower()
            )
        ]

        if author_articles:
            return author_articles[:limit]

    if any(term in q for term in about_terms):
        about_articles = [
            article
            for article in articles
            if (
                "website" in article.get("tags", [])
                or "about" in article.get("tags", [])
            )
        ]

        if about_articles:
            return about_articles[:limit]

    scored = []

    for article in articles:
        title = article.get("title", "")
        content = article.get("content", "")
        tags = " ".join(article.get("tags", []))

        combined = f"{title} {tags} {content}"
        article_words = words(combined)

        overlap = len(query_words & article_words)

        if overlap:
            scored.append((overlap, article))

    scored.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return [
        item[1]
        for item in scored[:limit]
    ]


# --------------------------------------------------
# PROMPT FOR GEMINI
# --------------------------------------------------

def make_prompt(question, relevant):
    context_blocks = []

    for article in relevant:
        context_blocks.append(
            f"TITLE: {article.get('title', '')}\n"
            f"URL: {article.get('url', '')}\n"
            f"SUMMARY: {article.get('summary', '')}\n"
            f"CONTENT: {article.get('content', '')[:700]}"
        )

    context = (
        "\n\n--- ARTICLE ---\n\n".join(context_blocks)
        or "No matching Venuvanam articles were found "
           "in the local index."
    )

    return f"""
You are Venuvanam AI, a helpful assistant for readers
of the Tamil literary website {SITE_URL}.

Answer naturally in the language and script used by
the user: Tamil, English, or Tanglish.

Help with:
- Website navigation
- Tamil word meanings
- Literary explanations
- Summaries
- Translations of user-provided text

RULES:
1. For Venuvanam-specific questions, use the supplied
   article context for factual claims.
2. Never invent article titles, quotations, author
   biography, or website features.
3. If the indexed context does not support a site-specific
   answer, clearly say that you could not verify it.
4. General Tamil-language questions may be answered using
   general language knowledge.
5. Translate text supplied by the user or included in
   the provided context. Do not reproduce long copyrighted
   passages.
6. Keep answers clear, useful, and concise.
7. When relevant, mention source article titles and URLs.

INDEXED ARTICLE CONTEXT:
{context}

USER QUESTION:
{question}
""".strip()


# --------------------------------------------------
# LOCAL FALLBACK
# --------------------------------------------------

def demo_answer(question, relevant):
    q = question.lower()

    if any(
        term in q
        for term in [
            "translate",
            "translation",
            "english",
            "ஆங்கிலம்",
            "மொழிபெயர்ப்பு"
        ]
    ):
        return (
            "Gemini AI is temporarily unavailable, so I "
            "couldn't complete the translation right now. "
            "Please try again shortly."
        )

    if relevant:
        lines = [
            "Gemini AI is temporarily unavailable. "
            "Here are the closest matching pages "
            "from the local Venuvanam index:"
        ]

        for item in relevant:
            title = item.get("title", "Untitled")
            summary = item.get(
                "summary",
                "Summary not available."
            )

            lines.append(f"• {title} — {summary}")

        return "\n\n".join(lines)

    return (
        "Gemini AI is temporarily unavailable, and I "
        "couldn't find a reliable answer in the local "
        "Venuvanam article index. Please try again shortly."
    )


# --------------------------------------------------
# SOURCE LINKS
# --------------------------------------------------

def collect_sources(relevant):
    sources = []
    seen = set()

    for item in relevant:
        url = item.get("url", "")

        if url and url not in seen:
            seen.add(url)

            sources.append({
                "title": item.get(
                    "title",
                    "Venuvanam article"
                ),
                "url": url
            })

    return sources


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.get("/")
def index():
    return render_template(
        "index.html",
        site_url=SITE_URL
    )


# --------------------------------------------------
# HEALTH STATUS
# --------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "ai_configured": bool(client),
        "model": MODEL_NAME,
        "articles_indexed": len(load_articles())
    })


# --------------------------------------------------
# CHAT API
# --------------------------------------------------

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}

    question = str(
        payload.get("message", "")
    ).strip()

    if not question:
        return jsonify({
            "error": "Please enter a question."
        }), 400

    if len(question) > 4000:
        return jsonify({
            "error": "Question is too long."
        }), 400

    q = question.lower()

    # Quick local answers for common website questions.
    author_questions = [
        "who is the author",
        "who wrote venuvanam",
        "who is the writer",
        "author of venuvanam",
        "வேணுவனத்தின் ஆசிரியர்",
        "வேணுவனத்தின் எழுத்தாளர்",
        "ஆசிரியர் யார்",
        "எழுத்தாளர் யார்"
    ]

    about_questions = [
        "what is venuvanam",
        "tell me about venuvanam",
        "about venuvanam",
        "வேணுவனம் என்றால் என்ன",
        "வேணுவனம் பற்றி"
    ]

    if any(term in q for term in author_questions):
        return jsonify({
            "answer": (
                "Venuvanam is a Tamil writing website "
                "associated with author Suga (சுகா)."
            ),
            "sources": [{
                "title": "வேணுவனம் — சுகா",
                "url": SITE_URL
            }],
            "mode": "local"
        })

    if any(term in q for term in about_questions):
        return jsonify({
            "answer": (
                "Venuvanam (வேணுவனம்) is a Tamil writing "
                "website associated with writer Suga (சுகா). "
                "For more details, visit the website."
            ),
            "sources": [{
                "title": "வேணுவனம் — சுகா",
                "url": SITE_URL
            }],
            "mode": "local"
        })

    articles = load_articles()

    relevant = retrieve_articles(
        question,
        articles,
        limit=3
    )

    sources = collect_sources(relevant)

    # If the API key is absent, keep the local chatbot usable.
    if client is None:
        return jsonify({
            "answer": demo_answer(question, relevant),
            "sources": sources,
            "mode": "fallback"
        })

    # Gemini generation.
    try:
        interaction = client.interactions.create(
            model=MODEL_NAME,
            input=make_prompt(question, relevant),
            generation_config={
                "thinking_level": "low",
                "max_output_tokens": 1024
            },
            timeout=90
        )

        answer = (
            getattr(interaction, "output_text", None)
            or ""
        ).strip()

        if not answer:
            app.logger.warning(
                "Gemini returned an empty response."
            )

            return jsonify({
                "answer": demo_answer(question, relevant),
                "sources": sources,
                "mode": "fallback"
            })

        return jsonify({
            "answer": answer,
            "sources": sources,
            "mode": "ai"
        })

    except Exception as e:
    app.logger.exception("Gemini API request failed")

    return jsonify({
        "answer": f"Gemini error: {type(e).__name__}: {str(e)}",
        "sources": sources,
        "mode": "error"
    }), 502


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False
    )
