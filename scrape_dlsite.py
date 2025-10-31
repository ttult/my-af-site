import asyncio
import time
import os
import sys
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup # ★追加：BeautifulSoupをインポート

# 実行日の日付を取得し、URLに組み込む
TODAY_DATE_STR = datetime.now().strftime("%Y-%m-%d")
ACCESS_DELAY = 5 # 秒: サーバー負荷軽減のための待機時間

# ターゲットURLをDLsite Maniaxの当日新着作品一覧ページに設定
HOME_URL = f"https://www.dlsite.com/maniax/new/=/date/{TODAY_DATE_STR}/"

# DLsiteのセレクター定義
# 実行結果でポップアップがスキップされたため、今回はパース処理に集中しますが、コードは残します。
LANGUAGE_SELECTOR = '#language_select_ja' 
AGE_CONFIRM_SELECTOR = '//*[@id="age_confirm"]/div/div/div[2]/button[2]' 

OUTPUT_FILENAME = "dlsite_new_products_final.html"

# ==========================================================
# 🚀 Playwrightによる非同期スクレイピング関数（変更なし）
# ==========================================================
async def scrape_dlsite_new_products(target_url: str, headless_mode: bool = True):
    """
    Playwright (Chromium) を使用してDLsiteにアクセスし、言語選択と年齢確認を処理します。
    """
    print(f"ターゲットURL: {target_url}")
    print(f"--- Playwright ブラウザ起動中 (Headless: {headless_mode}) ---")

    async with async_playwright() as p:
        # browserコンテキスト設定
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
            timeout=90000
        )
        page = await browser.new_page()

        try:
            # 1. ページにアクセス
            await page.goto(target_url, wait_until='domcontentloaded', timeout=90000)
            
            # --- 処理 A: 言語選択ポップアップの対応 ---
            print("--- 処理 A: 言語選択ポップアップの確認中 ---")
            try:
                await page.wait_for_selector(LANGUAGE_SELECTOR, timeout=10000)
                await page.click(LANGUAGE_SELECTOR)
                print("✅ 言語選択ポップアップを「日本語」で閉じました。")
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except PlaywrightTimeoutError:
                print("--- 処理 A: 言語選択ポップアップは表示されていませんでした。 ---")
            
            # --- 処理 B: 18歳以上確認モーダルの対応 ---
            print("--- 処理 B: 18歳以上確認モーダルの確認中 ---")
            try:
                await page.wait_for_selector(AGE_CONFIRM_SELECTOR, timeout=10000)
                await page.click(AGE_CONFIRM_SELECTOR)
                print("✅ 18歳以上確認モーダルを「はい」で閉じました。")
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except PlaywrightTimeoutError:
                print("--- 処理 B: 18歳以上確認モーダルは表示されていませんでした。 ---")
            # ------------------------------------

            # サーバー負荷軽減のための意図的な待機
            print(f"--- 待機中: {ACCESS_DELAY}秒 ---")
            time.sleep(ACCESS_DELAY)  

            html_content = await page.content()
            await browser.close()
            
            if "403 ERROR" in html_content or "アクセスがブロックされました" in html_content:
                print("--- 🚨 アクセスがブロックされています。 ---")
                return None
                
            print("✅ Playwrightによるアクセス成功！HTMLデータを受信しました。")
            return html_content

        except Exception as e:
            await browser.close()
            print(f"--- ⚠️ Playwright アクセスエラー: {type(e).__name__}: {e} ---")
            return None

# ==========================================================
# ★追加★ データのパース（抽出）処理
# ==========================================================
def parse_html_for_products(html_content: str):
    """
    DLsiteの新着作品一覧HTMLから、作品名とURLを抽出します。
    """
    print("\n--- データをHTMLから抽出中 ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []

    # DLsiteの作品一覧のタイトルリンクのCSSセレクター
    # div.work_1col > dl > dt > a は、作品のタイトルとリンクを保持する要素です。
    product_links = soup.select('#search_result div.work_1col > dl > dt > a') 
    
    if not product_links:
        print("--- ⚠️ 作品データ（リンク）が見つかりませんでした。本日の新着がないか確認してください。 ---")
        
    for link in product_links:
        title = link.get_text(strip=True)
        # URLは常に絶対URLで取得できる
        url = link.get('href')
        
        products.append({
            'title': title,
            'url': url
        })

    print(f"✅ **{len(products)}件**の作品データを抽出しました。")
    return products


# ==========================================================
# 実行メイン処理
# ==========================================================
def main():
    # コマンドライン引数に '--head' があるかチェック
    headless_mode = '--head' not in sys.argv
    
    print(f"**実行日付**: {TODAY_DATE_STR}")
    target_url = HOME_URL
    
    # 非同期関数を実行し、HTMLデータを取得
    html_data = asyncio.run(scrape_dlsite_new_products(target_url, headless_mode))
    
    if html_data:
        # HTMLデータをファイルに書き出す (デバッグ用)
        try:
            with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                f.write(html_data)
            # HTMLの長さやタイトルはPlaywrightパートで出力済みのため省略
        except Exception as file_error:
             print(f"--- ⚠️ ファイル書き込みエラー: {file_error} ---")

        # データのパース（抽出）を実行
        extracted_products = parse_html_for_products(html_data)
        
        # 抽出結果の表示
        print("\n--- 抽出された作品データ（上位5件） ---")
        if extracted_products:
            for i, product in enumerate(extracted_products[:5]):
                print(f"[{i+1}] タイトル: **{product['title']}**")
                print(f"    URL: {product['url']}")
            if len(extracted_products) > 5:
                print(f"  ...他 {len(extracted_products) - 5}件")
        else:
             print("抽出できる作品はありませんでした。")
            
        print("--------------------------------------")

    else:
        print("データ取得に失敗したため、処理を中断します。")


if __name__ == "__main__":
    if os.name == 'nt':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass
            
    main()