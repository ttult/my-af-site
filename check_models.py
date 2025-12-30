import os
from google import genai

def list_my_models():
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ APIキーが設定されていません。")
        return

    client = genai.Client(api_key=api_key)
    print("--- 接続テスト開始 ---")

    try:
        # 最新SDKでは単純にイテレートするだけでモデル情報が取れます
        # 属性名は name, display_name などです
        for m in client.models.list():
            print(f"✅ {m.name} ({m.display_name})")
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        # もし属性エラーが出る場合は、オブジェクトの中身を直接出力して確認します
        print("デバッグ情報: 構造が想定と異なる可能性があります。")

if __name__ == "__main__":
    list_my_models()