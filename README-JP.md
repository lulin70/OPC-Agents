# 🚀 OPC-Agents — 一人会社向けインテリジェントタスク実行システム

> **バージョン**: v0.1.5 | **状態**: Beta | **ライセンス**: MIT

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

- ✅ **LLM拡張コンテンツ生成** — Claude Sonnet 4搭載、高品質出力
- ✅ **リアルWeb検索** — DuckDuckGoライブ検索、データの捏造なし
- ✅ **ゼロプレースホルダー保証** — 全ての出力に具体的で実行可能な内容
- ✅ **非同期実行** — 投稿して即座に返却、バックグラウンド処理+進捗表示
- ✅ **自動リトライ** — 失敗タスクの指数バックオフ自動リトライ（最大2回）、タスク完了率向上
- ✅ **品質ゲート** — 納品物の自動チェック（プレースホルダー0+最低文字数+データソース）、不適格時は自動標記
- ✅ **出力秘匿化** — 生成内容のAPIキー/GitHubトークンを自動検出・置換、漏洩防止
- ✅ **ナレッジベースフォールバック** — 6カテゴリ20件の専門知識、検索失敗時の自動フォールバック
- ✅ **ファイル納品** — `.md`ファイルを自動生成、ダウンロードボタン付き
- ✅ **マルチターン会話** — 「XXを追加」「XXを修正」とフォローアップすると、前回の結果に基づいて継続し、最初からやり直しません
- ✅ **セキュリティ保護** — 入力検証+プロンプトインジェクション防御+URL安全性+エラー秘匿化+APIキー暗号化ストレージ
- ✅ **テストカバレッジ** — 350+テストケース、100%合格率、CI自動検証

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
│   └── version.py         # バージョン管理（SSOT）
├── opc_hr/                # 検索＆ナレッジベース
│   └── web_search.py      # DuckDuckGo Web検索
├── tests/                 # テストスイート（277+テスト、100%合格）
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
| 0.1.2 | 2026-04-28 | セキュリティ強化+パフォーマンス最適化：XSS修正、プロンプトインジェクション防御、シングルトンパターン、スレッドセーフ |
| 0.1.1-beta | 2026-04-27 | バグ修正：LLM初期化/検索依存/シナリオパス/コンテキスト汚染/プレースホルダー置換 |
| 0.1.0-beta | 2026-04-24 | Betaリリース：インストールフロー修正、セキュリティ強化、CI合格 |
| 0.1.0 | 2026-04-23 | 「信頼性と使いやすさ」：バージョン統一、Mock削除、MOKA API統合、非同期実行 |

## ライセンス

[MIT License](LICENSE)
