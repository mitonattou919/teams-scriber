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

## `ear/` の単体動作確認

`brain/`(脳)を介さず `ear/` だけを手動トークンで動かして確認したい場合:

```sh
cd ear
npm install
npx playwright install chromium
npm run typecheck   # tsc --noEmit
npm run build        # esbuildでdist/にバンドル

ACS_TOKEN=<ACSトークン(scope: voip, chat)> \
node dist/index.js \
  --meeting-link "<Teams会議リンク>" \
  --ws-url "ws://localhost:8765"
```

会議参加後、キャプションが `Final` になるたびにコンソールへ `[ear:browser] caption: <speaker> <text>` の形式でログ出力される。`ws-url` 先に脳のWebSocketサーバーが立っていない場合は接続エラーになるが、その他の動作(会議参加・キャプション取得)はコンソールログで確認できる。

### テスト用会議の作り方 / ロビー承認の手順

1. Outlook または Teams で通常のスケジュール会議を作成する(チャネル会議・ライブイベント・ウェビナーは不可)
2. 会議のテナントでキャプション/トランスクリプションポリシーが有効になっていることを確認する
3. ボットは匿名外部ユーザーとして参加登録されるため、会議主催者側でロビーからの手動承認が必要
4. 参加者の発言はTeamsクライアント側からミュート解除して行う(ボット自身は常にミュート・カメラオフ)

### 既知の制約

- テナントの外部ボット検出ポリシーで弾かれる場合は、テナント設定側で許可が必要
- 参加前のチャット履歴は読めない。会議終了後は送受信不可
- 翻訳キャプション(Teams Premium機能)は使わない。`spokenLanguage: 'ja-jp'` の生キャプションのみを扱う

## 議事録の自動生成(`caption-server`)

`brain/` の `caption-server` はキャプションをWSで受信して `--log-path`(デフォルト `captions.jsonl`)にJSONL保存しつつ、耳からの `call_ended` 通知(call切断時に自動送信される)を受け取ると、ログ全文をLLMに渡して議事録を生成し `--minutes-dir`(デフォルト `minutes/`)配下に `<meeting_id>.md` / `<meeting_id>.json` として保存する。LLM呼び出しには `AZURE_OPENAI_*`(デフォルト)または `ANTHROPIC_API_KEY` の環境変数が必要。

```sh
cd brain
uv run caption-server --log-path captions.jsonl --minutes-dir minutes
```

## 環境変数

```
ACS_CONNECTION_STRING=     # ACSリソースの接続文字列(脳が使用)
TEAMS_MEETING_LINK=        # テスト対象の会議リンク
LLM_PROVIDER=azure_openai  # azure_openai | anthropic (議事録生成に使用、デフォルトはAzure OpenAI)
AZURE_OPENAI_ENDPOINT=     # Azure AI Foundryのエンドポイント
AZURE_OPENAI_API_KEY=      # Azure AI FoundryのAPIキー
AZURE_OPENAI_MODEL=gpt-5.5-mini
ANTHROPIC_API_KEY=         # LLM_PROVIDER=anthropic のときのみ使用
INTERVENE_INTERVAL_SEC=180
```

## 動作確認ログ

- 基盤(ACSユーザー作成・トークン発行): 実機ACSリソースで確認済み(2026-07-19)。`issue-acs-token` でvoip+chatスコープのトークン発行に成功
- フェーズ1(耳単体・実機疎通): 実機ACSリソース・テスト用Teams会議で確認済み(2026-07-19)。`brain/` の `launch-ear` でトークン発行 → `ear/` が会議にロビー承認経由で参加 → `startCaptions` → 発話者名・タイムスタンプ付きキャプション(短文・長文とも)を `Final` 判定でコンソールに送出、まで一連の流れを確認
  - 確認中に見つかった不具合を修正: `brain/src/brain/identity.py` の `expires_on` が `azure-communication-identity==1.5.0` では既に `str` (ISO 8601) で返るため `.isoformat()` 呼び出しで例外になっていた点/`ear/src/index.ts` の静的サーバーが `127.0.0.1` でlistenしており、ACS Web Calling SDKが要求する `https:` / `file:` / `localhost` originの制約に違反して `CallClient` 生成時に失敗していた点(`localhost` に変更)
- フェーズ2(脳): 未着手。今回の確認で脳のWebSocketサーバー(:8765)が未実装なため、耳側で `brain WebSocket not open, dropping caption` が出ることを確認(想定通り)
- チャネル会議での動確(実機・2026-07-19): 会議チャットが使えないチャネル会議でも `launch-ear` で参加→ロビー承認→`Connected`→`startCaptions`→発話者名・`Final`判定付きキャプション取得、まで通常会議と同様に成功することを確認。チャット送受信はCalling SDKのキャプション機能と独立しているため、「チャットへの投稿は諦め、参加+トランスクリプト取得+会議後の議事録生成」の経路であればチャネル会議でも成立する見込み(展望1の設計と整合)
- フェーズ2・脳の耳↔脳疎通(実機・2026-07-19、Issue #4): `caption-server`(WSサーバー:8765)を起動した状態で `launch-ear` を実行し、ロビー承認→`Connected`→`captions started`後の発話に対し、キャプションが脳側コンソールに `[brain] caption: <speaker> <text>` として即時出力され、`captions.jsonl` に `{speaker, text, timestamp}` としてJSONLで逐次追記保存されることを確認
