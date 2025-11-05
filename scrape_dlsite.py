import asyncio
import time
import os
import sys
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
# タイムゾーン処理のためにpytzを追加（インストールが必要です: pip install pytz）
try:
    import pytz
except ImportError:
    print("pytz not found. Please install it using: pip install pytz")
    sys.exit(1)

# ==========================================================
# ⚙️ 設定値
# ==========================================================
ACCESS_DELAY = 5 # 秒: サーバー負荷軽減のための最終待機時間
MAX_ITEMS_TO_SCRAPE = 10 # 抽出する作品の最大件数

# DLsiteのセレクター定義（Playwright用）
LANGUAGE_SELECTOR_XPATH = '//div[@class="adult_check_box _adultcheck type_lang_select"]//a[text()="日本語"]' 
AGE_CONFIRM_SELECTOR_CSS = '.btn_yes.btn-approval a' 
ILLUST_TAB_SELECTOR_CSS = '.option_tab a:has-text("CG・イラスト")' 

# ==========================================================
# 🚀 Playwrightによる非同期スクレイピング関数
# ==========================================================
async def scrape_dlsite_new_products(target_url: str, today_date_str: str, headless_mode: bool = True):
    """
    Playwright (Chromium) を使用してDLsiteにアクセスし、言語選択、年齢確認、カテゴリ切り替えを処理します。
    """
    print(f"**実行日付**: {today_date_str}")
    print(f"ターゲットURL: {target_url}")
    print(f"--- Playwright ブラウザ起動中 (Headless: {headless_mode}) ---")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
            timeout=90000
        )
        page = await browser.new_page()

        try:
            await page.goto(target_url, wait_until='domcontentloaded', timeout=90000)
            
            # --- 処理 A: 言語選択ポップアップの対応 ---
            print("--- 処理 A: 言語選択ポップアップの確認中 ---")
            try:
                await page.wait_for_selector(LANGUAGE_SELECTOR_XPATH, timeout=10000) 
                await page.click(LANGUAGE_SELECTOR_XPATH)
                print("✅ 言語選択ポップアップを「日本語」で閉じました。")
                await page.wait_for_load_state("domcontentloaded", timeout=15000) 
            except PlaywrightTimeoutError:
                print("--- 処理 A: 言語選択ポップアップは表示されていませんでした。 ---")
            
            # --- 処理 B: 18歳以上確認モーダルの対応 ---
            print("--- 処理 B: 18歳以上確認モーダルの確認中 ---")
            try:
                await page.wait_for_selector(AGE_CONFIRM_SELECTOR_CSS, timeout=10000)
                await page.click(AGE_CONFIRM_SELECTOR_CSS)
                print("✅ 18歳以上確認モーダルを「はい」で閉じました。")
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except PlaywrightTimeoutError:
                print("--- 処理 B: 18歳以上確認モーダルは表示されていませんでした。 ---")

            # --- 処理 C: カテゴリ切り替え（「すべて」から「CG・イラスト」へ） ---
            print("--- 処理 C: カテゴリ切り替え（すべて -> CG・イラスト） ---")
            
            try:
                illust_link = page.locator(ILLUST_TAB_SELECTOR_CSS)
                
                await illust_link.wait_for(state="visible", timeout=10000)
                
                # クリック実行（ページ遷移が発生することを許容）
                await illust_link.click(timeout=10000) 
                
                # ★修正★ ページ遷移が発生したとみなし、ロード状態の完了を待機
                await page.wait_for_load_state("domcontentloaded", timeout=30000) 
                
                print("✅ カテゴリを「CG・イラスト」に切り替えました。（遷移完了）")
                
            except Exception as e:
                # 予期せぬエラー（要素が見つからないなど）の場合のみ警告
                print(f"--- 処理 C: ⚠️ カテゴリ切り替えの操作で予期せぬエラーが発生しました: {e.__class__.__name__} ---")
                
            print(f"--- 最終待機中: {ACCESS_DELAY}秒 ---")
            time.sleep(ACCESS_DELAY)  # サーバー負荷軽減

            html_content = await page.content()
            await browser.close()
                
            print("✅ Playwrightによるアクセス成功！HTMLデータを受信しました。")
            return html_content


        except Exception as e:
            await browser.close()
            print(f"--- ⚠️ Playwright アクセスエラー: {type(e).__name__}: {e} ---")
            return None


# ==========================================================
# 📊 データのパース（抽出）処理 - 複数件対応
# ==========================================================
def parse_html_for_products(html_content: str, max_items: int):
    """
    DLsiteのHTMLから、作品名、URL、概要などを抽出します。
    """
    print(f"\n--- データをHTMLから抽出中（最大{max_items}件） ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []

    # 確定した作品タイトルリンクのセレクターを使用
    product_links = soup.select('div.n_worklist_item .work_name a[href*="/product_id/"]') 
    
    if not product_links:
        print("--- ⚠️ 作品データ（リンク）が見つかりませんでした。 ---")
        return []
        
    for link in product_links[:max_items]: 
        
        # 1. 作品タイトル
        title = link.get_text(strip=True) or link.get('title')
        
        # 2. 作品URLとID
        url = link.get('href')
        full_url = f"https://www.dlsite.com{url}" if url and url.startswith('/') else url
        product_id = full_url.split('/')[-1].replace('.html', '').replace('.txt', '')
        
        # 3. 作品のテキストディスクリプション（概要）
        dt_element = link.find_parent('dt')
        description_element = dt_element.find_next_sibling('dd', class_='work_text') if dt_element else None
        description = description_element.get_text(strip=True).replace('\n', ' ') if description_element else '詳細な説明なし'

        # 4. 作者名 (抽出)
        author_link = link.find_parent('dt').find_next_sibling('dd', class_='maker_name').select_one('a')
        author_name = author_link.get_text(strip=True) if author_link else '不明'

        products.append({
            'product_id': product_id,
            'title': title,
            'url': full_url,
            'description': description,
            'author': author_name,
        })
        
    print(f"✅ **{len(products)}件**の作品データを抽出しました。")
    return products


# ==========================================================
# 📝 Hugo向けMarkdownファイル生成関数
# ==========================================================
def create_hugo_markdown(product: dict, date_info: datetime):
    """
    抽出した作品情報からHugo形式のMarkdown文字列を生成します。
    """
    # Hugoのフロントマター
    markdown_content = f"""+++
title = "{product['title']}"
date = "{date_info.isoformat()}"
description = "{product['description'][:150]}..."
product_id = "{product['product_id']}"
author = "{product['author']}"
dlsite_url = "{product['url']}"
tags = ["dlscrapes", "cg-illust"]
categories = ["new_releases"]
+++

## {product['title']}

{product['description']}

---

[DLsiteで見る]({product['url']})

"""
    return markdown_content

# ==========================================================
# 🏁 実行メイン処理
# ==========================================================
def main():
    # 実行日時とタイムゾーンの確定 (JST/Tokyo)
    tokyo_tz = pytz.timezone('Asia/Tokyo')
    now_tokyo = datetime.now(tokyo_tz)
    TODAY_DATE_STR = now_tokyo.strftime('%Y-%m-%d')
    CURRENT_MONTH_STR = now_tokyo.strftime('%Y-%m')

    # 初期アクセスURLの動的生成
    HOME_URL = f"https://www.dlsite.com/maniax/new/=/date/{TODAY_DATE_STR}/cdate/{CURRENT_MONTH_STR}/show_layout/2"

    headless_mode = '--head' not in sys.argv
    
    # 非同期関数を実行し、HTMLデータを取得
    html_data = asyncio.run(scrape_dlsite_new_products(HOME_URL, TODAY_DATE_STR, headless_mode))
    
    if html_data:
        # データのパース（抽出）を実行
        extracted_products = parse_html_for_products(html_data, MAX_ITEMS_TO_SCRAPE)
        
        # 抽出結果の表示とMarkdown生成
        print("\n--- 抽出された作品データとMarkdown生成 ---")
        if extracted_products:
            # Markdown出力ディレクトリの準備
            output_dir = "content/dlsite_new_releases"
            os.makedirs(output_dir, exist_ok=True)

            for product in extracted_products:
                # 抽出結果の表示
                print(f"  タイトル: **{product['title']}** (ID: {product['product_id']})")
                
                # Markdown生成
                markdown_content = create_hugo_markdown(product, now_tokyo)
                
                # ファイル名の決定: RJxxxxx.md 形式
                filename = os.path.join(output_dir, f"{product['product_id']}.md")
                
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    print(f"  ✅ Markdownファイルを生成しました: {filename}")
                except Exception as file_error:
                    print(f"  --- ⚠️ ファイル書き込みエラー: {file_error} ---")
        else:
             print("抽出できる作品はありませんでした。")
            
        print("--------------------------------------")


if __name__ == "__main__":
    if os.name == 'nt':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass
            
    main()