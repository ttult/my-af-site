#!/usr/bin/env python3
import asyncio
import time
import os
import sys
import glob
from datetime import datetime
from typing import Dict, Any, List

import pytz
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from google import genai

# Configuration
ACCESS_DELAY = 3
MAX_ITEMS_TO_SCRAPE = 3
OUTPUT_BASE_DIR = "content/posts/dlsite"

# Selectors
LANGUAGE_SELECTOR_XPATH = '//div[@class="adult_check_box _adultcheck type_lang_select"]//a[text()="日本語"]'
AGE_CONFIRM_SELECTOR_CSS = '.btn_yes.btn-approval a'
ILLUST_TAB_SELECTOR_CSS = '.option_tab a:has-text("CG・イラスト")'


async def generate_llm_content(product: Dict[str, Any]) -> str:
    """Gemini APIで『管理人の感想』を生成。失敗時は空文字を返す。"""
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return ""

    # 調査済みリストに基づいた安定モデル
    model_id = "models/gemini-2.5-flash-lite"
    
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""以下の作品の内容を読み、期待できるポイントや魅力を「管理人の感想」として150文字程度でポジティブに書いてください。
タイトル、内容などは含めず、純粋な感想文だけを出力してください。
【タイトル】: {product['title']}
【内容】: {product.get('full_description', '')[:1200]}"""

        for attempt in range(2):
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_id,
                    contents=prompt
                )
                return response.text if response.text else ""
            except Exception as e:
                if "429" in str(e) and attempt == 0:
                    await asyncio.sleep(15)
                    continue
                raise e
    except Exception as e:
        print(f"  > LLM Error: {e}")
        return ""


def parse_html_for_ids(html: str, max_items: int) -> List[Dict[str, Any]]:
    """DLsiteの一覧ページから商品情報を抽出する関数"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    links = soup.select('div.n_worklist_item .work_name a[href*="/product_id/"]')
    for a in links[:max_items]:
        title = a.get_text(strip=True) or a.get('title')
        href = a.get('href')
        full = f"https://www.dlsite.com{href}" if href and href.startswith('/') else href
        pid = full.split('/')[-1].replace('.html', '').replace('.txt', '')
        
        dt = a.find_parent('dt')
        author = '不明'
        if dt:
            maker = dt.find_next_sibling('dd', class_='maker_name')
            if maker:
                al = maker.select_one('a')
                if al:
                    author = al.get_text(strip=True)
        
        desc = '詳細な説明なし'
        if dt:
            desc_el = dt.find_next_sibling('dd', class_='work_text')
            if desc_el:
                desc = desc_el.get_text(strip=True).replace('\n', ' ')

        items.append({
            'product_id': pid, 
            'title': title, 
            'url': full, 
            'author': author, 
            'description': desc
        })
    return items


def create_hugo_markdown(product: Dict[str, Any], llm_review: str, date_info: datetime) -> str:
    """Markdown生成。説明文＋管理人の感想の構成。"""
    genres_list = product.get('genres', [])
    all_tags = ["DLsite"] + genres_list 
    tags_toml_array = ", ".join(f'"{tag}"' for tag in all_tags)
    main_image_url = product.get('image_url', 'no_image')
    
    original_desc = product.get('full_description', '詳細な説明はありません。')

    markdown_content = f"""+++
title = "{product['title']}"
date = "{date_info.isoformat()}"
product_id = "{product['product_id']}"
author = "{product['author']}"
dlsite_url = "{product['url']}"
tags = [{tags_toml_array}]
categories = ["new_releases"]
images = ["{main_image_url}"]
+++

![メイン画像]({main_image_url})

## {product['title']}

{original_desc}

---
"""
    if llm_review and llm_review.strip():
        markdown_content += f"""
## 管理人の感想
{llm_review.strip()}

---
"""

    if product.get('sub_images'):
        markdown_content += "\n## サンプル画像\n"
        for idx, sub_img_url in enumerate(product['sub_images']):
            markdown_content += f"![サンプル {idx+1}]({sub_img_url})\n\n"
            
    return markdown_content


async def scrape_dlsite_new_products(target_url: str, today_date_str: str, headless_mode: bool = True) -> str | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless_mode, 
            args=['--no-sandbox','--disable-blink-features=AutomationControlled'], 
            timeout=90000
        )
        page = await browser.new_page()
        try:
            await page.goto(target_url, wait_until='domcontentloaded', timeout=90000)
            try:
                await page.wait_for_selector(LANGUAGE_SELECTOR_XPATH, timeout=10000)
                await page.click(LANGUAGE_SELECTOR_XPATH)
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
            except: pass
            try:
                await page.wait_for_selector(AGE_CONFIRM_SELECTOR_CSS, timeout=10000)
                await page.click(AGE_CONFIRM_SELECTOR_CSS)
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
            except: pass
            try:
                ill = page.locator(ILLUST_TAB_SELECTOR_CSS)
                await ill.wait_for(state='visible', timeout=10000)
                await ill.click(timeout=10000)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
            except: pass
            time.sleep(ACCESS_DELAY)
            html = await page.content()
            await browser.close()
            return html
        except Exception:
            await browser.close()
            return None


async def scrape_detail_page(page, product: Dict[str, Any]) -> Dict[str, Any]:
    try:
        await page.goto(product['url'], wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_load_state('domcontentloaded', timeout=15000)
        soup = BeautifulSoup(await page.content(), 'html.parser')

        full_description_elem = soup.select_one('.work_parts_container .work_parts_area')
        if full_description_elem:
            for br in full_description_elem.find_all('br'):
                br.replace_with('\n\n')
            for p in full_description_elem.find_all('p'):
                p.insert_before('\n\n')
                p.insert_after('\n\n')
            raw_text = full_description_elem.get_text('\n', strip=True)
            product['full_description'] = '\n\n'.join(line.strip() for line in raw_text.splitlines() if line.strip())
        else:
            product['full_description'] = product['description']

        meta_img = soup.select_one('meta[itemprop="image"]')
        if meta_img and meta_img.get('content'):
            product['image_url'] = f"https:{meta_img['content']}"
        else:
            img = soup.select_one('.work_slider img.swiper-lazy-loaded')
            product['image_url'] = img['src'] if img and img.get('src') else '画像なし'
        
        if product['image_url'].startswith('//'):
            product['image_url'] = 'https:' + product['image_url']

        table = soup.find('table', id='work_outline')
        product['genres'] = [a.get_text(strip=True) for a in table.select('.main_genre a')] if table else []

        product['sub_images'] = []
        slider_imgs = soup.select('.slider_items li picture img')
        sub_image_urls = set()
        for img_elem in slider_imgs:
            src = img_elem.get('srcset', '').split(',')[0].strip().split(' ')[0] or img_elem.get('src')
            if src:
                if src.startswith('//'): src = 'https:' + src
                if src != product['image_url']: sub_image_urls.add(src)
        product['sub_images'] = list(sub_image_urls)[:10]

        time.sleep(ACCESS_DELAY)
        return product
    except:
        return product


async def main_async(headless_mode: bool):
    tz = pytz.timezone('Asia/Tokyo')
    now = datetime.now(tz)
    today, month = now.strftime('%Y-%m-%d'), now.strftime('%Y-%m')
    output_dir = os.path.join(OUTPUT_BASE_DIR, now.strftime('%Y/%m'))
    os.makedirs(output_dir, exist_ok=True)
    
    home_url = f"https://www.dlsite.com/maniax/new/=/date/{today}/cdate/{month}/show_layout/2"
    
    html = await scrape_dlsite_new_products(home_url, today, headless_mode)
    if not html: return

    products_to_process = parse_html_for_ids(html, MAX_ITEMS_TO_SCRAPE)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless_mode)
        page = await browser.new_page()

        for product in products_to_process:
            print(f"Processing {product['product_id']}...")
            product = await scrape_detail_page(page, product)
            review_text = await generate_llm_content(product)
            md = create_hugo_markdown(product, review_text, now)
            
            fname = os.path.join(output_dir, f"{product['product_id']}.md")
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(md)
            print('wrote', fname)
            
        await browser.close()

def main():
    headless_mode = '--head' not in sys.argv
    if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_async(headless_mode))

if __name__ == '__main__':
    main()