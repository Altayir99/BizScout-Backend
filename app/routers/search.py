from fastapi import APIRouter
from pydantic import BaseModel
from app.services.perplexity_service import search_perplexity

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    mode: str = "general"  # "restaurants" | "events" | "general"


class SearchResponse(BaseModel):
    answer: str
    sources: list[str]
    mode: str


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest):
    """
    Deep web search via Perplexity.
    mode=restaurants → Berlin Gastronomie focus
    mode=events      → upcoming events needing staff
    mode=general     → open search
    """
    result = await search_perplexity(req.query, req.mode)
    return SearchResponse(**result)
