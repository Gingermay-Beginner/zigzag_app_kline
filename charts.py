import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List, Dict, Any


def chart_zigzag_overlay(df: pd.DataFrame, pivots: List[Dict[str, Any]]) -> go.Figure:
    """
    生成ZigZag叠加收盘价的交互式图表。
    
    Args:
        df: 包含 date, close 列的DataFrame
        pivots: calc_zigzag_from_df 返回的转折点列表
    
    Returns:
        Plotly Figure对象
    """
    fig = go.Figure()

    # 1. 收盘价细灰线
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['close'],
        mode='lines',
        line=dict(color='rgba(200,200,200,0.4)', width=1),
        name='收盘价',
        hoverinfo='skip',
    ))

    if pivots:
        # 2. ZigZag折线：按波段着色（涨段绿色，跌段红色）
        for i in range(1, len(pivots)):
            p0 = pivots[i - 1]
            p1 = pivots[i]
            color = '#26a69a' if p1['wave_type'] == 'up' else '#ef5350'
            fig.add_trace(go.Scatter(
                x=[p0['date'], p1['date']],
                y=[p0['price'], p1['price']],
                mode='lines',
                line=dict(color=color, width=3),
                showlegend=False,
                hoverinfo='skip',
            ))

        # 3. 转折点 scatter
        highs = [p for p in pivots if p['type'] == 'high']
        lows = [p for p in pivots if p['type'] == 'low']

        def hover_text(p):
            date_str = pd.Timestamp(p['date']).strftime('%Y-%m-%d') if p['date'] is not None else 'N/A'
            direction = '↑' if p['wave_type'] == 'up' else '↓'
            return (
                f"日期: {date_str}<br>"
                f"价格: {p['price']:.2f}<br>"
                f"本段: {direction} {abs(p['wave_pct']):.1f}%<br>"
                f"持续: {p['wave_days']} 天"
            )

        if highs:
            fig.add_trace(go.Scatter(
                x=[p['date'] for p in highs],
                y=[p['price'] for p in highs],
                mode='markers',
                marker=dict(
                    symbol='triangle-down',
                    size=10,
                    color='#ef5350',
                    line=dict(color='#ff8a80', width=1),
                ),
                name='高点',
                text=[hover_text(p) for p in highs],
                hovertemplate='%{text}<extra></extra>',
            ))

        if lows:
            fig.add_trace(go.Scatter(
                x=[p['date'] for p in lows],
                y=[p['price'] for p in lows],
                mode='markers',
                marker=dict(
                    symbol='triangle-up',
                    size=10,
                    color='#26a69a',
                    line=dict(color='#80cbc4', width=1),
                ),
                name='低点',
                text=[hover_text(p) for p in lows],
                hovertemplate='%{text}<extra></extra>',
            ))

        # 4. 当前价格黄色水平虚线
        current_price = df['close'].iloc[-1]
        fig.add_hline(
            y=current_price,
            line=dict(color='#00e5ff', width=2, dash='dash'),
            annotation_text=f"  当前价 {current_price:.2f}",
            annotation_position="top right",
            annotation_font=dict(color='#00e5ff', size=12),
        )

    fig.update_layout(
        template='plotly_dark',
        height=600,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
        ),
        hovermode='closest',
        plot_bgcolor='#1a1a2e',
        paper_bgcolor='#1a1a2e',
    )

    return fig


def chart_wave_bars(pivots: List[Dict[str, Any]]) -> go.Figure:
    """
    生成每波涨跌幅柱状图。
    
    Args:
        pivots: calc_zigzag_from_df 返回的转折点列表（跳过第一个无波段信息的点）
    
    Returns:
        Plotly Figure对象
    """
    fig = go.Figure()

    if not pivots or len(pivots) < 2:
        fig.update_layout(
            template='plotly_dark',
            height=350,
            title=dict(text='暂无波段数据', font=dict(color='gray')),
        )
        return fig

    # 从第二个点开始（第一个点wave_pct=0无意义）
    waves = pivots[1:]

    x_labels = []
    y_values = []
    colors = []
    hover_texts = []

    for i, p in enumerate(waves):
        # X轴标签：波段序号 + 日期范围
        prev = pivots[i]
        prev_date = pd.Timestamp(prev['date']).strftime('%m/%d') if prev['date'] is not None else '?'
        curr_date = pd.Timestamp(p['date']).strftime('%m/%d') if p['date'] is not None else '?'
        label = f"W{i + 1}<br>{prev_date}→{curr_date}"
        x_labels.append(label)

        y_values.append(p['wave_pct'])
        colors.append('#26a69a' if p['wave_type'] == 'up' else '#ef5350')

        # Hover详细信息
        direction = '上涨' if p['wave_type'] == 'up' else '下跌'
        prev_date_full = pd.Timestamp(prev['date']).strftime('%Y-%m-%d') if prev['date'] is not None else '?'
        curr_date_full = pd.Timestamp(p['date']).strftime('%Y-%m-%d') if p['date'] is not None else '?'
        hover = (
            f"波段 {i + 1}：{direction}<br>"
            f"时间: {prev_date_full} → {curr_date_full}<br>"
            f"起点: {prev['price']:.2f}<br>"
            f"终点: {p['price']:.2f}<br>"
            f"涨跌幅: {p['wave_pct']:+.1f}%<br>"
            f"持续: {p['wave_days']} 天"
        )
        hover_texts.append(hover)

    fig.add_trace(go.Bar(
        x=x_labels,
        y=y_values,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in y_values],
        textposition='outside',
        textfont=dict(size=10),
        hovertext=hover_texts,
        hovertemplate='%{hovertext}<extra></extra>',
        name='波段涨跌幅',
    ))

    fig.update_layout(
        template='plotly_dark',
        height=350,
        margin=dict(l=40, r=40, t=40, b=60),
        xaxis=dict(showgrid=False, tickfont=dict(size=9)),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.1)',
            zeroline=True,
            zerolinecolor='rgba(255,255,255,0.3)',
            title='涨跌幅 %',
        ),
        bargap=0.3,
        plot_bgcolor='#1a1a2e',
        paper_bgcolor='#1a1a2e',
    )

    return fig
