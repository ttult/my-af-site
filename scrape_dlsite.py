#!/usr/bin/env python3
"""
scrape_dlsite.py

Scrapes DLsite new releases and writes Hugo-compatible Markdown files
into `content/posts/dlsite/YYYY/MM`.

This module keeps strings safe for TOML frontmatter by removing newlines
and escaping backslashes and double quotes in the `description` field.
"""

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

# Configuration
ACCESS_DELAY = 3
MAX_ITEMS_TO_SCRAPE = 3
OUTPUT_BASE_DIR = "content/posts/dlsite"

# Selectors
LANGUAGE_SELECTOR_XPATH = '//div[@class="adult_check_box _adultcheck type_lang_select"]//a[text()="日本語"]'
AGE_CONFIRM_SELECTOR_CSS = '.btn_yes.btn-approval a'
ILLUST_TAB_SELECTOR_CSS = '.option_tab a:has-text("CG・イラスト")'


def get_existing_ids(output_dir: str) -> set:
    """Return set of existing RJ IDs under output_dir (recursive)."""
    if not os.path.exists(output_dir):
        return set()
    existing = set()
    for p in glob.glob(os.path.join(output_dir, "**", "RJ*.md"), recursive=True):
        existing.add(os.path.splitext(os.path.basename(p))[0])
    return existing


def parse_html_for_ids(html: str, max_items: int) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    links = soup.select('div.n_worklist_item .work_name a[href*="/product_id/"]')
    for a in links[:max_items]:
        title = a.get_text(strip=True) or a.get('title')
        href = a.get('href')
        full = f"https://www.dlsite.com{href}" if href and href.startswith('/') else href
        pid = full.split('/')[-1].replace('.html', '').replace('.txt', '')
        # author and short description best-effort
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

        items.append({'product_id': pid, 'title': title, 'url': full, 'author': author, 'description': desc})
    return items


def create_hugo_markdown(product: Dict[str, Any], date_info: datetime) -> str:
    """Create Hugo TOML frontmatter + body. Make description TOML-safe."""
    description_text = product.get('full_description', product.get('description', ''))
    genres = product.get('genres', [])
    # Make safe for TOML basic string: remove newlines, escape backslash and double-quote
    safe_description = description_text.replace('\\', '\\\\').replace('\n', ' ').replace('"', '\\"')

    # Fix tags field to be a valid TOML array
    all_tags = ["DLsite", "CG・イラスト"] + genres
    tags_toml_array = ", ".join(f'"{tag}"' for tag in all_tags)

    front = f'''+++
title = "{product.get('title','') }"
date = "{date_info.isoformat()}"
description = "{safe_description[:150]}..."
product_id = "{product.get('product_id','')}"
author = "{product.get('author','')}"
dlsite_url = "{product.get('url','')}"
tags = [{tags_toml_array}]
categories = ["new_releases"]
image = "{product.get('image_url','no_image')}"
+++

'''
    body = f"""![メイン画像]({product.get('image_url','no_image')})

## {product.get('title','')}

{description_text}

---

"""
    # ★★★ サブ画像の追加ロジック ★★★
    if product.get('sub_images'):
        body += "\n## サンプル画像\n"
        for idx, sub_img_url in enumerate(product['sub_images']):
            # 全画像を本文に挿入（Markdown形式）
            body += f"![サンプル {idx+1}]({sub_img_url})\n\n"
            
    body += f"""
[DLsiteで見る]({product.get('url','')})

"""
    return front + body


async def scrape_dlsite_new_products(target_url: str, today_date_str: str, headless_mode: bool = True) -> str | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless_mode, args=['--no-sandbox','--disable-blink-features=AutomationControlled'], timeout=90000)
        page = await browser.new_page()
        try:
            await page.goto(target_url, wait_until='domcontentloaded', timeout=90000)
            # language popup
            try:
                await page.wait_for_selector(LANGUAGE_SELECTOR_XPATH, timeout=10000)
                await page.click(LANGUAGE_SELECTOR_XPATH)
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
            except Exception:
                pass
            # age confirm
            try:
                await page.wait_for_selector(AGE_CONFIRM_SELECTOR_CSS, timeout=10000)
                await page.click(AGE_CONFIRM_SELECTOR_CSS)
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
            except Exception:
                pass
            # category
            try:
                ill = page.locator(ILLUST_TAB_SELECTOR_CSS)
                await ill.wait_for(state='visible', timeout=10000)
                await ill.click(timeout=10000)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
            except Exception:
                pass
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

        # Full description extraction with improved formatting
        full_description_elem = soup.select_one('.work_parts_container .work_parts_area')
        if full_description_elem:
            # Replace <br> tags with double newlines for Markdown paragraph breaks
            for br in full_description_elem.find_all('br'):
                br.replace_with('\n\n')

            # Add double newlines before and after <p> tags for better paragraph separation
            for p in full_description_elem.find_all('p'):
                p.insert_before('\n\n')
                p.insert_after('\n\n')

            # Extract text and clean up excessive newlines
            raw_text = full_description_elem.get_text('\n', strip=True)
            product['full_description'] = '\n\n'.join(
                line.strip() for line in raw_text.splitlines() if line.strip()
            )
        else:
            product['full_description'] = product['description']

        # Image extraction
        meta_img = soup.select_one('meta[itemprop="image"]')
        if meta_img and meta_img.get('content'):
            product['image_url'] = f"https:{meta_img['content']}"
        else:
            img = soup.select_one('.work_slider img.swiper-lazy-loaded')
            if img and img.get('srcset'):
                product['image_url'] = img['srcset'].split(',')[0].strip().split(' ')[0]
            elif img and img.get('src'):
                product['image_url'] = img['src']
            else:
                product['image_url'] = '画像なし'
        if product['image_url'].startswith('//'):
            product['image_url'] = 'https:' + product['image_url']

        # Genre extraction
        genres = []
        table = soup.find('table', id='work_outline')
        if table:
            for th in table.find_all('th'):
                if 'ジャンル' in th.get_text(strip=True):
                    td = th.find_next_sibling('td')
                    if td:
                        genres = [a.get_text(strip=True) for a in td.select('.main_genre a')]
                        break
        product['genres'] = genres

        # T4: メイン画像URLとサブ画像リストの抽出開始
        print("  > T4: メイン画像URLとサブ画像リスト 抽出開始")

        product['sub_images'] = []

        # 1. メイン画像 (Front Matter用)
        main_img_elem = soup.select_one('.slider_items .slider_item.active picture img')
        main_img_meta = soup.select_one('meta[itemprop="image"]')

        if main_img_meta and 'content' in main_img_meta.attrs:
            product['image_url'] = f"https:{main_img_meta['content']}" 
        elif main_img_elem:
            # activeなliタグのsrcsetからURLを取得
            src_set = main_img_elem.get('srcset')
            if src_set:
                # srcsetの最初のURL（高解像度）を取得
                product['image_url'] = src_set.split(',')[0].strip().split(' ')[0]
            else:
                product['image_url'] = main_img_elem.get('src', '画像なし')
        else:
            product['image_url'] = "画像なし"

        if product['image_url'].startswith('//'):
            product['image_url'] = 'https:' + product['image_url']
            
        # 2. サブ画像リスト (本文用)
        slider_image_elements = soup.select('.slider_items li picture img')
        sub_image_urls = set()

        for img_elem in slider_image_elements:
            src_set = img_elem.get('srcset')
            if src_set:
                sub_img_url = src_set.split(',')[0].strip().split(' ')[0]
            else:
                sub_img_url = img_elem.get('src') or img_elem.get('data-src')

            if sub_img_url and sub_img_url.startswith('//'):
                sub_img_url = f"https:{sub_img_url}"

            # メイン画像と重複せず、かつ有効なURLである場合のみ追加
            if sub_img_url and sub_img_url != product['image_url']:
                sub_image_urls.add(sub_img_url)

        # セットからリストに戻し、最大10枚に制限
        product['sub_images'] = list(sub_image_urls)[:10]

        time.sleep(ACCESS_DELAY)
        return product
    except Exception:
        return product


async def main_async(headless_mode: bool):
    tz = pytz.timezone('Asia/Tokyo')
    now = datetime.now(tz)
    today = now.strftime('%Y-%m-%d')
    month = now.strftime('%Y-%m')
    ym_path = now.strftime('%Y/%m')
    output_dir = os.path.join(OUTPUT_BASE_DIR, ym_path)
    os.makedirs(output_dir, exist_ok=True)
    home_url = f"https://www.dlsite.com/maniax/new/=/date/{today}/cdate/{month}/show_layout/2"
    html = await scrape_dlsite_new_products(home_url, today, headless_mode)
    if not html:
        print('failed to fetch list')
        return

    # Extracted products are directly processed without duplicate checks
    products_to_process = parse_html_for_ids(html, MAX_ITEMS_TO_SCRAPE)

    if not products_to_process:
        print("抽出できる作品はありませんでした。処理を終了します。")
        return

    print(f"\n--- Stage 2: 処理対象作品 {len(products_to_process)}件の詳細データを取得中 (既存ファイルは上書き) ---")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless_mode, timeout=90000)
        page = await browser.new_page()

        for product in products_to_process:
            product = await scrape_detail_page(page, product)
            md = create_hugo_markdown(product, now)
            fname = os.path.join(output_dir, f"{product['product_id']}.md")
            try:
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(md)
                print('wrote', fname)
            except Exception as e:
                print('write error', e)
        await browser.close()


def main():
    headless_mode = '--head' not in sys.argv
    try:
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass
    asyncio.run(main_async(headless_mode))


if __name__ == '__main__':
    main()
