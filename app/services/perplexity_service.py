import httpx
from fastapi import HTTPException
from app.config import get_settings

settings = get_settings()

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# ── Mode-specific system prompts ──────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "restaurants": (
        "Du bist ein Elite-Marktforschungsexperte für die Berliner Gastronomie-Szene. "
        "Recherchiere GRÜNDLICH und liefere DETAILLIERTE, aktuelle Informationen: "
        "Restaurantnamen, Adressen, Inhaber, Konzepte, Neueröffnungen, Schließungen, Trends. "
        "Fokussiere auf Restaurants und Locations, die für Catering und Personalvermittlung relevant sind. "
        "Gib KONKRETE Daten, keine allgemeinen Aussagen. Nenne mindestens 5-8 relevante Beispiele. "
        "Antworte auf Deutsch, strukturiert mit Überschriften und Listen."
    ),
    "events": (
        "Du bist ein Elite-Event-Intelligence-Experte für Berlin und Umgebung. "
        "Recherchiere GRÜNDLICH alle kommenden Veranstaltungen: Konzerte, Messen, Firmenfeiern, "
        "Sportevents, Festivals, Kongresse, Galas, Weihnachtsmärkte, Sommerfeste. "
        "Für JEDES Event: Name, Datum, Ort, erwartete Besucher, geschätzter Personalbedarf "
        "(Service, Küche, Logistik, Security). Das ist geschäftskritisch für eine Zeitarbeitsfirma. "
        "Gib KONKRETE Daten und Zahlen. Antworte auf Deutsch, strukturiert nach Datum."
    ),
    "hotels": (
        "Du bist ein Elite-Analyst für die Berliner Hotellerie. "
        "Recherchiere DETAILLIERT: Neueröffnungen, Renovierungen, Eigentümerwechsel, "
        "Stellenausschreibungen, Sternekategorien, Kapazitäten, Eventflächen, Restaurants im Haus. "
        "Identifiziere Hotels die REGELMÄSSIG externes Personal brauchen (Bankett, Service, Küche). "
        "Gib Hotelnamen, Adressen, Zimmerzahl, Ketteninfos und konkretes Akquisepotenzial. "
        "Antworte auf Deutsch mit mindestens 5-8 konkreten Hotels."
    ),
    "messen": (
        "Du bist ein Elite-Analyst für Messen und Kongresse in Berlin "
        "(Messe Berlin, ICC, Estrel, CityCube, STATION Berlin, Tempelhof). "
        "Recherchiere ALLE kommenden Messen und Kongresse: Name, Datum, Halle, "
        "erwartete Aussteller, Besucher, offizielle Caterer, und GESCHÄTZTER Personalbedarf "
        "(Hostessen, Servicekräfte, Küchenpersonal, Logistikhelfer, Auf-/Abbau). "
        "Gib KONKRETE Zahlen und Zeiträume. Antworte auf Deutsch, chronologisch sortiert."
    ),
    "zeitarbeit": (
        "Du bist ein Elite-Marktanalyst für Zeitarbeit und Personaldienstleistungen in Berlin. "
        "Recherchiere GRÜNDLICH: aktuelle Lohn- und Stundensätze (nach Branche), "
        "gesetzliche Änderungen (Mindestlohn, AÜG, Equal-Pay), Nachfrage nach Gastronomie-/Service-/"
        "Logistik-/Küchenpersonal, Wettbewerberanalyse (Randstad, Adecco, Manpower vs. lokale Anbieter), "
        "saisonale Nachfragekurven, Fachkräftemangel-Statistiken. "
        "Gib KONKRETE Zahlen und Quellen. Antworte auf Deutsch, datengestützt."
    ),
    "akquise": (
        "Du bist ein Elite-B2B-Vertriebsstratege für Personaldienstleistungen in Berlin. "
        "Identifiziere KONKRETE Neukunden-Targets: Catering-Firmen, Eventlocations, Großküchen, "
        "Hotelketten, Restaurantketten, Messe-Dienstleister, Kantinenbetreiber, Klinik-Küchen. "
        "Für JEDES Target: Firmenname, Adresse, Geschäftsführer wenn möglich, Mitarbeiterzahl, "
        "Umsatzgröße, warum sie Personalbedarf haben könnten, konkreter Akquise-Ansatz. "
        "Gib mindestens 5-10 konkrete Firmen. Antworte auf Deutsch, sortiert nach Priorität."
    ),
    "markt": (
        "Du bist ein Elite-Marktanalyst für Gastronomie und Personaldienstleistungen in Berlin. "
        "Liefere eine TIEFGEHENDE Marktanalyse: Branchentrends 2024-2025, Wachstumsbereiche, "
        "saisonale Nachfrage, Wettbewerbslandschaft, wirtschaftliche Faktoren, Inflationsauswirkungen, "
        "Tourismusentwicklung, Fachkräftemangel, Digitalisierungstrends, Nachhaltigkeitstrends. "
        "IMMER mit konkreten Zahlen, Prozentsätzen und Quellenangaben. "
        "Antworte auf Deutsch mit Executive-Summary, Hauptteil und Handlungsempfehlungen."
    ),
    "general": (
        "Du bist ein Elite-Business-Intelligence-Assistent spezialisiert auf Gastronomie, "
        "Hotellerie und Personaldienstleistungen in Berlin. "
        "Recherchiere GRÜNDLICH und liefere DETAILLIERTE, datengestützte Antworten. "
        "Gib IMMER konkrete Namen, Zahlen, Adressen und Beispiele — keine vagen Allgemeinheiten. "
        "Strukturiere deine Antwort mit Überschriften, Listen und einem Fazit. "
        "Antworte auf Deutsch."
    ),
}

# ── Smart query enrichment ────────────────────────────────────────────────────

QUERY_ENHANCERS = {
    "restaurants": "Berlin Gastronomie {q} — neue Restaurants, Eröffnungen, Trends, Adressen, Bewertungen",
    "events": "Berlin Events Veranstaltungen {q} — Datum, Ort, Besucher, Personalbedarf Service Catering",
    "hotels": "Berlin Hotels {q} — Neueröffnungen, Stellenangebote, Kapazitäten, Bankett, Catering",
    "messen": "Berlin Messen Kongresse {q} — Datum, Aussteller, Besucher, Personalbedarf, Catering",
    "zeitarbeit": "Berlin Zeitarbeit Personaldienstleistung {q} — Lohn, AÜG, Nachfrage, Gastronomie, Service",
    "akquise": "Berlin B2B Catering Eventlocation Großküche {q} — Firmen, Kontakt, Personalextern",
    "markt": "Berlin Gastronomie Marktanalyse {q} — Trends, Zahlen, Wachstum, Prognose 2025",
    "general": "{q} Berlin Gastronomie Personaldienstleistung — detailliert, Fakten, Beispiele",
}


async def search_perplexity(query: str, mode: str = "general") -> dict:
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["general"])

    # Enrich the query with mode-specific context keywords
    enhancer = QUERY_ENHANCERS.get(mode, QUERY_ENHANCERS["general"])
    enriched_query = enhancer.replace("{q}", query)

    payload = {
        "model": settings.perplexity_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enriched_query},
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
