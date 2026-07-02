import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def calc_candle_streaks(df: pd.DataFrame, min_length: int = 2) -> dict:
    """
    统计连续阳线/连续阴线。

    阳线: close > open
    阴线: close < open
    平线: close == open，会打断连续段
    """
    if df.empty:
        return {
            "bullish": [],
            "bearish": [],
            "bullish_counts": pd.DataFrame(columns=["连续根数", "出现次数"]),
            "bearish_counts": pd.DataFrame(columns=["连续根数", "出现次数"]),
        }

    work = df.copy().sort_values("date").reset_index(drop=True)
    work["direction"] = "flat"
    work.loc[work["close"] > work["open"], "direction"] = "bullish"
    work.loc[work["close"] < work["open"], "direction"] = "bearish"

    streaks = {"bullish": [], "bearish": []}
    current_type = None
    start_idx = None

    for idx, row in work.iterrows():
        direction = row["direction"]

        if direction == "flat":
            if current_type in streaks:
                _append_streak(work, streaks[current_type], current_type, start_idx, idx - 1, min_length)
            current_type = None
            start_idx = None
            continue

        if direction != current_type:
            if current_type in streaks:
                _append_streak(work, streaks[current_type], current_type, start_idx, idx - 1, min_length)
            current_type = direction
            start_idx = idx

    if current_type in streaks:
        _append_streak(work, streaks[current_type], current_type, start_idx, len(work) - 1, min_length)

    return {
        "bullish": streaks["bullish"],
        "bearish": streaks["bearish"],
        "bullish_counts": _length_counts(streaks["bullish"]),
        "bearish_counts": _length_counts(streaks["bearish"]),
    }


def _append_streak(work: pd.DataFrame, bucket: list, streak_type: str, start_idx: int, end_idx: int, min_length: int):
    length = end_idx - start_idx + 1
    if length < min_length:
        return

    start = work.iloc[start_idx]
    end = work.iloc[end_idx]
    start_price = float(start["open"])
    end_price = float(end["close"])
    pct = (end_price - start_price) / start_price * 100 if start_price else 0

    bucket.append({
        "类型": "连续阳线" if streak_type == "bullish" else "连续阴线",
        "连续根数": int(length),
        "开始日期": pd.Timestamp(start["date"]).strftime("%Y-%m-%d"),
        "结束日期": pd.Timestamp(end["date"]).strftime("%Y-%m-%d"),
        "起始开盘": round(start_price, 2),
        "结束收盘": round(end_price, 2),
        "区间涨跌幅%": round(pct, 2),
    })


def _length_counts(streaks: list) -> pd.DataFrame:
    if not streaks:
        return pd.DataFrame(columns=["连续根数", "出现次数"])
    lengths = [item["连续根数"] for item in streaks]
    counts = pd.Series(lengths).value_counts().sort_index()
    return pd.DataFrame({
        "连续根数": counts.index.astype(int),
        "出现次数": counts.values.astype(int),
    })


def chart_streak_distribution(result: dict) -> go.Figure:
    """绘制连续阳线/阴线长度分布。"""
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("连续阳线长度分布", "连续阴线长度分布"),
        horizontal_spacing=0.12,
    )

    bull = result["bullish_counts"]
    bear = result["bearish_counts"]

    fig.add_trace(
        go.Bar(
            x=bull["连续根数"] if not bull.empty else [],
            y=bull["出现次数"] if not bull.empty else [],
            marker_color="#ef5350",
            text=bull["出现次数"] if not bull.empty else [],
            textposition="outside",
            name="连续阳线",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=bear["连续根数"] if not bear.empty else [],
            y=bear["出现次数"] if not bear.empty else [],
            marker_color="#26c6da",
            text=bear["出现次数"] if not bear.empty else [],
            textposition="outside",
            name="连续阴线",
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        template="plotly_dark",
        height=430,
        showlegend=False,
        margin=dict(l=40, r=40, t=70, b=50),
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#1a1a2e",
    )
    fig.update_xaxes(title_text="连续根数", dtick=1)
    fig.update_yaxes(title_text="出现次数", rangemode="tozero")
    return fig


def top_streaks(result: dict, limit: int = 10) -> pd.DataFrame:
    """返回最长连续阳线/阴线记录。"""
    rows = result["bullish"] + result["bearish"]
    if not rows:
        return pd.DataFrame(columns=[
            "类型", "连续根数", "开始日期", "结束日期", "起始开盘", "结束收盘", "区间涨跌幅%"
        ])
    out = pd.DataFrame(rows)
    out = out.sort_values(["连续根数", "结束日期"], ascending=[False, False]).head(limit)
    return out.reset_index(drop=True)
