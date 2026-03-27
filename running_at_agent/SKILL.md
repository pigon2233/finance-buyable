# Finance Buyable - 股票技術分析 + AI 預測工具

快速掃描股票技術指標，輸出 DMPI、RSI、MACD、綜合指標與 AI 預測，幫助判讀買賣點。

## 功能

- **DMPI**: 自創動態市場壓力指數
- **RSI**: 相對強弱指標 (14天)
- **MACD**: 平滑異同移動平均線
- **綜合指標**: 結合趨勢與動能的進出場訊號
- **AI 預測**: 基於 PPO+LSTM 強化學習模型的買賣建議

## 使用方式

### 基本用法

在對話中直接輸入股票代碼：

```
2330.TW 2317.TW 3008.TW 2882.TW
```

系統會自動分析並輸出：

```
代碼     DMPI   RSI    MACD   趨勢  綜合  AI  結果
=================================================================
2330.TW  -7.0  39.8   11.80   盤整   觀   買  ☕觀
2317.TW  -1.0  26.4   -5.97   空頭   買   觀  ☕觀
3008.TW -14.2  40.4   -6.20   空頭   買   買  🔥買
6669.TW  -4.4  35.5  -31.74   空頭   買   買  🔥買
2882.TW   9.4  31.4   -1.05   空頭   賣   觀  🧹賣
```

### 結果判讀

| 符號 | 意義 |
|------|------|
| 🔥買 | 綜合指標說買 |
| 🧹賣 | 綜合指標說賣 |
| ☕觀 | 無明確訊號 |

### 趨勢判斷

| 趨勢 | 條件 |
|------|------|
| 多頭 | MACD > 0 且 MACD_Hist >= 0 |
| 空頭 | MACD < 0 且 MACD_Hist <= 0 |
| 盤整 | 其他情況 |

### 綜合指標邏輯

- **多頭趨勢**: DMPI 在 -15 ~ 27 之間為買，否則為賣
- **空頭趨勢**: DMPI 在 -40 ~ 5 之間為買，否則為賣
- **盤整趨勢**: RSI < 30 為買，RSI > 70 為賣

## 技術細節

### DMPI 計算公式

```
DMPI = (Net_Pressure * Volume_Factor) / Volatility_Penalty

其中:
- Net_Pressure = (Close-Low)/(High-Low) - (High-Close)/(High-Low)
- Volume_Factor = Volume / Moving_Average(Volume, 20)
- Volatility_Penalty = ATR(14) / Close
```

### AI 模型

- 模型: Stable-Baselines3 PPO + LSTM
- 輸入: 20天 K線數據 (8維技術特徵 + 2維環境狀態)
- 輸出: 做多 (Long) 或 觀望 (Flat)

## 注意事項

- 需要安裝依賴: `yfinance`, `pandas`, `numpy`, `stable-baselines3`, `gymnasium`
- 股票代碼格式: `2330.TW` (台股) 或 `AAPL` (美股)
- 建議使用 1年以上歷史數據進行分析
