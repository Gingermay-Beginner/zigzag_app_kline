import pandas as pd
import akshare as ak
from datetime import datetime, timedelta

# T+1日8个买入时间段
BUY_TIMES = ["09:30", "10:00", "10:30", "11:00", "13:00", "13:30", "14:00", "14:30"]
BUY_LABELS = ["9:30", "10:00", "10:30", "11:00", "13:00", "13:30", "14:00", "14:30"]


def normalize_code(code: str) -> str:
    """将 sh.600000 或 sz.000001 转换为 akshare 格式：600000 或 000001"""
    if code.startswith("sh.") or code.startswith("sz."):
        return code[3:]
    return code


def find_3_consecutive_down(df: pd.DataFrame) -> list:
    closes = df["close"].values
    dates = df["date"].values
    signals = []
    streak = 0
    for i in range(1, len(closes)):
        if closes[i] < closes[i - 1]:
            streak += 1
        else:
            streak = 0
        if streak >= 3:
            signals.append({"signal_date": dates[i], "signal_idx": i})
    return signals


def get_daily_data(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """用akshare拉A股日线数据"""
    pure_code = normalize_code(code)
    try:
        df = ak.stock_zh_a_hist(
            symbol=pure_code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "close"])
        df = df.rename(columns={"日期": "date", "收盘": "close"})
        df = df[["date", "close"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        return pd.DataFrame(columns=["date", "close"])


def get_30min_data(code: str, date_str: str) -> pd.DataFrame:
    """用akshare拉A股30分钟K线，取某一天的数据"""
    pure_code = normalize_code(code)
    try:
        # akshare的分钟线接口，拉30分钟级别
        df = ak.stock_zh_a_hist_min_em(
            symbol=pure_code,
            start_date=date_str + " 09:00:00",
            end_date=date_str + " 15:30:00",
            period="30",
            adjust="qfq",
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={"时间": "datetime", "收盘": "close"})
        df = df[["datetime", "close"]].copy()
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        # 提取时间部分 HH:MM
        df["hhmm"] = pd.to_datetime(df["datetime"]).dt.strftime("%H:%M")
        return df
    except Exception as e:
        return pd.DataFrame()


def run_timing_analysis(code: str, start_date: str, end_date: str, progress_callback=None):
    """主分析函数，使用akshare"""

    # 1. 拉日线数据
    if progress_callback:
        progress_callback("正在获取日线数据...")
    df = get_daily_data(code, start_date, end_date)
    if df.empty:
        raise ValueError(f"未找到 {code} 在指定日期范围内的数据，请确认代码格式（如 sh.600000 或 sz.000001）")

    # 2. 扫描连续3根阴线
    signals = find_3_consecutive_down(df)
    signal_count = len(signals)
    if signal_count == 0:
        raise ValueError("未找到任何连续3根阴线的信号")

    date_list = df["date"].tolist()

    # 3. 逐个信号分析
    stats = {t: {"win": 0, "lose": 0, "returns": []} for t in BUY_LABELS}
    valid_count = 0

    for i, sig in enumerate(signals):
        if progress_callback and i % 5 == 0:
            progress_callback(f"正在分析信号 {i+1}/{signal_count}...")

        sig_idx = sig["signal_idx"]
        if sig_idx + 2 >= len(df):
            continue

        t1_date = date_list[sig_idx + 1]
        t1_str = pd.Timestamp(t1_date).strftime("%Y-%m-%d")

        sell_price = float(df.iloc[sig_idx + 2]["close"])

        min_df = get_30min_data(code, t1_str)
        if min_df.empty:
            continue

        hhmm_to_close = dict(zip(min_df["hhmm"], min_df["close"]))

        has_any = False
        for buy_time, label in zip(BUY_TIMES, BUY_LABELS):
            if buy_time in hhmm_to_close:
                buy_price = float(hhmm_to_close[buy_time])
                if buy_price <= 0:
                    continue
                has_any = True
                ret = (sell_price - buy_price) / buy_price * 100
                stats[label]["returns"].append(ret)
                if sell_price > buy_price:
                    stats[label]["win"] += 1
                else:
                    stats[label]["lose"] += 1

        if has_any:
            valid_count += 1

    # 4. 构建结果
    rows = []
    for label in BUY_LABELS:
        s = stats[label]
        total = s["win"] + s["lose"]
        win_rate = (s["win"] / total * 100) if total > 0 else 0
        avg_ret = (sum(s["returns"]) / len(s["returns"])) if s["returns"] else 0
        rows.append({
            "买入时间": label,
            "胜率%": round(win_rate, 2),
            "胜次数": s["win"],
            "负次数": s["lose"],
            "总次数": total,
            "平均收益%": round(avg_ret, 3),
        })

    result_df = pd.DataFrame(rows)
    return result_df, signal_count, valid_count
