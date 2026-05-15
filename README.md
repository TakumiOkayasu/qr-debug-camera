# QR Debug Camera

Windows Chrome/Chromium向けのデバッグ補助ツールです。画面上のQRコードを最前面オーバーレイ枠で囲み、対象Chromeページの `getUserMedia()` を差し替えて、QR入りの擬似カメラ映像として渡します。

本体は Python です。ブラウザへ注入するカメラ差し替えコードだけ TypeScript で管理し、Bunでビルドします。OBSや仮想カメラドライバは使いません。

## Requirements

- Windows
- Python 3.14系の最新パッチ版
- uv
- Bun
- Google Chrome または Chromium

## Setup

```powershell
cd C:\prog\qr-debug-camera
uv python install 3.14
uv sync
bun install
bun run build:injected
```

## Run

`config.toml` の `chrome.target_url` を対象ブラウザアプリのURLに変更してから実行します。

```powershell
uv run qr-debug-camera
```

URLだけ上書きする場合:

```powershell
uv run qr-debug-camera --url "https://target.example.test/path?mode=search&dummy_code=123"
```

終了キーの既定値は `q` です。ターミナルにフォーカスがある状態で押すと終了します。`Ctrl+C` でも終了できます。

## Behavior

- 半透明の最前面フレームを表示します。
- フレーム内の画面領域をキャプチャします。
- 画面キャプチャに一時失敗した場合も、前回画像または黒フレームでカメラ映像を継続します。
- QRコードを1つだけ検出します。
- QRの生バイトを `utf-8` / `cp932` / `shift_jis` / `euc_jp` の順で明示デコードします。
- 検出時はカメラ映像に `〇`、未検出時は `✖` を重ねます。
- 検出できたQRは中央寄せし、最大80%まで拡大表示します。
- 同じQRのログは既定で1秒重複抑制します。
- 読み取り結果はCLIと `logs/qr-readings.jsonl` に出力します。
- OpenCVのQRデコード警告は `OPENCV_LOG_LEVEL=ERROR` で抑制します。
- フレーム生成とChromeへの送信はバックグラウンドスレッドで行います。
- 終了時はChrome DevTools Protocol経由でChromeへ正常終了を要求します。

ログ例:

```json
{"captured_at":"2026-05-14T16:30:00.123+09:00","payload":"https://example.test","source":"qr-debug-camera"}
```

## Scripts

```powershell
bun run build:injected
bun run typecheck
uv run ruff check .
uv run mypy src
```

## Limitations

- OSのカメラ一覧に出る仮想カメラではありません。
- このツールが起動したChromeプロファイル内だけで動作します。
- 対象ページがiframe内でカメラ処理を行う場合、追加対応が必要になることがあります。
- 60fpsではPC性能やページ負荷の影響を受けます。
- Chromeの専用プロファイルを使うため、必要なら対象アプリへ再ログインしてください。
- Chrome DevTools Protocol接続用に `--remote-allow-origins=http://127.0.0.1:9222` を付けてChromeを起動します。
