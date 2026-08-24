"""少樣本提示（Few-Shot Examples）— 為每個 AI 節點提供精準的輸入/輸出示例。

少樣本提示讓 LLM 通過具體範例學習期望的輸出格式、深度和風格，
比純指令描述更精準，減少格式錯誤和空洞輸出。
"""

# ===== AI 0: 行情新聞 — 自然語言輸出示例 =====
MARKET_NEWS_EXAMPLE = """\
## 示例

### 輸入（示例）
實時大盤指數:
  上證指數(sh.000001): 3205.12 ↑ 0.85%
  深證成指(sz.399001): 10245.67 ↑ 1.23%
  創業板指(sz.399006): 2056.89 ↑ 1.56%
數據庫統計:
  掃描股票: 3354, 上漲: 2890, 下跌: 412, 漲停: 45

### 輸出（示例）
### 市場情緒
三大指數集體上漲，創業板領漲 1.56%，上證 0.85%，市場情緒偏多。數據庫統計顯示上漲 2890/3354（佔比 86%），漲停 45 家，資金活躍度高。

### 利好行業
基於指數數據，創業板漲幅最大（1.56%），深證成指上漲 1.23%，反映成長股和中小盤表現較強。數據庫統計中上漲股票佔比 86%，市場整體偏多，多數行業受益。

### 利空行業
下跌股票 412 家（佔比 12%），但輸入中未提供分行業漲跌數據，無法精確識別弱勢行業。

### 選股建議
市場整體偏多（86% 上漲），可關注跟隨創業板上漲的成長股。注意：輸入中未提供分行業數據，具體行業選擇需結合後續行業分析節點。
"""

# ===== AI 0.5: 行業分析 — JSON 輸出示例 =====
INDUSTRY_ANALYSIS_EXAMPLE = """\
## 示例

### 輸入（示例）
行情新聞分析: 利好行業為半導體、新能源汽車、醫藥生物
數據庫行業列表: ["C39電子設備製造", "C26化學原料和化學制品", "C27醫藥製造", ...]
行業下的股票（抽樣）: {"C39電子設備製造": ["sh.603501", "sz.002049", ...], ...}

### 輸出（示例）
{
  "reasoning": "行情新聞利好半導體和新能源，對應數據庫行業 C39電子設備製造和 C26化學原料（鋰電材料），醫藥對應 C27醫藥製造",
  "favorable_industries": ["C39電子設備製造", "C26化學原料和化學制品", "C27醫藥製造"],
  "filtered_codes": ["sh.603501", "sz.002049", "sh.688981", "sz.002460", "sz.300750", "sh.600276", "sz.000538"]
}
"""

# ===== AI 1: 行情分析 — 自然語言輸出示例 =====
MARKET_ANALYSIS_EXAMPLE = """\
## 示例

### 輸入（示例）
市場數據: 上漲股票2890隻(86%)，平均換手率1.8%，近20日波動率18%
歷史記錄: 第1輪收益-2.3%，回撤8.1%，夏普-0.3

### 輸出（示例）
當前市場處於震盪上行階段，上漲股票佔比86%表明賺錢效應較強，但近20日波動率18%偏高說明分歧仍大。適合採用趨勢跟蹤策略，重點選擇強勢板塊中量價齊升的個股，注意控制倉位應對波動。
"""

# ===== AI 2: 策略生成 — JSON 輸出示例 =====
STRATEGY_GENERATION_EXAMPLE = """\
## 示例

### 輸入（示例）
市場分析: 震盪上行，波動率18%，適合趨勢跟蹤
上一輪反思: 收益-2.3%因選股範圍太寬，應增加量價條件篩選強勢股
當前條件: {"adjustflag":3, "maxResults":50, "sortBy":"score"}

### 輸出（示例）
{
  "reasoning": "市場震盪上行適合趨勢跟蹤，反思指出需增加量價條件。新增換手率下限篩選活躍股，量比下限篩選資金流入股，20日收益下限篩選強勢股",
  "criteria": {
    "asOfDate": "2026-08-19",
    "adjustflag": 3,
    "excludeSt": true,
    "maxResults": 50,
    "sortBy": "score",
    "minTurn": 1.5,
    "minVolumeRatio": 1.2,
    "minReturn20": 3.0,
    "minRsi14": 40,
    "maxRsi14": 80,
    "macdCrossSignal": "golden_cross",
    "macdCrossWithinDays": 5,
    "priceAboveMa20": true,
    "ma5AboveMa20": true
  }
}

### 注意
- 只填寫需要調整的字段，其餘保持 null/false/"any"
- minTurn 1.5 表示換手率≥1.5%，篩選交投活躍的股票
- macdCrossSignal "golden_cross" + macdCrossWithinDays 5 表示近5日內MACD金叉
- priceAboveMa20 true 表示股價站上20日均線
"""

# ===== AI 3: 回測反思 — 自然語言輸出示例 =====
BACKTEST_REFLECTION_EXAMPLE = """\
## 示例

### 輸入（示例）
總收益: 5.2% | 年化: 12.1% | 基準: 3.1% | 超額: 2.1%
最大回撤: 6.8% | 夏普: 1.05 | 調倉: 8次 | 交易: 40筆
綜合評分: 68.5
選股條件: minTurn=1.5, minVolumeRatio=1.2, minReturn20=3.0, macdCrossSignal=golden_cross

### 輸出（示例）
優點：超額收益2.1%為正，夏普1.05>1說明風險調整後收益尚可，MACD金叉條件有效捕捉了趨勢。
不足：最大回撤6.8%偏高，調倉8次偏頻繁導致手續費侵蝕收益，總收益5.2%絕對值偏低。
收益來源：主要來自選股（量價條件篩選強勢股），擇時貢獻較弱。
風險控制：回撤控制一般，無止損條件導致個別股票大幅回撤拖累組合。
改進方向：
1. 增加 stopLossPct=8 限制個股最大虧損
2. 提高 minReturn20 至 5.0 篩選更強勢股票
3. 降低 rebalanceInterval 至 3 加快調倉響應速度
"""

# ===== AI 4: 提示詞生成 — 自然語言輸出示例 =====
PROMPT_GENERATION_EXAMPLE = """\
## 示例

### 輸入（示例）
回測反思: 回撤6.8%偏高，無止損，調倉偏頻繁
當前評分: 68.5
歷史趨勢: 第1輪評分55→第2輪評分68.5（上升）

### 輸出（示例）
下一輪重點增加止損條件（stopLossPct=8）控制回撤，提高minReturn20至5.0篩選更強勢股票以提升絕對收益，避免增加過多篩選條件導致選股數量不足。目標將最大回撤降至5%以下，綜合評分提升至75+。
"""

# ===== 評委 AI — 維度級 binary 判斷示例 =====
JUDGE_EXAMPLE = """\
## 示例

### 輸入（示例）
維度: 推理質量
標準: reasoning 是否說明了調整參數的具體原因和預期效果（非泛泛而談）
AI 輸出: {"reasoning": "市場震盪上行適合趨勢跟蹤，反思指出需增加量價條件。新增換手率下限1.5%篩選活躍股，量比下限1.2篩選資金流入股", "criteria": {...}}

### 輸出（示例）
{"passed": true, "reason": "reasoning 說明了趨勢跟蹤的市場判斷+量價條件的具體原因+預期篩選效果，非泛泛而談"}

### 反例（不通過）
{"passed": false, "reason": "reasoning 僅說「根據市場分析調整」，無具體參數原因和預期效果"}
"""

# ===== 回顧分析 AI — 每5輪分析各AI輸入輸出的回顧節點 =====
RETROSPECTIVE_EXAMPLE = """\
## 示例

### 輸入（示例）
回顧範圍: 第 1-5 輪
評分趨勢: [62.5, 65.3, 64.8, 68.1, 67.9]

第1輪各階段摘要:
- market_news: 識別出半導體、新能源為利好行業，但未引用具體新聞標題驗證
- strategy_generation: 生成策略 minTurn=1.5, minVolumeRatio=1.0, industries=["C39電子設備製造"]
- backtest_reflection: 收益3.2%, 回撤8.5%, 反思指出回撤偏高需加止損
- 評委: strategy_generation 得分 58（reasoning 引用數據不足）

第3輪各階段摘要:
- strategy_generation: 新增 stopLossPct=8, 但同時加了 maxRsi14<=30 導致選股數不足
- backtest_reflection: 交易=0筆，策略無功能

第5輪各階段摘要:
- strategy_generation: 移除 maxRsi14, 擴展至2個行業, 交易=12筆, 評分67.9
- 評委: reasoning 質量提升至 72 分

### 輸出（示例）
{
  "findings": "1. AI2策略生成在第3輪疊加過多條件(maxRsi14+單一行業)導致0交易，違反超短線鐵律\\n2. AI0行情新聞連續5輪未引用具體新聞標題驗證利好利空，數據引用不足\\n3. AI3反思質量穩定但建議過於籠統（如「需控制回撤」未給出具體止損值）\\n4. 評分從62.5升至67.9但第3輪因0交易跌至低點，說明策略生成對條件疊加敏感",
  "optimization_summary": "5輪中評分總體上升趨勢(+5.4分)，但第3輪出現0交易的低質量迭代。核心問題是AI2在嘗試改進時傾向疊加條件而非替換條件，導致過度收斂。AI0的新聞引用質量持續偏低，影響利好利空判斷可信度。AI3反思建議缺乏可執行性。",
  "improvement_plan": "1. AI2策略生成：下次調整時優先替換條件而非疊加，若新增條件必須同時移除一個舊條件\\n2. AI0行情新聞：必須在related_news中引用至少1條具體新聞標題，否則supported_by_news設為false\\n3. AI3回測反思：給出具體參數建議（如「stopLossPct從8調至5」）而非籠統建議\\n4. 評分提升目標：下一個5輪窗口目標達到72+分",
  "stage_issues": {
    "market_news": "新聞引用率低，5輪中僅1輪引用了具體新聞標題",
    "strategy_generation": "條件疊加傾向明顯，第3輪導致0交易",
    "backtest_reflection": "建議籠統缺乏可執行性"
  },
  "score_trend": "62.5→65.3→64.8→68.1→67.9，總體上升但第3輪因0交易出現波谷",
  "recommendations": [
    "AI2下次調整時替換而非疊加條件",
    "AI0必須引用至少1條新聞標題驗證利好利空",
    "AI3反思需給出具體參數值建議",
    "下一窗口目標評分72+"
  ]
}
"""


def get_few_shot(stage_name: str) -> str:
    """根據階段名稱返回對應的少樣本提示。"""
    examples = {
        "market_news": MARKET_NEWS_EXAMPLE,
        "industry_analysis": INDUSTRY_ANALYSIS_EXAMPLE,
        "market_analysis": MARKET_ANALYSIS_EXAMPLE,
        "strategy_generation": STRATEGY_GENERATION_EXAMPLE,
        "backtest_reflection": BACKTEST_REFLECTION_EXAMPLE,
        "prompt_generation": PROMPT_GENERATION_EXAMPLE,
        "judge": JUDGE_EXAMPLE,
        "retrospective": RETROSPECTIVE_EXAMPLE,
    }
    return examples.get(stage_name, "")
