# 🏛️ FinBot - 全功能智能金融與宏觀投研 Telegram 機器人

FinBot 是一套基於金融服務大模型架構與現代化 Telegram 互動體驗打造的**高階金融分析助理機器人**。

系統捨棄傳統繁瑣的終端指令操作，全面採用**全自適應小方塊按鈕（Inline Keyboard）**交互模式。支援雙引擎模型切換、8 大華爾街與供應鏈專家角色隨選、全球資金流動性指標、美股 11 大行業資金排名、13F 頂級基金機構加倉追蹤、冷門硬科技高爆發板塊以及全球貿易與跨國供應鏈策略。

> **語言規範**：本專案所有金融投研報告、即時行情解析與決策建議，**100% 強制繁體中文輸出**。

---

## ✨ 核心亮點

### 1. 🔘 純按鈕小方塊互動模式 (No-CLI Experience)
- 進入機器人後，所有功能均以精心設計的按鈕矩陣呈現。
- **角色自適應推薦**：切換不同專家角色時，首頁推薦按鈕將自動蛻變為該專家的量身工具箱。
- 支援任意標的即時檢索、深度圖表與多維度估值模型一鍵觸發。

### 2. 🧠 雙引擎模型選擇器 (Antigravity + 高速 API)
- **原生 Antigravity 驅動**：深度整合 Google DeepMind 最新 `Gemini 3.8 Flash (Low)`、`Gemini 3.7 Thinking`、`Claude Sonnet 4.6`、`Claude Opus 4.6` 等前沿模型。
- **商用 API 雙備援**：支援 SenseNova 等高速商用 API 作為備用線路，具備自動降級 (Failover) 與重試機制。
- **分頁切換面板**：隨時在 Telegram 內透過按鈕切換推理模型。

### 3. 🎭 8 大華爾街與跨國智庫專家角色
| 專家角色 | 頭銜 | 專屬視角與核心工具 |
| :--- | :--- | :--- |
| **🌐 宏觀資金策略首席** | Chief Global Macro & Liquidity Strategist | 全球大類資產資金流向 (DXY/美債/黃金/原油)、美股 11 大行業強弱排名 |
| **🏦 頂級基金動向總監** | Head of Institutional Flows & 13F Strategy | SEC 13F 季報聰明錢 (Smart Money)、巴菲特/橋水/木頭姐加倉板塊透視 |
| **🚢 全球貿易供應鏈專家** | Chief Global Trade & Supply Chain Strategist | 跨國關稅壁壘穿透、墨西哥/越南近岸轉口外包、海運運價 (SCFI/BDI) 與外匯對沖 |
| **🪙 加密資產首席研究員** | Chief Crypto & Web3 Research Analyst | 恐慌貪婪指數 (Fear & Greed)、AI+Crypto 算力、高性能公鏈、比特幣現貨 ETF |
| **💼 投行併購董事總經理** | M&A Investment Banking Managing Director | 併購 Pitch 提案、投資一頁紙 (One-Pager)、同業可比估值 (Comps) |
| **📐 華爾街量化建模專家** | Wall Street Quantitative & Financial Modeler | 自由現金流折現 (DCF) 模型、槓桿收購 (LBO) 敏感度、三張財務報表深度拆解 |
| **🔍 賣方股票研究首席** | Head of Sell-Side Equity Research | 季報業績會解讀、庫存與毛利率健康度體檢、未來 2-4 季催化劑與共識預期 |
| **🏛️ 私募股權基金合夥人** | Private Equity Senior Partner | 退出回報 (IRR/MoIC) 測算、投委會 (IC Memo) 審批備忘錄、下行安全邊際審查 |
| **🛡️ 金融風控與合規總監** | Chief Risk & Compliance Officer | 黑天鵝排查、反壟斷與監管政策穿透、債務違約與流動性壓力測試 |

### 4. 🚀 前沿冷門高爆發硬科技板塊
針對處於商業化奇點前夕的前沿賽道，提供產業鏈透視與標的實時追蹤：
- ⚛️ **可控核聚變與小堆 (SMR)**：OKLO, NuScale (SMR)
- 💻 **量子計算 (Quantum)**：IONQ, Rigetti (RGTI)
- 🧬 **基因編輯與合成生物**：CRISPR Therapeutics (CRSP)
- 🔋 **固態電池與次世代能源**：QuantumScape (QS)
- 🛸 **低空經濟與 eVTOL**：Joby Aviation (JOBY), Archer (ACHR), 億航 (EH)
- 🤖 **具身智能與人形機器人**：特斯拉 Optimus 生態鏈

---

## 📂 專案目錄結構

```text
fin-bot/
├── bot.py                # 主程式：Telegram 輪詢調度、狀態機與方塊按鈕互動
├── market_data.py        # 數據引擎：yfinance、加密情緒 API、13F 基金與前沿板塊字典
├── fsi_prompts.py        # 投研 Prompt 庫：嚴格約束 100% 繁體中文與專家角色系統提示詞
├── llm_client.py         # 雙引擎 LLM 客戶端：支援 agy 原生引擎與 SenseNova API Failover
├── permissions.py        # 權限與白名單管理：防止未授權存取
├── config.example.json   # 設定檔範本
├── requirements.txt      # Python 相依套件
├── start.sh              # 常駐後台啟動腳本
├── stop.sh               # 服務停止腳本
├── status.sh             # 狀態監控與日誌檢查腳本
└── README.md             # 說明文件
```

---

## 🛠️ 快速開始

### 1. 安裝環境依賴

```bash
git clone https://github.com/whypuss/fin-bot.git
cd fin-bot
pip install -r requirements.txt
```

### 2. 配置金鑰與參數

複製設定檔範本：
```bash
cp config.example.json config.json
```

編輯 `config.json`：
```json
{
  "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
  "owner_id": 123456789,
  "ai_api": {
    "base_url": "https://token.sensenova.cn/v1",
    "api_key": "YOUR_API_KEY",
    "model": "sensenova-6.8-flash-lite"
  },
  "active_model": "sensenova/sensenova-6.8-flash-lite",
  "active_role": "market_researcher"
}
```

### 3. 運行與守護

```bash
# 賦予執行權限
chmod +x *.sh

# 啟動後台常駐服務
./start.sh

# 查看運行狀態與即時日誌
./status.sh

# 停止服務
./stop.sh
```

---

## 🔒 安全與隱私保護

- 本專案已透過 `.gitignore` 排除 `config.json`、`permissions.json` 及所有日誌檔案。
- 預設具備白名單驗證機制（Owner 模式），只有授權之 Telegram ID 才能向機器人發出分析請求，確保 API 額度與隱私安全。

---

## 📄 開源授權

本專案採用 [MIT License](LICENSE) 授權。
