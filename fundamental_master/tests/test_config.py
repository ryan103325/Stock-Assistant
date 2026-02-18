"""
測試配置模組
"""
from fundamental_master.utils import Config


def test_config_validation():
    """測試配置驗證"""
    try:
        Config.validate()
        print("✅ 配置驗證通過")
        return True
    except ValueError as e:
        print(f"❌ 配置驗證失敗: {e}")
        return False


def test_create_directories():
    """測試資料夾建立"""
    try:
        Config.create_directories()
        print("✅ 資料夾建立成功")
        return True
    except Exception as e:
        print(f"❌ 資料夾建立失敗: {e}")
        return False


def test_api_keys():
    """測試 API Keys 是否正確載入"""
    print("\n=== API Keys 檢查 ===")
    
    keys_status = {
        'OPENAI_API_KEY': Config.OPENAI_API_KEY,
        'OPENAI_MODEL': Config.OPENAI_MODEL,
        'TELEGRAM_TOKEN': Config.TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': Config.TELEGRAM_CHAT_ID,
        'GOOGLE_API_KEY': Config.GOOGLE_API_KEY,
        'FINMIND_TOKEN': Config.FINMIND_TOKEN,
        'OPENROUTER_API_KEY': Config.OPENROUTER_API_KEY,
    }
    
    for key_name, key_value in keys_status.items():
        if key_value:
            # 只顯示前 10 個字元
            masked_value = f"{key_value[:10]}..." if len(key_value) > 10 else key_value
            print(f"✅ {key_name}: {masked_value}")
        else:
            print(f"⚠️ {key_name}: 未設定")
    
    return True


if __name__ == '__main__':
    print("=== 基本面評分系統 - 配置測試 ===\n")
    
    # 測試 API Keys
    test_api_keys()
    
    print("\n=== 配置驗證 ===")
    test_config_validation()
    
    print("\n=== 資料夾建立 ===")
    test_create_directories()
    
    print("\n=== 測試完成 ===")
