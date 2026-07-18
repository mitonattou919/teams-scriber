# teams-scriber

Microsoft Teams会議に外部参加者として入り、ライブキャプションを読み取って必要なときだけ会議チャットにコメントを投稿するAIファシリテーターボットのPoC。

詳細な仕様・アーキテクチャは [`.claude/CLAUDE.md`](.claude/CLAUDE.md) を参照。

## 構成

- `ear/` — Node.js + Playwright。ヘッドレスChromium内でACS Calling SDKを実行し、会議に参加してキャプションを取得、WebSocketで脳に転送する
- `brain/` — Python。ACSユーザー作成・トークン発行、キャプション判定、会議チャットへの投稿を行う(セットアップは [`brain/README.md`](brain/README.md))
- `docs/` — セットアップ手順などのドキュメント

## セットアップの順序

1. [`docs/azure-resource-setup.md`](docs/azure-resource-setup.md) の手順でACSリソースを作成し、`ACS_CONNECTION_STRING` を取得する
2. `brain/` で `uv sync` して `issue-acs-token` を実行し、トークン発行が成功することを確認する
3. `ear/` で `npm install && npx playwright install chromium && npm run build` する
4. `brain/` の `launch-ear` で耳(`ear/`)をトークン付きで起動し、テスト用Teams会議に参加させる(会議のロビー承認は人間が手動で行う)

## 環境変数

```
ACS_CONNECTION_STRING=   # ACSリソースの接続文字列(脳が使用)
TEAMS_MEETING_LINK=      # テスト対象の会議リンク
LLM_PROVIDER=anthropic   # anthropic | azure_openai
ANTHROPIC_API_KEY=       # または AZURE_OPENAI_* 一式
INTERVENE_INTERVAL_SEC=180
```

## 動作確認ログ

- 基盤(ACSユーザー作成・トークン発行): `brain/` の `issue-acs-token` で発行したトークンが `ear/` の会議参加・キャプション取得に使えることを確認予定(実機ACSリソースでの確認待ち)
- フェーズ1(耳単体): 未確認(別ブランチで実装中)
- フェーズ2(脳): 未着手
