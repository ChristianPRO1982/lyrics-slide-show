from __future__ import annotations

import json


DEV_MOCK_ACCOUNTS: list[dict[str, str]] = [
    {
        "label": "testmock (Admin)",
        "external_id": "11111111-1111-1111-1111-111111111111",
        "username": "testmock",
        "email": "testmock@example.test",
        "first_name": "Test",
        "last_name": "Mock",
    },
    {
        "label": "disabled.user (Disabled)",
        "external_id": "22222222-2222-2222-2222-222222222222",
        "username": "disabled.user",
        "email": "disabled.user@example.test",
        "first_name": "Disabled",
        "last_name": "User",
    },
    {
        "label": "unknown.user (Unknown)",
        "external_id": "33333333-3333-3333-3333-333333333333",
        "username": "unknown.user",
        "email": "unknown.user@example.test",
        "first_name": "Unknown",
        "last_name": "User",
    },
    {
        "label": "testmock_moderateur (Moderator)",
        "external_id": "44444444-4444-4444-4444-444444444444",
        "username": "testmock_moderateur",
        "email": "testmock_moderateur@example.test",
        "first_name": "Testmock",
        "last_name": "Moderateur",
    },
    {
        "label": "testmock_simpletuser (Member)",
        "external_id": "55555555-5555-5555-5555-555555555555",
        "username": "testmock_simpletuser",
        "email": "testmock_simpletuser@example.test",
        "first_name": "Testmock",
        "last_name": "Simpletuser",
    },
]


def dev_mock_accounts_json() -> str:
    return json.dumps(DEV_MOCK_ACCOUNTS, separators=(",", ":"), ensure_ascii=True)
