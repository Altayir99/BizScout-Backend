from fastapi import APIRouter
from pydantic import BaseModel
from app.services.perplexity_service import search_perplexity
from app.services.claude_service import get_claude_client
from app.config import get_settings

router = APIRouter(prefix="/research", tags=["research"])
settings = get_settings()


class ResearchRequest(BaseModel):
    query: str
    mode: str = "general"


class ResearchResponse(BaseModel):
    search_summary: str
    ai_analysis: str
    sources: list[str]
    mode: str


@router.post("", response_model=ResearchResponse)
async def research(req: ResearchRequest):
    """
    Power search: Perplexity fetches live data → Claude analyzes and advises.
    Returns both the raw search summary and Claude's strategic analysis.
    """
    # Step 1: Get live data from Perplexity
    search_result = await search_perplexity(req.query, req.mode)

    # Step 2: Pass search results to Claude for strategic analysis
    import anthropic
    client = get_claude_client()

    analysis_prompt = f"""Du hast folgende aktuelle Marktinformationen zum Thema "{req.query}" erhalten:

---
{search_result['answer']}
---

Analysiere diese Informationen aus der Perspektive eines Unternehmensberaters für Gastronomie- und Zeitarbeitsunternehmen in Berlin:

1. **Wichtigste Erkenntnisse** — Was sind die 2-3 wichtigsten Punkte?
2. **Chancen** — Welche konkreten Geschäftsmöglichkeiten ergeben sich?
3. **Handlungsempfehlungen** — Was sollte das Unternehmen als nächstes tun?

Sei präzise und praxisorientiert. Maximal 300 Wörter."""

    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": analysis_prompt}],
    )

    ai_analysis = message.content[0].text

    return ResearchResponse(
        search_summary=search_result["answer"],
        ai_analysis=ai_analysis,
        sources=search_result["sources"],
        mode=req.mode,
    )
