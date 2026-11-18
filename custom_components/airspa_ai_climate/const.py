"""Constants for the AIRSPA AI climate integration."""

from urllib.parse import urlsplit

DOMAIN = "airspa_ai_climate"
INTEGRATION_NAME = "艾尔斯派 AI 五恒"
DEFAULT_DEVICE_NAME = "AI 五恒系统"

CONF_APPID = "appid"
CONF_DEVICE_ID = "device_id"
CONF_SERVER_URL = "server_url"
CONF_WS_URL = "ws_url"

# The AppID and DID are supplied by the user at setup time. No account,
# application identifier or device identifier is baked into the source.
DEFAULT_SERVER_URL = "wss://aisp.airspa.cn:81"
DEFAULT_WS_URL = DEFAULT_SERVER_URL + "/{device_id}"
WS_ORIGIN = "https://aisp.airspa.cn:81"
WS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/144.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Windows WindowsWechat/WMPF "
    "WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541d41) XWEB/25560"
)
LEGACY_DEFAULT_WS_URLS = (
    "ws://sandbox.gizwits.com:8080/ws/app/v1",
    "wss://aisp.airspa.cn:81/ws/app/v1",
)

READ_NAMES = "1FFFFFFF"
HEARTBEAT_INTERVAL = 180
PING_INTERVAL = 30
READ_REFRESH_INTERVAL = 5
WS_PING_INTERVAL = 10
WS_PING_TIMEOUT = 10
RECONNECT_DELAY = 3


def build_ws_url(server_url: str, device_id: str) -> str:
    """Join a server base and DID into the final device WebSocket URL."""
    base = (server_url or "").strip()
    did = (device_id or "").strip().strip("/")
    if not base:
        base = DEFAULT_SERVER_URL
    if "{device_id}" in base:
        return base.replace("{device_id}", did).rstrip("/")
    base = base.rstrip("/")
    if did and base.endswith("/" + did):
        return base
    return f"{base}/{did}" if did else base


def server_base_from_ws_url(ws_url: str, device_id: str) -> str:
    """Remove the DID suffix from a stored WebSocket URL for form display."""
    url = (ws_url or "").strip()
    did = (device_id or "").strip().strip("/")
    if not url:
        return DEFAULT_SERVER_URL
    if "{device_id}" in url:
        return url.split("{device_id}", 1)[0].rstrip("/")
    if did:
        suffix = "/" + did
        if url.rstrip("/").endswith(suffix):
            return url.rstrip("/")[: -len(suffix)]
    return url.rstrip("/")


def is_valid_ws_url(value: str) -> bool:
    """Return whether a value is an absolute ws:// or wss:// URL."""
    try:
        parsed = urlsplit((value or "").strip())
        return parsed.scheme in {"ws", "wss"} and bool(parsed.hostname)
    except ValueError:
        return False
