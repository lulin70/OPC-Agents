# 🚀 OPC-Agents — 一人会社向けインテリジェントタスク実行システム

> **バージョン**: v0.3.27 | **ステータス**: Beta | **ライセンス**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/opc-agents)](https://pypi.org/project/opc-agents/)

---

**言語**: [中文](README.md) | [English](README-EN.md) | **日本語**

---

## 30秒で理解するOPC-Agents

**🎯 一言で**: 一人会社のAI実行チーム — あなたが要件を言えば、成果物を出します。

**⚡ コアフロー**:
```
あなたが要件を入力 → AIが分析+検索+生成 → 成果物（レポート/プラン/文案/メール...）を取得
```

**🚀 3ステップで開始**:
```bash
pip install opc-agents          # 1. インストール
opc-agents                      # 2. 起動
# 3. 「週報を作成して」と入力 → 成果物を取得
```

---

## 🆕 v0.3.27 ハイライト

> 完全な変更履歴は [CHANGELOG.md](CHANGELOG.md)、アーキテクチャ設計は [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md)、成熟度評価は [docs/ASSESSMENT_D02_MATURITY.md](docs/ASSESSMENT_D02_MATURITY.md) を参照。

- **⚡ 三賢者並列投票アーキテクチャ**: 直列パイプライン（3×RTT）から並列投票（1×RTT）に変更、レイテンシ3分の1に低下。EVA MAGI三賢者同期投票+マイノリティレポート機構を参考に、重要意思決定点を事前コンセンサスで保護。
- **🎯 3つのコアスキルに集中**: メール / 財務 / レポート。非コアスキルを凍結（[docs/spec/SKILL_FREEZE_LIST.md](docs/spec/SKILL_FREEZE_LIST.md) 参照）、各コアスキルを本当に使いやすくする。
- **🧠 IntentRouter 3分類スマートルーティング**: SIMPLE / COMPLEX / GREETINGの3分類。簡単なタスクは三賢者をバイパスして直接実行—速くてお得；複雑なタスクのみ並列投票に入り、品質を保証。
- **🛡 重要意思決定点の事前コンセンサス保護**: ConsensusEngineを「事後補救」から「事前関門」に変更、ExecutorBrainは真の意見を提供（偽意見ルール削除）、ReflectorBrainは事前予測+マイノリティレポート。
- **📊 継続的な品質向上**: 4278テスト、カバレッジ74%+、全CIゲート通過（ruff/mypy/Black/E2E/coverage/radon D+/Bandit/pip-audit/Docker build/バージョン一致性/三言語README一致性）。D02成熟度評価82点 B+。
- **🔧 tool_system.py分割**: 754行のGod Classを4つのサブモジュール（tool_registry + tool_handlers_fs/smtp/cmd）+ Facadeパターンに分割、後方互換、複雑度D→Cに低下。
- **🧹 Mockアンチパターン修正**: 56件のアンチパターンMockを修正（未使用依存→None、内部コンポーネント→SimpleNamespace）、テストがより誠実で失敗がより明確に。
- **🔒 セキュリティスキャンクリーン**: pip-audit 0脆弱性 + Bandit 0高危険度、6パッケージアップグレードで21の既知脆弱性を修正（pillow/pyjwt/python-multipart/soupsieve/weasyprint/pip）。
- **✅ v0.4.0リリースゲート 14/14 全て達成**: E2E実テスト 0失敗、ローカル起動 HTTP 200、weekly-e2e-real.yml手動トリガー成功。v0.4.0リリース準備完了。
- **🌐 i18nリファクター**: 3857行 → 133行ロジック層 + JSON化、後方互換、メンテナンスコスト激減。

> 🧪 試してみたい？[docs/guides/USER_TRIAL_GUIDE.md](docs/guides/USER_TRIAL_GUIDE.md) をお読みください（3分で設定完了）、デモスクリプトは [docs/guides/DEMO_SCRIPTS.md](docs/guides/DEMO_SCRIPTS.md)、フィードバックフォームは [docs/guides/FEEDBACK_FORM.md](docs/guides/FEEDBACK_FORM.md)。

---

## これは何か

OPC-Agents（One-Person Company Agents）は、**一人会社/独立起業家/フリーランス向けのインテリジェントタスク実行システム**です。

**コアコンセプト：求める結果をシステムに伝えれば、作業を完了してファイルを納品します。**

チャットボットでも、アドバイスエンジンでもありません。**仕事をこなす実行者**です。

## 何ができるか

| あなたの指示 | 納品物 |
|-------------|--------|
| 「OPC会社のトレンドを収集して」 | 🔍 調査レポート（実際の検索+ソースリンク+構造化整理） |
| 「Q2マーケティングプランを作成して」 | ✍ 完全なプラン（SMART目標+ロードマップ+リスク+受入基準） |
| 「競合Aを分析して」 | 📊 分析レポート（SWOT+アクションリスト+優先順位付け） |
| 「顧客にメールを送信して」 | 📧 メール送信（テンプレート描画+SMTP送信+頻度制限） |
| 「収入を記録して」 | 💰 財務記録（自動分類+月次レポート+トレンド分析） |
| 「顧客情報を追加して」 | 👥 顧客プロファイル（暗号化保存+沈黙警告+協力追跡） |

---

## コア能力

**三賢者並列投票アーキテクチャ** — 3つのAI役割が同期投票でクローズドループ協調、重要意思決定点を事前コンセンサスで保護（v0.3.0アップグレード、[docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md) 参照）：
- 🧠 **戦略脳（StrategistBrain）**: あなたの意図を理解、実行ステップを計画
- ⚡ **実行脳（ExecutorBrain）**: スキルとツールを呼び出し、成果物を生成（v0.3.0から「真の意見」を提供、偽意見ルールなし）
- 🔍 **反省脳（ReflectorBrain）**: 結果品質を評価、事前予測+マイノリティレポート、不適格時は自動修正
- 🛡 **コンセンサスエンジン（ConsensusEngine）**: 三賢者並列投票（1×RTT、直列3×RTTより3倍高速）、重要意思決定点の事前保護

**IntentRouter 3分類スマートルーティング** — タスク複雑度で振り分け、時間とコストを節約：
- 🟢 **SIMPLE**: 簡単なタスクは直接実行、三賢者をバイパス
- 🟡 **COMPLEX**: 複雑なタスクは並列投票に入り、品質を保証
- 👋 **GREETING**: 挨拶/雑談は直接応答

**3つのコアスキル** — v0.3.0集中打磨、一人会社の最頻シナリオをカバー（他のスキルは凍結、[docs/spec/SKILL_FREEZE_LIST.md](docs/spec/SKILL_FREEZE_LIST.md) 参照）：
- 📧 **メール（email）**: SMTP送信+テンプレート描画+頻度制限
- 💰 **財務（finance）**: 収支記録+月次レポート+トレンド分析
- 📊 **レポート（report）**: 週報/月報/年報の自動生成

**リアル検索** — DuckDuckGoライブ検索統合、データ捏造なし、全ての結論にソースあり。

---

## アクセラレーター

これらの機能はコアフローを**より良く、より速く、使うほど強力に**します：

| アクセラレーター | どのように成果を早く出すか |
|----------------|------------------------|
| 🧠 **クロスセッション記憶** | 好みとコンテキストを記憶、毎回の繰り返し説明不要（[CarryMem](https://github.com/lulin70/carrymem)が必要、`pip install opc-agents[memory]`） |
| 🔄 **フライホイール成長** | 使うほどレベルアップ（🌱初心者→👑伝説）、出力品質が自動向上 |
| 🏪 **スキルマーケット** | サードパーティスキルの検索・インストール、オンデマンドで能力拡張 |
| 📚 **外部ナレッジベース** | Obsidian/語雀/飛書/Notion/思源ノートに接続、AIがプライベート資料を参照 |
| 📜 **ルールエンジン** | 失敗経験を自動的にルール化、同じエラーを二度と繰り返さない |
| ↩ **アンドゥ機能** | 操作は取り消し可能、安心して大胆に使用 |
| 🌐 **3言語切替** | 中国語/英語/日本語UIワンクリック切替 |
| 🧊 **LLMキャッシュ** | 同じ質問は重複API呼び出しなし、時間とコストを節約 |

## エコシステムツール

特定のシナリオに遭遇？組み合わせて使うとさらに効果的：

| シナリオ | 推奨ツール | 説明 |
|---------|-----------|------|
| AIに好みを記憶させたい | [CarryMem](https://github.com/lulin70/carrymem) | クロスセッション永続記憶エンジン、`pip install opc-agents[memory]`で有効化 |
| 開発タスクで多役割協力が必要 | [DevSquad](https://github.com/lulin70/DevSquad) | 7役割AIチーム（アーキテクト/PM/セキュリティ/テスター/開発/DevOps/UI）、複雑な開発タスクの分解と協力 |

## アーキテクチャ概要

> v0.3.0で三賢者並列投票アーキテクチャにアップグレード、完全な設計は [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md)、レイテンシ比較は [docs/internal/PARALLEL_LATENCY_REPORT.md](docs/internal/PARALLEL_LATENCY_REPORT.md) を参照。

```
┌─────────────────────────────────────────────────────┐
│                    OPC-Agents v0.3.0                 │
├─────────────────────────────────────────────────────┤
│  ユーザー入力                                          │
│       ↓                                              │
│  IntentRouter 3分類スマートルーティング            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ SIMPLE   │  │ COMPLEX  │  │ GREETING │          │
│  │ 直接実行  │  │ 投票へ   │  │ 直接応答 │          │
│  └────┬─────┘  └────┬─────┘  └──────────┘          │
│       ↓              ↓                              │
│  ┌─────────────────────────────────────────┐        │
│  │ 三賢者並列投票（1×RTT、レイテンシ3分の1） │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │        │
│  │  │ 戦略脳    │ │ 実行脳    │ │ 反省脳    │ │        │
│  │  │ (真の意見)│ │ (真の意見)│ │ (事前予測)│ │        │
│  │  └─────┬────┘ └─────┬────┘ └─────┬────┘ │        │
│  │        └──────┬─────┴──────┬──────┘     │        │
│  │               ↓            ↓            │        │
│  │     ConsensusEngine（重要意思決定点事前保護）│        │
│  │     · 並列投票 · マイノリティレポート · 衝突解決│        │
│  └────────────────────┬────────────────────┘        │
│                       ↓                             │
├─────────────────────────────────────────────────────┤
│  3つのコアスキル（v0.3.0集中）                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │ 📧 email     │ │ 💰 finance   │ │ 📊 report    ││
│  │ SMTP+テンプレ│ │ 収支+月報    │ │ 週/月/年報    ││
│  └──────────────┘ └──────────────┘ └──────────────┘│
│  （他11個の非コアスキルは凍結、SKILL_FREEZE_LIST参照）│
├─────────────────────────────────────────────────────┤
│  外部拡張                                             │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 🔌 スキル    │  │ 🔗 MCP       │                │
│  │   マーケット │  │   サービス   │                │
│  └──────────────┘  └──────────────┘                │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 👤 ユーザー  │  │ 🔒 データ    │                │
│  │   プロファイル│  │   セキュリティ│                │
│  └──────────────┘  └──────────────┘                │
├─────────────────────────────────────────────────────┤
│  SQLite統一ストレージ（AES暗号化 + ファイル権限0600）  │
└─────────────────────────────────────────────────────┘
```

## クイックスタート

> 🆕 **v0.3.0トライアルユーザー**：非技術背景のユーザーは [docs/guides/USER_TRIAL_GUIDE.md](docs/guides/USER_TRIAL_GUIDE.md) を直接お読みください（図解版、3分で設定完了、APIキー取得リンクとAPIキー不要体験モード含む）。本節は開発者向けのクイックリファレンスです。

### 前提条件

- Python 3.10+
- 少なくとも1つのLLM APIキー（推奨: [MOKA](https://moka-ai.com)）

### 方法1：pipインストール

```bash
# 1. インストール
pip install opc-agents==0.3.27

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
chmod +x scripts/install.sh scripts/start.sh
./scripts/install.sh

# 暗号化依存パッケージをインストール
pip install cryptography

# APIキーの設定
cp .env.example .env
# .envを編集し、MOKA APIキーを入力

# 起動
./scripts/start.sh
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

> ⚠ **セキュリティ注意**：`OPC_ENCRYPTION_KEY`は必須です。未設定時、`encrypt_field()`が`RuntimeError`をスローし、メールパスワードや顧客機密フィールド等の暗号化操作が失敗します。`.env`に強力なランダムキーを必ず設定してください。

### APIキーについて

> ⚠ **OPC-AgentsはLLMサービスを提供しません。** ご自身のLLMプロバイダーを選択し、APIキーを各自で取得してください。プロジェクトはAPIキーや機密情報を一切保存しません。

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
│   │   ├── shared.py      # 16個のUIヘルパー関数（384行）
│   │   ├── session_utils.py      # セッションユーティリティ関数
│   │   ├── export_helpers.py     # エクスポートヘルパー関数
│   │   ├── progress_indicator.py # 進捗インジケーターコンポーネント
│   │   ├── toast_notifications.py # Toast通知コンポーネント
│   │   ├── theme_manager.py      # テーママネージャー
│   │   ├── timeline_data.py      # タイムラインデータ処理
│   │   ├── timeline_export.py    # タイムラインエクスポート
│   │   ├── timeline_filters.py   # タイムラインフィルター
│   │   ├── undo_display.py       # アンドゥ操作表示
│   │   ├── undo_export.py        # アンドゥ操作エクスポート
│   │   └── undo_actions.py       # アンドゥ操作アクション
│   ├── page_modules/      # ページモジュール
│   │   ├── dashboard_page.py   # ダッシュボードページ（578行+テンプレート）
│   │   ├── marketplace_page.py # スキルマーケットV2（547行）
│   │   └── settings_page.py    # 設定管理ページ（666行）
│   ├── routers/            # ルーターモジュール
│   └── renderers/          # レンダラーモジュール
├── opc_manager/           # コアビジネスロジック（99個の.pyモジュール）
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
│   ├── error_handler.py   # 🛡 ErrorHandler（9種例外タイプ→フレンドリーメッセージ）
│   ├── data_backup.py     # 💾 DataBackupManager（ZIP/JSON/CSVエクスポート、SHA256、Zip Slip保護）
│   ├── i18n.py            # 🌐 I18nManager（zh_CN/en_US/ja_JP、1242翻訳キー）
│   ├── dashboard_config.py# 📊 DashboardConfig（3レイアウト×3密度×6パネル=9組合せ）
│   ├── shortcuts_handler.py# ⌨ Apple Shortcuts統合（5つのCLIアクション）
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
├── opc_manager/export/     # エクスポートモジュール
│   ├── manager.py          # エクスポートマネージャー
│   ├── models.py           # エクスポートモデル
│   └── exporters/          # フォーマットエクスポーター
│       ├── excel_exporter.py
│       ├── pdf_exporter.py
│       ├── word_exporter.py
│       └── image_exporter.py
├── tests/                 # テストスイート（100テストファイル、4278テスト、100%合格）
├── docs/                  # プロジェクトドキュメント
│   ├── API.md             # APIドキュメント
│   └── guides/            # クイックスタートガイド（中/英/日）
├── scripts/               # デプロイ＆運用スクリプト
│   ├── install.sh         # ワンクリックインストールスクリプト
│   └── start.sh           # ワンクリック起動スクリプト
├── requirements.txt       # コア依存パッケージ
├── requirements-dev.txt   # 開発依存パッケージ
├── .env.example           # 環境変数テンプレート
├── .env.local             # 自動生成暗号化キー（gitignore保護）
└── VERSION                # バージョンファイル
```

## テスト

```bash
# 開発依存パッケージをインストール
pip install -r requirements-dev.txt

# 全テストを実行（4278テストケース）
PYTHONPATH=. pytest tests/ -v

# カバレッジレポート付きで実行
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing

# 特定モジュールテストを実行
PYTHONPATH=. pytest tests/integration/test_settings.py tests/integration/test_onboarding.py tests/unit/test_i18n.py -v
```

> **テストカバレッジ範囲**：全99個のopc_managerモジュール + フロントエンド38モジュール + 新モジュール（settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler/wechat等）

## バージョン履歴

| バージョン | 日付 | マイルストーン |
|-----------|------|---------------|
| **0.3.14** | **2026-07-12** | **mypyオーバーライド削除 Batch 3(P3-3完了)** — 11モジュールをper-module overridesから削除（11→0）、84関数のアノテーション補完、mypy `disallow_untyped_defs = true`が全83モジュールをカバー、per-module overrides完全クリア |
| **0.3.22** | **2026-07-12** | **P3-5 Mockアンチパターン修正** — 2テストファイルのMagicMockを本物fakeクラスに置換（test_brain_modules 40箇所→6個fakeクラス: FakeLLMService/FakeSkill/FakeAsyncSkill/FakeSkillRegistry/FakeTaskResult/FakeTaskEngine / test_live_log_panel 4箇所→2個fakeクラス: FakeAuditLog/FakeProgressEmitter）、合理的@patchとpsutil Mock保持 |
| **0.3.18** | **2026-07-12** | **P3-4 Mockアンチパターン修正 Batch 4（P3-4完了）** — test_timeline_view 8テストメソッド~17箇所MagicMockを本物コンポーネントとfakeクラスに置換（UndoManager/UndoRecord→本物UndoManager+push()で本物レコード作成 / AuditLog→FakeAuditLog / ProgressEmitter→FakeProgressEmitter / SimpleNamespaceでMagicMock record置換）、~18箇所streamlit Mock保持 |
| **0.3.17** | **2026-07-12** | **P3-4 Mockアンチパターン修正 Batch 3** — 2テストファイルのMagicMockを本物fakeクラスと本物コンポーネントに置換（test_undo_panel 17箇所@patch+22箇所MagicMock→本物UndoManagerインスタンス+tmp_path / test_skill_executors 30+箇所MagicMock→8個の本物fakeクラス: FakeLLMService/FakeContentGenerator/FakeSearchProcessor/FakeToolSystem/FakeWebSearch等） |
| **0.3.16** | **2026-07-12** | **P3-4 Mockアンチパターン修正 Batch 2** — 2テストファイルのMagicMockを本物fakeクラスに置換（test_delta_integration 5箇所 MagicMock LLM→MockLLMService/RaisingLLMService / test_integration_modules 12箇所 MagicMock SkillRegistry/Skill→FakeSkillRegistry/FakeSkill + 本物SkillRegistryインスタンス） |
| **0.3.15** | **2026-07-12** | **P3-4 Mockアンチパターン修正 Batch 1** — 3テストファイルのMockアンチパターン修正（test_email_skill_coverage Mockファイルシステム→tmp_path+monkeypatch / test_simple_llm_service Mock os.environ.get→monkeypatch.setenv/delenv / test_executor_opinion MagicMock→RaisingLLMService本物fakeクラス） |
| **0.3.13** | **2026-07-11** | **mypyオーバーライド削除 Batch 2(P3-3)** — 26モジュールをper-module overridesから削除（37→11）、88関数のアノテーション補完、mypy `disallow_untyped_defs = true`カバレッジ拡大。残り11モジュール（Batch 3、6+ untyped）は今後対応 |
| **0.3.12** | **2026-07-11** | **mypyオーバーライド削除 Batch 1(P3-3)** — 46モジュールをper-module overridesから削除（83→37）、戻り値型+パラメータ型アノテーション補完（`__init__`/`__post_init__`/`execute_goal`/`undo_*`/`**kwargs: Any`等）、mypy `disallow_untyped_defs = true`グローバル適用 |
| **0.3.11** | **2026-07-11** | **radon cc D+ ブロッキングゲート(P3-2)** — 6つのD/E級関数を全てダウングレード（`_parse_analysis_result` E(36)→A(2) / `finance_skill.execute_goal` D(30)→A(4) / `_extract_keywords` D(29)→A(2) / `_calculate_quality_score` D(28)→B(6) / `_parallel_data_analysis` D(22)→A(4) / `_execute_collaborative` D(21)→A(4)）、CI radon ccを非ブロッキングからD+ブロッキングに変更、Dockerfile/start.shバージョン修正（0.3.5→0.3.11） |
| **0.3.10** | **2026-07-11** | **crm_skill テスト+カバレッジ向上(P3-1)** — 64個のcrm_skillテスト追加（カバレッジ14.8%→70%+）、3件のソースバグ修正（_handle_deal金額文字列クリーンアップ / _handle_search「查」「找」キーワード欠落 / undo非決定的並び替え）、CIカバレッジ閾値64%→65%（実際66%）、テスト数3717→3781 |
| **0.3.9** | **2026-07-11** | **高複雑度関数リファクタリング(P2)** — TaskEngineV3.execute E(31)→B + extract_json_from_llm D(27)→A(4) + crm_skill.execute_goal D(26)→C(13) + email_skill.execute_goal D(23)→C(11)、4つのヘルパーメソッド抽出で重複並列コードを削除 |
| **0.3.8** | **2026-07-11** | **DevSquadコンセンサス第1弾** — cli.pyカバレッジ0%→95%(+17テスト) + mcp_transport.py 23%→92%(+31テスト) + CIカバレッジ閾値62%→64%(実際64.84%) + radon cc循環的複雑度ゲート(非ブロッキング) + sse-starlette依存関係 |
| **0.3.7** | **2026-07-11** | **カバレッジ最適化バッチ** — 6モジュールのカバレッジ向上(export/task_skill/user_profile/task_lifecycle/social_skill/task_content_generators) +234テスト + 3バグ修正(execute_goal文字列置換順序/SQLパラメータ化/空データフォールバック) |
| **0.3.6** | **2026-07-10** | **技術債務クリーンアップ P2-P3** — install.bat削除(pip installクロスプラットフォーム) + task_skill SQLパラメータ化(IN/NOT INプレースホルダー) + web_search.pyをopc_hr/からopc_manager/へ移行(偽装階層解消) + 2つの失敗テスト修正 + CIカバレッジ閾値59%→65% |
| **0.3.5** | **2026-07-09** | **成熟度修正+God Class分割** — DevSquad 7次元評価18項P0+P1+P2修正（ruff 43→0 / 三言README / 幽霊関数クリーンアップ / pre-commit hooks）+ tests/階層化unit/integration/e2e（87ファイル移行）+ StrategistBrain/ReflectorBrain Facade分割（884→176 / 841→222行）+ 仮想階層アーキテクチャ保護（96テスト）+ Dockerfileバージョン同期 |
| **0.3.4** | **2026-07-07** | **凍結スキル完全削除+リリースパイプライン修正** — tax_reminder/calendar/proposal 3凍結スキル削除 + 90件i18n孤立キークリーンアップ + release.yml E2E分離修正 + 初回release.ymlパイプライントリガー |
| **0.3.3** | **2026-06-28** | **技術債務クリーンアップ** — TD-065 mypy 516→0エラー（CIブロッキング）+ TD-066 settings_encryption fail-open→fail-closed + flake8 E501ゼロ化 + 3174 passed |
| **0.3.2** | **2026-06-27** | **プロジェクト整理評価修正** — DevSquad 7次元評価 72→79 (B+) + 17箇所バージョン同期 + check_prompt_injectionゴースト関数統合 + mypy CI統合 + 3167 passed |
| **0.3.1** | **2026-06-26** | **ゴースト機能削除** — api/events + experimental/wechat + plugin_system + plugins/削除（~2196行デッドコード）+ flake8 F401/F841 348項目ゼロ化 + 3165 passed |
| **0.3.0** | **2026-06-19** | **三賢者並列投票アーキテクチャ回帰** — 並列投票(1×RTT、レイテンシ3分の1)+ConsensusEngine事前+ExecutorBrain真の意見+ReflectorBrain事前予測+IntentRouter 3分類ルーティング+3コアスキル集中(メール/財務/レポート)+9非コアスキル凍結+i18nリファクター(3857→133行)+カバレッジ62.87%+実LLM E2Eテスト |
| **0.2.5** | **2026-06-07** | **アーキテクチャ統合+セキュリティ強化** — アーキテクチャ統合リファクター+LLM同時実行制御+セキュリティ強化+3305テスト/76ファイル |
| **0.2.4** | **2026-05-24** | **記憶+ナレッジベース強化** — CarryMem深層統合+ナレッジ検索最適化+通知システム+拡張テスト |
| **0.2.3** | **2026-05-24** | **CarryMem統合** — クロスセッション永続記憶(MemoryBridge)+ルールエンジン+フライホイール機構+LLMキャッシュ+スキルスコアリング |
| **0.2.2** | **2026-05-21** | **CarryMem+ナレッジベース+フライホイール** — クロスセッション永続記憶+ルールエンジン+6種KBアダプタ+フライホイール機構+LLMキャッシュ+スキルレビュー+フロントエンドモジュラー化+E2Eテスト（1952テスト/56ファイル） |
| **0.2.2** | **2026-05-20** | **品質修正** — i18n 315+ハードコードクリーンアップ+バックアップAES暗号化+エクスポート秘匿化+MCPデフォルトlocalhost+オンボーディング統合+モバイル対応+キーボードショートカット修正+CIセキュリティスキャン |
| 0.2.1 | 2026-05-18 | 8個のOPCスキル統合+技術債務クリーンアップ（32 bare except+i18n 97キー） |
| **0.2.0** | **2026-05-17** | **FINAL** — 製品リリース：統一設定管理+初回ガイド+データバックアップ/リストア+エラー処理+WeChat E2E+モジュラーダッシュボード+i18n 3言語+スキルマーケットV2+グローバル検索+Apple Shortcuts+API Key暗号化(Fernet)+コードモジュラー化リファクター（87モジュール/56テストファイル/1860テスト） |
| 0.1.8 | 2026-05-14 | 21ビルトインスキル+外部スキルマーケット+MCPサービス発見+ユーザープロファイル+データセキュリティ+SQLite統一ストレージ |
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
