import asyncio
import time
from datetime import datetime
from playwright.async_api import async_playwright

ACCESS_DELAY = 5 # 秒

# ターゲットURLをMGSのホーム画面に変更
HOME_URL = "https://www.mgstage.com/"

# ==========================================================
# 🚀 Playwrightによる非同期スクレイピング関数
# ==========================================================
async def scrape_mgstage_home(target_url):
    """
    Playwright (Chromium) を使用して指定されたURLのHTMLコンテンツを取得する。
    """
    print(f"ターゲットURL: {target_url}")
    print("--- Playwright ブラウザ起動中 (Headlessモード) ---")

    async with async_playwright() as p:
        # Headless=True (画面表示なし) のまま実行
        browser = await p.chromium.launch(
            headless=True, 
            # 自動化の痕跡を隠すオプションは、Headlessでも有効
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
            timeout=60000
        )
        page = await browser.new_page()

        try:
            # 1. ホーム画面にアクセス
            await page.goto(target_url, timeout=60000)

            # ページのJavaScriptが完全に実行され、ネットワーク活動が落ち着くのを待機
            await page.wait_for_load_state("networkidle", timeout=30000) 

            # サーバー負荷軽減のための意図的な待機
            print(f"--- 待機中: {ACCESS_DELAY}秒 (MGS対策) ---")
            time.sleep(ACCESS_DELAY) 

            # HTMLコンテンツを取得
            html_content = await page.content()
            await browser.close()
            
            # 403エラーページが返されていないかチェック
            if "403 ERROR" in html_content or "Request blocked" in html_content:
                 print("--- 🚨 依然としてアクセスがブロックされています（IPアドレスの問題の可能性が高いです）。 ---")
                 return None
            
            print("✅ Playwrightによるアクセス成功！データを受信しました。")
            return html_content

        except Exception as e:
            await browser.close()
            print(f"--- ⚠️ Playwright アクセスエラー: {e} ---")
            return None

# ==========================================================
# 実行メイン処理
# ==========================================================
def main():
    # ターゲットURLをホームに設定
    target_url = HOME_URL
    
    # 非同期関数を実行
    html_data = asyncio.run(scrape_mgstage_home(target_url))
    
    if html_data:
        # 取得したデータをここで処理
        print(f"取得したHTMLデータの長さ: {len(html_data)}文字")
        # デバッグ：取得したHTMLのタイトルを確認
        if "<title>" in html_data:
             title_start = html_data.find("<title>") + 7
             title_end = html_data.find("</title>")
             page_title = html_data[title_start:title_end].strip()
             print(f"ページタイトル: {page_title}")
        # print(html_data[:500]) # 取得内容の先頭500文字を出力して目で確認

    else:
        print("データ取得に失敗したため、処理を中断します。")


if __name__ == "__main__":
    # Windows/Linux/macOS環境で実行可能
    main()