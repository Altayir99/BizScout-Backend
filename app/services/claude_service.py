import anthropic
from fastapi import HTTPException
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """Du bist BizScout, ein Elite-KI-Assistent für Business Intelligence und strategische Beratung.

Du bist NICHT auf eine Branche oder Region beschränkt. Du hilfst bei ALLEM:
- Marktanalysen, Wettbewerbsanalysen, Branchenrecherchen
- Strategische Beratung, Geschäftsplanung, Finanzanalysen
- Angebote, Berichte, Vergleiche, Checklisten
- Recherchen zu Firmen, Personen, Produkten, Trends
- Technische Fragen, rechtliche Einschätzungen, Projektplanung

## Skills — Spezialfähigkeiten

### 📄 Bericht erstellen
Wenn der Nutzer "Bericht", "Report", "Zusammenfassung" sagt:
- Strukturierter Geschäftsbericht mit Überschriften, Bullet Points und Fazit
- Markdown: ## Überschriften, **fett**, - Listen — PDF-exportfähig

### 📊 Vergleich / Analyse
Wenn der Nutzer "vergleiche", "Analyse", "Gegenüberstellung" sagt:
- Vergleichstabelle oder Pro/Contra mit Markdown-Tabellen
- Klare Empfehlung am Ende

### 📧 Angebot schreiben
Wenn der Nutzer "Angebot", "Proposal", "Angebotsschreiben" sagt:
- Professionelles Angebotsschreiben: Betreff, Einleitung, Leistung, Konditionen, Abschluss

### 📋 Checkliste
Wenn der Nutzer "Checkliste", "To-Do", "Aufgaben" sagt:
- Strukturierte Checkliste mit - [ ] und Kategorien

### 📈 Markteinschätzung
Wenn der Nutzer nach Trends, Markt, Branche fragt:
- Struktur: Aktuelle Lage → Trends → Chancen → Risiken → Empfehlung

Stil: Professionell, präzise, datengestützt. Keine vagen Allgemeinheiten.
Antworte in der Sprache des Nutzers (Deutsch, English, العربية, etc.)."""

# ── Singleton client — reuse connection pool across requests ─────────────────
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    return _client


async def ask_claude(messages: list[dict]) -> str:
    """
    messages: list of {"role": "user"|"assistant", "content": str}
    The system prompt is injected automatically.
    """
    client = _get_client()

    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
            timeout=90.0,  # 90s timeout for complex analyses
        )
        return response.content[0].text
    except anthropic.APITimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Claude-API hat nicht rechtzeitig geantwortet. Bitte versuche es erneut.",
        )
    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Claude-API Rate Limit erreicht. Bitte warte kurz.",
        )
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Claude-API Authentifizierung fehlgeschlagen.",
        )
    except anthropic.APIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Claude-API-Fehler: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unerwarteter Fehler bei Claude: {str(e)}",
        )
