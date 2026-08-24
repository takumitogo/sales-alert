# 営業機会アラートツール（FREE版 MVP）

失注企業・過去取引企業・長期未接触企業などを登録しておき、Web公開情報の新着を
ルールベースで検知してメールアラートする社内ツールです。実装は
「技術設計書（FREE版MVP・アーキテクチャ編）」の設計に基づいています。

## 実装済み機能（MVP完成条件チェック）

1. ユーザー登録・ログイン（`/accounts/register/`, `/accounts/login/`）
2. CSV一括登録（列名の揺れを吸収するマッピング確認画面つき、`/companies/csv/upload/`）
3. 企業ごとの監視ON/OFF
4. 定期的なWeb公開情報取得（`python manage.py run_weekly_scan`）
5. 過去取得済みURLとの重複判定（`(company, url)` のUNIQUE制約）
6. キーワードベースのスコア算出（情報源加点・鮮度加点込み、組織ごとに編集可能）
7. 80点以上での登録メールへの通知（Gmail SMTP）
8. ダッシュボードでの検知情報確認
9. 企業ごとの検知履歴（タイムライン表示）
10. 👍／👎フィードバックの保存
11. AI APIは一切利用していません

## ディレクトリ構成

```
config/       Django設定・ルートURL
accounts/     組織・ユーザー・通知設定、登録/ログイン
companies/    監視対象企業、CSV一括登録
intel/        キーワード・検索クエリ・情報源加点、クローラー、スコアリング、
              検索プロバイダ、メール送信、パイプライン、定期実行コマンド
dashboard/    ダッシュボード画面
templates/    画面テンプレート（共通base.html＋各アプリ配下）
```

## ローカルでの動かし方

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 必要に応じて値を編集（未編集でもSQLite+コンソール出力メールで動作します）
python manage.py migrate
python manage.py createsuperuser   # 管理画面(/admin/)を使う場合のみ
python manage.py runserver
```

`http://localhost:8000/accounts/register/` からユーザー登録すると、組織・通知設定・
デフォルトのキーワード/情報源加点/検索クエリテンプレートが自動作成されます。

## 定期実行（Web情報取得・スコアリング・通知）

```bash
python manage.py run_weekly_scan            # 監視ONで巡回時期が来た企業をまとめて処理
python manage.py run_weekly_scan --limit 10 # 一度に処理する企業数を絞る（負荷分散・動作確認用）
python manage.py run_weekly_scan --company-id <UUID>  # 特定の1社だけ処理（動作確認用）
```

本番ではこれをRenderの Cron Job（`render.yaml` に定義済み。毎週月曜3:00 JST）から
週次で呼び出します。技術設計書4章のとおり、1社ごとに `last_scanned_at` を更新する
冪等な設計のため、途中で失敗しても安全に再実行できます。

## メール送信（Gmail SMTP）の設定

1. 通知に使うGoogleアカウントで2段階認証を有効にする。
2. Googleアカウントの「アプリパスワード」を発行する（16桁）。
3. `.env`（または本番のホスティング環境変数）に以下を設定する。

```
EMAIL_USE_CONSOLE=false
EMAIL_HOST_USER=your-alert-address@gmail.com
EMAIL_HOST_PASSWORD=発行したアプリパスワード
DEFAULT_FROM_EMAIL=your-alert-address@gmail.com
```

`EMAIL_HOST_USER` を設定しない場合は自動的にコンソール出力バックエンドになり、
送信内容がターミナルに表示されるだけになります（ローカル動作確認用）。

Gmail無料アカウントは1日500通までの送信上限があります（技術設計書5章）。
将来的に通知量が増える場合は、`EMAIL_BACKEND` 関連の環境変数を変更するだけで
SendGrid／AWS SES等へ切り替えられます（コード変更不要）。

## 本番デプロイ（Render + Neon の想定）

1. **Neon**（https://neon.tech ）で無料のPostgresプロジェクトを作成し、接続文字列を控える。
2. **Render**（https://render.com ）で本リポジトリを接続し、`render.yaml` を検出させる
   （Web Service と Cron Job の2サービスが定義されています）。
3. Render の環境変数に `DATABASE_URL`（Neonの接続文字列）、`EMAIL_HOST_USER` /
   `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL`、`SITE_BASE_URL`（例:
   `https://xxxx.onrender.com`）を設定する。
4. デプロイ後、Render Shellから `python manage.py createsuperuser` を実行して
   管理者アカウント（Django Admin用）を作成する。

料金の目安は技術設計書6章（$0/月〜、小規模本番で$7〜10/月程度）を参照してください。

## クロール・検索の設計について

- まず登録企業の公式サイトを直接クロールし（`intel/crawler.py`）、次にGoogle News RSS
  （`intel/search_providers.py`）で補完します。検索APIは初期は使いません
  （Bing Search APIの2025年retire、Google Programmable Search Engineの2026年無料枠縮小を
  踏まえた設計判断。技術設計書3.2節参照）。
- robots.txtの尊重、同一ドメインへの最小アクセス間隔、タイムアウト・リトライ、
  連続失敗ドメインの一時除外（サーキットブレーカー）を実装しています。すべての
  試行は `CrawlLog` に記録され、Django Admin（`/admin/`）から確認できます。
- 将来、有償の補助検索API（例：Brave Search API）を追加する場合は、
  `intel/search_providers.py` の `SearchProvider` を実装したクラスを追加し、
  `get_enabled_providers()` に加えるだけで済む構成にしています。

## テスト

```bash
python manage.py test
```

ドメイン正規化・重複判定・スコアリング（元設計書16章の計算例含む）・CSV列マッピング・
CSVインポートの重複ポリシー・登録フロー・パイプライン（クローラーはモック化）を
自動テストでカバーしています（24件）。

## 既知の制約・今後の改善候補

- キーワード判定は単純な部分文字列一致です（形態素解析・同義語展開は未対応）。
- RSSで見つかった記事は本文までは取得せずタイトルのみでスコアリングしています
  （本文取得は将来の改善候補）。
- 情報ソース加点・情報鮮度加点は組織ごとにDBを持たせていますが、鮮度加点は
  現状アプリ設定値（`settings.FRESHNESS_SCORE_RULES`）としており、画面からの編集には
  未対応です（元設計書24章の設定画面要件には明記されていないため）。
- CSVは現状メモリ上でbase64受け渡しする実装のため、数万行規模の大容量CSVは
  非対応です（一時ストレージ経由の分割アップロードは将来の拡張候補）。
- PRO版（AI解析）は未実装です。技術設計書7章のとおり、`ai_analyses` /
  `company_products` / `organization_assets` テーブルを追加し、`organizations.plan`
  で機能を出し分ける構成を前提に設計してあります。
