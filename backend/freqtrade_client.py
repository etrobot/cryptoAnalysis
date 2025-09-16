from __future__ import annotations
import os
import logging
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)

# Environment-based configuration
API_BASE_URL = os.getenv("FREQTRADE_API_URL", "http://freqtrade-bot:8080")  # default to docker service
API_USERNAME = os.getenv("FREQTRADE_API_USERNAME")
API_PASSWORD = os.getenv("FREQTRADE_API_PASSWORD")
API_TOKEN = os.getenv("FREQTRADE_API_TOKEN")  # If provided and valid (JWT), preferred over username/password
REQUEST_TIMEOUT = int(os.getenv("FREQTRADE_API_TIMEOUT", "15"))


def _api_url(path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    # Freqtrade usually serves under /api/v1
    if not path.startswith("/api/"):
        path = f"/api/v1{path}"
    return f"{API_BASE_URL.rstrip('/')}{path}"


def _get_headers(token: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_auth() -> Optional[tuple]:
    """Get basic authentication credentials."""
    if API_USERNAME and API_PASSWORD:
        return (API_USERNAME, API_PASSWORD)
    return None


def obtain_token() -> Optional[str]:
    """Obtain JWT token from Freqtrade API using username/password.
    If API_TOKEN is already a valid-looking JWT (contains dots), reuse it.
    """
    global API_TOKEN
    # Reuse cached token if it looks like a JWT
    if API_TOKEN and API_TOKEN.count(".") >= 2:
        return API_TOKEN

    if not API_USERNAME or not API_PASSWORD:
        logger.warning("No Freqtrade API credentials provided; API calls may fail if auth is required.")
        return None
    try:
        url = _api_url("/token")
        resp = requests.post(url, json={"username": API_USERNAME, "password": API_PASSWORD}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        if token:
            API_TOKEN = token
            return token
        logger.error(f"No token in response from {url}: {data}")
    except Exception as e:
        logger.error(f"Failed to obtain Freqtrade API token: {e}")
    return None


def _get_token_if_needed(token: Optional[str] = None) -> Optional[str]:
    """Helper function to get token if not provided. Avoid using non-JWT env tokens (e.g., WS tokens)."""
    if token and token.count('.') >= 2:
        return token
    # If API_TOKEN was provided via env but is not a JWT, ignore and obtain a proper one.
    return obtain_token()


def get_api_credentials() -> Dict[str, Optional[str]]:
    """Get current API credentials configuration."""
    return {
        "api_url": API_BASE_URL,
        "username": API_USERNAME,
        "password": "***" if API_PASSWORD else None,  # Hide password
        "has_token": bool(API_TOKEN),
        "timeout": REQUEST_TIMEOUT
    }


def test_credentials() -> Dict[str, Any]:
    """Test Freqtrade API credentials and connection."""
    result = {
        "api_url": API_BASE_URL,
        "credentials_available": bool(API_USERNAME and API_PASSWORD) or bool(API_TOKEN),
        "connection_healthy": False,
        "token_obtained": False,
        "error": None
    }
    
    try:
        # Test connection
        if health():
            result["connection_healthy"] = True
            
        # Test token acquisition
        token = obtain_token()
        if token:
            result["token_obtained"] = True
            result["token_length"] = len(token)
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Credential test failed: {e}")
    
    return result


def refresh_token() -> Optional[str]:
    """Force refresh the API token."""
    global API_TOKEN
    API_TOKEN = None  # Clear cached token
    return obtain_token()


def health(token: Optional[str] = None) -> bool:
    """Check if Freqtrade API is healthy."""
    try:
        # First try with basic auth
        auth = _get_auth()
        url = _api_url("/ping")
        resp = requests.get(url, auth=auth, timeout=REQUEST_TIMEOUT)
        if resp.ok:
            return True
        
        # Fallback to token-based auth
        token = _get_token_if_needed(token)
        resp = requests.get(url, headers=_get_headers(token), timeout=REQUEST_TIMEOUT)
        return resp.ok
    except Exception as e:
        logger.warning(f"Freqtrade API health check failed: {e}")
        return False


def list_open_trades(token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get list of open trades from Freqtrade."""
    try:
        # First try with basic auth
        auth = _get_auth()
        url = _api_url("/status")  # Changed from /open_trades to /status
        resp = requests.get(url, auth=auth, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            # Fallback to token-based auth
            token = _get_token_if_needed(token)
            resp = requests.get(url, headers=_get_headers(token), timeout=REQUEST_TIMEOUT)
        
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "trades" in data:
            return data.get("trades", [])
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to list open trades: {e}")
        return []


def forceentry(pair: str, stake_amount: Optional[float] = None, token: Optional[str] = None) -> bool:
    """Force entry for a trading pair."""
    payload: Dict[str, Any] = {"pair": pair}
    if stake_amount is not None:
        payload["stake_amount"] = stake_amount
    try:
        # First try with basic auth using the correct endpoint
        auth = _get_auth()
        url = _api_url("/forceenter")  # Changed from /forceentry to /forceenter
        resp = requests.post(url, json=payload, auth=auth, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            # Fallback to token-based auth
            token = _get_token_if_needed(token)
            resp = requests.post(url, json=payload, headers=_get_headers(token), timeout=REQUEST_TIMEOUT)
        
        if resp.ok:
            logger.info(f"Force entry sent for {pair}")
            return True
        logger.error(f"Force entry failed for {pair}: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Force entry exception for {pair}: {e}")
    return False


def forceexit_by_pair(pair: str, token: Optional[str] = None) -> int:
    """Force-exit all open trades for a given pair. Returns number of closes attempted."""
    trades = list_open_trades(token)
    count = 0
    for t in trades:
        if t.get("pair") == pair:
            trade_id = t.get("trade_id") or t.get("id")
            if trade_id is None:
                continue
            try:
                # First try with basic auth
                auth = _get_auth()
                url = _api_url(f"/forceexit/{trade_id}")
                resp = requests.post(url, auth=auth, timeout=REQUEST_TIMEOUT)
                if not resp.ok:
                    # Fallback to token-based auth
                    token = _get_token_if_needed(token)
                    resp = requests.post(url, headers=_get_headers(token), timeout=REQUEST_TIMEOUT)
                
                if resp.ok:
                    count += 1
                else:
                    logger.error(f"Force exit failed for trade {trade_id} ({pair}): {resp.status_code} {resp.text}")
            except Exception as e:
                logger.error(f"Force exit exception for trade {trade_id} ({pair}): {e}")
    return count


# Note: Function uses /forceenter endpoint but keeps forceentry name for backward compatibility
