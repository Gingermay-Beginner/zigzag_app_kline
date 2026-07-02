import pandas as pd
from typing import List, Dict, Any


def calc_zigzag(prices: pd.Series, threshold: float = 0.20) -> List[Dict[str, Any]]:
    """
    计算ZigZag转折点。

    Args:
        prices: 价格序列（Series），index为整数，对应日期需通过dates参数传入
        threshold: 波动阈值，默认0.20（20%）

    Returns:
        转折点列表，每个元素包含：
        {
            'idx': int,           # 在prices中的索引位置
            'date': datetime,
            'price': float,
            'type': 'high' or 'low',
            'wave_pct': float,    # 本段涨跌幅%（相对上一个转折点）
            'wave_days': int,     # 本段持续天数
            'wave_type': 'up' or 'down'
        }
    """
    # 保留原始索引（通常是日期），后续通过 idx 回写转折点日期
    original_index = prices.index
    n = len(prices)
    if n < 2:
        return []

    pivots_raw = []  # 存储 (idx, price, type)

    # 初始化：从第一个点开始
    direction = None  # 'up' or 'down'，初始未定
    extreme_idx = 0
    extreme_price = float(prices.iloc[0])

    for i in range(1, n):
        price = float(prices.iloc[i])

        if direction is None:
            # 确定初始方向
            if price > extreme_price:
                direction = 'up'
                extreme_idx = i
                extreme_price = price
            elif price < extreme_price:
                direction = 'down'
                extreme_idx = i
                extreme_price = price
            # 价格相同则继续等待
        elif direction == 'up':
            if price > extreme_price:
                # 继续创新高，更新候选高点
                extreme_idx = i
                extreme_price = price
            else:
                # 检查是否回撤超过阈值
                drawdown = (extreme_price - price) / extreme_price
                if drawdown >= threshold:
                    # 确认高点
                    pivots_raw.append((extreme_idx, extreme_price, 'high'))
                    # 切换方向，以当前点为新候选低点
                    direction = 'down'
                    extreme_idx = i
                    extreme_price = price
        elif direction == 'down':
            if price < extreme_price:
                # 继续创新低，更新候选低点
                extreme_idx = i
                extreme_price = price
            else:
                # 检查是否反弹超过阈值
                rebound = (price - extreme_price) / extreme_price
                if rebound >= threshold:
                    # 确认低点
                    pivots_raw.append((extreme_idx, extreme_price, 'low'))
                    # 切换方向，以当前点为新候选高点
                    direction = 'up'
                    extreme_idx = i
                    extreme_price = price

    # 追加最后一个候选点
    if direction == 'up':
        last_type = 'high'
    elif direction == 'down':
        last_type = 'low'
    else:
        last_type = 'low'

    # 避免重复追加
    if not pivots_raw or pivots_raw[-1][0] != extreme_idx:
        pivots_raw.append((extreme_idx, extreme_price, last_type))

    # 转换为带统计信息的字典列表
    pivots = []
    for k, (idx, price, ptype) in enumerate(pivots_raw):
        if k == 0:
            wave_pct = 0.0
            wave_days = 0
            wave_type = 'up' if ptype == 'high' else 'down'
        else:
            prev_idx, prev_price, prev_type = pivots_raw[k - 1]
            wave_pct = (price - prev_price) / prev_price * 100
            wave_days = idx - prev_idx
            wave_type = 'up' if price > prev_price else 'down'

        # 获取日期
        if hasattr(original_index, '__getitem__'):
            try:
                date_val = original_index[idx]
                if hasattr(date_val, 'to_pydatetime'):
                    date_val = date_val.to_pydatetime()
            except Exception:
                date_val = None
        else:
            date_val = None

        pivots.append({
            'idx': idx,
            'date': date_val,
            'price': price,
            'type': ptype,
            'wave_pct': round(wave_pct, 2),
            'wave_days': wave_days,
            'wave_type': wave_type,
        })

    return pivots


def calc_zigzag_from_df(df: 'pd.DataFrame', threshold: float = 0.20) -> list:
    """
    从包含 date, close 列的DataFrame计算ZigZag。
    date列作为索引传入，确保日期正确关联。
    """
    prices = df.set_index('date')['close']
    return calc_zigzag(prices, threshold)
