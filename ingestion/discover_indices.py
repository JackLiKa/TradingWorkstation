"""從 Baostock query_all_stock 動態發現所有有效指數代碼。

驗證邏輯：
1. 調用 query_all_stock 獲取某日全部代碼與名稱
2. 過濾可能為指數的代碼（sh.000xxx/88xxxx、sz.399xxx/980xxx/990xxx）
3. 對每個候選調用 query_history_k_data_plus 驗證是否有日線數據
4. 按名稱模式分類（綜合/規模/行業/策略/成長/價值/主題/基金/債券）
5. 輸出為 index_list.json 結構
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "ingestion")

import baostock as bs

_SAMPLE_DELAY = 0.2


def _safe_name(raw: str) -> str:
    """處理 Baostock 返回的中文名稱編碼（GBK/UTF-8 兼容）。"""
    if isinstance(raw, bytes):
        for enc in ("gbk", "gb18030", "utf-8"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    elif isinstance(raw, str):
        for enc in ("gbk", "gb18030"):
            try:
                return raw.encode("latin1").decode(enc)
            except (UnicodeError, UnicodeDecodeError):
                continue
    return raw


def _is_index_candidate(code: str, name: str) -> bool:
    """判斷是否為指數候選（基於代碼區間）。

    排除 ETF、LOF、可轉債等基金/債券產品，只保留真正指數：
    - sh.000xxx / sh.88xxxx: 上證指數 / 申萬行業
    - sz.399xxx / sz.980xxx / sz.990xxx: 深證指數 / 國證 / 中華
    """
    if not re.match(r"^(sh|sz)\.\d{6}$", code):
        return False
    num = int(code.split(".")[1])
    prefix = code.split(".")[0]
    if prefix == "sh":
        return (0 <= num <= 999) or (880000 <= num <= 889999)
    if prefix == "sz":
        return (399000 <= num <= 399999) or (980000 <= num <= 989999) or (990000 <= num <= 999999)
    return False


def _categorize(code: str, name: str) -> tuple[str, str]:
    """根據名稱與代碼推測指數分類。"""
    # 基金/債券
    if "基金" in name:
        return "基金指數", "fund"
    if "債" in name:
        return "債券指數", "bond"

    # 成長/價值
    if "成長" in name:
        return "成長指數", "growth"
    if "價值" in name:
        return "價值指數", "value"

    # 策略/等權
    if "等權" in name or "等权" in name or "等權重" in name:
        return "策略指數", "strategy"

    # 規模
    scale_markers = ["50", "300", "500", "1000", "2000", "180", "380", "成指", "創業板", "科創", "中小"]
    if any(m in name for m in scale_markers):
        return "規模指數", "scale"

    # 主題
    theme_markers = ["紅利", "周期", "非周期", "資源", "能源", "消費", "民營", "國企", "新興"]
    if any(m in name for m in theme_markers):
        return "主題指數", "theme"

    # 二級行業（300 + 行業名）
    if "300" in name and any(k in name for k in ["地產", "銀行", "能源", "材料", "工業", "可選", "消費", "醫藥", "金融", "信息", "電信", "公用"]):
        return "二級行業指數", "industry_l2"

    # 一級行業（國證、上證、中證全指 + 行業名）
    if "中證全指" in name or "國證" in name or "上證" in name:
        return "一級行業指數", "industry_l1"

    # 綜合
    if "綜指" in name or "綜合" in name or "A股" in name or "B股" in name or code in ("sh.000001", "sh.000002", "sh.000003"):
        return "綜合指數", "composite"

    # 默認歸類為一級行業
    return "一級行業指數", "industry_l1"


def _fetch_index_sample(code: str, day: str) -> bool:
    """調用一次 query_history_k_data_plus 驗證指數是否有效。"""
    base = datetime.strptime(day, "%Y-%m-%d")
    end = (base - timedelta(days=15)).strftime("%Y-%m-%d")
    start = (base - timedelta(days=45)).strftime("%Y-%m-%d")
    rs = bs.query_history_k_data_plus(code, "date", start_date=start, end_date=end, frequency="d")
    if rs.error_code != "0":
        return False
    while rs.error_code == "0" and rs.next():
        return True
    return False


def discover_indices(day: str = "2024-12-31", sample: bool = False, delay: float = 0.2) -> list[dict]:
    """發現並驗證 Baostock 中的指數。

    Args:
        day: 查詢日期（默認 2024-12-31）
        sample: 是否對候選指數做 sample 驗證（較慢但更準）
        delay: 驗證間隔秒數

    Returns:
        list[dict]: 每項含 code/name/category/category_code
    """
    print(f"[discover] 查詢 {day} 全部代碼...")
    rs = bs.query_all_stock(day=day)
    if rs.error_code != "0":
        raise RuntimeError(f"query_all_stock failed: {rs.error_msg}")

    candidates = []
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        code = row[0].strip()
        name = _safe_name(row[2])
        if _is_index_candidate(code, name):
            candidates.append({"code": code, "name": name})

    print(f"[discover] 找到 {len(candidates)} 個指數候選")

    for item in candidates:
        cat, cat_code = _categorize(item["code"], item["name"])
        item["category"] = cat
        item["category_code"] = cat_code

    if not sample:
        return candidates

    # sample 驗證：逐個調用 query_history_k_data_plus
    valid = []
    for i, item in enumerate(candidates):
        is_valid = _fetch_index_sample(item["code"], day)
        item["_valid"] = is_valid
        if is_valid:
            valid.append(item)
            print(f"[ok]   {item['code']} {item['name']} -> {item['category']}")
        else:
            print(f"[skip] {item['code']} {item['name']}: no data")
        time.sleep(delay)
        if (i + 1) % 100 == 0:
            print(f"[progress] {i + 1}/{len(candidates)}")

    print(f"[discover] 驗證有效: {len(valid)} / {len(candidates)} 個")
    return valid


def group_by_category(indices: list[dict]) -> list[dict]:
    """將扁平指數列表按 category_code 分組。"""
    by_cat = {}
    for item in indices:
        cat_code = item["category_code"]
        cat = item["category"]
        if cat_code not in by_cat:
            by_cat[cat_code] = {"category": cat, "category_code": cat_code, "indices": []}
        by_cat[cat_code]["indices"].append({"code": item["code"], "name": item["name"]})

    order = ["composite", "scale", "industry_l1", "industry_l2", "strategy", "growth", "value", "theme", "fund", "bond"]
    return [by_cat[k] for k in order if k in by_cat]


def main():
    parser = argparse.ArgumentParser(description="從 Baostock 動態發現並驗證指數代碼")
    parser.add_argument("--day", default="2024-12-31", help="查詢日期（默認 2024-12-31）")
    parser.add_argument("--sample", action="store_true", help="對候選指數做 sample 驗證（較慢但更準）")
    parser.add_argument("--delay", type=float, default=0.2, help="每次驗證間隔秒數（默認 0.2）")
    parser.add_argument("--output", default="ingestion/index_list.json", help="輸出文件路徑")
    parser.add_argument("--dry-run", action="store_true", help="只輸出到 index_list_discovered.json，不改 index_list.json")
    args = parser.parse_args()

    bs.login()
    try:
        indices = discover_indices(day=args.day, sample=args.sample, delay=args.delay)
        if args.sample:
            invalid = [item for item in indices if not item.get("_valid", False)]
            valid = [item for item in indices if item.get("_valid", False)]
            # 注意：discover_indices 在 sample=True 時已返回 valid
            # 這裡 indices 即 valid
            output = {
                "_comment": f"Baostock 指數清單 — 經 sample 驗證，共 {len(indices)} 個有效指數。",
                "_source": "https://www.baostock.com/mainContent?file=indexData.md",
                "_updated": datetime.now().strftime("%Y-%m-%d"),
                "_verified": True,
                "_valid_count": len(indices),
                "_invalid_count": len(invalid),
                "categories": group_by_category(indices),
            }
        else:
            output = {
                "_comment": f"Baostock 指數清單 — 從 query_all_stock 動態發現，未經 sample 驗證，共 {len(indices)} 個候選。",
                "_source": "https://www.baostock.com/mainContent?file=indexData.md",
                "_updated": datetime.now().strftime("%Y-%m-%d"),
                "_verified": False,
                "_valid_count": len(indices),
                "categories": group_by_category(indices),
            }

        out_path = Path(args.output) if not args.dry_run else Path("ingestion/index_list_discovered.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到 {out_path}: {len(indices)} 個指數")
    finally:
        bs.logout()


if __name__ == "__main__":
    main()
