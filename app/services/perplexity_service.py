import httpx
from app.config import get_settings

settings = get_settings()

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

SYSTEM_PROMPTS = {
    "restaurants": (
        "Du bist ein Marktforschungsexperte für die Berliner Gastronomie-Szene. "
        "Gib präzise, aktuelle Informationen über Restaurants, neue Eröffnungen, "
        "Trends und Standorte in Berlin. Fokussiere auf Restaurants und Locations, "
        "die für Catering-Dienstleistungen und Personalvermittlung relevant sind. "
        "Antworte auf Deutsch mit strukturierten, übersichtlichen Informationen."
    ),
    "events": (
        "Du bist ein Experte für Veranstaltungen und Events in Berlin und Umgebung. "
        "Gib Informationen über kommende Großveranstaltungen, Messen, Kongresse, "
        "Konzerte und Events, die Servicepersonal, Köche oder Logistikpersonal benötigen. "
        "Das ist wichtig für eine Zeitarbeitsfirma in der Gastronomie und Logistik. "
        "Antworte auf Deutsch mit konkreten Angaben zu Datum, Ort und geschätztem Personalbedarf."
    ),
    "general": (
        "Du bist ein Business-Intelligence-Assistent für Gastronomie- und Zeitarbeitsunternehmen "
        "in Berlin. Recherchiere und analysiere Marktinformationen, die für die Personalvermittlung "
        "in Gastronomie, Service, Logistik und Küche relevant sind. Antworte auf Deutsch."
    ),
}


async def search_perplexity(query: str, mode: str = "general") -> dict:
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["general"])

    payload = {
        "model": settings.perplexity_model,
        "messages": [
            {"role": "system", "content": system_prompt},
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

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(PERPLEXITY_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])

    return {"answer": content, "sources": citations, "mode": mode}
