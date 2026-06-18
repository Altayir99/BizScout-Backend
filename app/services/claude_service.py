import anthropic
from fastapi import HTTPException
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """Du bist BizScout, ein persönlicher KI-Assistent für einen Unternehmer 
mit mehreren Firmen in der Gastronomie und Zeitarbeit in Berlin.

Deine Aufgaben:
- Marktanalysen und Business Intelligence für die Gastronomie-Branche
- Identifikation von Events und Locations, die Servicepersonal, Köche oder Logistikpersonal benötigen
- Unterstützung bei der Akquise neuer Kunden (Restaurants, Hotels, Veranstalter)
- Strategische Beratung für Zeitarbeitsfirmen in Service, Logistik und Küche
- Formulierung von Angeboten und Geschäftsvorschlägen

Unternehmen des Nutzers:
- Mehrere Gastronomie-Firmen in Berlin
- Zeitarbeitsfirmen in den Bereichen: Service, Logistik, Koch (Köche)

Stil: Professionell, präzise, direkt. Antworte immer auf Deutsch, 
außer der Nutzer schreibt auf Englisch oder Arabisch."""

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
