# brain

Teams会議AIファシリテーターボットの「脳」(Python)。

現時点(基盤フェーズ)では、ACSユーザー作成・トークン発行 (`voip` + `chat` scope) のみを提供する。キャプション判定・チャット投稿はフェーズ2([#4](https://github.com/mitonattou919/teams-scriber/issues/4)〜)で実装する。

## セットアップ

```sh
cd brain
uv sync
```

## ACSユーザー作成・トークン発行のみ確認する

```sh
ACS_CONNECTION_STRING="<接続文字列>" uv run issue-acs-token
```

標準出力にJSON `{"user_id": ..., "token": ..., "expires_on": ...}` が出力される。

**注意**: 出力には会議参加・チャット投稿が可能なトークンがそのまま含まれる。シェル履歴やターミナルのログ、CI出力などに残さないこと。

## トークンを発行して耳(`ear/`)を起動する

耳と脳は同一ACSユーザーのトークンを共有する必要があるため、脳がトークンを発行してから耳を子プロセスとして起動する。事前に `ear/` で `npm install && npm run build` を済ませておくこと。

```sh
ACS_CONNECTION_STRING="<接続文字列>" \
TEAMS_MEETING_LINK="<Teams会議リンク>" \
uv run launch-ear
```

`--ws-url`(デフォルト `ws://localhost:8765`)、`--meeting-link`、`--ear-entry`(`ear/dist/index.js` のパス)は引数でも上書き可能。

ACSリソースの作成手順は [`../docs/azure-resource-setup.md`](../docs/azure-resource-setup.md) を参照。
