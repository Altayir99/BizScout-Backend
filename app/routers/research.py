from fastapi import APIRouter
from pydantic import BaseModel
from app.services.perplexity_service import search_perplexity
from app.services.claude_service import ask_claude

router = APIRouter(prefix="/research", tags=["research"])


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
    """
    # Step 1: Live data from Perplexity
    search_result = await search_perplexity(req.query, req.mode)

    # Step 2: Claude analyzes the results
    analysis_prompt = f"""Du hast folgende aktuelle Marktinformationen zum Thema "{req.query}" erhalten:

---
{search_result['answer']}
---

Analysiere diese Informationen aus der Perspektive eines Unternehmensberaters für Gastronomie- und Zeitarbeitsunternehmen in Berlin:

1. **Wichtigste Erkenntnisse** — Was sind die 2-3 wichtigsten Punkte?
2. **Chancen** — Welche konkreten Geschäftsmöglichkeiten ergeben sich?
3. **Handlungsempfehlungen** — Was sollte das Unternehmen als nächstes tun?

Sei präzise und praxisorientiert. Maximal 300 Wörter."""

    ai_analysis = await ask_claude([{"role": "user", "content": analysis_prompt}])

    return ResearchResponse(
        search_summary=search_result["answer"],
        ai_analysis=ai_analysis,
        sources=search_result["sources"],
        mode=req.mode,
    )
