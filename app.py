import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024
SITE_URL = os.getenv("SITE_URL", "https://venuvanam.com/")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
client = (
    genai.Client(
        api_key=API_KEY,
        http_options={"timeout": 20000}
    )
    if API_KEY else None
)
@app.route("/api/test-gemini")
def test_gemini():
    try:
        result = client.interactions.create(
            model=MODEL_NAME,
            input="Reply with only: Hello",
            timeout=30
        )
        return {"ok": True, "answer": result.output_text}
    except Exception as e:
        app.logger.exception("Gemini test failed")
        return {"ok": False, "error": str(e)}, 502

def load_articles():
    path = BASE_DIR / "data" / "articles.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def words(text):
    return set(re.findall(r"[\w\u0B80-\u0BFF]+", (text or "").lower()))


def retrieve_articles(question, articles, limit=5):
    query_words = words(question)
    q = question.lower()

    # Handle common questions about Venuvanam and its author
    author_terms = [
        "author", "who wrote", "writer", "founder",
        "யார் எழுதியது", "ஆசிரியர்", "எழுத்தாளர்",
        "யாருடையது", "யார்"
    ]
    about_terms = [
        "what is venuvanam", "about venuvanam",
        "tell me about venuvanam", "வேணுவனம் என்றால் என்ன",
        "வேணுவனம் பற்றி", "வேணுவனம்"
    ]

    if any(term in q for term in author_terms):
        author_articles = [
            article for article in articles
            if "author" in " ".join(article.get("tags", [])).lower()
            or "author name" in article.get("content", "").lower()
        ]
        if author_articles:
            return author_articles[:limit]

    if any(term in q for term in about_terms):
        about_articles = [
            article for article in articles
            if "website" in article.get("tags", [])
            or "about" in article.get("tags", [])
        ]
        if about_articles:
            return about_articles[:limit]

    scored = []
    for article in articles:
        title = article.get("title", "")
        content = article.get("content", "")
        tags = " ".join(article.get("tags", []))
        combined = f"{title} {title} {tags} {content}"
        article_words = words(combined)
        overlap = len(query_words & article_words)
        if overlap:
            scored.append((overlap, article))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def demo_answer(question, relevant):
    q = question.lower()
    if any(term in q for term in ["translate", "translation", "english", "ஆங்கிலம்", "மொழிபெயர்ப்பு"]):
        return ("Demo mode-la full AI translation enabled illa. `.env` file-la Gemini API key add pannina, "
                "Tamil ↔ English translation and article explanations AI moolama work aagum. "
                "Ippo naan site-la irukkura article metadata mattum use panren.")
    if relevant:
        lines = ["Demo mode: indha question-ku site index-la closest-a match aana pages:"]
        for item in relevant:
            lines.append(f"• {item.get('title', 'Untitled')} — {item.get('summary', 'Summary not available.')}")
        lines.append("Full AI answers, meaning explanations and translation use panna `.env`-la Gemini API key configure pannunga.")
        return "\n\n".join(lines)
    return ("Indha question-ku current starter content-la reliable answer kidaikkala. "
            "Gemini API key set pannina general explanation/translation features work aagum; "
            "Venuvanam-specific answers-ku site article index update pannunga.")


def make_prompt(question, relevant):
    context_blocks = []
    for article in relevant:
        context_blocks.append(
            f"TITLE: {article.get('title', '')}\n"
            f"URL: {article.get('url', '')}\n"
            f"SUMMARY: {article.get('summary', '')}\n"
            f"CONTENT: {article.get('content', '')[:700]}"
        )
    context = "\n\n--- ARTICLE ---\n\n".join(context_blocks) or "No matching Venuvanam articles were found in the local index."
    return f"""You are Venuvanam AI, a helpful assistant for readers of the Tamil literary website {SITE_URL}.
Answer naturally in the language/script the user uses: Tamil, English, or Tanglish. Help with website navigation, Tamil word meanings, literary explanations, summaries, and translations.

TRUTH AND SOURCE RULES:
- For questions about Venuvanam, its author, or published content, use the supplied article context only for factual claims.
- If the local article context does not support a site-specific answer, say you could not verify it from the indexed pages. Do not invent articles, quotes, author biography, or site features.
- For general Tamil language questions, you may answer from general language knowledge and clearly distinguish that from website-specific facts.
- For translation requests, translate only the text the user provides or text included in the supplied context. Do not reproduce large amounts of copyrighted article text. A brief excerpt can be explained; offer a summary for longer passages.
- Be respectful of the author's style and preserve nuance. Clearly label a summary or interpretation as such.
- Be concise and easy to understand. When relevant, finish with source article titles and URLs from the context.

INDEXED ARTICLE CONTEXT:
{context}

USER QUESTION:
{question}
"""


@app.get("/")
def index():
    return render_template("index.html", site_url=SITE_URL)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "ai_configured": bool(API_KEY), "model": MODEL_NAME, "articles_indexed": len(load_articles())})



@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("message", "")).strip()

    if not question:
        return jsonify({"error": "Please enter a question."}), 400

    if len(question) > 4000:
        return jsonify({"error": "Question is too long."}), 400

    q = question.lower()

    # Instant answers: no Gemini request needed
    author_questions = [
        "who is the author", "who wrote venuvanam",
        "who is the writer", "author of venuvanam",
        "வேணுவனத்தின் ஆசிரியர்", "வேணுவனத்தின் எழுத்தாளர்",
        "ஆசிரியர் யார்", "எழுத்தாளர் யார்"
    ]

    about_questions = [
        "what is venuvanam", "tell me about venuvanam",
        "about venuvanam", "வேணுவனம் என்றால் என்ன",
        "வேணுவனம் பற்றி"
    ]

    if any(term in q for term in author_questions):
        return jsonify({
            "answer": "Venuvanam is a Tamil writing website associated with author Suga (சுகா).",
            "sources": [{
                "title": "வேணுவனம் — சுகா",
                "url": "https://venuvanam.com/"
            }],
            "mode": "local"
        })

    if any(term in q for term in about_questions):
        return jsonify({
            "answer": "Venuvanam (வேணுவனம்) is a Tamil writing website associated with writer Suga (சுகா). It features essays, personal experiences and tributes.",
            "sources": [{
                "title": "வேணுவனம் — சுகா",
                "url": "https://venuvanam.com/"
            }],
            "mode": "local"
        })

    articles = load_articles()
    relevant = retrieve_articles(question, articles, limit=3)

    sources = []
    seen = set()

    for item in relevant:
        url = item.get("url", "")
        if url and url not in seen:
            seen.add(url)
            sources.append({
                "title": item.get("title", "Venuvanam article"),
                "url": url
            })

    if not client:
        return jsonify({
            "answer": demo_answer(question, relevant),
            "sources": sources,
            "mode": "demo"
        })

    try:
        interaction = client.interactions.create(
    model=MODEL_NAME,
    input=make_prompt(question, relevant),
    generation_config={"max_output_tokens": 200},
    timeout=60
)

        answer = (
            getattr(interaction, "output_text", None) or ""
        ).strip()

        if not answer:
            answer = "Sorry, I couldn't generate an answer. Please try again."

        return jsonify({
            "answer": answer,
            "sources": sources,
            "mode": "ai"
        })

    except Exception:
        app.logger.exception("Gemini API request failed")
        return jsonify({
            "error": "Gemini request failed or timed out. Please try again."
        }), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
