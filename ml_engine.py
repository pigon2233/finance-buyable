import sys
import os
import pandas as pd
import numpy as np

# 動態加入使用者的訓練環境路徑，以便 PPO.load 能正確解開自定義的 LSTMFeatureExtractor 類別
TRAIN_DIR = r"e:\coding\股票策略機器學習\finance stratigy learning"
if TRAIN_DIR not in sys.path:
    sys.path.append(TRAIN_DIR)

try:
    from stable_baselines3 import PPO
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False

class MLExpertEngine:
    """
    載入外部專案訓練完畢的「深度強化學習 (DRL)模型」，實現儀表板推論介接。
    """
    def __init__(self, model_path=r"e:\coding\股票策略機器學習\finance stratigy learning\models\saved\ppo_trading_lstm.zip"):
        self.model_path = model_path
        self.model = None
        self.is_loaded = False
        self.error_msg = ""
        
        self._load_model()
        
    def _load_model(self):
        if not SB3_AVAILABLE:
            self.error_msg = "尚未安裝 stable_baselines3，無法啟動 AI 引擎。"
            return
            
        if not os.path.exists(self.model_path):
            self.error_msg = f"找不到訓練好的權重檔：{self.model_path}"
            return
            
        try:
            # PPO.load 會自動利用 sys.path 去找自定義的 LSTMFeatureExtractor
            self.model = PPO.load(self.model_path)
            self.is_loaded = True
        except Exception as e:
            self.error_msg = f"AI 權重載入失敗：{e}"
            
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
            
            df_feat['Norm_Open'] = (df_feat['Open'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            df_feat['Norm_High'] = (df_feat['High'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            df_feat['Norm_Low'] = (df_feat['Low'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            df_feat['Norm_Close'] = (df_feat['Close'] - df_feat['Prev_Close']) / df_feat['Prev_Close']
            
            df_feat['Norm_Volume'] = np.log1p(df_feat['Volume']) - np.log1p(df_feat['Volume'].shift(1))
            
            features = ['Norm_Open', 'Norm_High', 'Norm_Low', 'Norm_Close', 'Norm_Volume', 'Macro_Pos_60', 'Macro_Pos_20']
            feature_df = df_feat[features].fillna(0)
            
            # 取最後 window_size 根 K 線作為單次看盤視野 (Shape: 20x7)
            recent_obs = feature_df.iloc[-window_size:].values.astype(np.float32)
            
            # =========================================================
            # 2. 補齊強化學習環境 (trading_env.py) 的額外維度狀態
            # =========================================================
            extra = np.zeros((window_size, 2), dtype=np.float32)
            # 假設給定 AI 最中立的初始觀點來作預測：目前空手 (0)，未實現損益 (0%)
            extra[:, 0] = 0.0
            extra[:, 1] = 0.0
            
            # 總維度與訓練時完美吻合 -> Shape: (20, 9)
            obs = np.hstack([recent_obs, extra]).astype(np.float32)
            
            # =========================================================
            # 3. 呼叫 LSTM 神經網路推論
            # =========================================================
            action, _states = self.model.predict(obs, deterministic=True)
            
            # 決定對應文字 (Action map 對照 trading_env.py)
            action_code = int(action)
            if action_code == 2:
                return {"action": "🔥 AI 強烈做多 (Long)", "reason": "DRL 大腦判定當前時間切片期望值極高，建議進場做多。"}
            elif action_code == 0:
                return {"action": "❄️ AI 轉空撤退 (Short)", "reason": "DRL 偵測到高度風險特徵，建議反手做空或清倉。"}
            else:
                return {"action": "☕ AI 建議觀望 (Flat)", "reason": "LSTM 掃描無明確套利空間，建議保持空手。"}
                
        except Exception as e:
            return {"action": "推論異常", "reason": f"擷取特徵時發生錯誤：{e}"}

if __name__ == "__main__":
    # 基本測試腳本
    engine = MLExpertEngine()
    print("模型是否載入成功:", engine.is_loaded)
    if not engine.is_loaded:
        print("錯誤訊息:", engine.error_msg)
