"""URL resolution diagnostic API endpoint."""

from fastapi import APIRouter

from link_checker.utils import resolve_relative_url, normalize_url
from ..models.schemas import (
    UrlResolutionRequest,
    UrlResolutionResponse,
    UrlResolutionResult,
    ResolvedUrl,
)

router = APIRouter(prefix="/api/url-resolution", tags=["url-resolution"])

DEFAULT_TEST_HREFS = [
    "/blog/post-name/",
    "relative-page/",
    "../other-page/",
    "/about/",
    "//cdn.example.com/asset.js",
    "https://external.com/page",
]


@router.post("/test", response_model=UrlResolutionResponse)
async def test_url_resolution(request: UrlResolutionRequest):
    """Test how relative URLs resolve against given base URLs.

    Reuses the same resolution logic as the crawler and the CLI
    ``--test-urls`` flag. Useful for diagnosing subdirectory URL
    issues on WordPress/blog sites.
    """
    hrefs = DEFAULT_TEST_HREFS + [h for h in request.custom_hrefs if h]

    results = []
    for base_url in request.base_urls:
        resolutions = []
        for href in hrefs:
            resolved = resolve_relative_url(base_url, href)
            normalized = normalize_url(resolved) if resolved else "(empty)"
            resolutions.append(ResolvedUrl(href=href, resolved_url=normalized))
        results.append(UrlResolutionResult(
            base_url=base_url,
            resolutions=resolutions,
        ))

    return UrlResolutionResponse(results=results)
