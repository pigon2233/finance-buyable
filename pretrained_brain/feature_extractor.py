import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from gymnasium import spaces

class LSTMFeatureExtractor(BaseFeaturesExtractor):
    """
    自定義 LSTM 特徵提取器 for Stable Baselines3.
    由於我們傳入的觀察值是一個 2D 矩陣 (window_size, n_features)，
    將此序列傳入 LSTM 來提取時間序列特徵。
    """
    def __init__(self, observation_space: spaces.Box, features_dim: int = 128, hidden_size: int = 256, num_layers: int = 2):
        super(LSTMFeatureExtractor, self).__init__(observation_space, features_dim)
        
        # 觀察值形狀：(window_size, n_features)
        # 不過 SB3 PPO 預設輸入 shape 是 flatten 還是原樣？
        # 如果是 Box, shape 是 (window_size, n_features)，SB3 可能會保留此 shape 傳給我們。
        self.window_size, self.n_features = observation_space.shape
        
        # LSTM 輸入維度是 n_features
        self.lstm = nn.LSTM(
            input_size=self.n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True
        )
        
        # 經過 LSTM 之後，我們只取最後一個時間步的 hidden state
        self.linear = nn.Sequential(
            nn.Linear(hidden_size, features_dim),
            nn.ReLU()
        )
        
    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        # observations shape: (batch_size, window_size, n_features)
        
        # 由於 SB3 傳過來的 Tensor 可能是平坦化的 (Flatten)，我們需要確保它的形狀是正確的
        # 如果是 flatten 過的，我們需要 reshape
        if observations.dim() == 2:
            # 假設輸入被攤平了 (batch_size, window_size * n_features)
            observations = observations.view(-1, self.window_size, self.n_features)
            
        lstm_out, (h_n, c_n) = self.lstm(observations)
        
        # lstm_out shape: (batch_size, seq_len, hidden_size)
        # 取最後一個時間步的輸出: (batch_size, hidden_size)
        last_out = lstm_out[:, -1, :]
        
        # 傳入全連接層
        return self.linear(last_out)
