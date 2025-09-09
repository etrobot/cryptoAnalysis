import logging
from datetime import datetime, date, timedelta
import pandas as pd
from pybit.unified_trading import HTTP

# bybit apy key, can be set by environment variables
# BYBIT_API_KEY = "..."
# BYBIT_API_SECRET = "..."

logger = logging.getLogger(__name__)

session = HTTP(testnet=False)

def get_symbols():
    """获取所有可用的交易对"""
    try:
        result = session.get_instruments_info(category="spot")
        if result['retCode'] == 0:
            symbols = result['result']['list']
            df = pd.DataFrame(symbols)
            df = df[df['status'] == 'Trading']
            df = df[df['quoteCoin'] == 'USDT']
            df = df[['symbol', 'baseCoin', 'quoteCoin']]
            df['name'] = df['baseCoin'] + '/' + df['quoteCoin']
            return df
        else:
            logger.error(f"Failed to get symbols from Bybit: {result['retMsg']}")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Exception in get_symbols: {e}")
        return pd.DataFrame()

def get_kline(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    """获取K线数据"""
    try:
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
        
        all_klines = []
        seen_timestamps = set()
        while start_ts < end_ts:
            result = session.get_kline(
                category="spot",
                symbol=symbol,
                interval="D",  # Daily kline
                start=start_ts,
                limit=1000 
            )
            
            if result['retCode'] == 0 and result['result']['list']:
                klines = result['result']['list']
                # 去重处理，确保每个时间戳只添加一次
                unique_klines = []
                for kline in klines:
                    timestamp = kline[0]
                    if timestamp not in seen_timestamps:
                        seen_timestamps.add(timestamp)
                        unique_klines.append(kline)
                
                all_klines.extend(unique_klines)
                # bybit returns from oldest to newest, so the last one is the newest
                last_ts = int(klines[-1][0])
                # move to the next day
                start_ts = last_ts + (24 * 60 * 60 * 1000)
            else:
                break
        
        if not all_klines:
            return pd.DataFrame()

        df = pd.DataFrame(all_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df['turnover'] = pd.to_numeric(df['turnover'])
        
        # 按日期排序，确保数据顺序正确
        df = df.sort_values('timestamp')
        
        # calculate change_pct
        df['change_pct'] = (df['close'].pct_change() * 100).fillna(0)

        return df[['date', 'open', 'high', 'low', 'close', 'volume', 'turnover', 'change_pct']]
        
    except Exception as e:
        logger.error(f"Exception in get_kline for {symbol}: {e}")
        return pd.DataFrame()
