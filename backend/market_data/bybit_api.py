import logging
import time
import threading
from datetime import datetime, date, timedelta
import pandas as pd
from pybit.unified_trading import HTTP

# bybit apy key, can be set by environment variables
# BYBIT_API_KEY = "..."
# BYBIT_API_SECRET = "..."

logger = logging.getLogger(__name__)

session = HTTP(testnet=False)

# Global lock to prevent concurrent API calls
_api_lock = threading.Lock()
# Track active API calls to prevent overlapping requests for the same symbol
_active_requests = set()

def get_spot_tickers():
    """获取现货tickers，包含24h成交额等指标，用于按成交额排序"""
    with _api_lock:
        time.sleep(0.1)  # Small delay to prevent API rate limiting
        try:
            result = session.get_tickers(category="spot")
            if result.get('retCode') == 0:
                items = result['result']['list']
                df = pd.DataFrame(items)
                # 保留我们需要的字段
                cols = [
                    'symbol',
                    'lastPrice',
                    'highPrice24h',
                    'lowPrice24h',
                    'volume24h',
                    'turnover24h'
                ]
                for c in cols:
                    if c not in df.columns:
                        df[c] = None
                # 数值字段转成数值类型
                for c in ['lastPrice', 'highPrice24h', 'lowPrice24h', 'volume24h', 'turnover24h']:
                    df[c] = pd.to_numeric(df[c], errors='coerce')
                return df[cols]
            else:
                logger.error(f"Failed to get spot tickers: {result.get('retMsg')}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Exception in get_spot_tickers: {e}")
            return pd.DataFrame()

def get_symbols():
    """获取所有可用的交易对"""
    with _api_lock:
        time.sleep(0.1)  # Small delay to prevent API rate limiting
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

def get_kline(symbol: str, start_date: date, end_date: date, interval: str = "D") -> pd.DataFrame:
    """获取K线数据"""
    # Use lock to prevent concurrent API calls and check for duplicate requests
    request_key = f"{symbol}_{start_date}_{end_date}_{interval}"
    
    with _api_lock:
        if request_key in _active_requests:
            logger.warning(f"Duplicate request for {symbol} detected, skipping to prevent API conflicts")
            return pd.DataFrame()
        _active_requests.add(request_key)
    
    try:
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
        
        logger.info(f"Fetching kline data for {symbol} from {start_date} to {end_date} (interval: {interval})")
        
        all_klines = []
        seen_timestamps = set()
        max_iterations = 50  # 进一步减少最大迭代次数，避免超时
        iteration_count = 0
        
        while start_ts < end_ts and iteration_count < max_iterations:
            iteration_count += 1
            
            # 增加全局率限制延迟，防止API调用过于频繁
            if iteration_count > 1:
                time.sleep(0.5)  # 增加到500ms延迟以减少API冲突
                
            logger.debug(f"Fetching kline batch {iteration_count} for {symbol}, start_ts: {start_ts}")
            
            try:
                result = session.get_kline(
                    category="spot",
                    symbol=symbol,
                    interval=interval,
                    start=start_ts,
                    limit=1000 
                )
            except Exception as api_error:
                logger.error(f"API call failed for {symbol}: {api_error}")
                break
            
            if result['retCode'] == 0 and result['result']['list']:
                klines = result['result']['list']
                logger.debug(f"Received {len(klines)} klines for {symbol}")
                
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
                
                # move forward by interval
                if interval == "D":
                    step_ms = 24 * 60 * 60 * 1000
                elif interval == "60":
                    step_ms = 60 * 60 * 1000
                elif interval == "240":
                    step_ms = 4 * 60 * 60 * 1000
                else:
                    # default to daily step
                    step_ms = 24 * 60 * 60 * 1000
                
                new_start_ts = last_ts + step_ms
                
                # 防止无限循环：如果时间戳没有前进，强制退出
                if new_start_ts <= start_ts:
                    logger.warning(f"Time not advancing for {symbol}, breaking loop. start_ts: {start_ts}, new_start_ts: {new_start_ts}")
                    break
                    
                # 如果已经获取到结束时间，退出循环
                if last_ts >= end_ts:
                    logger.debug(f"Reached end time for {symbol}")
                    break
                    
                start_ts = new_start_ts
            else:
                # API返回错误或没有数据，退出循环
                if result.get('retCode') != 0:
                    logger.warning(f"API error for {symbol}: {result.get('retMsg')}")
                else:
                    logger.info(f"No more data available for {symbol}")
                break
        
        if iteration_count >= max_iterations:
            logger.warning(f"Maximum iterations reached for {symbol}, possible infinite loop prevented")
        
        if not all_klines:
            return pd.DataFrame()

        df = pd.DataFrame(all_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['date'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
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
    finally:
        # Always remove from active requests when done
        with _api_lock:
            _active_requests.discard(request_key)
