import requests
import time
from datetime import datetime, timedelta

# ----------------- 修正ポイント -----------------
# 1. 偽装するUser-Agentを定義する
headers = {
    # 🚨 これが最も重要な対策です。一般的なChromeブラウザからのアクセスに見せかけます。
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    # 日本語圏からのアクセスに見せかけるため、Accept-Languageも設定
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
}
# -----------------------------------------------

def scrape_data(target_date):
    """指定された日付のMGS情報をスクレイピングする関数"""
    
    # URL生成
    date_str = target_date.strftime("%Y.%m.%d")
    target_url = f"https://www.mgstage.com/search/cSearch.php?sale_start_range={date_str}-{date_str}&type=top"
    
    print(f"ターゲットURL: {target_url}")
    print("--- 待機中: 5秒 ---")
    time.sleep(5)  # アクセス間隔の確保 (スクレイピング対策)

    try:
        # 2. リクエスト時に headers を渡す
        response = requests.get(target_url, headers=headers, timeout=15)
        
        # 4xx や 5xx ステータスコードの場合は例外を発生させる
        response.raise_for_status()
        
        print("✅ スクレイピング成功！データを受信しました。")
        
        # ここに続くスクレイピング処理 (例: Beautiful Soupを使った解析など)
        # ...
        
        return response.text # 成功した場合、HTMLコンテンツを返す

    except requests.exceptions.HTTPError as err:
        print(f"--- ⚠️ Error fetching URL {target_url}: {err} ---")
        return None
    except requests.exceptions.RequestException as e:
        print(f"--- ⚠️ リクエストエラー: {e} ---")
        return None

# 今日の日付を設定（ログを見る限り、2025年10月29日をターゲットにしているようです）
today = datetime(2025, 10, 29) # ログの日付に合わせて固定
# today = datetime.now() # 実際は現在の日付を使用

scrape_data(today)