import httpx
from fastapi import HTTPException
from app.config import get_settings

settings = get_settings()

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# ── Universal system prompt — no industry lock-in ─────────────────────────────

SYSTEM_PROMPT = (
    "Du bist ein Elite-Recherche-Assistent. Recherchiere GRÜNDLICH und liefere "
    "DETAILLIERTE, datengestützte Antworten. Gib IMMER konkrete Namen, Zahlen, "
    "Adressen, Daten und Beispiele — keine vagen Allgemeinheiten. "
    "Strukturiere deine Antwort mit Überschriften und Listen. "
    "Nenne mindestens 5-8 relevante Ergebnisse wenn möglich. "
    "Antworte in der Sprache der Anfrage."
)


async def search_perplexity(query: str, mode: str = "general") -> dict:
    payload = {
        "model": settings.perplexity_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "return_citations": True,
        "search_recency_filter": "month",
        "return_images": False,
    }

    headers = {
        "Authorization": f"Bearer {settings.perplexity_api_key}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(connect=10.0, read=90.0, write=30.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(PERPLEXITY_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Suche hat zu lange gedauert. Bitte erneut versuchen."
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Perplexity API-Fehler: {e.response.status_code}"
        )

    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])

    return {"answer": content, "sources": citations, "mode": mode}
