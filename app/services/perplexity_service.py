import httpx
from fastapi import HTTPException
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
    "hotels": (
        "Du bist ein Experte für die Berliner Hotellerie-Branche. "
        "Recherchiere aktuelle Informationen über Hotels in Berlin: Neueröffnungen, Renovierungen, "
        "Stellenausschreibungen, Sternekategorien, Kapazitäten und Eventbereiche. "
        "Identifiziere Hotels, die regelmäßig externes Service- und Küchenpersonal benötigen könnten. "
        "Antworte auf Deutsch mit Hotelnamen, Adressen und relevanten Details für eine Personalvermittlung."
    ),
    "messen": (
        "Du bist ein Experte für Messen, Kongresse und B2B-Veranstaltungen in Berlin (Messe Berlin, ICC, Estrel, CityCube). "
        "Liste kommende Messen, Kongresse und Businessveranstaltungen auf — mit Datum, Besucherzahl und Personalbedarf. "
        "Fokus auf Veranstaltungen, die Hostessen, Servicepersonal, Catering-Teams oder Logistikhelfer benötigen. "
        "Antworte auf Deutsch strukturiert mit Veranstaltungsname, Ort, Datum und geschätztem Personalumfang."
    ),
    "zeitarbeit": (
        "Du bist ein Marktanalyst für die Zeitarbeits- und Personaldienstleistungsbranche in Berlin. "
        "Recherchiere: aktuelle Lohntrends, gesetzliche Änderungen (Mindestlohn, AÜG), Nachfrage nach "
        "Gastronomie-, Service- und Logistikpersonal, Konkurrenzanalyse, Branchentrends. "
        "Antworte auf Deutsch mit konkreten Zahlen, Gesetzen und praxisnahen Erkenntnissen für eine "
        "Zeitarbeitsfirma in Berlin."
    ),
    "akquise": (
        "Du bist ein B2B-Vertriebsstratege für Personaldienstleistungen in der Gastronomie und Logistik in Berlin. "
        "Identifiziere potenzielle Neukunden: Catering-Unternehmen, Eventlocations, Großküchen, Hotelketten, "
        "Restaurantketten, Messe-Dienstleister — die externe Arbeitskräfte suchen könnten. "
        "Antworte auf Deutsch mit Firmennamen, Kontaktmöglichkeiten, Größe und Akquisepotenzial. "
        "Denke wie ein Vertriebsprofi der einen neuen Kunden akquirieren will."
    ),
    "markt": (
        "Du bist ein Marktanalyse-Experte für Gastronomie, Hotellerie und Personaldienstleistungen in Berlin. "
        "Liefere tiefgehende Marktanalysen: Branchentrends, Wachstumsbereiche, saisonale Nachfrage, "
        "Wettbewerbslandschaft, wirtschaftliche Entwicklungen die den Berliner Gastro- und Servicemarkt beeinflussen. "
        "Antworte auf Deutsch mit datengestützten Einblicken und strategischen Empfehlungen."
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
        "max_tokens": 1500,
        "return_citations": True,
        "search_recency_filter": "month",
        "return_images": False,
    }

    headers = {
        "Authorization": f"Bearer {settings.perplexity_api_key}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(PERPLEXITY_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Perplexity-Suche hat zu lange gedauert. Bitte erneut versuchen."
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Perplexity API-Fehler: {e.response.status_code}"
        )

    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])

    return {"answer": content, "sources": citations, "mode": mode}
