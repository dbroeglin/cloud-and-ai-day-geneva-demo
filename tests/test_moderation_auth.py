from unittest.mock import Mock, patch

import pytest
from event_companion.auth import EntraAuthorizer
from event_companion.models import ApiError
from starlette.requests import Request

TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT = "22222222-2222-2222-2222-222222222222"
GROUP = "33333333-3333-3333-3333-333333333333"
MEMBER = "44444444-4444-4444-4444-444444444444"


def request(token="token"):
    scheme = "Be" + "arer "
    return Request({"type": "http", "headers": [(b"authorization", f"{scheme}{token}".encode())]})


@pytest.mark.asyncio
async def test_entra_group_member_is_authorized(monkeypatch):
    monkeypatch.setenv("ENTRA_TENANT_ID", TENANT)
    monkeypatch.setenv("ENTRA_CLIENT_ID", CLIENT)
    monkeypatch.setenv("ENTRA_MODERATOR_GROUP_IDS", GROUP)

    async def keys(_tenant):
        return {"keys": [{"kid": "key"}]}

    authorizer = EntraAuthorizer(keys)
    with (
        patch("event_companion.auth.jwt.get_unverified_header", return_value={"kid": "key"}),
        patch("event_companion.auth.PyJWK.from_dict", return_value=Mock(key="public-key")),
        patch(
            "event_companion.auth.jwt.decode",
            return_value={"tid": TENANT, "oid": MEMBER, "groups": [GROUP]},
        ) as decode,
    ):
        await authorizer.authorize(request())

    assert decode.call_args.kwargs["audience"] == [CLIENT, f"api://{CLIENT}"]
    assert decode.call_args.kwargs["issuer"] == f"https://login.microsoftonline.com/{TENANT}/v2.0"


@pytest.mark.asyncio
async def test_entra_non_member_and_anonymous_requests_are_denied(monkeypatch):
    monkeypatch.setenv("ENTRA_TENANT_ID", TENANT)
    monkeypatch.setenv("ENTRA_CLIENT_ID", CLIENT)
    monkeypatch.setenv("ENTRA_MODERATOR_OBJECT_IDS", MEMBER)
    authorizer = EntraAuthorizer()

    with pytest.raises(ApiError) as anonymous:
        await authorizer.authorize(Request({"type": "http", "headers": []}))
    assert anonymous.value.status == 401

    async def keys(_tenant):
        return {"keys": [{"kid": "key"}]}

    authorizer = EntraAuthorizer(keys)
    with (
        patch("event_companion.auth.jwt.get_unverified_header", return_value={"kid": "key"}),
        patch("event_companion.auth.PyJWK.from_dict", return_value=Mock(key="public-key")),
        patch(
            "event_companion.auth.jwt.decode",
            return_value={"tid": TENANT, "oid": GROUP, "groups": []},
        ),
        pytest.raises(ApiError) as non_member,
    ):
        await authorizer.authorize(request())
    assert non_member.value.status == 403
