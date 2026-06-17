import anthropic
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


async def ask_claude(messages: list[dict]) -> str:
    """
    messages: list of {"role": "user"|"assistant", "content": str}
    The system prompt is injected automatically.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text
