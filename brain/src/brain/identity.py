"""ACSユーザー作成・トークン発行。

耳(Node/Playwright)と脳(Python)は同一ACSユーザーのトークンを共有する必要がある
(チャット投稿は「会議コールに参加承認されたACSユーザー」しかできないため)。
このモジュールは脳の起動時に一度だけ呼び出し、発行したトークンを耳に渡す想定。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

from azure.communication.identity import (
    CommunicationIdentityClient,
    CommunicationTokenScope,
)


@dataclass(frozen=True)
class IssuedIdentity:
    user_id: str
    token: str
    expires_on: str  # ISO 8601


def issue_user_and_token(connection_string: str) -> IssuedIdentity:
    client = CommunicationIdentityClient.from_connection_string(connection_string)
    user, token_response = client.create_user_and_token(
        scopes=[CommunicationTokenScope.VOIP, CommunicationTokenScope.CHAT],
    )
    return IssuedIdentity(
        user_id=user.properties["id"],
        token=token_response.token,
        expires_on=token_response.expires_on.isoformat(),
    )


def main() -> None:
    connection_string = os.environ.get("ACS_CONNECTION_STRING")
    if not connection_string:
        sys.exit("ACS_CONNECTION_STRING が設定されていません")

    identity = issue_user_and_token(connection_string)
    json.dump(
        {
            "user_id": identity.user_id,
            "token": identity.token,
            "expires_on": identity.expires_on,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
