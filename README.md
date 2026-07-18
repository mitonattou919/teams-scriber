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
- フェーズ1(耳単体): 実機ACSリソース・テスト会議での確認待ち。`ear/dist/index.js` はダミー引数でPlaywright起動・静的サーバー配信・ブラウザ側スクリプト実行・WebSocket接続試行までは動作確認済み
- フェーズ2(脳): 未着手
