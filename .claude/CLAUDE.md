# PoC: Teams会議AIファシリテーターボット — 実装指示書

## ゴール

Microsoft Teams会議に外部参加者として入り、ライブキャプションを準リアルタイムで読み取り、必要なときだけ**会議チャットに短いコメントを投稿する**ボットのPoCを作る。音声・映像の送受信は行わない(ミュート・カメラオフで参加するだけ)。

成功条件(受け入れ基準):
1. 会議リンクを渡すとボットが会議に参加できる(ロビー承認は人間が手動で行う)
2. 参加者の発言がキャプションとしてPython側にストリーム到達する(発話者名付き)
3. `@AI-Facilitator` を含むチャット投稿、または「明確な事実誤認と判定した発言」に対してのみ、会議チャットに日本語で1〜3文のコメントを投稿する
4. 投稿頻度はデフォルトで最大1回/3分(メンション応答は除く)

## アーキテクチャ(確定事項 — 変更しないこと)

2プロセス構成。PoCでは同一マシン上のローカル実行でよい(コンテナ化・Azure Container Apps化はフェーズ3)。

```
[耳: Node.js + Playwright(headless Chromium)]
  - ACS Calling SDK (@azure/communication-calling) をブラウザ内で実行
  - 会議参加(ミュート/カメラオフ) → startCaptions → キャプションイベント受信
  - 受信したキャプションを ws://localhost:8765 へJSONで転送するだけの薄い層
        │
        ▼ WebSocket (localhost)
[脳: Python 3.11+]
  - キャプションを発話者別にバッファリング
  - LLMで「介入すべきか」を判定(構造化出力)
  - azure-communication-chat SDK で会議チャットへ send_message
```

### なぜこの構成か(前提知識)
- ACS Calling SDKはブラウザ用クライアントSDKで**Pythonは存在しない**。よって耳だけNode+ヘッドレスブラウザ。これはRead.ai等のノートテイカー系プロダクトと同じ業界標準構成
- ACS外部ユーザーはTeams会議参加後、会議チャットのスレッドに送受信できる(公式サポート)
- キャプション/チャットはTCP/443のシグナリング経由なのでメディア品質は問題にならない

## 技術仕様

### 共通: ACS ID・トークン
- ACSリソースの接続文字列は環境変数 `ACS_CONNECTION_STRING` から取得
- `azure-communication-identity`(Python)でユーザーを1つ作成し、**scopeは `voip` と `chat` の両方**でトークン発行
- **耳と脳で同一ACSユーザーのトークンを使うこと**(チャット投稿は「会議コールに参加承認されたACSユーザー」しかできないため)。脳が起動時にID/トークンを発行し、耳に渡す設計にする

### 耳(Node/TypeScript)
- Playwrightでヘッドレス Chromium を起動し、ローカルの最小HTMLページを開いて `@azure/communication-calling` を実行する(Node直実行は不可、ブラウザ環境必須)
- 起動引数: ACSトークン、Teams会議リンク、脳のWS URL
- 処理:
  1. `CallClient` → `callAgent.join({ meetingLink }, { audioOptions: { muted: true } })`(映像は送らない)
  2. call state が `Connected` になったら `call.feature(Features.Captions)` を取得。`captions.kind === 'TeamsCaptions'` を確認し、`startCaptions({ spokenLanguage: 'ja-jp' })`
  3. `CaptionsReceived` イベントごとに `{ speaker, text, resultType, timestamp }` をWSへJSON送出。`resultType: 'Final'` のみ転送する(Partialはノイズ)
  4. call切断でプロセス終了
- 表示名は `AI-Facilitator (transcribing)` とする(転写している旨の開示はMSの規約上の義務)

### 脳(Python)
- 依存: `azure-communication-chat`, `azure-communication-identity`, `websockets`, LLM SDK(環境変数 `LLM_PROVIDER` で Azure OpenAI / Anthropic を切替可能に。デフォルトはAnthropicの `claude-sonnet-4-6`)
- 処理:
  1. WSサーバー(:8765)でキャプションを受信、`deque` に直近10分ぶん保持
  2. 会議チャットのthread_idは会議リンクの `meetup-join/<threadId>/` 部分をURLデコードして抽出。`ChatClient.get_chat_thread_client(thread_id)` で接続
  3. チャットをポーリング(3秒間隔)して `@AI-Facilitator` 宛メンションを検知 → 直近の文脈を添えてLLMに回答生成 → 投稿
  4. 30秒ごとに未処理キャプションをまとめてLLMに渡し、`{"intervene": bool, "reason": str, "comment": str|null}` の構造化判定をさせる。`intervene=true` かつレートリミット内のときだけ投稿
  5. LLM判定プロンプトの方針: 「明確な事実誤認・数字の間違いのみ指摘。意見の相違・曖昧な話には介入しない。コメントは敬体の日本語で1〜3文、断定を避け『〜のようです』調」
- 投稿レートリミット: メンション応答以外は3分に1回まで(設定可能に)

## フェーズ分割(この順で実装・動作確認すること)

1. **フェーズ1(最優先)**: 耳の単体動作。会議に参加してキャプションをコンソールに出力できるまで。ここが最大の技術リスク
2. **フェーズ2**: 脳を接続。メンション応答 → 自発介入の順に実装
3. **フェーズ3(週末に余裕があれば)**: Dockerfile 2本 + docker-compose。ACA化は不要、composeで止めてよい

## 既知の制約・ハマりどころ

- Teams側でキャプション(トランスクリプション)ポリシーが有効なテナント・会議であること。無効だと `startCaptions` が失敗する
- ボットは匿名外部ユーザー扱い。ロビー承認必須。テナントの外部ボット検出ポリシーで弾かれる場合はテナント設定を確認
- 参加前のチャット履歴は読めない。会議終了後は送受信不可
- チャネル会議は音声参加できてもチャット不可。**通常のスケジュール会議でテストすること**
- E2E暗号化会議、ウェビナー、ライブイベントは参加不可
- 翻訳キャプションはTeams Premiumが要るので使わない(spoken language = ja-jp の生キャプションのみ)

## 環境変数一覧

```
ACS_CONNECTION_STRING=   # ACSリソースの接続文字列
TEAMS_MEETING_LINK=      # テスト対象の会議リンク
LLM_PROVIDER=anthropic   # anthropic | azure_openai
ANTHROPIC_API_KEY=       # または AZURE_OPENAI_* 一式
INTERVENE_INTERVAL_SEC=180
```

## 成果物

- `ear/` (TypeScript, Playwright, 最小HTML)
- `brain/` (Python, pyproject.toml)
- `README.md` (セットアップ手順、テスト用会議の作り方、ロビー承認の手順)
- 動作確認ログ(フェーズ1・2それぞれ)

---

## 将来の展望(今週末のスコープ外 — ただし設計判断の参考にすること)

このPoCは以下のロードマップの第一歩である。**実装は不要**だが、将来の拡張を殺す設計判断を避けるため、方向性を共有しておく。

### 展望1: 会議後の議事録自動生成 → SharePoint保存
- 会議終了検知(roster監視で自分以外の退出、またはcall切断)をトリガーに、キャプション全文から議事録(決定事項・宿題・担当・期限)をLLMで構造化生成し、Graph APIでプロジェクトのSharePointサイトのドキュメントライブラリに保存する
- 認可はEntraアプリ登録 + アプリケーション許可 `Sites.Selected`(対象サイト限定)、ACA移行後はmanaged identityを想定
- 注意: ACS外部ユーザーは会議終了後にチャット送受信不可になるため、成果物の恒久保存先はチャットではなくストレージとする方針

### 展望2: 議事録のAzure AI Searchインデックス化(RAG)
- 既存の就業規則インデックス/パイプラインとは**別インデックス**として議事録用を新設する
- 議事録は脳が生成するため、SharePointをクロールせず、生成時に構造化チャンク(決定事項1件=1ドキュメント等)を**プッシュAPIで直接投入**する
- これにより脳が過去の経緯を引ける(「その件は先月結論が出ています」等の交通整理)

### 展望3: コンテキスト注入によるファシリテーション強化
- 段階1: 会社理念・行動指針などの静的コンテキストをプロンプトに固定注入
- 段階2: 会議ごとのゴールを起動時パラメータまたは予定表本文(Graph)から取得
- 段階3: 展望2のインデックスをRAGとして参照
- 介入の強さ(傍聴のみ / 求められたら回答 / 自発的に整理)を会議オーナーが設定できる仕組みを想定

### 展望4: 情報アクセス層のMCP化
- AI Search等へのアクセスを `search_minutes` / `search_regulations` / `get_project_context` 等のツールを持つMCPサーバーに切り出し、脳はMCPクライアントとする
- 同じMCPサーバーを会議ボット以外(社員向けチャットAI等)からも共用する構想
- 入口はOAuth 2.1。認可は「プロジェクト = SharePointサイト = セキュリティグループ」の対応を前提に、インデックスのメタデータにグループIDを焼き込み、クエリ時にトークンのグループクレームでセキュリティフィルタする方式を予定

### PoC実装時に意識すべき布石(ここだけは今週末に効く)
1. **キャプションの全文バッファを捨てない設計にする**(直近10分のdequeとは別に、会議全体のログをJSONLでローカル保存しておく)。展望1の入力になる
2. **キャプションログには speaker / timestamp を必ず保持**する。議事録の担当割り当てと展望4の参加者スコープ認可の材料になる
3. 脳のLLM呼び出し部分は**プロバイダ非依存の薄い抽象**にしておく(既に環境変数で切替可能な設計だが、将来ツール呼び出し/MCPクライアント化することを見越して、判定ロジックとLLM呼び出しを分離しておく)
4. 参加者リスト(roster)を取得できるなら会議ログに含めておく。議事録メタデータ(参加者・対象グループ)の元ネタになる
