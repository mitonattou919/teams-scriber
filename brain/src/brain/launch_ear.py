"""ACSトークンを発行し、耳(ear/)プロセスを同一トークンで起動する。

フェーズ1では手動トークンでear/を単体起動していたが、これは脳と耳が
同一ACSユーザーを共有するための起動スクリプト(#2の受け入れ基準)。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from brain.identity import issue_user_and_token

# brain/src/brain/launch_ear.py からリポジトリルートまで3階層上。
# editable install (src layout) を前提としており、インストール方式を変えると崩れる。
REPO_ROOT = Path(__file__).resolve().parents[3]
EAR_DIR = REPO_ROOT / "ear"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meeting-link", default=os.environ.get("TEAMS_MEETING_LINK"))
    parser.add_argument("--ws-url", default="ws://localhost:8765")
    parser.add_argument("--ear-entry", default=str(EAR_DIR / "dist" / "index.js"))
    args = parser.parse_args()

    if not args.meeting_link:
        sys.exit("--meeting-link または TEAMS_MEETING_LINK が必要です")

    connection_string = os.environ.get("ACS_CONNECTION_STRING")
    if not connection_string:
        sys.exit("ACS_CONNECTION_STRING が設定されていません")

    identity = issue_user_and_token(connection_string)
    print(
        f"[brain] ACS user issued: {identity.user_id} (expires {identity.expires_on})",
        file=sys.stderr,
    )

    subprocess.run(
        [
            "node",
            args.ear_entry,
            "--meeting-link", args.meeting_link,
            "--ws-url", args.ws_url,
        ],
        check=True,
        cwd=EAR_DIR,
        env={**os.environ, "ACS_TOKEN": identity.token},
    )


if __name__ == "__main__":
    main()
