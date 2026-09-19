import os
import sys
import time
import json
import re
import logging
import requests

from permissions import PermissionManager
from market_data import (
    get_ticker_data,
    get_global_flows_data,
    get_sector_ranking_data,
    get_frontier_sector_data,
    get_crypto_overview_data,
    FRONTIER_SECTORS,
    CRYPTO_SECTORS,
    INSTITUTIONAL_FUNDS,
    get_fund_flows_data
)
from fsi_prompts import (
    FINANCIAL_ROLES,
    get_role_prompt,
    build_comps_prompt,
    build_dcf_prompt,
    build_lbo_prompt,
    build_earnings_prompt,
    build_onepager_prompt,
    build_global_flows_interpretation_prompt,
    build_sector_ranking_interpretation_prompt,
    build_frontier_sector_prompt,
    build_crypto_overview_prompt,
    build_trade_analysis_prompt,
    build_fund_flows_prompt
)
from llm_client import LLMClient, ALL_MODELS

# 日誌設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "bot.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

BOT_TOKEN = CONFIG["telegram_bot_token"]
OWNER_ID = CONFIG["owner_id"]
AI_CFG = CONFIG["ai_api"]

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# 初始化
default_model = CONFIG.get("active_model", "Gemini 3.8 Flash (Low)")
active_role = CONFIG.get("active_role", "market_researcher")

perms = PermissionManager(owner_id=OWNER_ID)
llm = LLMClient(
    base_url=AI_CFG["base_url"],
    api_key=AI_CFG["api_key"],
    default_model=default_model
)

COMMON_TICKERS = {
    # 股票
    "輝達": "NVDA", "英偉達": "NVDA", "nvda": "NVDA", "nvidia": "NVDA",
    "蘋果": "AAPL", "aapl": "AAPL", "apple": "AAPL",
    "微軟": "MSFT", "msft": "MSFT", "microsoft": "MSFT",
    "特斯拉": "TSLA", "tsla": "TSLA", "tesla": "TSLA",
    "谷歌": "GOOGL", "googl": "GOOGL", "google": "GOOGL", "goog": "GOOGL",
    "亞馬遜": "AMZN", "amzn": "AMZN", "amazon": "AMZN",
    "元宇宙": "META", "meta": "META", "臉書": "META", "facebook": "META",
    "台積電": "TSM", "tsm": "TSM", "2330": "2330.TW",
    "騰訊": "0700.HK", "0700": "0700.HK", "700": "0700.HK",
    "阿里": "BABA", "阿里巴巴": "BABA", "baba": "9988.HK", "9988": "9988.HK",
    "美團": "3690.HK", "3690": "3690.HK",
    "比亞迪": "1211.HK", "1211": "1211.HK",
    "奧克洛": "OKLO", "oklo": "OKLO",
    "nuscale": "SMR", "smr": "SMR",
    "ionq": "IONQ", "量子公司": "IONQ",
    "rigetti": "RGTI", "rgti": "RGTI",
    "crispr": "CRSP", "crsp": "CRSP",
    "quantumscape": "QS", "qs": "QS",
    "joby": "JOBY", "archer": "ACHR", "achr": "ACHR", "億航": "EH", "eh": "EH",
    # 加密貨幣
    "比特幣": "BTC-USD", "btc": "BTC-USD", "大餅": "BTC-USD",
    "以太坊": "ETH-USD", "以太幣": "ETH-USD", "eth": "ETH-USD",
    "索拉納": "SOL-USD", "sol": "SOL-USD",
    "幣安幣": "BNB-USD", "bnb": "BNB-USD",
    "狗狗幣": "DOGE-USD", "doge": "DOGE-USD",
    "near": "NEAR-USD", "render": "RENDER-USD",
    # 航運與國際貿易
    "以星": "ZIM", "以星航運": "ZIM", "zim": "ZIM",
    "美森": "MATX", "美森輪船": "MATX", "matx": "MATX",
    "波羅的海": "BDRY", "散貨運價": "BDRY", "bdry": "BDRY",
    "馬士基": "AMKBY", "maersk": "AMKBY",
    "中遠海控": "1919.HK", "中遠": "1919.HK", "1919": "1919.HK",
    # 頂級基金與機構代碼
    "波克夏": "BRK-B", "伯克希爾": "BRK-B", "巴菲特": "BRK-B", "brk": "BRK-B", "brk-b": "BRK-B",
    "木頭姐": "ARKK", "方舟基金": "ARKK", "ark": "ARKK", "arkk": "ARKK",
    "西方石油": "OXY", "oxy": "OXY",
    "安達保險": "CB", "cb": "CB",
    "新興市場": "IEMG", "iemg": "IEMG",
    "拼多多": "PDD", "pdd": "PDD"
}

PAGE_SIZE = 5

def save_config():
    try:
        CONFIG["active_model"] = llm.get_current_model()
        CONFIG["active_role"] = active_role
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"儲存配置失敗: {e}")

def extract_ticker(text: str) -> str:
    lower = text.lower().strip()
    for name, sym in COMMON_TICKERS.items():
        if name in lower or name in text:
            return sym
    
    match = re.search(r'\b([A-Za-z]{1,5}|[0-9]{4,5}\.[A-Za-z]{2}|[A-Za-z0-9]+-USD)\b', text)
    if match:
        cand = match.group(1).upper()
        if cand not in ["THE", "FOR", "AND", "CAN", "YOU", "WHAT", "HOW", "HELP", "BOT", "MODEL", "ROLE"]:
            return cand
    return ""

def format_telegram_tables(text: str) -> str:
    """
    手機直屏專用自適應排版引擎：
    將易在手機直屏嚴重擠壓、折行錯位的表格，自動轉換為 100% 垂直對齊、清爽易讀的【手機直屏結構化卡片流】
    """
    if "|" not in text and "┌" not in text:
        return text

    def flush_table_to_cards(tbl_lines):
        if not tbl_lines:
            return []
        rows = []
        for line in tbl_lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                stripped = stripped[1:-1]
            cells = [c.strip() for c in stripped.split("|")]
            # 過濾純分隔線
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                continue
            rows.append(cells)

        if len(rows) < 2:
            return tbl_lines

        headers = rows[0]
        data_rows = rows[1:]

        # 情況 A：兩欄式鍵值表單 (如 財務指標 | 數值)
        if len(headers) == 2:
            items = []
            for r in data_rows:
                if len(r) >= 2 and (r[0] or r[1]):
                    items.append(f"• *{r[0]}*：`{r[1]}`")
                elif len(r) == 1 and r[0]:
                    items.append(f"• *{r[0]}*")
            return ["\n" + "\n".join(items) + "\n"]

        # 情況 B：多欄同業/數據對比卡片
        cards = []
        for row_idx, r in enumerate(data_rows):
            if not any(r):
                continue
            first_col = r[0] if len(r) > 0 else f"項目 {row_idx+1}"
            second_col = r[1] if len(r) > 1 and len(headers) > 2 else ""

            if second_col and len(first_col) < 12 and not any(ch.isdigit() for ch in second_col):
                title = f"🏷️ *{first_col}* ({second_col})"
                start_idx = 2
            else:
                title = f"🏷️ *{first_col}*"
                start_idx = 1

            card_lines = [title]
            items = []
            for idx in range(start_idx, len(r)):
                val = r[idx]
                if not val:
                    continue
                h_name = headers[idx] if idx < len(headers) else f"指標{idx}"
                items.append(f"{h_name}: `{val}`")

            # 兩兩一組，手機直屏絕對不超寬折行
            for i in range(0, len(items), 2):
                chunk = items[i:i+2]
                card_lines.append("  • " + " ｜ ".join(chunk))

            cards.append("\n".join(card_lines))

        return ["\n" + "\n\n".join(cards) + "\n"]

    def _parse_boxed_table_to_cards(block_str):
        raw_lines = [l.strip() for l in block_str.split("\n") if l.strip() and not l.strip().startswith("```")]
        content_lines = []
        for l in raw_lines:
            if any(edge in l for edge in ["┌", "├", "└", "┬", "┼", "┴"]):
                continue
            if l.startswith("│") and l.endswith("│"):
                cells = [c.strip() for c in l[1:-1].split("│")]
                content_lines.append("| " + " | ".join(cells) + " |")
        if len(content_lines) >= 2:
            sep = "| " + " | ".join(["---"] * len(content_lines[0].split("|")[1:-1])) + " |"
            test_tbl = [content_lines[0], sep] + content_lines[1:]
            res = flush_table_to_cards(test_tbl)
            return "\n".join(res)
        return block_str

    # 1. 處理已存在的代碼框線表格，轉化為直屏卡片
    text = re.sub(r"```(?:text)?\s*[\n\r]+[┌├└│─┼┬┴\s\S]+?```", lambda m: _parse_boxed_table_to_cards(m.group(0)), text)

    # 2. 處理原生 markdown 表格
    lines = text.split("\n")
    new_lines = []
    table_buffer = []
    in_codeblock = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_codeblock = not in_codeblock
            if table_buffer:
                new_lines.extend(flush_table_to_cards(table_buffer))
                table_buffer = []
            new_lines.append(line)
            continue

        if not in_codeblock and stripped.startswith("|") and stripped.endswith("|"):
            table_buffer.append(line)
        else:
            if table_buffer:
                new_lines.extend(flush_table_to_cards(table_buffer))
                table_buffer = []
            new_lines.append(line)

    if table_buffer:
        new_lines.extend(flush_table_to_cards(table_buffer))

    return "\n".join(new_lines)

def send_message(chat_id: int, text: str, parse_mode: str = "Markdown", reply_markup: dict = None) -> bool:
    text = format_telegram_tables(text)
    url = f"{API_BASE}/sendMessage"
    max_len = 3800
    
    chunks = []
    while len(text) > max_len:
        split_idx = text.rfind("\n", 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip()
    chunks.append(text)
    
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        payload = {
            "chat_id": chat_id,
            "text": chunk
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if is_last and reply_markup:
            payload["reply_markup"] = reply_markup
            
        try:
            r = requests.post(url, json=payload, timeout=15)
            if not r.json().get("ok"):
                payload.pop("parse_mode", None)
                requests.post(url, json=payload, timeout=15)
        except Exception as e:
            logger.error(f"發送訊息失敗: {e}")
            return False
    return True

def edit_message(chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown", reply_markup: dict = None) -> bool:
    text = format_telegram_tables(text)
    url = f"{API_BASE}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        logger.error(f"編輯訊息失敗: {e}")
        return False

def answer_callback(callback_id: str, text: str = None, show_alert: bool = False):
    url = f"{API_BASE}/answerCallbackQuery"
    try:
        data = {"callback_query_id": callback_id}
        if text:
            data["text"] = text
            data["show_alert"] = show_alert
        requests.post(url, json=data, timeout=5)
    except Exception:
        pass

def send_chat_action(chat_id: int, action: str = "typing"):
    url = f"{API_BASE}/sendChatAction"
    try:
        requests.post(url, json={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass

# ── 角色專屬推薦小方塊與首頁面板生成區 ──────────────────────────

def make_home_buttons(user_id: int = 0) -> dict:
    current_model = llm.get_current_model()
    model_info = llm.get_model_info(current_model)
    model_short = model_info.get("name", current_model)[:11]

    role_info = next((r for r in FINANCIAL_ROLES if r["id"] == active_role), FINANCIAL_ROLES[0])
    role_badge = f"🎭 角色：{role_info['name'][:8]}"

    common_nav = [
        {"text": role_badge, "callback_data": "menu:role_picker"},
        {"text": f"🧠 模型：{model_short}", "callback_data": "menu:model_picker:0"}
    ]
    
    # 嚴格安全隔離：只有 Owner 能看到管理控制台按鈕
    if user_id and perms.is_owner(user_id):
        is_public = perms.is_public_mode()
        status_tag = "🟢對外開放" if is_public else "🔴僅管理員"
        common_bottom = [
            {"text": f"👥 權限與開關 [{status_tag}]", "callback_data": "act:users:self"},
            {"text": "🔄 刷新面板", "callback_data": "menu:home"}
        ]
    else:
        common_bottom = [
            {"text": "ℹ️ 關於 FinBot", "callback_data": "act:about:self"},
            {"text": "🔄 刷新面板", "callback_data": "menu:home"}
        ]

    # 1. 🌐 全球宏觀與資金流向策略首席 (market_researcher)
    if active_role == "market_researcher":
        buttons = [
            [
                {"text": "🌍 全球資金流動看板", "callback_data": "act:global_flows:market"},
                {"text": "📊 11大行業資金排名", "callback_data": "act:sector_ranking:market"}
            ],
            [
                {"text": "🏦 大型基金加倉動向 (13F)", "callback_data": "menu:fund_flows_picker"},
                {"text": "🪙 加密大盤與恐慌指數", "callback_data": "act:crypto_overview:market"}
            ],
            [
                {"text": "🚀 冷門高爆發前沿板塊", "callback_data": "menu:frontier_picker"},
                {"text": "⚡ 查龍頭 NVDA", "callback_data": "pick:NVDA"}
            ],
            common_nav,
            common_bottom
        ]

    # 2. 🪙 加密資產與 Web3 首席研究員 (crypto_analyst)
    elif active_role == "crypto_analyst":
        buttons = [
            [
                {"text": "🪙 加密大盤與恐慌指數", "callback_data": "act:crypto_overview:market"},
                {"text": "🤖 AI + Crypto 算力概念", "callback_data": "act:crypto_sector:ai_crypto"}
            ],
            [
                {"text": "⚡ 高性能公鏈 (Solana)", "callback_data": "act:crypto_sector:l1_l2"},
                {"text": "🏦 DeFi 去中心化質押", "callback_data": "act:crypto_sector:defi"}
            ],
            [
                {"text": "🐶 Meme 迷因情緒監控", "callback_data": "act:crypto_sector:meme"},
                {"text": "🏛️ 比特幣現貨 ETF 流向", "callback_data": "top:market:比特幣現貨ETF資金淨流入走勢"}
            ],
            [
                {"text": "⚡ 查比特幣 BTC", "callback_data": "pick:BTC-USD"},
                {"text": "💎 查以太坊 ETH", "callback_data": "pick:ETH-USD"}
            ],
            common_nav,
            common_bottom
        ]

    # 3. 💼 投行併購董事總經理 (pitch_agent)
    elif active_role == "pitch_agent":
        buttons = [
            [
                {"text": "📝 撰寫併購 Pitch 提案", "callback_data": "top:memo:戰略併購與控股收購提案"},
                {"text": "📑 投資一頁紙 One-Pager", "callback_data": "act:onepager:NVDA"}
            ],
            [
                {"text": "⚖️ 同業可比估值 Comps", "callback_data": "act:comps:AAPL"},
                {"text": "🎯 潛在買方與收購清單", "callback_data": "top:leaders:產業鏈核心並購標的"}
            ],
            [
                {"text": "⚡ 輝達 NVDA 估值", "callback_data": "pick:NVDA"},
                {"text": "🪙 Web3 企業併購估值", "callback_data": "act:crypto_overview:market"}
            ],
            common_nav,
            common_bottom
        ]

    # 4. 📐 華爾街量化與建模專家 (model_builder)
    elif active_role == "model_builder":
        buttons = [
            [
                {"text": "📐 現金流折現 DCF 模型", "callback_data": "act:dcf:NVDA"},
                {"text": "💰 槓桿收購 LBO 敏感度", "callback_data": "act:lbo:TSLA"}
            ],
            [
                {"text": "📑 3-Statement 三張表", "callback_data": "act:earnings:MSFT"},
                {"text": "⚖️ 估值倍數敏感度分析", "callback_data": "act:comps:NVDA"}
            ],
            [
                {"text": "⚡ 跑 NVDA DCF 測算", "callback_data": "act:dcf:NVDA"},
                {"text": "🚗 跑 TSLA 估值模型", "callback_data": "act:comps:TSLA"}
            ],
            common_nav,
            common_bottom
        ]

    # 5. 🔍 賣方股票研究首席 (earnings_reviewer)
    elif active_role == "earnings_reviewer":
        buttons = [
            [
                {"text": "📑 財報業績深度透視", "callback_data": "act:earnings:NVDA"},
                {"text": "⚡ 未來 2-4 季催化劑", "callback_data": "top:risks:未來業績催化劑與下行點"}
            ],
            [
                {"text": "🔍 毛利率受壓與庫存體檢", "callback_data": "act:quote:AAPL"},
                {"text": "📊 賣方評級與共識預期", "callback_data": "act:comps:MSFT"}
            ],
            [
                {"text": "🍎 蘋果 AAPL 業績會", "callback_data": "act:earnings:AAPL"},
                {"text": "⚡ 輝達 NVDA 財報透視", "callback_data": "act:earnings:NVDA"}
            ],
            common_nav,
            common_bottom
        ]

    # 6. 🏛️ 私募股權基金合夥人 (valuation_reviewer)
    elif active_role == "valuation_reviewer":
        buttons = [
            [
                {"text": "💰 退出回報 IRR/MoIC 測算", "callback_data": "act:lbo:NVDA"},
                {"text": "🏦 頂級基金13F動向", "callback_data": "menu:fund_flows_picker"}
            ],
            [
                {"text": "📋 投委會 IC Memo 審批", "callback_data": "top:memo:控股型收購IC備忘錄"},
                {"text": "🚀 挖掘冷門十倍標的", "callback_data": "menu:frontier_picker"}
            ],
            [
                {"text": "🏢 標的公司護城河評估", "callback_data": "act:onepager:NVDA"},
                {"text": "🛡️ 下行安全邊際審查", "callback_data": "act:dcf:AAPL"}
            ],
            common_nav,
            common_bottom
        ]

    # 7. 🛡️ 金融風控與合規總監 (risk_officer)
    elif active_role == "risk_officer":
        buttons = [
            [
                {"text": "⚠️ 標的潛在黑天鵝排查", "callback_data": "top:risks:標的下行風險與黑天鵝排查"},
                {"text": "📉 債務違約與流動性壓力", "callback_data": "act:quote:TSLA"}
            ],
            [
                {"text": "🏛️ 政策法規與反壟斷審查", "callback_data": "top:market:反壟斷監管與合規審查"},
                {"text": "🛡️ 穿透式盡調清單 (DD)", "callback_data": "top:memo:穿透式盡職調查清單"}
            ],
            [
                {"text": "🔍 排查 NVDA 估值泡沫", "callback_data": "act:comps:NVDA"},
                {"text": "🪙 加密合約清算擠兌風險", "callback_data": "act:crypto_overview:market"}
            ],
            common_nav,
            common_bottom
        ]

    # 8. 🚢 全球貿易與跨國供應鏈首席專家 (trade_expert)
    elif active_role == "trade_expert":
        buttons = [
            [
                {"text": "🚢 全球海運與運價指數 (SCFI/BDI)", "callback_data": "act:trade:海運運價指數與全球航線擁堵趨勢"},
                {"text": "📦 跨國關稅壁壘與出海合規", "callback_data": "act:trade:跨國關稅壁壘穿透與原產地規則"}
            ],
            [
                {"text": "🌐 墨西哥/越南近岸轉口外包", "callback_data": "act:trade:墨西哥越南近岸外包與轉口架構剖析"},
                {"text": "💱 匯率波動與外匯對沖 (FX)", "callback_data": "act:trade:跨境結算與多幣種外匯風險對沖方案"}
            ],
            [
                {"text": "🛢️ 關鍵大宗與能源貿易流向", "callback_data": "act:trade:關鍵大宗原物料與能源供應鏈安全評估"},
                {"text": "⚓ 紅海航道與地緣咽喉危機", "callback_data": "act:trade:紅海航道與重要海峽地緣風險應對"}
            ],
            [
                {"text": "⚡ 查航運以星 ZIM", "callback_data": "pick:ZIM"},
                {"text": "🚢 查美森輪船 MATX", "callback_data": "pick:MATX"}
            ],
            common_nav,
            common_bottom
        ]

    else:
        buttons = [
            [{"text": "🌍 全球資金流動", "callback_data": "act:global_flows:market"}],
            common_nav,
            common_bottom
        ]

    return {"inline_keyboard": buttons}

def get_home_text() -> str:
    r_info = next((r for r in FINANCIAL_ROLES if r["id"] == active_role), FINANCIAL_ROLES[0])
    return f"""🏛️ *FinBot 智能金融與宏觀投研顧問*
───────────────────────
👤 *當前執勤專家*：*{r_info['name']}*
💼 *英文頭銜*：`{r_info['title']}`
🎯 *專屬視角*：_{r_info['desc']}_

👇 *下方為你量身推薦的【{r_info['name'][:10]}】專屬工具小方塊*："""

def build_users_keyboard(is_owner: bool) -> dict:
    is_public = perms.is_public_mode()
    buttons = []
    if is_owner:
        if is_public:
            buttons.append([{"text": "🔒 臨時關閉對外開放 (僅限自己使用)", "callback_data": "act:toggle_pause:self"}])
        else:
            buttons.append([{"text": "🔓 開啟對外開放 (允許所有TG用戶使用)", "callback_data": "act:toggle_pause:self"}])
    
    buttons.append([
        {"text": "🔄 刷新名單與狀態", "callback_data": "act:users:self"},
        {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
    ])
    return {"inline_keyboard": buttons}

def get_users_panel_text() -> str:
    is_public = perms.is_public_mode()
    status_emoji = "🟢 對外開放中 (全體 TG 用戶可正常使用金融功能)" if is_public else "🔴 已臨時關閉對外開放 (僅 Owner 可用)"
    users = perms.list_users()
    
    lines = [
        "👥 *FinBot 用戶權限與系統安全控制台*",
        "───────────────────────",
        f"⚡ *當前模式*：*{status_emoji}*",
        f"👑 *超級管理員 (Owner)*：`{OWNER_ID}`",
        "───────────────────────",
        "🛡️ *本地安全防護機制*：*【已全面啟用】*",
        "• 已禁止外部用戶存取主機系統目錄與檔案",
        "• 已遮蔽 API Key、Token 與伺服器環境變數",
        "• 已鎖定純金融投研沙箱，阻斷非金融探測指令",
        "───────────────────────",
        "📋 *目前註冊用戶名單*："
    ]
    for uid, uinfo in users.items():
        tag = "👑 Owner" if str(uid) == str(OWNER_ID) else f"👤 {uinfo.get('role', 'user')}"
        lines.append(f"• ID: `{uid}` ({tag})")
    
    if not is_public:
        lines.append("\n⚠️ _注意：當前處於【臨時關閉/私有模式】。除管理員外，其他所有訪客的請求均已被安全暫停。_")
    else:
        lines.append("\n💡 _提示：Owner 可點擊上方按鈕隨時一鍵臨時切換對外開放/關閉。_")
        
    return "\n".join(lines)

def get_about_panel_text() -> str:
    return """🏛️ *FinBot 智能金融與宏觀投研顧問*
───────────────────────
歡迎使用 FinBot！本機器人專為高階金融投資者與研究員打造：

• 🌍 *全球宏觀流動性*：美元指數、美債殖利率、大類資產跨市場監控
• 📊 *行業板塊資金排名*：美股 11 大核心產業 ETF 強弱表現
• 🏦 *13F 機構聰明錢*：巴菲特波克夏、橋水、木頭姐最新持倉加倉動態
• 🚢 *全球貿易與供應鏈*：海運運價指數、跨國關稅壁壘與近岸轉口外包
• 🪙 *加密貨幣與 Web3*：大盤恐慌貪婪指數、算力板塊與現貨 ETF
• 🚀 *冷門高爆發硬科技*：可控核聚變、量子計算、基因治療、固態電池

💡 *操作提示*：點擊下方小方塊即可直接調閱實時行情與 100% 繁體中文深度研報！"""

def build_crypto_keyboard() -> dict:
    """加密貨幣專區小方塊選單"""
    buttons = [
        [{"text": "── 🪙 加密貨幣與 Web3 專題看板 ──", "callback_data": "noop"}],
        [
            {"text": "📊 加密大盤與恐慌貪婪指數", "callback_data": "act:crypto_overview:market"},
            {"text": "🤖 AI + Crypto 去中心化算力", "callback_data": "act:crypto_sector:ai_crypto"}
        ],
        [
            {"text": "⚡ 高性能公鏈 (Solana生態)", "callback_data": "act:crypto_sector:l1_l2"},
            {"text": "🏦 DeFi 去中心化借貸質押", "callback_data": "act:crypto_sector:defi"}
        ],
        [
            {"text": "🐶 Meme 迷因幣情緒指標", "callback_data": "act:crypto_sector:meme"},
            {"text": "🏛️ 比特幣現貨 ETF 資金淨流向", "callback_data": "top:market:比特幣現貨ETF機構淨流入分析"}
        ],
        [
            {"text": "⚡ 查比特幣 BTC", "callback_data": "pick:BTC-USD"},
            {"text": "💎 查以太坊 ETH", "callback_data": "pick:ETH-USD"}
        ],
        [
            {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"},
            {"text": "❌ 關閉選單", "callback_data": "menu:close"}
        ]
    ]
    return {"inline_keyboard": buttons}

def get_crypto_panel_text() -> str:
    return """🪙 *加密貨幣與 Web3 專屬板塊*
───────────────────────
即時追蹤加密市場流動性、鏈上巨鯨與細分熱門板塊：

• 📊 *恐慌與貪婪指數*：市場多空情緒與週期定錨
• 🤖 *AI + Crypto*：NEAR、RENDER、去中心化算力與鏈上 Agent
• ⚡ *高性能公鏈*：Solana、Sui 高並發低手續費生態
• 🏦 *DeFi 質押*：Uniswap、Aave 鏈上真實收益 (Real Yield)
• 🐶 *Meme 迷因幣*：DOGE、SHIB 市場流動性溢出風向標

👇 *點選下方方塊即刻取得實時行情與深度投研報告 (100% 繁體中文)*："""

def build_frontier_keyboard() -> dict:
    buttons = []
    buttons.append([{"text": "── 🚀 冷門高爆發前沿賽道選單 ──", "callback_data": "noop"}])
    sec_keys = list(FRONTIER_SECTORS.keys())
    for i in range(0, len(sec_keys), 2):
        row = []
        k1 = sec_keys[i]
        row.append({"text": FRONTIER_SECTORS[k1]["name"], "callback_data": f"act:frontier:{k1}"})
        if i + 1 < len(sec_keys):
            k2 = sec_keys[i + 1]
            row.append({"text": FRONTIER_SECTORS[k2]["name"], "callback_data": f"act:frontier:{k2}"})
        buttons.append(row)
        
    buttons.append([
        {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"},
        {"text": "❌ 關閉選單", "callback_data": "menu:close"}
    ])
    return {"inline_keyboard": buttons}

def get_frontier_panel_text() -> str:
    return """🚀 *冷門高爆發硬科技前沿賽道*
───────────────────────
精選具備「十倍至百倍爆發空間、處於技術突破前夕或商業化奇點」的前沿賽道：

• ⚛️ *可控核聚變與小堆 (SMR)*：AI 算力中心終極零碳能源
• 💻 *量子計算 (Quantum)*：指數級算力躍遷、密碼學與分子模擬
• 🧬 *基因編輯與合成生物*：CRISPR 臨床落地與細胞基因治療
• 🔋 *固態電池與次世代能源*：全固態鋰金屬電池量產裝車節點
• 🛸 *低空經濟與 eVTOL*：城市空中立體交通載人商業化開局
• 🤖 *具身智能與人形機器人*：端到端神經網路工廠規模化落地

👇 *點選下方賽道方塊，即刻取得實時行情與頂級創投深度剖析 (100% 繁體中文)*："""

def build_fund_flows_keyboard() -> dict:
    buttons = []
    buttons.append([{"text": "── 🏦 大型基金動向與 13F 機構加倉選單 ──", "callback_data": "noop"}])
    fund_keys = list(INSTITUTIONAL_FUNDS.keys())
    for i in range(0, len(fund_keys), 2):
        row = []
        k1 = fund_keys[i]
        row.append({"text": INSTITUTIONAL_FUNDS[k1]["name"][:18], "callback_data": f"act:fund_flows:{k1}"})
        if i + 1 < len(fund_keys):
            k2 = fund_keys[i + 1]
            row.append({"text": INSTITUTIONAL_FUNDS[k2]["name"][:18], "callback_data": f"act:fund_flows:{k2}"})
        buttons.append(row)
        
    buttons.append([
        {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"},
        {"text": "❌ 關閉選單", "callback_data": "menu:close"}
    ])
    return {"inline_keyboard": buttons}

def get_fund_flows_panel_text() -> str:
    return """🏦 *華爾街大型基金動向與 13F 聰明錢 (Smart Money) 看板*
───────────────────────
追蹤全球頂級機構投資人、傳奇對沖基金與大額 ETF 資金流向：

• 🏆 *頂級基金集體加倉榜*：數千家機構最新季度集中重倉買入的板塊
• 💼 *巴菲特波克夏 (Berkshire)*：現金儲備調配、能源/保險增持與蘋果減持
• 🌊 *橋水基金 (Bridgewater)*：全天候宏觀配置、新興市場與黃金/防禦股
• 🚀 *木頭姐方舟 (ARK Invest)*：破壞性硬科技、AI應用、加密資產抄底
• 🇨🇳 *頂級出海私募 (高瓴/景林)*：中概互聯網巨頭、跨境出海龍頭掃貨
• 📊 *機構 ETF 淨流向*：華爾街大額資金在科技/公用事業/能源等板塊的進出

👇 *請點擊下方小方塊，查看該機構/板塊之最新持倉剖析與實戰研報*："""

def build_role_keyboard() -> dict:
    buttons = []
    buttons.append([{"text": "── 🎭 選擇金融專家 Agent 角色 ──", "callback_data": "noop"}])
    for r in FINANCIAL_ROLES:
        rid = r["id"]
        is_active = (rid == active_role)
        prefix = "✓ " if is_active else "　 "
        buttons.append([{"text": f"{prefix}{r['name']}", "callback_data": f"set_role:{rid}"}])
        
    buttons.append([
        {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"},
        {"text": "❌ 關閉", "callback_data": "menu:close"}
    ])
    return {"inline_keyboard": buttons}

def get_role_panel_text() -> str:
    r_info = next((r for r in FINANCIAL_ROLES if r["id"] == active_role), FINANCIAL_ROLES[0])
    return f"""🎭 *金融專家 Agent 角色切換*
───────────────────────
當前執勤角色：*{r_info['name']}*
英文職稱：`{r_info['title']}`
核心職責：_{r_info['desc']}_

💡 點選下方方塊切換專家身分，*首頁將立即變換為該角色的專屬推薦方塊矩陣*！"""

def build_model_keyboard(page: int = 0) -> dict:
    current_model = llm.get_current_model()
    total_items = len(ALL_MODELS)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_items)
    page_items = ALL_MODELS[start_idx:end_idx]
    
    buttons = []
    buttons.append([{"text": f"── 🧠 AI 模型選擇器 (第 {page+1}/{total_pages} 頁) ──", "callback_data": "noop"}])
    
    for m in page_items:
        mid = m["id"]
        backend_tag = "⚡ AGY" if m.get("backend") == "agy" else "💻 API"
        is_active = (mid.lower() == current_model.lower())
        prefix = "✓ " if is_active else "　 "
        btn_text = f"{prefix}[{backend_tag}] {m['name']}"
        buttons.append([{"text": btn_text, "callback_data": f"set_model:{mid}:{page}"}])
    
    nav_row = []
    if page > 0:
        nav_row.append({"text": "⬅️ 上一頁", "callback_data": f"page_model:{page - 1}"})
    nav_row.append({"text": f"📄 {page + 1}/{total_pages}", "callback_data": "noop"})
    if page < total_pages - 1:
        nav_row.append({"text": "下一頁 ➡️", "callback_data": f"page_model:{page + 1}"})
    buttons.append(nav_row)
    
    buttons.append([
        {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"},
        {"text": "❌ 關閉選單", "callback_data": "menu:close"}
    ])
    return {"inline_keyboard": buttons}

def get_model_panel_text() -> str:
    current_model = llm.get_current_model()
    info = llm.get_model_info(current_model)
    backend_desc = "⚡ Antigravity 官方 CLI 原生驅動" if info.get("backend") == "agy" else "💻 高速 API 備援線路"
    
    return f"""🧠 *AI 模型選擇器（雙引擎：Antigravity + API）*
───────────────────────
當前啟用模型：*{info.get('name')}*
模型後端：`{backend_desc}`
模型說明：_{info.get('desc')}_

💡 支援雙引擎模型無縫切換（Antigravity 官方前沿推理模型與商用高速 API）。
點擊下方小方塊可立即切換模型："""

def make_ticker_buttons(symbol: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📊 實時報價", "callback_data": f"act:quote:{symbol}"},
                {"text": "⚖️ 同業估值 Comps", "callback_data": f"act:comps:{symbol}"}
            ],
            [
                {"text": "📐 現金流 DCF", "callback_data": f"act:dcf:{symbol}"},
                {"text": "💰 槓桿收購 LBO", "callback_data": f"act:lbo:{symbol}"}
            ],
            [
                {"text": "📑 財報解讀", "callback_data": f"act:earnings:{symbol}"},
                {"text": "🚀 一頁紙速覽", "callback_data": f"act:onepager:{symbol}"}
            ],
            [
                {"text": "🪙 加密貨幣專區", "callback_data": "menu:crypto_picker"},
                {"text": "🌍 全球資金流動", "callback_data": "act:global_flows:market"}
            ],
            [
                {"text": "🎭 切換專家角色", "callback_data": "menu:role_picker"},
                {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
            ]
        ]
    }

def make_topic_buttons(topic: str) -> dict:
    short_topic = topic[:20]
    return {
        "inline_keyboard": [
            [
                {"text": "🌐 產業鏈與競爭格局", "callback_data": f"top:market:{short_topic}"},
                {"text": "📝 投委會 Memo 提案", "callback_data": f"top:memo:{short_topic}"}
            ],
            [
                {"text": "🎯 賽道核心龍頭梳理", "callback_data": f"top:leaders:{short_topic}"},
                {"text": "⚠️ 核心下行風險剖析", "callback_data": f"top:risks:{short_topic}"}
            ],
            [
                {"text": "🪙 加密貨幣專區", "callback_data": "menu:crypto_picker"},
                {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
            ]
        ]
    }

def format_quote_card(data: dict) -> str:
    if not data.get("success"):
        return f"❌ 無法取得代號 `{data.get('symbol')}` 之行情數據: {data.get('error')}"
    
    return f"""📈 *{data.get('name')}* (`{data.get('symbol')}`)
───────────────────────
💵 *現價*：`{data.get('price')}`
📊 *市值*：`{data.get('market_cap')}`
📅 *52週區間*：`{data.get('52w_range')}`
───────────────────────
⚡ *估值倍數 (Multiples)*：
• 市盈率 (TTM / Fwd)：`{data.get('trailing_pe')} / {data.get('forward_pe')}`
• EV/EBITDA：`{data.get('ev_ebitda')}`
• 市銷率 (P/S)：`{data.get('ps_ratio')}`
• 市淨率 (P/B)：`{data.get('pb_ratio')}`
───────────────────────
💼 *財務體質*：
• 營收規模 (TTM)：`{data.get('revenue')}`
• 毛利率 / EBITDA率：`{data.get('gross_margins')} / {data.get('ebitda_margins')}`
• 自由現金流 (FCF)：`{data.get('free_cashflow')}`
• 賣方評級：*{data.get('recommendation')}*
"""

def execute_action(chat_id: int, action: str, target: str, user_id: int = 0):
    effective_user = user_id if user_id != 0 else chat_id
    send_chat_action(chat_id, "typing")
    current_system_prompt = get_role_prompt(active_role)
    
    # 1. 加密大盤與恐慌指數
    if action == "crypto_overview":
        send_message(chat_id, "⏳ 正在抓取加密貨幣恐慌與貪婪指數 (Fear & Greed) 及主流幣實時報價...")
        send_chat_action(chat_id, "typing")
        
        cdata = get_crypto_overview_data()
        if not cdata.get("success"):
            send_message(chat_id, f"❌ 抓取加密數據失敗: {cdata.get('error')}")
            return
            
        fng_val = cdata.get("fng_value", "50")
        fng_cls = cdata.get("fng_class", "Neutral")
        coins = cdata.get("coins", [])
        
        lines = [
            "🪙 *加密貨幣全域態勢與情緒指數看板*：",
            "───────────────────────",
            f"🧭 *恐慌與貪婪指數*：`{fng_val} / 100` — *{fng_cls}*",
            "───────────────────────",
            "📊 *主流加密資產實時行情*："
        ]
        for c in coins:
            sign = "+" if c["change_pct"] > 0 else ""
            lines.append(f"• *{c['name']}*：`${c['price']}` ({sign}{c['change_pct']}%)")
        lines.append("───────────────────────\n_🤖 正在以加密首席研究員視角生成週期研報 (100% 繁體中文)..._")
        
        send_message(chat_id, "\n".join(lines))
        send_chat_action(chat_id, "typing")
        
        prompt = build_crypto_overview_prompt(fng_val, fng_cls, coins)
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        followup = {
            "inline_keyboard": [
                [
                    {"text": "⚡ 查比特幣 BTC", "callback_data": "pick:BTC-USD"},
                    {"text": "💎 查以太坊 ETH", "callback_data": "pick:ETH-USD"}
                ],
                [
                    {"text": "🤖 AI+Crypto 賽道", "callback_data": "act:crypto_sector:ai_crypto"},
                    {"text": "⚡ 高性能公鏈 Solana", "callback_data": "act:crypto_sector:l1_l2"}
                ],
                [
                    {"text": "🪙 加密貨幣專區選單", "callback_data": "menu:crypto_picker"},
                    {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
                ]
            ]
        }
        send_message(chat_id, ans, reply_markup=followup)
        return

    # 2. 加密細分賽道
    elif action == "crypto_sector":
        sec = CRYPTO_SECTORS.get(target)
        if not sec:
            send_message(chat_id, f"❌ 未知的加密賽道: {target}")
            return
            
        send_message(chat_id, f"⏳ 正在拉取【{sec['name']}】鏈上代幣實時報價...")
        send_chat_action(chat_id, "typing")
        
        tickers_dict = sec["tickers"]
        lines = [f"{sec['name']} *實時行情*：", "───────────────────────"]
        for sym, name in tickers_dict.items():
            tdata = get_ticker_data(sym)
            if tdata.get("success"):
                lines.append(f"• *{name}* (`{sym}`)：`{tdata.get('price')}`")
            else:
                lines.append(f"• *{name}* (`{sym}`)：實時報價抓取中")
        lines.append("───────────────────────\n_🤖 正在剖析代幣經濟學、鏈上生態與催化劑 (100% 繁體中文)..._")
        
        send_message(chat_id, "\n".join(lines))
        send_chat_action(chat_id, "typing")
        
        prompt = f"""請以「加密資產與 Web3 首席研究員」視角，針對【{sec['name']}】賽道進行深度投研剖析：
賽道背景：{sec['desc']}
代表代幣：{', '.join(tickers_dict.values())}

請全程 100% 使用繁體中文輸出：
1. 🪙 【代幣賦能與經濟學 (Tokenomics)】：核心代幣價值捕獲機制、通脹解鎖壓力與質押收益率。
2. 🌊 【鏈上生態活躍度與 TVL 流向】：資金沉澱、用戶留存與競爭壁壘。
3. 🚀 【未來 3-6 個月爆發催化劑】：主網升級、代幣銷毀、交易所上幣或重磅合作。
4. ⚠️ 【合約代碼審計、巨鯨拋壓與監管風險】。
"""
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        btns = []
        row = []
        for sym, name in tickers_dict.items():
            row.append({"text": f"⚡ 查 {name[:8]}", "callback_data": f"pick:{sym}"})
            if len(row) == 2:
                btns.append(row)
                row = []
        if row:
            btns.append(row)
        btns.append([
            {"text": "🪙 加密貨幣專區", "callback_data": "menu:crypto_picker"},
            {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
        ])
        send_message(chat_id, ans, reply_markup={"inline_keyboard": btns})
        return

    # 3. 大型基金動向與 13F 機構加倉 (fund_flows)
    elif action == "fund_flows":
        fund_obj = INSTITUTIONAL_FUNDS.get(target)
        if not fund_obj:
            send_message(chat_id, f"❌ 未知的基金動向主題: {target}")
            return
            
        send_message(chat_id, f"⏳ 正在拉取【{fund_obj['name']}】最新 13F 持倉與成分股即時表現...")
        send_chat_action(chat_id, "typing")
        
        fdata = get_fund_flows_data(target)
        context_data = f"機構主題：{fund_obj['name']}\n主題定位：{fund_obj['desc']}\n核心加倉板塊與焦點：{fund_obj['key_themes']}\n"
        
        lines = [
            f"🏦 *{fund_obj['name']}* 最新持倉與板塊動態：",
            "───────────────────────",
            f"🎯 *機構定位*：_{fund_obj['desc']}_",
            f"💡 *核心方向*：`{fund_obj['key_themes']}`",
            "───────────────────────",
            "📊 *代表性標的最新行情*："
        ]
        if fdata.get("success") and fdata.get("data"):
            context_data += "關聯標的實時報價：\n"
            for item in fdata["data"]:
                sign = "+" if item["change_pct"] > 0 else ""
                lines.append(f"• *{item['name']}* (`{item['symbol']}`)：`${item['price']}` ({sign}{item['change_pct']}%)")
                context_data += f"- {item['name']} ({item['symbol']}): 現價 ${item['price']}, 當日漲跌 {sign}{item['change_pct']}%\n"
        else:
            for s, n in fund_obj.get("tickers", {}).items():
                lines.append(f"• *{n}* (`{s}`)")
        
        lines.append("───────────────────────\n_🤖 正在以對沖基金分析總監視角，解構 13F 聰明錢加倉邏輯 (100% 繁體中文)..._")
        send_message(chat_id, "\n".join(lines))
        send_chat_action(chat_id, "typing")
        
        prompt = build_fund_flows_prompt(fund_obj["name"], context_data)
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        pick_btns = []
        syms = list(fund_obj.get("tickers", {}).keys())
        if len(syms) >= 2:
            pick_btns.append([
                {"text": f"⚡ 查 {syms[0]}", "callback_data": f"pick:{syms[0]}"},
                {"text": f"⚡ 查 {syms[1]}", "callback_data": f"pick:{syms[1]}"}
            ])
        
        followup = {
            "inline_keyboard": pick_btns + [
                [
                    {"text": "🏆 頂級基金集體加倉榜", "callback_data": "act:fund_flows:top_sectors"},
                    {"text": "💼 巴菲特波克夏加倉動態", "callback_data": "act:fund_flows:berkshire"}
                ],
                [
                    {"text": "🌊 橋水基金宏觀配置", "callback_data": "act:fund_flows:bridgewater"},
                    {"text": "🚀 木頭姐 ARK 抄底清單", "callback_data": "act:fund_flows:ark_invest"}
                ],
                [
                    {"text": "🏦 基金動向完整選單", "callback_data": "menu:fund_flows_picker"},
                    {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
                ]
            ]
        }
        send_message(chat_id, f"🏦 *華爾街機構資金與 13F 聰明錢研報*：\n───────────────────────\n{ans}", reply_markup=followup)
        return

    # 4. 前沿板塊
    elif action == "frontier":
        sec_info = FRONTIER_SECTORS.get(target)
        if not sec_info:
            send_message(chat_id, f"❌ 未知的前沿賽道代號: {target}")
            return
            
        send_message(chat_id, f"⏳ 正在拉取【{sec_info['name']}】前沿代表性標的實時行情與產業鏈數據...")
        send_chat_action(chat_id, "typing")
        
        fdata = get_frontier_sector_data(target)
        data_list = fdata.get("data", [])
        
        lines = [f"{sec_info['name']} *核心代表標的實時看板*：", "───────────────────────"]
        for it in data_list:
            sign = "+" if it["change_pct"] > 0 else ""
            lines.append(f"• *{it['name']}* (`{it['symbol']}`)：`{it['price']} USD` ({sign}{it['change_pct']}%)")
        lines.append("───────────────────────\n_🤖 正在以當前專家視角生成深度研報 (100% 繁體中文)..._")
        
        send_message(chat_id, "\n".join(lines))
        send_chat_action(chat_id, "typing")
        
        prompt = build_frontier_sector_prompt(sec_info, data_list)
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        ticker_btns = []
        row = []
        for it in data_list[:4]:
            row.append({"text": f"⚡ 查 {it['symbol']}", "callback_data": f"pick:{it['symbol']}"})
            if len(row) == 2:
                ticker_btns.append(row)
                row = []
        if row:
            ticker_btns.append(row)
            
        ticker_btns.append([
            {"text": "🚀 換其他前沿賽道", "callback_data": "menu:frontier_picker"},
            {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
        ])
        
        send_message(chat_id, ans, reply_markup={"inline_keyboard": ticker_btns})
        return

    # 4. 全球資金流向
    elif action == "global_flows":
        send_message(chat_id, "⏳ 正在抓取全球核心資產最新報價與跨市場資金流動指標...")
        send_chat_action(chat_id, "typing")
        flow_res = get_global_flows_data()
        if not flow_res.get("success"):
            send_message(chat_id, f"❌ 抓取全球資金數據失敗: {flow_res.get('error')}")
            return
            
        data_list = flow_res.get("data", [])
        lines = ["🌍 *全球大類資產與資金流動監控看板*：", "───────────────────────"]
        for it in data_list:
            sign = "+" if it["change_pct"] > 0 else ""
            lines.append(f"• *{it['name']}*：`{it['price']}` ({sign}{it['change_pct']}%)")
        lines.append("───────────────────────\n_🤖 正在生成宏觀資金策略解讀 (100% 繁體中文)..._")
        
        send_message(chat_id, "\n".join(lines))
        send_chat_action(chat_id, "typing")
        
        prompt = build_global_flows_interpretation_prompt(data_list)
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        followup_markup = {
            "inline_keyboard": [
                [
                    {"text": "📊 看行業板塊排名", "callback_data": "act:sector_ranking:market"},
                    {"text": "🪙 加密大盤與恐慌", "callback_data": "act:crypto_overview:market"}
                ],
                [
                    {"text": "🎭 切換專家角色", "callback_data": "menu:role_picker"},
                    {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
                ]
            ]
        }
        send_message(chat_id, ans, reply_markup=followup_markup)
        return

    # 5. 行業板塊排名
    elif action == "sector_ranking":
        send_message(chat_id, "⏳ 正在拉取美股 11 大核心產業板塊 ETF 資金表現並生成強弱排行...")
        send_chat_action(chat_id, "typing")
        sec_res = get_sector_ranking_data()
        if not sec_res.get("success"):
            send_message(chat_id, f"❌ 抓取板塊數據失敗: {sec_res.get('error')}")
            return
            
        ranked = sec_res.get("data", [])
        lines = ["📊 *美股核心產業板塊資金強弱排名榜*：", "───────────────────────"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "1️⃣1️⃣", "1️⃣2️⃣"]
        for idx, it in enumerate(ranked):
            badge = medals[idx] if idx < len(medals) else "•"
            sign = "+" if it["change_pct"] > 0 else ""
            lines.append(f"{badge} *{it['name']}*：`{sign}{it['change_pct']}%` (價位: {it['price']})")
        lines.append("───────────────────────\n_🤖 正在生成板塊輪動與資金邏輯解讀 (100% 繁體中文)..._")
        
        send_message(chat_id, "\n".join(lines))
        send_chat_action(chat_id, "typing")
        
        prompt = build_sector_ranking_interpretation_prompt(ranked)
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        followup_markup = {
            "inline_keyboard": [
                [
                    {"text": "🌍 看全球資金流動", "callback_data": "act:global_flows:market"},
                    {"text": "🪙 看加密資產專區", "callback_data": "menu:crypto_picker"}
                ],
                [
                    {"text": "🎭 切換專家角色", "callback_data": "menu:role_picker"},
                    {"text": "🏠 返回專屬首頁", "callback_data": "menu:home"}
                ]
            ]
        }
        send_message(chat_id, ans, reply_markup=followup_markup)
        return

    # 6. 股票與加密貨幣報價
    elif action == "quote":
        tdata = get_ticker_data(target)
        msg = format_quote_card(tdata)
        send_message(chat_id, msg, reply_markup=make_ticker_buttons(target))
        return

    # 7. Comps
    elif action == "comps":
        send_message(chat_id, f"⏳ 正在拉取 `{target}` 市場同業數據並執行 Trading Comps 可比公司分析...")
        send_chat_action(chat_id, "typing")
        tdata = get_ticker_data(target)
        prompt = build_comps_prompt(tdata)
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_ticker_buttons(target))
        return

    # 8. DCF
    elif action == "dcf":
        send_message(chat_id, f"⏳ 正在提取 `{target}` 自由現金流並構建 DCF 敏感度折現模型...")
        send_chat_action(chat_id, "typing")
        tdata = get_ticker_data(target)
        prompt = build_dcf_prompt(tdata)
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_ticker_buttons(target))
        return

    # 9. LBO
    elif action == "lbo":
        send_message(chat_id, f"⏳ 正在以 PE Sponsor 視角試算 `{target}` LBO 槓桿收購投報模型...")
        send_chat_action(chat_id, "typing")
        tdata = get_ticker_data(target)
        prompt = build_lbo_prompt(tdata)
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_ticker_buttons(target))
        return

    # 10. Earnings
    elif action == "earnings":
        send_message(chat_id, f"⏳ 正在深度剖析 `{target}` 最新財報結構與利潤率質量...")
        send_chat_action(chat_id, "typing")
        tdata = get_ticker_data(target)
        prompt = build_earnings_prompt(tdata)
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_ticker_buttons(target))
        return

    # 11. One-Pager
    elif action == "onepager":
        send_message(chat_id, f"⏳ 正在為 `{target}` 生成投行標準 Executive One-Pager...")
        send_chat_action(chat_id, "typing")
        tdata = get_ticker_data(target)
        prompt = build_onepager_prompt(tdata)
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_ticker_buttons(target))
        return

    # 12. 專題研究
    elif action in ["market", "leaders", "risks"]:
        send_message(chat_id, f"⏳ 正在針對【{target}】進行深入產業分析...")
        send_chat_action(chat_id, "typing")
        if action == "market":
            prompt = f"請針對【{target}】執行深度產業概覽與競爭格局分析。包含：產業鏈分工、市場規模與 CAGR、龍頭護城河與技術壁壘。"
        elif action == "leaders":
            prompt = f"請梳理【{target}】賽道的前三大核心龍頭公司，對比各自商業模式、市場份額及財務特徵。"
        else:
            prompt = f"請剖析【{target}】領域未來 2-3 年的核心下行風險、政策不確定性與潛在黑天鵝因素。"
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_topic_buttons(target))
        return

    # 13. 併購 Memo
    elif action == "memo":
        send_message(chat_id, f"⏳ 正在為【{target}】草擬投資委員會備忘錄 (IC Memo)...")
        send_chat_action(chat_id, "typing")
        prompt = f"請針對【{target}】撰寫一份符合一線私募基金審核標準的「投資委員會備忘錄 (IC Memo)」。包含交易架構、戰略價值、回報推演與盡調清單。"
        ans = llm.chat_complete(current_system_prompt, prompt)
        send_message(chat_id, ans, reply_markup=make_topic_buttons(target))
        return

    # 14. 全球貿易與跨國供應鏈專題 (trade)
    elif action == "trade":
        send_message(chat_id, f"⏳ 正在調集全球航運運價、跨國關稅政策與近岸轉口數據，由【全球貿易與跨國供應鏈首席專家】深度剖析【{target}】...")
        send_chat_action(chat_id, "typing")
        prompt = build_trade_analysis_prompt(target)
        ans = llm.chat_complete(current_system_prompt, prompt)
        
        trade_markup = {
            "inline_keyboard": [
                [
                    {"text": "🚢 查以星航運 ZIM", "callback_data": "pick:ZIM"},
                    {"text": "📦 查美森輪船 MATX", "callback_data": "pick:MATX"}
                ],
                [
                    {"text": "🌐 墨西哥/越南近岸轉口外包", "callback_data": "act:trade:墨西哥越南近岸外包與轉口架構剖析"},
                    {"text": "💱 跨境外匯對沖方案", "callback_data": "act:trade:跨境結算與多幣種外匯風險對沖方案"}
                ],
                [
                    {"text": "🎭 切換其他專家角色", "callback_data": "menu:role_picker"},
                    {"text": "🏠 返回首頁", "callback_data": "menu:home"}
                ]
            ]
        }
        send_message(chat_id, f"🚢 *全球貿易與供應鏈實戰策略報告*：\n───────────────────────\n{ans}", reply_markup=trade_markup)
        return

    # 14. 關於 FinBot (普通用戶專屬)
    elif action == "about":
        send_message(chat_id, get_about_panel_text(), reply_markup=make_home_buttons(effective_user))
        return

    # 15. 用戶名單與安全控制台 (嚴格限制僅 Owner 可查閱)
    elif action == "users":
        if not perms.is_owner(effective_user):
            send_message(chat_id, "⛔ *權限不足*：用戶名單與系統安全開關僅供超級管理員 (Owner) 查閱，嚴禁外部存取。")
            return
        send_message(chat_id, get_users_panel_text(), reply_markup=build_users_keyboard(True))
        return

    # 16. 臨時對外開放開關切換 (僅限 Owner)
    elif action == "toggle_pause":
        if not perms.is_owner(effective_user):
            send_message(chat_id, "⛔ *權限不足*：只有超級管理員 (Owner) 具備切換對外開放狀態的權限！")
            return
            
        new_state = perms.toggle_public_mode()
        state_str = "🟢 已恢復【對外開放】模式（全體 TG 用戶可正常使用金融功能）" if new_state else "🔴 已切換為【臨時關閉/私有模式】（非 Owner 請求將被暫停）"
        send_message(chat_id, f"⚡ *系統開關變更通知*：\n───────────────────────\nFinBot 服務狀態現已切換為：\n*{state_str}*")
        send_message(chat_id, get_users_panel_text(), reply_markup=build_users_keyboard(True))
        return

def handle_callback(cb: dict):
    global active_role
    cb_id = cb["id"]
    from_user = cb["from"]["id"]
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    
    if not perms.is_authorized(from_user):
        if perms.is_paused():
            answer_callback(cb_id, "⏸️ 系統維護中：FinBot 目前已由管理員臨時關閉服務，僅管理員可用。", show_alert=True)
        else:
            answer_callback(cb_id, "⛔ 未授權的使用者", show_alert=True)
        return
    
    if data == "noop":
        answer_callback(cb_id)
        return

    # 加密貨幣專區選單
    if data == "menu:crypto_picker":
        answer_callback(cb_id)
        panel_text = get_crypto_panel_text()
        if message_id:
            edit_message(chat_id, message_id, panel_text, reply_markup=build_crypto_keyboard())
        else:
            send_message(chat_id, panel_text, reply_markup=build_crypto_keyboard())
        return

    # 基金與機構動向面板
    if data == "menu:fund_flows_picker":
        answer_callback(cb_id)
        panel_text = get_fund_flows_panel_text()
        if message_id:
            edit_message(chat_id, message_id, panel_text, reply_markup=build_fund_flows_keyboard())
        else:
            send_message(chat_id, panel_text, reply_markup=build_fund_flows_keyboard())
        return

    # 前沿賽道面板
    if data == "menu:frontier_picker":
        answer_callback(cb_id)
        panel_text = get_frontier_panel_text()
        if message_id:
            edit_message(chat_id, message_id, panel_text, reply_markup=build_frontier_keyboard())
        else:
            send_message(chat_id, panel_text, reply_markup=build_frontier_keyboard())
        return

    # 角色選擇面板
    if data == "menu:role_picker":
        answer_callback(cb_id)
        panel_text = get_role_panel_text()
        if message_id:
            edit_message(chat_id, message_id, panel_text, reply_markup=build_role_keyboard())
        else:
            send_message(chat_id, panel_text, reply_markup=build_role_keyboard())
        return

    # 切換專家角色
    if data.startswith("set_role:"):
        new_role = data.split(":", 1)[1]
        active_role = new_role
        save_config()
        r_info = next((r for r in FINANCIAL_ROLES if r["id"] == new_role), None)
        r_name = r_info["name"] if r_info else new_role
        answer_callback(cb_id, f"✅ 已切換為：{r_name}，專屬工具方塊已更新！")
        if message_id:
            edit_message(chat_id, message_id, get_home_text(), reply_markup=make_home_buttons())
        else:
            send_message(chat_id, get_home_text(), reply_markup=make_home_buttons())
        return

    # 模型選擇面板
    if data.startswith("menu:model_picker"):
        parts = data.split(":")
        page = int(parts[2]) if len(parts) > 2 else 0
        answer_callback(cb_id)
        panel_text = get_model_panel_text()
        if message_id:
            edit_message(chat_id, message_id, panel_text, reply_markup=build_model_keyboard(page))
        else:
            send_message(chat_id, panel_text, reply_markup=build_model_keyboard(page))
        return

    # 模型分頁導航
    if data.startswith("page_model:"):
        page = int(data.split(":")[1])
        answer_callback(cb_id)
        panel_text = get_model_panel_text()
        edit_message(chat_id, message_id, panel_text, reply_markup=build_model_keyboard(page))
        return

    # 設定模型
    if data.startswith("set_model:"):
        parts = data.split(":")
        new_model_id = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        
        llm.set_model(new_model_id)
        save_config()
        
        info = llm.get_model_info(new_model_id)
        answer_callback(cb_id, f"✅ 模型已切換為：{info.get('name')}")
        
        panel_text = get_model_panel_text()
        edit_message(chat_id, message_id, panel_text, reply_markup=build_model_keyboard(page))
        return

    # 回首頁與關閉
    if data == "menu:home":
        answer_callback(cb_id)
        if message_id:
            edit_message(chat_id, message_id, get_home_text(), reply_markup=make_home_buttons(from_user))
        else:
            send_message(chat_id, get_home_text(), reply_markup=make_home_buttons(from_user))
        return

    if data == "menu:close":
        answer_callback(cb_id, "選單已關閉")
        url = f"{API_BASE}/deleteMessage"
        requests.post(url, json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
        return

    answer_callback(cb_id)
    if data.startswith("pick:"):
        sym = data.split(":", 1)[1]
        msg_text = f"💡 已為你選中標的：*{sym}*\n請選擇你希望執行的金融分析模組："
        send_message(chat_id, msg_text, reply_markup=make_ticker_buttons(sym))
        return
        
    if data.startswith("act:"):
        _, action, target = data.split(":", 2)
        execute_action(chat_id, action, target, user_id=from_user)
        return
        
    if data.startswith("top:"):
        _, action, target = data.split(":", 2)
        execute_action(chat_id, action, target, user_id=from_user)
        return

def handle_message(update: dict):
    msg = update.get("message")
    if not msg or "text" not in msg:
        return
    
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg["text"].strip()
    
    if not perms.is_authorized(user_id):
        logger.warning(f"攔截請求（對外開放已關閉）: User ID {user_id}")
        send_message(chat_id, "⏸️ *系統維護中*：FinBot 目前處於【臨時關閉/私有模式】，暫不對外開放訪客使用，請稍後再試。")
        return

    # 🛡️ 本地安全防禦：防止外部用戶刺探本機系統、檔案與金鑰
    sensitive_probes = [
        "電腦路徑", "伺服器路徑", "查看文件", "讀取文件", "環境變數", "api_key", "apikey",
        "bot_token", "token是什麼", "終端指令", "執行命令", "bash", "cat /", "ls -",
        "whoami", "ipconfig", "ifconfig", "etc/passwd", "敏感資料", "管理員是誰", "獲取配置",
        "config.json", "permissions.json", "主機目錄", "硬盤"
    ]
    if any(p in text.lower() for p in sensitive_probes):
        send_message(chat_id, "🔒 *【系統安全保護機制已觸發】*：\n───────────────────────\nFinBot 僅專注於提供公開金融市場數據與投研分析服務。\n底層伺服器已全面沙箱化隔離，嚴禁查詢任何主機環境、本地檔案與系統敏感資訊。")
        return

    # 管理員開關指令 (僅限 Owner)
    if text.lower() in ["/pause", "關閉bot", "臨時關閉", "暫停bot", "關閉服務", "維護模式"] and perms.is_owner(user_id):
        perms.set_public_mode(False)
        send_message(chat_id, "🔒 *FinBot 已臨時關閉對外開放*！除管理員外，所有外部請求均已被安全暫停。", reply_markup=build_users_keyboard(True))
        return

    if text.lower() in ["/resume", "開啟bot", "恢復bot", "開放服務", "解除鎖定"] and perms.is_owner(user_id):
        perms.set_public_mode(True)
        send_message(chat_id, "🔓 *FinBot 已恢復對外開放*！所有 Telegram 訪客用戶可正常使用金融功能。", reply_markup=build_users_keyboard(True))
        return

    # 加密貨幣喚起詞
    if any(kw in text.lower() for kw in ["加密貨幣", "虛擬貨幣", "crypto", "比特幣", "以太坊", "恐慌指數", "web3", "代幣"]):
        if any(kw in text.lower() for kw in ["恐慌", "大盤", "行情", "指數", "加密貨幣"]):
            execute_action(chat_id, "crypto_overview", "market")
            return
        else:
            send_message(chat_id, get_crypto_panel_text(), reply_markup=build_crypto_keyboard())
            return

    # 前沿冷門賽道喚起
    if any(kw in text for kw in ["冷門", "高爆發", "前沿", "硬科技", "爆發賽道"]):
        send_message(chat_id, get_frontier_panel_text(), reply_markup=build_frontier_keyboard())
        return

    # 前沿單項賽道命中
    if any(kw in text for kw in ["核聚變", "核能", "小堆", "smr", "可控核聚變"]):
        execute_action(chat_id, "frontier", "fusion")
        return
    if any(kw in text for kw in ["量子", "量子電腦", "量子計算", "quantum"]):
        execute_action(chat_id, "frontier", "quantum")
        return
    if any(kw in text for kw in ["生物科技", "基因編輯", "合成生物", "crispr", "生技"]):
        execute_action(chat_id, "frontier", "biotech")
        return
    if any(kw in text for kw in ["固態電池", "新能源", "清潔能源", "次世代能源", "電池"]):
        execute_action(chat_id, "frontier", "cleantech")
        return
    if any(kw in text for kw in ["低空經濟", "飛行汽車", "evtol", "無人機"]):
        execute_action(chat_id, "frontier", "evtol")
        return
    if any(kw in text for kw in ["人形機器人", "具身智能", "機器人", "optimus"]):
        execute_action(chat_id, "frontier", "humanoid")
        return

    # 宏觀與排名
    if any(kw in text for kw in ["全球資金", "資金流動", "資金流向", "流動性", "大類資產"]):
        execute_action(chat_id, "global_flows", "market")
        return
        
    if any(kw in text for kw in ["行業排名", "板塊排名", "行業流動", "板塊流向", "板塊強弱", "行業表現"]):
        execute_action(chat_id, "sector_ranking", "market")
        return

    # 基金動向與機構 13F 加倉喚起
    if any(kw in text.lower() for kw in ["基金動向", "大型基金", "機構動向", "13f", "聰明錢", "smart money", "機構持倉", "機構買入", "買入什麼板塊", "基金買入", "機構加倉", "大佬持倉"]):
        if any(kw in text for kw in ["巴菲特", "波克夏", "berkshire"]):
            execute_action(chat_id, "fund_flows", "berkshire")
            return
        elif any(kw in text for kw in ["橋水", "達利歐", "bridgewater"]):
            execute_action(chat_id, "fund_flows", "bridgewater")
            return
        elif any(kw in text.lower() for kw in ["木頭姐", "方舟", "ark", "arkk"]):
            execute_action(chat_id, "fund_flows", "ark_invest")
            return
        elif any(kw in text for kw in ["中概", "出海私募", "高瓴", "景林"]):
            execute_action(chat_id, "fund_flows", "china_smart_money")
            return
        elif any(kw in text for kw in ["板塊", "集體加倉", "增持榜", "大量買入"]):
            execute_action(chat_id, "fund_flows", "top_sectors")
            return
        else:
            send_message(chat_id, get_fund_flows_panel_text(), reply_markup=build_fund_flows_keyboard())
            return

    # 全球貿易與跨國供應鏈
    if any(kw in text for kw in ["貿易", "關稅", "出海", "海運", "轉口", "近岸外包", "運價", "外貿", "貿易專家", "墨西哥工廠", "越南外包"]):
        execute_action(chat_id, "trade", text)
        return

    if text.lower() in ["/role", "role", "角色", "切換角色", "換角色"]:
        send_message(chat_id, get_role_panel_text(), reply_markup=build_role_keyboard())
        return

    if text.lower() in ["/model", "model", "模型", "換模型", "切換模型", "選擇模型"]:
        send_message(chat_id, get_model_panel_text(), reply_markup=build_model_keyboard(0))
        return

    if text.lower() in ["/start", "/help", "hi", "hello", "你好", "選單", "菜單"]:
        send_message(chat_id, get_home_text(), reply_markup=make_home_buttons(user_id))
        return

    if text.startswith("/auth ") and perms.is_owner(user_id):
        parts = text.split()
        if len(parts) > 1:
            new_id = parts[1]
            role = parts[2] if len(parts) > 2 else "user"
            perms.add_user(new_id, role=role)
            send_message(chat_id, f"✅ 已成功授權 ID: `{new_id}` 為 *{role}*。")
            return
            
    if text.startswith("/revoke ") and perms.is_owner(user_id):
        parts = text.split()
        if len(parts) > 1:
            perms.revoke_user(parts[1])
            send_message(chat_id, f"🗑️ 已移除 ID: `{parts[1]}`。")
            return

    # 標的辨識
    detected_ticker = extract_ticker(text)
    if detected_ticker:
        guide_text = f"🎯 辨識到你想研究的標的：*{detected_ticker}*\n請直接點選以下方塊進行分析："
        send_message(chat_id, guide_text, reply_markup=make_ticker_buttons(detected_ticker))
        return

    # 產業專題
    if len(text) < 30 and any(kw in text for kw in ["行業", "產業", "賽道", "晶片", "市場", "經濟", "概念", "投資", "併購"]):
        guide_text = f"🌐 辨識到你想探索的專題：*【{text}】*\n請直接點選以下分析模組："
        send_message(chat_id, guide_text, reply_markup=make_topic_buttons(text))
        return

    send_chat_action(chat_id, "typing")
    current_system_prompt = get_role_prompt(active_role)
    ans = llm.chat_complete(current_system_prompt, text)
    send_message(chat_id, ans, reply_markup=make_home_buttons())

def main():
    logger.info("FinBot 加密貨幣板塊 + 專屬角色矩陣全面上線...")
    offset = 0

    while True:
        try:
            url = f"{API_BASE}/getUpdates?offset={offset}&timeout=25"
            resp = requests.get(url, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        if "callback_query" in update:
                            handle_callback(update["callback_query"])
                        elif "message" in update:
                            handle_message(update)
                    except Exception as ex:
                        logger.error(f"處理更新異常: {ex}", exc_info=True)
            elif resp.status_code == 409:
                logger.warning("檢測到實例衝突，休眠 5 秒...")
                time.sleep(5)
            else:
                time.sleep(2)
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            logger.error(f"輪詢錯誤: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
