import pandas as pd
import time
from datetime import datetime, timedelta


def get_stock_data(code: str, market: str) -> pd.DataFrame:
    """
    获取股票历史收盘价数据。
    
    Args:
        code: 股票代码（A股如"300750"，港股如"9992"，美股如"META"）
        market: 市场类型（"A股" / "港股" / "美股"）
    
    Returns:
        包含 date(datetime), close(float) 两列的DataFrame，按日期升序
    """
    end_date = datetime.today()
    start_date = datetime(2000, 1, 1)  # 拉全量历史

    if market == "A股":
        import baostock as bs
        code = code.strip()
        # 判断市场前缀
        if code.startswith("6"):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        lg = bs.login()
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,close",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="2"  # 前复权
        )
        data = []
        while (rs.error_code == "0") and rs.next():
            data.append(rs.get_row_data())
        bs.logout()
        if not data:
            raise ValueError(f"未找到股票 {code} 的数据，请检查代码是否正确")
        df = pd.DataFrame(data, columns=rs.fields)
        df = df.rename(columns={"date": "date", "close": "close"})
        df["date"] = pd.to_datetime(df["date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df[["date", "close"]].sort_values("date").reset_index(drop=True)

    elif market == "港股":
        import akshare as ak
        # 补零到5位
        hk_code = code.strip().zfill(5)
        for attempt in range(3):
            try:
                df = ak.stock_hk_hist(
                    symbol=hk_code,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="qfq"
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2)
        df = df.rename(columns={"日期": "date", "收盘": "close"})
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "close"]].sort_values("date").reset_index(drop=True)

    elif market == "美股":
        import yfinance as yf
        ticker = yf.Ticker(code.strip().upper())
        hist = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                              end=end_date.strftime("%Y-%m-%d"))
        if hist.empty:
            raise ValueError(f"yfinance 未能获取 {code} 的数据，请检查代码是否正确")
        hist = hist.reset_index()
        # Date列可能是tz-aware，统一转为tz-naive
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        df = hist.rename(columns={"Date": "date", "Close": "close"})[["date", "close"]]
        df = df.sort_values("date").reset_index(drop=True)

    else:
        raise ValueError(f"不支持的市场类型: {market}")

    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_stock_ohlc_data(code: str, market: str) -> pd.DataFrame:
    """
    获取股票历史OHLC数据，用于K线形态统计。

    Returns:
        包含 date, open, high, low, close 列的DataFrame，按日期升序
    """
    end_date = datetime.today()
    start_date = datetime(1990, 1, 1)

    if market == "A股":
        import baostock as bs
        code = code.strip()
        if code.startswith("6"):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        lg = bs.login()
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="2",
        )
        data = []
        while (rs.error_code == "0") and rs.next():
            data.append(rs.get_row_data())
        bs.logout()
        if not data:
            raise ValueError(f"未找到股票 {code} 的数据，请检查代码是否正确")
        df = pd.DataFrame(data, columns=rs.fields)

    elif market == "港股":
        import akshare as ak
        hk_code = code.strip().zfill(5)
        for attempt in range(3):
            try:
                df = ak.stock_hk_hist(
                    symbol=hk_code,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="qfq",
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2)
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
        })

    elif market == "美股":
        import yfinance as yf
        ticker = yf.Ticker(code.strip().upper())
        hist = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )
        if hist.empty:
            raise ValueError(f"yfinance 未能获取 {code} 的数据，请检查代码是否正确")
        hist = hist.reset_index()
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        df = hist.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
        })

    else:
        raise ValueError(f"不支持的市场类型: {market}")

    required_cols = ["date", "open", "high", "low", "close"]
    df = df[required_cols].copy()
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def resample_ohlc(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """
    将日K聚合为周K/月K/季K。period 可选：日K、周K、月K、季K。
    """
    if period == "日K":
        return df.copy()

    rule_map = {
        "周K": "W-FRI",
        "月K": "ME",
        "季K": "QE",
    }
    if period not in rule_map:
        raise ValueError(f"不支持的K线周期: {period}")

    out = (
        df.set_index("date")
        .resample(rule_map[period])
        .agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        })
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    return out
