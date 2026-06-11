# 🚀 OPC-Agents — 一人会社向けインテリジェントタスク実行システム

> **バージョン**: v0.2.5 | **ステータス**: Beta | **ライセンス**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/opc-agents)](https://pypi.org/project/opc-agents/)

---

**言語**: [中文](README.md) | [English](README-EN.md) | **日本語**

---

## これは何か

OPC-Agents（One-Person Company Agents）は、**一人会社/独立起業家/フリーランス向けのインテリジェントタスク実行システム**です。

**コアコンセプト：求める結果をシステムに伝えれば、作業を完了してファイルを納品します。**

チャットボットでも、アドバイスエンジンでもありません。**仕事をこなす実行者**です。

## 何ができるか

| あなたの指示 | システムの納品物 |
|-------------|----------------|
| 「OPC会社のトレンドを収集して」 | 🔍 **調査レポート**（実際の検索結果+ソースリンク+構造化整理） |
| 「Q2マーケティングプランを作成して」 | ✍️ **完全な計画書**（SMART目標+ロードマップ+リソース/リスク/受入基準） |
| 「競合Aを分析して」 | 📊 **分析レポート**（SWOT+アクションリスト+優先順位付け） |
| 「製品ローンチ計画を作成して」 | 🚀 **ローンチプラン**（価格戦略+プロモーションチャネル+タイムライン） |

### 主な特徴

- ✅ **三賢者アーキテクチャ** — 戦略脳(意図理解)+実行脳(スキル実行)+反省脳(結果評価)クローズドループ協調
- ✅ **スキルコンテキスト渡し** — SkillContextがスキル間データフローをサポート、検索→分析→作成クローズドループ
- ✅ **LLM拡張コンテンツ生成** — Claude Sonnet 4搭載、高品質出力
- ✅ **リアルWeb検索** — DuckDuckGoライブ検索、データの捏造なし
- ✅ **ゼロプレースホルダー保証** — 全ての出力に具体的で実行可能な内容
- ✅ **自動修正** — 品質が基準に満たない場合、自動的に修正戦略をトリガー（リトライ/検索してリトライ/スキル切替/ダウングレード）
- ✅ **マルチスキルオーケストレーション** — 複合意図を自動的にマルチステップ実行計画に分解（例：「競合分析してプラン作成」→検索→分析→作成）
- ✅ **タスク一時停止/再開** — 実行中のタスクを一時停止し、後でブレークポイントから再開
- ✅ **実行進捗可視化** — イベント駆動のリアルタイム進捗追跡、SSEサポート
- ✅ **長セッションコンテキスト** — マルチターン会話でコンテキストを維持、「XXを追加」で前回の結果から継続
- ✅ **非同期実行** — 投稿して即座に返却、バックグラウンド処理+進捗表示
- ✅ **品質ゲート** — 納品物の自動チェック（プレースホルダー0+最低文字数+データソース）、不適格時は自動標記
- ✅ **出力秘匿化** — 生成内容のAPIキー/GitHubトークンを自動検出・置換、漏洩防止
- ✅ **ナレッジベースフォールバック** — 6カテゴリ20件の専門知識、検索失敗時の自動フォールバック
- ✅ **ファイル納品** — `.md`ファイルを自動生成、ダウンロードボタン付き
- ✅ **セキュリティ保護** — コマンドホワイトリスト+パス検証+入力長制限+監査ログ+入力検証+プロンプトインジェクション防御+URL安全性+エラー秘匿化+APIキー暗号化ストレージ
- ✅ **テストカバレッジ** — 2939テストケース、100%合格率、CI自動検証（settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler等全モジュールをカバー）
- ✅ **スキルマーケットAPI** — 外部スキル登録/発見/呼び出し、APIキー認証+権限レベル
- ✅ **MCPプロトコル互換** — Microsoft Model Context Protocol標準互換、ツール/リソース/プロンプト対応
- ✅ **プラグインシステム** — コミュニティプラグインのホットロード+サンドボックス隔離+ライフサイクル管理
- ✅ **カスタムスキルエディタ** — フォーム式スキル作成/テスト/プレビュー/公開
- ✅ **品質/クイックモード** — ユーザー選択可能な三賢者フルクローズドループまたはリフレクションスキップ高速実行
- ✅ **📋 統一設定管理** — 5タブ設定センター（LLM/SMTP/API Keys/Security/Profile）、SettingsManagerシングルトン
- ✅ **🚶 初回実行オンボーディング** — 3ステップOnboardingウィザード（ウェルカム→API Key設定→機能紹介）
- ✅ **💾 データバックアップ/リストア** — ZIP/JSON/CSVマルチフォーマットエクスポート、SHA256検証、Zip Slip保護、DataBackupManager
- ✅ **🛡️ フレンドリーエラーハンドリング** — 9種例外タイプ→日本語フレンドリーメッセージ、ErrorHandler統一例外変換
- ✅ **💬 WeChat E2E統合** — WeChatAgent + WeChatGateway、WeChat経由のタスク対話対応
- ✅ **📊 モジュラー ダッシュボード** — DashboardConfig（3レイアウト×3密度×6パネル=9組合せ）、テンプレートシステム
- ✅ **🌐 3言語i18n** — I18nManagerがzh_CN/en_US/ja_JPをサポート、58+翻訳キー
- ✅ **🛒 スキルマーケットV2** — 詳細パネル+16カテゴリフィルター+バージョンピンニング、新UI体験
- ✅ **🔍 グローバル検索** — クロスモジュール統一検索、スキル/顧客/記事/TODOを一括検索
- ✅ **⌨️ Apple Shortcuts統合** — 5つのショートカットアクション（quick_task/query_status/create_deliverable/record_income/daily_report）
- ✅ **🔐 API Key暗号化保存** — Fernet対称暗号化、自動生成キー（.env.local）、secure_storage強化
- ✅ **🧩 コードモジュラー化リファクター** — フロントエンドを3834行モノリシックから8モジュールに分割、バックエンドからskill_models/skill_builtin/skill_executors/task_types/task_content_generators/scenario_definitions等を独立モジュールとして抽出

## アクセラレーター

これらの機能はコアフローを**より良く、より速く、使うほど強力に**します：

| アクセラレーター | どのように成果を早く出すか |
|----------------|------------------------|
| 🧠 **クロスセッション記憶** | 好みとコンテキストを記憶、毎回の繰り返し説明不要（[CarryMem](https://github.com/lulin70/carrymem)が必要、`pip install opc-agents[memory]`） |
| 🔄 **フライホイール成長** | 使うほどレベルアップ（🌱初心者→👑伝説）、出力品質が自動向上 |
| 🏪 **スキルマーケット** | サードパーティスキルの検索・インストール、オンデマンドで能力拡張 |
| 📚 **外部ナレッジベース** | Obsidian/語雀/飛書/Notion/思源ノートに接続、AIがプライベート資料を参照 |
| 📜 **ルールエンジン** | 失敗経験を自動的にルール化、同じエラーを二度と繰り返さない |
| ↩️ **アンドゥ機能** | 操作は取り消し可能、安心して大胆に使用 |
| 🌐 **3言語切替** | 中国語/英語/日本語UIワンクリック切替 |
| 🧊 **LLMキャッシュ** | 同じ質問は重複API呼び出しなし、時間とコストを節約 |

## エコシステムツール

特定のシナリオに遭遇？組み合わせて使うとさらに効果的：

| シナリオ | 推奨ツール | 説明 |
|---------|-----------|------|
| AIに好みを記憶させたい | [CarryMem](https://github.com/lulin70/carrymem) | クロスセッション永続記憶エンジン、`pip install opc-agents[memory]`で有効化 |
| 開発タスクで多役割協力が必要 | [DevSquad](https://github.com/lulin70/DevSquad) | 7役割AIチーム（アーキテクト/PM/セキュリティ/テスター/開発/DevOps/UI）、複雑な開発タスクの分解と協力 |

## クイックスタート

### 前提条件

- Python 3.10+
- 少なくとも1つのLLM APIキー（推奨: [MOKA](https://moka-ai.com)）

### 方法1：pipインストール

```bash
# 1. インストール
pip install opc-agents==0.2.5

# 2. 暗号化依存パッケージをインストール（推奨、メールパスワード等の機密フィールド暗号化に使用）
pip install cryptography

# 3. ワークスペースを作成し、APIキーを設定
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# （オプション）平文.envの代わりに暗号化ストレージを使用
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

# 初回起動時に.env.localが自動生成（暗号化キーを含む、gitignoreで保護）
# 暗号化キーを手動設定する場合：
# echo "OPC_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env.local

# 4. 起動
opc-agents
```

> pipインストール後、`.env`、成果物、ログはカレントディレクトリに保存されます。

### 方法2：ソースインストール（開発者向け推奨）

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x install.sh start.sh
./install.sh

# 暗号化依存パッケージをインストール
pip install cryptography

# APIキーの設定
cp .env.example .env
# .envを編集し、MOKA APIキーを入力

# 起動
./start.sh
```

### 方法3：Dockerデプロイ

```bash
docker compose up -d
```

| ポート | サービス | 説明 |
|--------|---------|------|
| 8501 | メインアプリ (Streamlit) | Web UI |
| 8900 | スキルマーケットAPI (FastAPI) | REST API |
| 8901 | MCP SSEエンドポイント | Model Context Protocol |

### 環境変数

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `OPC_DATA_DIR` | データ保存ディレクトリ | プロジェクトルート下の `data/` |
| `OPC_ENCRYPTION_KEY` | AES暗号化キー（**必須設定**、未設定時は暗号化操作でRuntimeError発生） | なし（未設定時は暗号化拒否） |
| `MOKA_API_KEY` | MOKA LLM APIキー | — |
| `GLM_API_KEY` | 智譜GLM APIキー | — |
| `OPENAI_API_KEY` | OpenAI APIキー | — |
| `OLLAMA_BASE_URL` | Ollamaローカルモデルアドレス | — |
| `OPC_SKIP_REFLECT` | リフレクション段階をスキップ（クイックモード） | `false` |
| `CARRYMEM_ENABLED` | クロスセッション永続記憶を有効化 | `false` |
| `CARRYMEM_DB_PATH` | CarryMemデータベースパス | `~/.opc-agents/memory.db` |
| `OPC_KB_ENABLED` | 外部ナレッジベースを有効化 | `false` |
| `OPC_KB_TYPE` | ナレッジベースタイプ | `local` |
| `OPC_KB_PATH` | ナレッジベースパス（Obsidian/ローカル） | `~/knowledge` |

> ⚠️ **セキュリティ注意**：`OPC_ENCRYPTION_KEY`は必須です。未設定時、`encrypt_field()`が`RuntimeError`をスローし、メールパスワードや顧客機密フィールド等の暗号化操作が失敗します。`.env`に強力なランダムキーを必ず設定してください。

### APIキーについて

| バックエンド | モデル | 設定変数 | 品質 | 取得方法 |
|-------------|--------|----------|------|---------|
| **MOKA（推奨）** | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ | [moka-ai.com](https://moka-ai.com) |
| Zhipu GLM | GLM-4 | `GLM_API_KEY` | ⭐⭐⭐⭐ | [open.bigmodel.cn](https://open.bigmodel.cn) |
| OpenAI | GPT-4o | `OPENAI_API_KEY` | ⭐⭐⭐⭐ | [platform.openai.com](https://platform.openai.com) |
| Ollama | ローカルモデル | `OLLAMA_BASE_URL` / `OLLAMA_ENABLED` / `OLLAMA_MODEL` | ⭐⭐⭐ | [ollama.com](https://ollama.com) |

> APIキーなしでも動作します（テンプレートモード）が、コンテンツ品質は限定的です。**少なくとも1つのAPIキーの設定を強く推奨します。**

### トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| ページに「テンプレートモード」と表示 | `.env`ファイルにAPIキーが入力されているか確認 |
| ポートが使用中 | `opc-agents -- --server.port 8502` |
| Pythonバージョンが違う | Python 3.10+が必要、`python3 --version`で確認 |
| 依存パッケージのインストール失敗 | `pip install --upgrade pip`を試してから再実行 |
| 暗号化機能が利用不可 | `pip install cryptography`で暗号化依存パッケージをインストール |

## プロジェクト構成

```
OPC-Agents/
├── frontend/              # Streamlitフロントエンド（モジュラー化）
│   ├── app.py             # メインUIルーター（579行、ルーティングのみ）
│   ├── components/        # 共有コンポーネント
│   │   └── shared.py      # 16個のUIヘルパー関数（384行）
│   ├── page_modules/      # ページモジュール
│   │   ├── dashboard_page.py   # ダッシュボードページ（578行+テンプレート）
│   │   ├── marketplace_page.py # スキルマーケットV2（547行）
│   │   └── settings_page.py    # 設定管理ページ（666行）
│   ├── routers/            # ルーターモジュール
│   └── renderers/          # レンダラーモジュール
├── opc_manager/           # コアビジネスロジック（88個の.pyモジュール）
│   ├── cli.py             # CLIエントリポイント
│   ├── agent_loop.py      # 実行ループ
│   ├── strategist_brain.py# 戦略脳
│   ├── executor_brain.py  # 実行脳
│   ├── reflector_brain.py # 反省脳
│   ├── consensus_engine.py# コンセンサスエンジン
│   ├── skill_registry.py  # スキルレジストリ（21ビルトインスキル+DI）
│   ├── tool_system.py     # ツールフレームワーク
│   ├── utils.py           # ユーティリティ
│   │
│   ├── # === v0.2.0 新コアモジュール ===
│   ├── settings.py        # 📋 SettingsManagerシングルトン（5タブ：LLM/SMTP/API Keys/Security/Profile）
│   ├── onboarding.py      # 🚶 OnboardingManager（3ステップ初回実行ウィザード）
│   ├── error_handler.py   # 🛡️ ErrorHandler（9種例外タイプ→フレンドリーメッセージ）
│   ├── data_backup.py     # 💾 DataBackupManager（ZIP/JSON/CSVエクスポート、SHA256、Zip Slip保護）
│   ├── i18n.py            # 🌐 I18nManager（zh_CN/en_US/ja_JP、58+翻訳キー）
│   ├── dashboard_config.py# 📊 DashboardConfig（3レイアウト×3密度×6パネル=9組合せ）
│   ├── shortcuts_handler.py# ⌨️ Apple Shortcuts統合（5つのCLIアクション）
│   │
│   ├── # === v0.2.5 新規：CarryMem + ナレッジベース + フライホイール ===
│   ├── memory_bridge.py   # 🧠 MemoryBridge（CarryMemアダプタ、永続記憶+ルールエンジン+フライホイール）
│   ├── knowledge_bridge.py# 📚 KnowledgeBridge（6種KBアダプタ：Obsidian/語雀/飛書/Notion/思源/ローカル）
│   ├── search_cache.py    # 🔍 検索キャッシュ（SQLiteキャッシュ+TTL+ヒット追跡）
│   ├── intent_classifier.py # 🎯 インテント分類器（軽量インテントルーティング）
│   ├── correction_manager.py # 🔧 修正マネージャー（自動修正戦略調整）
│   ├── embedding_service.py # 📐 埋め込みサービス（ベクトル埋め込み+類似度計算）
│   ├── llm_cache.py       # 🧊 LLMキャッシュ（SQLiteキャッシュ+SHA256キー+7日TTL+スレッドセーフ）
│   ├── skill_reviews.py   # ⭐ スキルレビュー（1-5星+テキストレビュー+集計平均）
│   │
│   ├── # === v0.2.0 モジュラー抽出 ===
│   ├── task_types.py              # task_engine_v3から抽出したタスクタイプ定義
│   ├── task_content_generators.py # task_engine_v3から抽出したコンテンツジェネレータ
│   ├── skill_models.py            # skill_registryから抽出したスキルモデル
│   ├── skill_builtin.py           # 21個のビルトインスキル定義（スタンドアロンモジュール）
│   ├── skill_executors.py         # SkillExecutorMixin（20個のexecuteメソッド）
│   ├── scenario_definitions.py    # 9個のシナリオ定義+dataclasses
│   │
│   ├── skill_marketplace.py # スキルマーケットV2（検索/インストール/詳細/フィルター/バージョンピンニング）
│   ├── skill_marketplace_api.py # スキルマーケットAPIサーバー
│   ├── mcp_protocol.py      # MCPプロトコルサポート
│   ├── mcp_transport.py     # MCP転送層
│   ├── plugin_system.py     # プラグインシステム
│   ├── skill_editor.py      # スキルエディタ
│   ├── performance_monitor.py# パフォーマンス監視
│   ├── task_engine_v3.py  # タスク実行エンジン
│   ├── llm_content.py     # LLM拡張コンテンツ生成
│   ├── llm_service.py     # LLMサービス層
│   ├── search_processor.py# 検索結果後処理
│   ├── async_executor.py  # 非同期タスク実行器
│   ├── session_context.py # マルチターン会話コンテキスト管理
│   ├── validators.py      # 入力検証層
│   ├── business_type_detector_v2.py  # ビジネスタイプ検出
│   ├── business_types.py             # ビジネスタイプ列挙定義
│   ├── scenario_engine_v2.py         # シナリオマッチングエンジン
│   ├── flywheel_tracker.py           # 成長フライホイールトラッカー
│   ├── persona_manager.py            # ペルソナ管理
│   ├── persona_variants.yaml         # 6種ビジネスタイプペルソナ設定
│   ├── monitoring.py                 # モニタリング＆ロギング
│   ├── config.py                     # 設定管理
│   ├── protocols.py                  # Protocolインターフェース+NullProvider降格
│   ├── secure_storage.py             # APIキー暗号化ストレージ（Fernet）
│   ├── undo_manager.py               # アンドゥマネージャー
│   ├── audit_log.py                  # 監査ログ
│   ├── confirmer.py                  # 確認メカニズム
│   ├── progress_emitter.py           # 進捗イベントエミッター
│   └── version.py         # バージョン管理（SSOT）
│   ├── experimental/      # 実験的モジュール（コアフロー外）
│   │   ├── wechat_agent.py    # 💬 WeChat E2Eエージェント
│   │   ├── wechat_gateway.py  # 💬 WeChatゲートウェイ
│   │   └── plugin_worker.py   # 🔌 プラグインワーカー
├── opc_manager/api/        # APIイベントモジュール
│   └── events.py          # イベント定義
├── opc_manager/export/     # エクスポートモジュール
│   ├── manager.py          # エクスポートマネージャー
│   ├── models.py           # エクスポートモデル
│   └── exporters/          # フォーマットエクスポーター
│       ├── excel_exporter.py
│       ├── pdf_exporter.py
│       ├── word_exporter.py
│       └── image_exporter.py
├── opc_hr/                # 検索＆ナレッジベース
│   └── web_search.py      # DuckDuckGo Web検索
├── plugins/               # コミュニティプラグイン
│   ├── plugin_config.json
│   ├── data_converter.py
│   └── text_summarizer.py
├── tests/                 # テストスイート（76テストファイル、2939テスト、100%合格）
├── docs/                  # プロジェクトドキュメント
│   ├── API.md             # APIドキュメント
│   └── guides/            # クイックスタートガイド（中/英/日）
├── requirements.txt       # コア依存パッケージ
├── requirements-dev.txt   # 開発依存パッケージ
├── .env.example           # 環境変数テンプレート
├── .env.local             # 自動生成暗号化キー（gitignore保護）
├── install.sh             # ワンクリックインストールスクリプト
├── start.sh               # ワンクリック起動スクリプト
└── VERSION                # バージョンファイル
```

## テスト

```bash
# 開発依存パッケージをインストール
pip install -r requirements-dev.txt

# 全テストを実行（2939テストケース）
PYTHONPATH=. pytest tests/ -v

# カバレッジレポート付きで実行
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing

# 特定モジュールテストを実行
PYTHONPATH=. pytest tests/test_settings.py tests/test_onboarding.py tests/test_i18n.py -v
```

> **テストカバレッジ範囲**：全88個のopc_managerモジュール + フロントエンド38モジュール + 新モジュール（settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler/wechat等）

## バージョン履歴

| バージョン | 日付 | マイルストーン |
|-----------|------|---------------|
| **0.2.5** | **2026-06-07** | **アーキテクチャ統合+セキュリティ強化** — アーキテクチャ統合リファクター+LLM同時実行制御+セキュリティ強化+2939テスト/76ファイル |
| **0.2.4** | **2026-05-25** | **記憶+ナレッジベース強化** — CarryMem深層統合+ナレッジ検索最適化+通知システム+拡張テスト |
| **0.2.3** | **2026-05-22** | **CarryMem統合** — クロスセッション永続記憶(MemoryBridge)+ルールエンジン+フライホイール機構+LLMキャッシュ+スキルスコアリング |
| **0.2.2** | **2026-05-21** | **CarryMem+ナレッジベース+フライホイール** — クロスセッション永続記憶+ルールエンジン+6種KBアダプタ+フライホイール機構+LLMキャッシュ+スキルレビュー+フロントエンドモジュラー化+E2Eテスト（1952テスト/56ファイル） |
| **0.2.2** | **2026-05-20** | **品質修正** — i18n 315+ハードコードクリーンアップ+バックアップAES暗号化+エクスポート秘匿化+MCPデフォルトlocalhost+オンボーディング統合+モバイル対応+キーボードショートカット修正+CIセキュリティスキャン |
| 0.2.1 | 2026-05-18 | 8個のOPCスキル統合+技術債務クリーンアップ（32 bare except+i18n 97キー） |
| **0.2.0** | **2026-05-17** | **FINAL** — 製品リリース：統一設定管理+初回ガイド+データバックアップ/リストア+エラー処理+WeChat E2E+モジュラーダッシュボード+i18n 3言語+スキルマーケットV2+グローバル検索+Apple Shortcuts+API Key暗号化(Fernet)+コードモジュラー化リファクター（87モジュール/56テストファイル/1860テスト） |
| 0.1.9-delta | 2026-05-09 | 実動作検証：三賢者LLM駆動+スキルマーケットFastAPI+MCP転送+プラグイン例+エディタUI+パフォーマンス監視 |
| 0.1.9-gamma | 2026-05-09 | リファクタリング：三賢者統合+スキルマーケットAPI+MCPプロトコル+プラグインシステム+スキルエディタ |
| 0.1.9 | 2026-05-09 | エンドツーエンドクローズドループ：自動修正+マルチスキルオーケストレーション+タスク一時停止/再開+進捗可視化+長セッションコンテキスト |
| 0.1.8 | 2026-05-08 | コアスキル開発：6スキルをモックからリアルにアップグレード+検索強化+LLM統合 |
| 0.1.7 | 2026-05-07 | 三賢者アーキテクチャ：戦略脳+実行脳+反省脳+コンセンサスエンジン+スキルレジストリ+ツールフレームワーク |
| 0.1.6 | 2026-05-03 | ユーザーオンボーディング+品質フィードバック+成果物検索+空状態例+3Dコードレビュー修正 |
| 0.1.5 | 2026-05-03 | マルチターンフォローアップ+品質ゲート+セキュリティテスト+Protocol降格+出力秘匿化+Ollamaサポート |
| 0.1.2 | 2026-04-28 | セキュリティ強化+パフォーマンス最適化：XSS修正、プロンプトインジェクション防御、シングルトンパターン、スレッドセーフ |
| 0.1.1-beta | 2026-04-27 | バグ修正：LLM初期化/検索依存/シナリオパス/コンテキスト汚染/プレースホルダー置換 |
| 0.1.0-beta | 2026-04-24 | Betaリリース：インストールフロー修正、セキュリティ強化、CI合格 |
| 0.1.0 | 2026-04-23 | 「信頼性と使いやすさ」：バージョン統一、Mock削除、MOKA API統合、非同期実行 |

## ライセンス

[MIT License](LICENSE)
