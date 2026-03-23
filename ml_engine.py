import sys
import os
import pandas as pd
import numpy as np

# ================================================================
# 動態取得 pretrained_brain/ 的絕對路徑（相對於本檔案的位置）
# 這樣不管專案放在哪台電腦、哪個目錄，都能正確找到模型。
# ================================================================
_HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.join(_HERE, "pretrained_brain")

if BRAIN_DIR not in sys.path:
    sys.path.insert(0, BRAIN_DIR)

try:
    from stable_baselines3 import PPO
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False

class MLExpertEngine:
    """
    載入 pretrained_brain/ 裡的「深度強化學習 (DRL)模型」，實現儀表板推論介接。
    """
    def __init__(self, model_path: str = ""):
        # 預設使用 pretrained_brain/ 資料夾的相對路徑
        if not model_path:
            model_path = os.path.join(BRAIN_DIR, "ppo_trading_lstm_updated.zip")
        self.model_path = model_path
        self.model = None
        self.is_loaded = False
        self.error_msg = ""
        
        self._load_model()

        
    def _load_model(self):
        if not SB3_AVAILABLE:
            self.error_msg = "尚未安裝 stable_baselines3，無法啟動 AI 引擎。"
            print(f"[ML Engine] SB3 not available: {self.error_msg}")
            return
            
        if not os.path.exists(self.model_path):
            self.error_msg = f"找不到訓練好的權重檔：{self.model_path}"
            print(f"[ML Engine] Model file not found: {self.model_path}")
            return
            
        try:
            print(f"[ML Engine] Loading model from: {self.model_path}")
            # 先嘗試匯入 LSTMFeatureExtractor，確保類別可被 cloudpickle 找到
            from models.feature_extractor import LSTMFeatureExtractor
            
            # 反推結果：hidden_size=128, features_dim=64, num_layers=2, input_features=10
            self.model = PPO.load(
                self.model_path,
                custom_objects={
                    "policy_kwargs": {
                        "features_extractor_class": LSTMFeatureExtractor,
                        "features_extractor_kwargs": {
                            "features_dim": 64,
                            "hidden_size": 128,
                            "num_layers": 2,
                        },
                        "net_arch": [64, 64],
                    }
                }
            )
            self.is_loaded = True
            print("[ML Engine] Model loaded successfully!")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ML Engine] LOAD FAILED:\n{tb}")
            self.error_msg = f"AI 權重載入失敗：{type(e).__name__}: {e}"
            
    def predict_action(self, df: pd.DataFrame, window_size=20) -> dict:
        """
        傳入最新的 yfinance Dataframe，輸出 AI 大腦神經網路的建議。
        """
        if not self.is_loaded:
            return {"action": "AI 引擎離線", "reason": self.error_msg}
            
        if len(df) < 60:
            return {"action": "資料不足", "reason": "需要至少 60 天的歷史K線供 AI 判讀宏觀位階。"}
            
        try:
            # =========================================================
            # 1. 完美重製訓練環境的特徵工程 (來自 preprocessor.py)
            # =========================================================
            df_feat = df.copy()
            df_feat['Prev_Close'] = df_feat['Close'].shift(1)
            
            rolling_max_60 = df_feat['Close'].rolling(window=60).max()
            rolling_min_60 = df_feat['Close'].rolling(window=60).min()
            df_feat['Macro_Pos_60'] = (df_feat['Close'] - rolling_min_60) / (rolling_max_60 - rolling_min_60 + 1e-8)
            
            rolling_max_20 = df_feat['Close'].rolling(window=20).max()
            rolling_min_20 = df_feat['Close'].rolling(window=20).min()
            df_feat['Macro_Pos_20'] = (df_feat['Close'] - rolling_min_20) / (rolling_max_20 - rolling_min_20 + 1e-8)
            
            rolling_max_252 = df_feat['Close'].rolling(window=252).max()
            rolling_min_252 = df_feat['Close'].rolling(window=252).min()
            df_feat['Macro_Pos_252'] = (df_feat['Close'] - rolling_min_252) / (rolling_max_252 - rolling_min_252 + 1e-8)
            
            df_feat['Norm_Open'] = (df_feat['Open'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            df_feat['Norm_High'] = (df_feat['High'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            df_feat['Norm_Low'] = (df_feat['Low'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            df_feat['Norm_Close'] = (df_feat['Close'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            
            df_feat['Norm_Volume'] = np.log1p(df_feat['Volume']) - np.log1p(df_feat['Volume'].shift(1))
            
            features = ['Norm_Open', 'Norm_High', 'Norm_Low', 'Norm_Close', 'Norm_Volume', 'Macro_Pos_60', 'Macro_Pos_20', 'Macro_Pos_252']
            feature_df = df_feat[features].fillna(0)
            
            # 取最後 window_size 根 K 線作為單次看盤視野 (Shape: 20x7)
            recent_obs = feature_df.iloc[-window_size:].values.astype(np.float32)
            
            # =========================================================
            # 2. 補齊強化學習環境 (trading_env.py) 的額外維度狀態
            # =========================================================
            # 模型期望 10 維輸入：8個技術特徵 + 2個環境狀態（空手/損益）
            extra = np.zeros((window_size, 2), dtype=np.float32)
            # 給 AI 最中立的初始觀點：目前空手(0)，未實現損益(0%)
            extra[:, 0] = 0.0
            extra[:, 1] = 0.0
            
            # 總維度與訓練時完美吻合 -> Shape: (20, 10)
            obs = np.hstack([recent_obs, extra]).astype(np.float32)
            
            # =========================================================
            # 3. 呼叫 LSTM 神經網路推論
            # =========================================================
            action, _states = self.model.predict(obs, deterministic=True)
            
            # 決定對應文字 (Action map 對照 trading_env.py)
            action_code = int(action)
            if action_code == 1:
                return {"action": "🔥 AI 建議做多 (Long)", "reason": "DRL 大腦判定當前時間切片期望值較高，建議進場做多。"}
            else:
                return {"action": "☕ AI 建議觀望 (Flat)", "reason": "LSTM 掃描無明確套利空間，建議保持空手。"}
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ML Engine ERROR]\n{tb}")
            return {"action": "推論異常", "reason": f"錯誤: {type(e).__name__}: {e}"}

if __name__ == "__main__":
    # 基本測試腳本
    engine = MLExpertEngine()
    print("模型是否載入成功:", engine.is_loaded)
    if not engine.is_loaded:
        print("錯誤訊息:", engine.error_msg)
