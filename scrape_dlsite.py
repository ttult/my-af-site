import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import date
import re

# --- 1. 定数設定 ---
# 出力ファイルパス (Hugoのデータディレクトリ)
DATA_OUTPUT_PATH = 'data/dlsite_new.json'

# --- 2. URL動的生成 ---
def generate_target_url():
    """実行日当日のDLsite新作一覧URLを生成する (YYYY-MM-DD形式)"""
    today = date.today().strftime("%Y-%m-%d") 
    url = f'https://www.dlsite.com/maniax/new/=/date/{today}/'
    print(f"ターゲットURL: {url}")
    return url

# --- 3. HTMLの取得 ---
def fetch_html(url, delay):
    """指定されたURLからHTMLを取得し、負荷対策として遅延を入れる"""
    time.sleep(delay)  # 負荷対策のための遅延
    try:
        # User-Agentを設定（ブラウザからのアクセスに見せかける）
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # 200番台以外のステータスコードなら例外発生
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"--- ⚠️ Error fetching URL {url}: {e}")
        return None

# --- 4. 第1段階: 一覧ページから作品IDリストを抽出 ---
def get_product_ids(html_content):
    """一覧ページからRJコード(作品ID)のリストを抽出する"""
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    ids = []
    
    # 新作一覧ページの作品リンク要素からRJコードを抽出
    # セレクタはDLsiteのHTML構造に合わせています
    product_links = soup.select('div.work_item a.work_link') 
    
    for link in product_links:
        href = link.get('href')
        if href and 'product_id' in href:
            # URLから RJxxxxxx の部分を正規表現で抽出
            match = re.search(r'product_id/([a-zA-Z0-9]+)\.html', href)
            if match:
                ids.append(match.group(1))
    
    unique_ids = list(set(ids))
    print(f"--- ✅ 一覧から {len(unique_ids)} 件の作品IDを抽出しました。")
    return unique_ids

# --- 5. 第2段階: 詳細ページからデータを抽出 ---
def scrape_product_details(product_id):
    """個別の作品詳細ページにアクセスし、詳細データを抽出する"""
    detail_url = f'https://www.dlsite.com/maniax/work/=/product_id/{product_id}.html'
    
    # ⚠️ 負荷対策として10秒遅延 ⚠️
    html = fetch_html(detail_url, delay=10) 
    
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    data = {'id': product_id, 'url': detail_url}

    try:
        # タイトル
        data['title'] = soup.select_one('#work_name a').text.strip()
        
        # 作者/サークル名
        maker_tag = soup.select_one('#work_maker a.maker_name') 
        data['maker'] = maker_tag.text.strip() if maker_tag else '作者情報なし'

        # サムネイル画像URL（メイン画像）
        img_tag = soup.select_one('#work_image img')
        # data-src属性があればそれを優先（遅延読み込み対策）
        data['image_url'] = img_tag.get('data-src', img_tag.get('src')) if img_tag else ''

        # 価格
        # 価格情報が格納されているセレクタ
        price_text = soup.select_one('.work_detail_area .price').text.strip() if soup.select_one('.work_detail_area .price') else '価格情報なし'
        data['price_text'] = price_text

        # タグ/ジャンル
        tags = []
        # work_outline内のタグやジャンルのリンクを抽出
        category_table = soup.select_one('#work_outline')
        if category_table:
            # ジャンル、属性などのaタグをすべて取得
            tags = [a.text.strip() for a in category_table.select('a[href*="/genre/"], a[href*="/attribute/"]')]

        data['tags'] = tags
        
        print(f"--- 📊 成功: {data['id']} - {data['title'][:20]}...")
        return data

    except AttributeError:
        print(f"--- ❌ エラー: {product_id} - 必要な情報が見つかりませんでした。スキップします。")
        return None
    except Exception as e:
        print(f"--- ❌ エラー: {product_id} - 処理中に予期せぬエラーが発生しました: {e}")
        return None

# --- 6. データ出力 ---
def save_to_json(data):
    """データをJSON形式でHugoのデータディレクトリに保存する"""
    # dataフォルダがなければ作成
    os.makedirs(os.path.dirname(DATA_OUTPUT_PATH), exist_ok=True)
    
    # Hugoのデータファイル形式に合わせてデータを格納
    output_data = {
        "products": data 
    }
    
    with open(DATA_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        # JSONを読みやすく（インデント付き）で保存
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ 全処理完了: 正常に {len(data)} 件の作品データを {DATA_OUTPUT_PATH} に保存しました。")

# --- メイン実行 ---
if __name__ == "__main__":
    # 1. ターゲットURLを生成し、HTMLを取得
    target_url = generate_target_url()
    list_html = fetch_html(target_url, delay=5) # 一覧アクセス時は5秒待機

    if not list_html:
        print("\n--- 🛑 処理中断: 一覧ページの取得に失敗しました。")
    else:
        # 2. 作品IDリストを取得
        product_ids = get_product_ids(list_html)
        
        if not product_ids:
            print("\n--- ℹ️ 情報: 本日新作の情報が見つかりませんでした。処理を終了します。")
        else:
            final_products = []
            
            # 3. 各作品の詳細ページをスクレイピング (10秒遅延)
            for i, pid in enumerate(product_ids):
                print(f"処理中 ({i+1}/{len(product_ids)}): {pid} の詳細を取得...")
                detail = scrape_product_details(pid)
                if detail:
                    final_products.append(detail)
            
            # 4. JSONファイルとして保存
            save_to_json(final_products)