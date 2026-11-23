"""The current user's MCP tokens: issue, list and revoke."""

from fastapi import APIRouter, Response, status

from shtab_core.dependencies import CurrentUser
from shtab_core.exceptions import NotFoundError
from shtab_core.mcp_auth import McpTokens
from shtab_core.schemas import McpTokenIssued, McpTokenOut

router = APIRouter(prefix="/api/me/mcp-tokens", tags=["mcp"])


@router.get("", response_model=list[McpTokenOut], summary="My MCP tokens")
async def list_tokens(user: CurrentUser, tokens: McpTokens):
    return await tokens.list_for(user.id)


@router.post(
    "",
    response_model=McpTokenIssued,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an MCP token",
    description="The token is shown only once.",
)
async def issue_token(user: CurrentUser, tokens: McpTokens, response: Response):
    token = await tokens(user.id)
    response.headers["Cache-Control"] = "no-store"
    return McpTokenIssued(
        id=tokens.token_id(token.value),
        token=token.value,
        expires_in=int(token.ttl.total_seconds()),
    )


@router.delete(
    "/{token_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke an MCP token"
)
async def revoke_token(token_id: str, user: CurrentUser, tokens: McpTokens) -> Response:
    if not await tokens.revoke(user.id, token_id):
        raise NotFoundError("Token not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
