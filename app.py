import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta

from data import get_stock_data, get_stock_ohlc_data, resample_ohlc
from zigzag import calc_zigzag_from_df
from charts import chart_zigzag_overlay, chart_wave_bars
from streak_analysis import calc_candle_streaks, chart_streak_distribution, top_streaks


def is_valid_stock_code(code: str, market: str) -> bool:
    code = code.strip()
    if market == "A股":
        return bool(re.fullmatch(r"\d{6}", code))
    if market == "港股":
        return bool(re.fullmatch(r"\d{1,5}", code))
    if market == "美股":
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9\.\-]*", code))
    return False

st.set_page_config(
    page_title="ZigZag波段分析",
    page_icon="🐆",
    layout="wide"
)

# ── 侧边栏 ──────────────────────────────────────────────────────────────
with st.sidebar:
    mode = st.radio(
        "功能选择",
        options=["📈 ZigZag波段分析", "⏱️ 择时胜率分析", "🕯️ 连续K线统计"],
        index=0,
    )

    st.divider()

    # 根据模式显示对应参数
    analyze_btn = False
    timing_btn = False
    streak_btn = False

    if mode == "📈 ZigZag波段分析":
        st.header("⚙️ ZigZag分析参数")

        market = st.radio(
            "选择市场",
            options=["A股", "港股", "美股"],
            index=0,
            horizontal=True,
        )

        placeholder_map = {
            "A股": "如 300750",
            "港股": "如 9992",
            "美股": "如 META",
        }

        code = st.text_input(
            "股票代码",
            placeholder=placeholder_map[market],
            help="A股输入6位数字代码；港股输入数字代码（会自动补零）；美股输入英文代码",
        )

        threshold_pct = st.slider(
            "ZigZag 阈值",
            min_value=10,
            max_value=40,
            value=20,
            step=5,
            format="%d%%",
            help="转折确认的最小波动幅度，越大则转折点越少",
        )
        threshold = threshold_pct / 100.0

        analyze_btn = st.button("🔍 开始分析", use_container_width=True, type="primary")

    else:
        if mode == "⏱️ 择时胜率分析":
            st.header("⏱️ 择时胜率参数")

            timing_code = st.text_input(
                "A股代码（择时）",
                placeholder="如 sh.600000 或 sz.000001",
                help="仅支持A股，格式为 sh.600000 或 sz.000001",
            )

            default_end = datetime.today()
            default_start = default_end - timedelta(days=3 * 365)

            timing_dates = st.date_input(
                "分析时间范围",
                value=(default_start.date(), default_end.date()),
                help="选择起止日期，默认最近3年",
            )

            timing_btn = st.button("📊 开始择时分析", use_container_width=True, type="primary")

        else:
            st.header("🕯️ 连续K线统计参数")

            streak_market = st.radio(
                "选择市场",
                options=["A股", "港股", "美股"],
                index=0,
                horizontal=True,
                key="streak_market",
            )

            streak_placeholder_map = {
                "A股": "如 300750",
                "港股": "如 9992",
                "美股": "如 META",
            }

            streak_code = st.text_input(
                "股票代码",
                placeholder=streak_placeholder_map[streak_market],
                help="A股输入6位数字代码；港股输入数字代码（会自动补零）；美股输入英文代码",
                key="streak_code",
            )

            k_period = st.radio(
                "K线周期",
                options=["日K", "周K", "月K", "季K"],
                index=0,
                horizontal=True,
            )

            min_streak_len = st.slider(
                "最小连续根数",
                min_value=2,
                max_value=10,
                value=2,
                step=1,
                help="只统计达到这个长度的连续阳线/阴线",
            )

            streak_btn = st.button("📊 开始统计", use_container_width=True, type="primary")

# ── 主标题：随模式切换 ────────────────────────────────────────────────────
header_map = {
    "📈 ZigZag波段分析": ("🐆 股票ZigZag波段分析", "支持A股 / 港股 / 美股 | 阈值可调"),
    "⏱️ 择时胜率分析": ("⏱️ 连续3阴线择时胜率分析", "仅支持A股 | 扫描信号后统计T+1买入、T+2卖出的胜率"),
    "🕯️ 连续K线统计": ("🕯️ 连续阳线 / 连续阴线统计", "支持A股 / 港股 / 美股 | 按日K/周K/月K/季K统计"),
}
page_title, page_caption = header_map.get(mode, ("🐆 股票分析工具", ""))
st.title(page_title)
if page_caption:
    st.caption(page_caption)

# ── 主区域：根据模式显示对应内容 ─────────────────────────────────────────
if mode == "📈 ZigZag波段分析":
    if not analyze_btn:
        st.info("👈 在左侧填写参数后点击「开始分析」")
    elif not code.strip():
        st.warning("请输入股票代码")
    elif not is_valid_stock_code(code, market):
        st.warning("代码格式不正确：A股需6位数字，港股为1-5位数字，美股为英文代码")
    else:
        # 数据获取
        df = None
        with st.spinner(f"正在获取 {market} · {code} 的数据..."):
            try:
                df = get_stock_data(code.strip(), market)
            except Exception as e:
                st.error(f"❌ 数据获取失败：{e}")
                if "Connection aborted" in str(e) or "RemoteDisconnected" in str(e):
                    st.info("数据源连接被中断，请稍等重试，或切换到美股/港股验证应用是否正常。")
                st.info("请检查：① 股票代码是否正确 ② 网络是否正常 ③ 数据源是否可用")

        if df is not None and not df.empty:
            # ZigZag计算
            pivots = None
            with st.spinner("计算ZigZag转折点..."):
                try:
                    pivots = calc_zigzag_from_df(df, threshold=threshold)
                except Exception as e:
                    st.error(f"❌ ZigZag计算出错：{e}")

            if not pivots:
                st.warning("⚠️ 未能计算出转折点，请尝试降低阈值")
            else:
                # ── 当前状态计算 ───────────────────────────────────────
                current_price = float(df['close'].iloc[-1])
                current_date = df['date'].iloc[-1]
                last_pivot = pivots[-1]

                last_pivot_date = last_pivot['date']
                last_pivot_price = last_pivot['price']

                if last_pivot_date is not None:
                    if hasattr(current_date, 'to_pydatetime'):
                        current_date_dt = current_date.to_pydatetime().replace(tzinfo=None)
                    else:
                        current_date_dt = pd.Timestamp(current_date).to_pydatetime().replace(tzinfo=None)

                    if hasattr(last_pivot_date, 'tzinfo') and last_pivot_date.tzinfo:
                        last_pivot_date_dt = last_pivot_date.replace(tzinfo=None)
                    else:
                        last_pivot_date_dt = pd.Timestamp(last_pivot_date).to_pydatetime().replace(tzinfo=None)

                    current_wave_days = max(0, (current_date_dt - last_pivot_date_dt).days)
                else:
                    current_wave_days = 0

                current_wave_pct = (current_price - last_pivot_price) / last_pivot_price * 100
                current_wave_type = 'up' if current_wave_pct >= 0 else 'down'

                same_direction_waves = [
                    abs(p['wave_pct']) for p in pivots[1:]
                    if p['wave_type'] == current_wave_type and p['wave_pct'] != 0
                ]

                if same_direction_waves:
                    percentile = float(np.sum(np.array(same_direction_waves) <= abs(current_wave_pct))) / len(same_direction_waves) * 100
                else:
                    percentile = 0.0

                # ── 顶部摘要卡片（3列）────────────────────────────────
                st.subheader(f"📊 {market} · {code.upper()} 分析结果")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        label="当前价格",
                        value=f"{current_price:.2f}",
                        delta=f"{current_wave_pct:+.1f}% 本波",
                        delta_color="normal",
                    )

                with col2:
                    wave_emoji = "📈" if current_wave_type == 'up' else "📉"
                    wave_label = "上涨" if current_wave_type == 'up' else "下跌"
                    last_date_str = pd.Timestamp(last_pivot_date).strftime('%Y-%m-%d') if last_pivot_date is not None else 'N/A'
                    st.metric(
                        label=f"本波状态 {wave_emoji}",
                        value=f"{wave_label} {abs(current_wave_pct):.1f}%",
                        delta=f"自 {last_date_str} 已持续 {current_wave_days} 天",
                        delta_color="off",
                    )

                with col3:
                    pct_label = f"{percentile:.0f}th 分位"
                    pct_desc = "历史偏低" if percentile < 33 else ("历史中位" if percentile < 67 else "历史偏高")
                    st.metric(
                        label="历史分位（同向波段）",
                        value=pct_label,
                        delta=pct_desc,
                        delta_color="off",
                    )

                st.divider()

                # ── 图表一：ZigZag叠加收盘价 ──────────────────────────
                st.subheader("📈 ZigZag 波段叠加图")
                try:
                    fig1 = chart_zigzag_overlay(df, pivots)
                    st.plotly_chart(fig1, use_container_width=True)
                except Exception as e:
                    st.error(f"图表生成失败：{e}")

                st.divider()

                # ── 图表二：波段涨跌幅柱状图 ─────────────────────────
                st.subheader("📊 历史波段涨跌幅")
                try:
                    fig2 = chart_wave_bars(pivots)
                    st.plotly_chart(fig2, use_container_width=True)
                except Exception as e:
                    st.error(f"波段柱状图生成失败：{e}")

                st.divider()

                # ── 底部统计摘要 ──────────────────────────────────────
                st.subheader("📋 历史波段统计")

                up_waves = [p for p in pivots[1:] if p['wave_type'] == 'up']
                down_waves = [p for p in pivots[1:] if p['wave_type'] == 'down']

                def wave_summary(waves, label):
                    if not waves:
                        st.markdown(f"**{label}**\n\n暂无数据")
                        return
                    pcts = [abs(w['wave_pct']) for w in waves]
                    days = [w['wave_days'] for w in waves]
                    max_pct_wave = max(waves, key=lambda w: abs(w['wave_pct']))
                    max_pct_date = pd.Timestamp(max_pct_wave['date']).strftime('%Y-%m-%d') if max_pct_wave['date'] is not None else 'N/A'
                    max_days_wave = max(waves, key=lambda w: w['wave_days'])
                    max_days_date = pd.Timestamp(max_days_wave['date']).strftime('%Y-%m-%d') if max_days_wave['date'] is not None else 'N/A'
                    st.markdown(f"**{label}**")
                    st.markdown(f"""
- 波段数量：**{len(waves)}** 段
- 平均涨跌幅：**{np.mean(pcts):.1f}%**
- 最大涨跌幅：**{max(pcts):.1f}%**（截至 {max_pct_date}）
- 平均持续天数：**{np.mean(days):.0f}** 天
- 最长持续天数：**{max(days)}** 天（截至 {max_days_date}）
""")

                col_up, col_down = st.columns(2)
                with col_up:
                    wave_summary(up_waves, "📈 上涨区间汇总")
                with col_down:
                    wave_summary(down_waves, "📉 下跌区间汇总")
        elif df is not None and df.empty:
            st.error("❌ 获取到的数据为空，请检查代码是否正确")

elif mode == "⏱️ 择时胜率分析":
    st.subheader("📊 3根阴线后择时胜率分析")
    st.caption("扫描连续3根阴线信号，分析T+1不同时间段买入、T+2卖出的胜率")

    if not timing_btn:
        st.info("👈 在左侧填写A股代码和时间范围后点击「开始择时分析」")
    elif not timing_code.strip():
        st.warning("请输入A股代码（格式如 sh.600000 或 sz.000001）")
    elif not isinstance(timing_dates, (list, tuple)) or len(timing_dates) != 2:
        st.warning("请选择完整的起止日期范围")
    else:
        tc = timing_code.strip()
        # 自动补全前缀：6开头=上交所sh，其他=深交所sz
        if not (tc.startswith("sh.") or tc.startswith("sz.")):
            if tc.startswith("6"):
                tc = "sh." + tc
            else:
                tc = "sz." + tc
            st.info(f"自动识别为 {tc}")
        if not (tc.startswith("sh.") or tc.startswith("sz.")):
            st.error("代码格式错误，请使用 sh.600000 或 sz.000001 格式")
        else:
            from timing_analysis import run_timing_analysis

            t_start = timing_dates[0].strftime("%Y-%m-%d")
            t_end = timing_dates[1].strftime("%Y-%m-%d")

            status_text = st.empty()

            def update_status(msg):
                status_text.text(msg)

            try:
                with st.spinner(f"正在分析 {tc}，这可能需要几分钟..."):
                    result_df, signal_count, valid_count = run_timing_analysis(
                        tc, t_start, t_end, progress_callback=update_status
                    )

                status_text.empty()

                st.success(f"共找到 **{signal_count}** 个连续3根阴线信号，其中 **{valid_count}** 个有效（有分钟线数据）")

                # ── 柱状图 ──────────────────────────────────────────
                st.subheader("📊 各时间段买入胜率")

                colors = ['#ef5350' if v < 50 else '#26a69a' for v in result_df["胜率%"]]

                fig = go.Figure(data=[
                    go.Bar(
                        x=result_df["买入时间"],
                        y=result_df["胜率%"],
                        marker_color=colors,
                        text=[f"{v:.1f}%" for v in result_df["胜率%"]],
                        textposition="outside",
                    )
                ])
                fig.update_layout(
                    template="plotly_dark",
                    xaxis_title="T+1 买入时间段",
                    yaxis_title="胜率 %",
                    yaxis=dict(range=[0, max(100, result_df["胜率%"].max() + 10)]),
                    height=450,
                    title=f"{tc} 连续3阴线后择时胜率（{t_start} ~ {t_end}）",
                )
                fig.add_hline(y=50, line_dash="dash", line_color="yellow", opacity=0.5,
                              annotation_text="50%", annotation_position="top left")
                st.plotly_chart(fig, use_container_width=True)

                # ── 数据表 ──────────────────────────────────────────
                st.subheader("📋 详细统计数据")
                st.dataframe(
                    result_df.style.format({
                        "胜率%": "{:.2f}",
                        "平均收益%": "{:.3f}",
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

            except ValueError as e:
                status_text.empty()
                st.error(f"❌ {e}")
            except Exception as e:
                status_text.empty()
                st.error(f"❌ 分析出错：{e}")
                st.info("请检查：① 股票代码格式是否正确 ② 网络是否正常 ③ baostock是否可用")

else:
    st.subheader("🕯️ 连续阳线 / 连续阴线统计")
    st.caption("按日K / 周K / 月K / 季K统计连续阳线、连续阴线的长度分布和最长记录")

    if not streak_btn:
        st.info("👈 在左侧填写参数后点击「开始统计」")
    elif not streak_code.strip():
        st.warning("请输入股票代码")
    elif not is_valid_stock_code(streak_code, streak_market):
        st.warning("代码格式不正确：A股需6位数字，港股为1-5位数字，美股为英文代码")
    else:
        try:
            with st.spinner(f"正在获取 {streak_market} · {streak_code} 的K线数据..."):
                raw_df = get_stock_ohlc_data(streak_code.strip(), streak_market)
                k_df = resample_ohlc(raw_df, k_period)

            if k_df.empty:
                st.error("❌ 获取到的数据为空，请检查代码是否正确")
            else:
                result = calc_candle_streaks(k_df, min_length=min_streak_len)
                bull = result["bullish"]
                bear = result["bearish"]
                top_df = top_streaks(result, limit=12)

                st.subheader(f"📊 {streak_market} · {streak_code.upper()} · {k_period} 统计结果")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("K线数量", f"{len(k_df)} 根")
                with col2:
                    max_bull = max([item["连续根数"] for item in bull], default=0)
                    st.metric("最长连续阳线", f"{max_bull} 根")
                with col3:
                    max_bear = max([item["连续根数"] for item in bear], default=0)
                    st.metric("最长连续阴线", f"{max_bear} 根")

                st.divider()
                st.subheader("📊 连续长度分布")
                st.plotly_chart(chart_streak_distribution(result), use_container_width=True)

                st.divider()
                st.subheader("📋 最长连续记录")
                if top_df.empty:
                    st.info(f"没有找到连续 {min_streak_len} 根及以上的阳线/阴线记录")
                else:
                    st.dataframe(
                        top_df.style.format({
                            "起始开盘": "{:.2f}",
                            "结束收盘": "{:.2f}",
                            "区间涨跌幅%": "{:.2f}",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

                with st.expander("查看原始K线数据"):
                    display_df = k_df.copy()
                    display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
                    st.dataframe(display_df.tail(300), use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"❌ 统计失败：{e}")
            if "Connection aborted" in str(e) or "RemoteDisconnected" in str(e):
                st.info("数据源连接被中断，请稍等后重试；A股偶尔会出现接口波动。")
            st.info("请检查：① 股票代码是否正确 ② 网络是否正常 ③ 数据源是否可用")

# ── 免责声明 ──────────────────────────────────────────────────────────
st.divider()
st.caption("⚠️ 仅供参考，不构成投资建议。市场有风险，投资需谨慎。")
