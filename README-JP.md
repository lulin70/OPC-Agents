# 🚀 OPC-Agents — 一人会社向けインテリジェントタスク実行システム

> **バージョン**: v0.1.9 | **ステータス**: Beta | **ライセンス**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
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
- ✅ **テストカバレッジ** — 470テストケース、100%合格率、CI自動検証
- ✅ **スキルマーケットAPI** — 外部スキル登録/発見/呼び出し、APIキー認証+権限レベル
- ✅ **MCPプロトコル互換** — Microsoft Model Context Protocol標準互換、ツール/リソース/プロンプト対応
- ✅ **プラグインシステム** — コミュニティプラグインのホットロード+サンドボックス隔離+ライフサイクル管理
- ✅ **カスタムスキルエディタ** — フォーム式スキル作成/テスト/プレビュー/公開
- ✅ **品質/クイックモード** — ユーザー選択可能な三賢者フルクローズドループまたはリフレクションスキップ高速実行

## クイックスタート

### 前提条件

- Python 3.9+
- 少なくとも1つのLLM APIキー（推奨: [MOKA](https://moka-ai.com)）

### 方法1：pipインストール

```bash
# 1. インストール
pip install opc-agents

# 2. ワークスペースを作成し、APIキーを設定
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# （オプション）平文.envの代わりに暗号化ストレージを使用
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

# 3. 起動
opc-agents
```

> pipインストール後、`.env`、成果物、ログはカレントディレクトリに保存されます。

### 方法2：ソースインストール（開発者向け推奨）

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x install.sh start.sh
./install.sh

# APIキーの設定
cp .env.example .env
# .envを編集し、MOKA APIキーを入力

# 起動
./start.sh
```

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
| Pythonバージョンが違う | Python 3.9+が必要、`python3 --version`で確認 |
| 依存パッケージのインストール失敗 | `pip install --upgrade pip`を試してから再実行 |

## プロジェクト構成

```
OPC-Agents/
├── frontend/              # Streamlitフロントエンド
│   └── app.py             # メインUI（非同期実行+進捗+成果物管理）
├── opc_manager/           # コアビジネスロジック
│   ├── cli.py             # CLIエントリポイント（pip install後opc-agentsコマンド）
│   ├── agent_loop.py      # 実行ループ（Plan→Act→Observe→Reflect 4フェーズクローズドループ）
│   ├── strategist_brain.py# 戦略脳（意図理解+タスク計画+複合意図分解）
│   ├── executor_brain.py  # 実行脳（スキル実行+ツール呼び出し+リソース管理）
│   ├── reflector_brain.py # 反省脳（結果評価+自動修正戦略提案）
│   ├── consensus_engine.py# コンセンサスエンジン（三賢者意見調整+紛争解決）
│   ├── skill_registry.py  # スキルレジストリ（6コアスキル+シナリオ移行+DI）
│   ├── tool_system.py     # ツールフレームワーク（権限制御+セキュリティ保護+監査ログ）
│   ├── utils.py           # ユーティリティ（BoundedDict+EventEmitter）
│   ├── scenario_migrator.py# シナリオ移行ツール（9シナリオ→スキルマッピング）
│   ├── task_engine_adapter.py# TaskEngineアダプタ（三賢者↔TaskEngineV3ブリッジ）
│   ├── skill_marketplace.py # スキルマーケットAPI（登録/発見/呼び出し+認証+権限）
│   ├── mcp_protocol.py      # MCPプロトコルサポート（Model Context Protocol互換）
│   ├── mcp_transport.py     # MCP転送層（SSE + stdio）
│   ├── plugin_system.py     # プラグインシステム（サンドボックス隔離+ライフサイクル管理）
│   ├── skill_editor.py      # スキルエディタ（カスタムスキル作成/テスト/公開）
│   ├── performance_monitor.py# パフォーマンス監視（SLA管理+LLMキャッシュ+メトリクス）
│   ├── task_engine_v3.py  # タスク実行エンジン
│   ├── llm_content.py     # LLM拡張コンテンツ生成（RAGハイブリッドモード）
│   ├── llm_service.py     # LLMサービス層（MOKA/GLM/OpenAI/Ollama）
│   ├── search_processor.py# 検索結果後処理（TF-IDF+KBフォールバック）
│   ├── async_executor.py  # 非同期タスク実行器
│   ├── session_context.py # マルチターン会話コンテキスト管理
│   ├── validators.py      # 入力検証層（Pydanticモデル）
│   ├── business_type_detector_v2.py  # ビジネスタイプ検出
│   ├── business_types.py             # ビジネスタイプ列挙定義
│   ├── scenario_engine_v2.py         # シナリオマッチングエンジン
│   ├── flywheel_tracker.py           # 成長フライホイールトラッカー
│   ├── persona_manager.py            # ペルソナ管理
│   ├── persona_variants.yaml         # 6種ビジネスタイプペルソナ設定
│   ├── monitoring.py                 # モニタリング＆ロギング
│   ├── config.py                     # 設定管理
│   ├── protocols.py                  # Protocolインターフェース+NullProvider降格
│   ├── secure_storage.py             # APIキー暗号化ストレージ
│   └── version.py         # バージョン管理（SSOT）
├── opc_hr/                # 検索＆ナレッジベース
│   └── web_search.py      # DuckDuckGo Web検索
├── tests/                 # テストスイート（470テスト、100%合格）
├── docs/                  # プロジェクトドキュメント
├── requirements.txt       # コア依存パッケージ
├── requirements-dev.txt   # 開発依存パッケージ（black/flake8/pytest）
├── .env.example           # 環境変数テンプレート
├── install.sh             # ワンクリックインストールスクリプト
├── start.sh               # ワンクリック起動スクリプト
└── VERSION                # バージョンファイル
```

## テスト

```bash
# 開発依存パッケージをインストール
pip install -r requirements-dev.txt

# 全テストを実行
PYTHONPATH=. pytest tests/ -v

# カバレッジレポート付きで実行
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing
```

## バージョン履歴

| バージョン | 日付 | マイルストーン |
|-----------|------|---------------|
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
