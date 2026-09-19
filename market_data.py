import yfinance as yf
import pandas as pd

def get_ticker_data(symbol: str) -> dict:
    """抓取指定股票代號的實時行情與財務指標"""
    try:
        clean_sym = symbol.strip().upper()
        ticker = yf.Ticker(clean_sym)
        info = ticker.info
        
        name = info.get("shortName") or info.get("longName") or clean_sym
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        currency = info.get("currency", "USD")
        market_cap = info.get("marketCap", 0)
        trailing_pe = info.get("trailingPE", "N/A")
        forward_pe = info.get("forwardPE", "N/A")
        ev_ebitda = info.get("enterpriseToEbitda", "N/A")
        ps_ratio = info.get("priceToSalesTrailing12Months", "N/A")
        pb_ratio = info.get("priceToBook", "N/A")
        revenue = info.get("totalRevenue", 0)
        gross_margins = info.get("grossMargins", 0)
        ebitda_margins = info.get("ebitdaMargins", 0)
        debt_to_equity = info.get("debtToEquity", "N/A")
        free_cashflow = info.get("freeCashflow", "N/A")
        recommendation = info.get("recommendationKey", "N/A")
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", 0)
        fifty_two_week_low = info.get("fiftyTwoWeekLow", 0)

        def fmt_curr(val):
            if isinstance(val, (int, float)):
                if val >= 1e12:
                    return f"{val/1e12:.2f}T {currency}"
                elif val >= 1e9:
                    return f"{val/1e9:.2f}B {currency}"
                elif val >= 1e6:
                    return f"{val/1e6:.2f}M {currency}"
                return f"{val:,.2f} {currency}"
            return str(val)

        def fmt_pct(val):
            if isinstance(val, (int, float)):
                return f"{val*100:.2f}%"
            return str(val)

        return {
            "success": True,
            "symbol": clean_sym,
            "name": name,
            "price": f"{price} {currency}",
            "market_cap": fmt_curr(market_cap),
            "52w_range": f"{fifty_two_week_low} - {fifty_two_week_high} {currency}",
            "trailing_pe": f"{trailing_pe:.2f}" if isinstance(trailing_pe, (int, float)) else str(trailing_pe),
            "forward_pe": f"{forward_pe:.2f}" if isinstance(forward_pe, (int, float)) else str(forward_pe),
            "ev_ebitda": f"{ev_ebitda:.2f}" if isinstance(ev_ebitda, (int, float)) else str(ev_ebitda),
            "ps_ratio": f"{ps_ratio:.2f}" if isinstance(ps_ratio, (int, float)) else str(ps_ratio),
            "pb_ratio": f"{pb_ratio:.2f}" if isinstance(pb_ratio, (int, float)) else str(pb_ratio),
            "revenue": fmt_curr(revenue),
            "gross_margins": fmt_pct(gross_margins),
            "ebitda_margins": fmt_pct(ebitda_margins),
            "debt_to_equity": str(debt_to_equity),
            "free_cashflow": fmt_curr(free_cashflow),
            "recommendation": str(recommendation).upper()
        }
    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "error": str(e)
        }

def get_global_flows_data() -> dict:
    """抓取全球主要資產、美元流動性與避險指標"""
    assets = {
        "DX-Y.NYB": "美元指數 (DXY)",
        "^TNX": "美債10年殖利率",
        "^GSPC": "標普500 (美股)",
        "^IXIC": "納斯達克 (科技股)",
        "^N225": "日經225 (日股)",
        "^HSI": "恆生指數 (港股)",
        "GC=F": "黃金現貨 (避險)",
        "CL=F": "WTI原油 (大宗)",
        "BTC-USD": "比特幣 (流動性偏好)"
    }
    
    results = []
    try:
        tickers = list(assets.keys())
        df = yf.download(tickers, period="5d", progress=False)["Close"]
        
        for sym, name in assets.items():
            try:
                series = df[sym].dropna()
                if len(series) >= 2:
                    curr = series.iloc[-1]
                    prev = series.iloc[-2]
                    chg_pct = ((curr - prev) / prev) * 100
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "price": round(float(curr), 2),
                        "change_pct": round(float(chg_pct), 2)
                    })
            except Exception:
                continue
        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_sector_ranking_data() -> dict:
    """抓取美股 11 大核心產業板塊 ETF 表現並按強弱排序（行業資金流向）"""
    sectors = {
        "XLK": "資訊科技 (Technology)",
        "SOXX": "半導體晶片 (Semiconductor)",
        "XLC": "通訊服務 (Communication)",
        "XLF": "金融銀行 (Financials)",
        "XLV": "醫療保健 (Healthcare)",
        "XLE": "能源石油 (Energy)",
        "XLI": "工業製造 (Industrials)",
        "XLY": "非必需消費 (Consumer Disc)",
        "XLP": "必需消費品 (Consumer Staples)",
        "XLB": "基礎材料 (Materials)",
        "XLU": "公用事業 (Utilities)",
        "XLRE": "房地產信託 (Real Estate)"
    }
    
    results = []
    try:
        tickers = list(sectors.keys())
        df = yf.download(tickers, period="5d", progress=False)["Close"]
        
        for sym, name in sectors.items():
            try:
                series = df[sym].dropna()
                if len(series) >= 2:
                    curr = series.iloc[-1]
                    prev = series.iloc[-2]
                    chg_pct = ((curr - prev) / prev) * 100
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "price": round(float(curr), 2),
                        "change_pct": round(float(chg_pct), 2)
                    })
            except Exception:
                continue
                
        results.sort(key=lambda x: x["change_pct"], reverse=True)
        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── 冷門高爆發前沿板塊標的定義 ────────────────────────────────────

FRONTIER_SECTORS = {
    "fusion": {
        "id": "fusion",
        "name": "⚛️ 可控核聚變與模組化小堆 (SMR)",
        "desc": "AI 算力中心對零碳基荷電力極限需求催生之世紀能源革命",
        "tickers": {"OKLO": "Oklo (奧克洛快堆)", "SMR": "NuScale Power", "NNE": "Nano Nuclear", "CCJ": "Cameco (鈾礦龍頭)"}
    },
    "quantum": {
        "id": "quantum",
        "name": "💻 量子計算 (Quantum Computing)",
        "desc": "突破摩爾定律極限之指數級算力躍遷，抗量子加密與新藥合成",
        "tickers": {"IONQ": "IonQ (離子阱量子)", "RGTI": "Rigetti Computing", "QBTS": "D-Wave (量子退火)", "QUBT": "Quantum Computing Inc"}
    },
    "biotech": {
        "id": "biotech",
        "name": "🧬 基因編輯與合成生物學 (Biotech & CRISPR)",
        "desc": "CRISPR 體內編輯臨床落地、AI 蛋白質設計與細胞基因治療",
        "tickers": {"CRSP": "CRISPR Therapeutics", "BEAM": "Beam Therapeutics", "NTLA": "Intellia Therapeutics", "XBI": "標普生技ETF"}
    },
    "cleantech": {
        "id": "cleantech",
        "name": "🔋 固態電池與次世代能源",
        "desc": "全固態鋰金屬電池量產節點、千公里續航與鈣鈦礦光伏",
        "tickers": {"QS": "QuantumScape (固態鋰電)", "SLDP": "Solid Power", "ENPH": "Enphase Energy", "ICLN": "清潔能源ETF"}
    },
    "evtol": {
        "id": "evtol",
        "name": "🛸 低空經濟與 eVTOL 飛行汽車",
        "desc": "城市立體交通、各國適航認證商業化載人運營開局之年",
        "tickers": {"JOBY": "Joby Aviation", "ACHR": "Archer Aviation", "EH": "億航智能 (無人駕駛eVTOL)"}
    },
    "humanoid": {
        "id": "humanoid",
        "name": "🤖 具身智能與人形機器人",
        "desc": "端到端大模型驅動實體機器人、工廠打螺絲與商業服務規模化",
        "tickers": {"TSLA": "特斯拉 (Optimus)", "SYM": "Symbotic (倉儲機器人)", "ISRG": "直覺外科 (達文西手術機器人)"}
    }
}

def get_frontier_sector_data(sector_key: str) -> dict:
    """抓取指定前沿賽道的即時標的報價與漲跌表現"""
    sec = FRONTIER_SECTORS.get(sector_key)
    if not sec:
        return {"success": False, "error": f"找不到前沿板塊: {sector_key}"}
        
    tickers_dict = sec["tickers"]
    tickers = list(tickers_dict.keys())
    results = []
    
    try:
        df = yf.download(tickers, period="5d", progress=False)["Close"]
        for sym, name in tickers_dict.items():
            try:
                series = df[sym].dropna()
                if len(series) >= 2:
                    curr = series.iloc[-1]
                    prev = series.iloc[-2]
                    chg_pct = ((curr - prev) / prev) * 100
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "price": round(float(curr), 2),
                        "change_pct": round(float(chg_pct), 2)
                    })
            except Exception:
                continue
        return {
            "success": True,
            "sector": sec,
            "data": results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── 加密貨幣與 Web3 賽道 ──────────────────────────────────────────

CRYPTO_SECTORS = {
    "ai_crypto": {
        "id": "ai_crypto",
        "name": "🤖 AI + Crypto 算力與去中心化大模型",
        "desc": "去中心化 GPU 算力租賃、AI 數據標註與自主鏈上 Agent",
        "tickers": {"NEAR-USD": "NEAR Protocol", "RENDER-USD": "Render (去中心化算力)", "TAO-USD": "Bittensor (去中心化AI)"}
    },
    "l1_l2": {
        "id": "l1_l2",
        "name": "⚡ 高性能公鏈 (Solana / Layer 2)",
        "desc": "百萬級高並發 TPS、極低 Gas 費用與新一代生態公鏈",
        "tickers": {"SOL-USD": "Solana (高並發公鏈)", "BNB-USD": "BNB Chain"}
    },
    "defi": {
        "id": "defi",
        "name": "🏦 DeFi 去中心化金融與借貸質押",
        "desc": "去中心化交易所、鏈上借貸協議、超額質押與真實收益 (Real Yield)",
        "tickers": {"UNI7083-USD": "Uniswap", "AAVE-USD": "Aave (去中心化借貸)"}
    },
    "meme": {
        "id": "meme",
        "name": "🐶 Meme 迷因幣與鏈上流動性風向標",
        "desc": "社群共識、注意力經濟與牛市流動性溢出最敏感溫度計",
        "tickers": {"DOGE-USD": "狗狗幣 Dogecoin", "SHIB-USD": "柴犬幣 Shiba Inu"}
    }
}

def get_crypto_overview_data() -> dict:
    """獲取加密大盤、恐慌貪婪指數與主流幣實時表現"""
    import requests
    # 1. 恐慌貪婪指數
    fng_val = "50"
    fng_class = "中性 (Neutral)"
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if r.status_code == 200:
            d = r.json().get("data", [])
            if d:
                fng_val = d[0].get("value", "50")
                fng_class = d[0].get("value_classification", "Neutral")
    except Exception:
        pass

    # 2. 核心主流幣
    main_tickers = {
        "BTC-USD": "比特幣 (Bitcoin)",
        "ETH-USD": "以太坊 (Ethereum)",
        "SOL-USD": "Solana (索拉納)",
        "BNB-USD": "幣安幣 (BNB)",
        "DOGE-USD": "狗狗幣 (Dogecoin)"
    }
    
    results = []
    try:
        tickers = list(main_tickers.keys())
        df = yf.download(tickers, period="5d", progress=False)["Close"]
        for sym, name in main_tickers.items():
            try:
                series = df[sym].dropna()
                if len(series) >= 2:
                    curr = series.iloc[-1]
                    prev = series.iloc[-2]
                    chg_pct = ((curr - prev) / prev) * 100
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "price": round(float(curr), 4) if curr < 1 else round(float(curr), 2),
                        "change_pct": round(float(chg_pct), 2)
                    })
            except Exception:
                continue
        return {
            "success": True,
            "fng_value": fng_val,
            "fng_class": fng_class,
            "coins": results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── 大型基金與 13F 機構資金動向 ──────────────────────────────────────────

INSTITUTIONAL_FUNDS = {
    "top_sectors": {
        "id": "top_sectors",
        "name": "🏆 頂級基金最新季度集體加倉板塊 (13F)",
        "desc": "華爾街數千家對沖基金與資產管理巨頭集體淨增持最多的板塊龍頭",
        "key_themes": "AI算力基礎設施、獨立電力公用事業、減肥藥GLP-1、國防軍工",
        "tickers": {
            "NVDA": "輝達 (AI算力)",
            "CEG": "星座能源 (核電/AI數據中心供電)",
            "LLY": "禮來 (GLP-1減肥藥)",
            "JPM": "摩根大通 (金融防禦)"
        }
    },
    "berkshire": {
        "id": "berkshire",
        "name": "💼 巴菲特波克夏·海瑟威 (Berkshire Hathaway)",
        "desc": "股神最新持倉、高額現金儲備去向、加倉能源/保險與減持科技動態",
        "key_themes": "西方石油增持、巨額短期美債配置、安達保險建倉、蘋果減持節奏",
        "tickers": {
            "BRK-B": "波克夏 B 股",
            "OXY": "西方石油 (連續增持)",
            "CB": "安達保險 (隱密重倉)",
            "AAPL": "蘋果 (第一大持倉)"
        }
    },
    "bridgewater": {
        "id": "bridgewater",
        "name": "🌊 橋水基金 (Bridgewater Associates)",
        "desc": "全球最大對沖基金宏觀配置、全天候抗通脹資產與新興市場掃貨動態",
        "key_themes": "新興市場核心指數 ETF、大型科技龍頭、防禦性醫療與黃金配置",
        "tickers": {
            "IEMG": "核心新興市場 ETF",
            "IVV": "標普 500 ETF",
            "GOOGL": "谷歌 Alphabet",
            "GLD": "黃金信託 ETF"
        }
    },
    "ark_invest": {
        "id": "ark_invest",
        "name": "🚀 木頭姐方舟投資 (ARK Invest)",
        "desc": "破壞性創新顛覆者、高頻調倉、硬科技與加密資產抄底動態",
        "key_themes": "特斯拉加倉波段、Coinbase加密敞口、Palantir大數據AI、基因編輯CRISPR",
        "tickers": {
            "ARKK": "ARK 旗艦創新 ETF",
            "TSLA": "特斯拉 (第一權重)",
            "COIN": "Coinbase (加密券商)",
            "PLTR": "Palantir (企業級AI)"
        }
    },
    "china_smart_money": {
        "id": "china_smart_money",
        "name": "🇨🇳 頂級中概與華人出海私募 (高瓴/景林/高毅)",
        "desc": "頂級出海美元基金在美股中概、跨境電商出海龍頭的大筆調倉",
        "key_themes": "拼多多Temu出海增持、阿里騰訊電商回購、網易防禦、網聯科技平台",
        "tickers": {
            "PDD": "拼多多 Temu 出海",
            "BABA": "阿里巴巴",
            "NTES": "網易",
            "FUTU": "富途控股"
        }
    },
    "etf_sector_inflows": {
        "id": "etf_sector_inflows",
        "name": "📊 機構 ETF 巨額資金淨流向排行榜",
        "desc": "機構投資人於各大美股行業 ETF 的單週/單月淨申購與資金抽離",
        "key_themes": "科技XLK、公用事業XLU、金融XLF、生物科技XBI資金進出",
        "tickers": {
            "XLK": "科技板塊 ETF",
            "XLU": "公用事業板塊 (AI供電)",
            "XLF": "金融板塊 ETF",
            "XBI": "生物科技 ETF"
        }
    }
}

def get_fund_flows_data(topic_id: str) -> dict:
    """獲取指定基金主題核心成分股即時行情"""
    fund_info = INSTITUTIONAL_FUNDS.get(topic_id)
    if not fund_info:
        return {"success": False, "error": f"找不到機構主題: {topic_id}"}
    
    tickers_dict = fund_info.get("tickers", {})
    results = []
    try:
        symbols = list(tickers_dict.keys())
        df = yf.download(symbols, period="5d", progress=False)["Close"]
        for sym, name in tickers_dict.items():
            try:
                series = df[sym].dropna()
                if len(series) >= 2:
                    curr = series.iloc[-1]
                    prev = series.iloc[-2]
                    chg_pct = ((curr - prev) / prev) * 100
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "price": round(float(curr), 2),
                        "change_pct": round(float(chg_pct), 2)
                    })
            except Exception:
                continue
        return {
            "success": True,
            "fund": fund_info,
            "data": results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


