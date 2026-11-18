"""Gizwits-compatible WebSocket client for the raw AI climate protocol."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import websockets
from websockets.protocol import State

from .const import (
    HEARTBEAT_INTERVAL,
    PING_INTERVAL,
    READ_NAMES,
    READ_REFRESH_INTERVAL,
    RECONNECT_DELAY,
    WS_ORIGIN,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_USER_AGENT,
)
from .protocol import (
    RawFrameError,
    SWING_OFF_RAW,
    SWING_ON_RAW,
    fan_speed_raw,
    mode_raw,
    parse_status_frame,
    power_raw,
)

_LOGGER = logging.getLogger(__name__)


class AirspaWebsocketClient:
    """Maintain a cloud connection and publish parsed status updates."""

    def __init__(
        self,
        appid: str,
        device_id: str,
        ws_url: str,
    ) -> None:
        self.appid = appid
        self.device_id = device_id
        self.ws_url = ws_url.replace("{device_id}", device_id)

        self.status: dict[str, int | float] = {}
        self.last_error: str | None = None
        self.last_stage = "idle"
        self.last_message_cmd: str | None = None
        self.subscription_status = "not_requested"
        self.raw_frames_received = 0
        self.refresh_reads_sent = 0
        self.connection_attempts = 0
        self.login_responses = 0
        self.last_login_result = "未开始"
        self.last_raw_length: int | None = None
        self.last_raw_error: str | None = None
        self.last_close_code: int | None = None
        self.last_close_reason: str | None = None
        self._callbacks: set[Callable[[], None]] = set()
        self._running = False
        self._logged_in = False
        self._task: asyncio.Task[None] | None = None
        self._retry_task: asyncio.Task[None] | None = None
        self._ws: Any = None
        self._received_status_on_connection = False

    @property
    def is_connected(self) -> bool:
        """Return True when the socket is open and the session is usable."""
        return (
            self._ws is not None
            and self._ws.state == State.OPEN
            and (self._logged_in or self._received_status_on_connection)
        )

    @property
    def has_data(self) -> bool:
        return bool(self.status)

    def register_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register an entity update callback and return its remover."""
        self._callbacks.add(callback)

        def _remove() -> None:
            self._callbacks.discard(callback)

        return _remove

    def _notify(self) -> None:
        for callback in tuple(self._callbacks):
            try:
                callback()
            except Exception:  # noqa: BLE001 - isolate entity callbacks
                _LOGGER.exception("Entity update callback failed")

    async def async_start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._run())

    async def async_stop(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 - shutdown must continue
                _LOGGER.debug("Ignoring WebSocket close error", exc_info=True)

        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._ws = None
        self._logged_in = False
        self.last_stage = "disconnected"
        self._notify()

    async def _run(self) -> None:
        while self._running:
            heartbeat_task: asyncio.Task[None] | None = None
            refresh_task: asyncio.Task[None] | None = None
            self.connection_attempts += 1
            try:
                async with websockets.connect(
                    self.ws_url,
                    origin=WS_ORIGIN,
                    user_agent_header=WS_USER_AGENT,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                    close_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._logged_in = False
                    self._received_status_on_connection = False
                    self.last_login_result = "等待 login_res"
                    self.last_error = None
                    self.last_close_code = None
                    self.last_close_reason = None
                    self.last_stage = "socket_connected"
                    self._notify()
                    await self._send_json(self._login_payload())
                    # The mini-program capture sends its first c2s_read directly
                    # after login_req without waiting for login_res.
                    await self.async_request_update()
                    self.last_stage = "login_and_read_sent"
                    self._notify()
                    heartbeat_task = asyncio.create_task(self._heartbeat())
                    refresh_task = asyncio.create_task(self._refresh_status())
                    self._retry_task = asyncio.create_task(
                        self._retry_read_strategy()
                    )
                    await self._listen()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - reconnect on network errors
                self.last_error = f"{type(err).__name__}: {err}"
                _LOGGER.warning("AI climate WebSocket disconnected: %s", self.last_error)
            finally:
                for task in (heartbeat_task, refresh_task, self._retry_task):
                    if task is not None:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                self._retry_task = None
                self._record_close()
                self._ws = None
                self._logged_in = False
                self._received_status_on_connection = False
                self.last_stage = "disconnected"
                self._notify()

            if self._running:
                await asyncio.sleep(RECONNECT_DELAY)

    def _login_payload(self) -> dict[str, Any]:
        # This device endpoint authenticates by DID and never sends uid/token.
        return {
            "cmd": "login_req",
            "data": {
                "appid": self.appid,
                "p0_type": "custom",
                "heartbeat_interval": HEARTBEAT_INTERVAL,
                "auto_subscribe": False,
            },
        }

    async def _listen(self) -> None:
        async for message in self._ws:
            try:
                msg = json.loads(message)
            except (TypeError, json.JSONDecodeError):
                _LOGGER.debug("Ignoring non-JSON WebSocket message")
                continue

            cmd = msg.get("cmd")
            data = msg.get("data", {})
            self.last_message_cmd = cmd

            if cmd == "login_res":
                self.login_responses += 1
                if not data.get("success", False):
                    self.last_login_result = "失败"
                    self.last_error = "云端登录失败（login_res.success=false）"
                    _LOGGER.warning("AI climate cloud login failed")
                    await self._ws.close(code=1008)
                    continue

                self._logged_in = True
                self.last_login_result = "成功"
                self.last_error = None
                self.last_stage = "login_succeeded"
                self.subscription_status = "not_requested"
                self._notify()

            elif cmd == "subscribe_res":
                failed = data.get("failed", []) if isinstance(data, dict) else []
                if failed:
                    self.subscription_status = "failed"
                    self.last_error = "设备订阅失败，请检查 DID 和 WebSocket 地址"
                    _LOGGER.warning("AI climate device subscription failed")
                else:
                    self.subscription_status = "subscribed"
                    _LOGGER.debug("AI climate device subscription acknowledged")
                self.last_stage = "subscribe_res"
                self._notify()

            elif cmd == "s2c_raw":
                self._received_status_on_connection = True
                raw = data.get("raw") if isinstance(data, dict) else None
                self.raw_frames_received += 1
                if isinstance(raw, str):
                    try:
                        self.last_raw_length = len(bytes.fromhex(raw))
                    except ValueError:
                        self.last_raw_length = None
                elif isinstance(raw, (bytes, bytearray, list, tuple)):
                    self.last_raw_length = len(raw)
                else:
                    self.last_raw_length = None

                try:
                    parsed = parse_status_frame(raw)
                except RawFrameError as err:
                    self.last_raw_error = str(err)
                    self.last_stage = "raw_unsupported"
                    _LOGGER.debug("Ignoring unsupported raw frame: %s", err)
                    self._notify()
                    continue
                self.status.update(parsed)
                self.last_error = None
                self.last_raw_error = None
                self.last_stage = "status_received"
                self._notify()

            elif cmd == "s2c_invalid_msg":
                self.last_error = (
                    data.get("msg", "云端返回非法消息")
                    if isinstance(data, dict)
                    else "云端返回非法消息"
                )
                self.last_stage = "invalid_message"
                _LOGGER.warning("AI climate cloud rejected a message: %s", self.last_error)
                self._notify()

        self._record_close()

    def _record_close(self) -> None:
        """Persist the server close code without exposing message contents."""
        ws = self._ws
        if ws is None:
            return
        code = getattr(ws, "close_code", None)
        reason = getattr(ws, "close_reason", None)
        if code is not None:
            self.last_close_code = code
            self.last_close_reason = reason
            if not self.last_error:
                self.last_error = (
                    f"云端关闭连接: code={code}, reason={reason or '无'}"
                )

    async def _heartbeat(self) -> None:
        while self._ws is not None and self._ws.state == State.OPEN:
            await asyncio.sleep(PING_INTERVAL)
            if self._ws is not None and self._ws.state == State.OPEN:
                await self._send_json({"cmd": "ping"})

    async def _refresh_status(self) -> None:
        """Periodically read status so the device does not fall back asleep."""
        while self._ws is not None and self._ws.state == State.OPEN:
            await asyncio.sleep(READ_REFRESH_INTERVAL)
            try:
                if (
                    self._ws is not None
                    and self._ws.state == State.OPEN
                ):
                    await self.async_request_update()
                    self.refresh_reads_sent += 1
                    self._notify()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - retry on next interval
                self.last_error = f"定期刷新失败: {type(err).__name__}: {err}"
                _LOGGER.debug("Periodic status refresh failed: %s", self.last_error)
                self._notify()

    async def _retry_read_strategy(self) -> None:
        """Try read-only fallbacks only after the first read has been sent."""
        try:
            await asyncio.sleep(8)
            if self._ws is None or self._ws.state != State.OPEN or self.has_data:
                return
            self.last_stage = "retry_read_all"
            await self.async_request_update(include_names=False)
            self._notify()

            await asyncio.sleep(8)
            if self._ws is None or self._ws.state != State.OPEN or self.has_data:
                return
            self.subscription_status = "requested"
            self.last_stage = "retry_subscribe"
            await self._send_json(
                {
                    "cmd": "subscribe_req",
                    "data": [{"did": self.device_id}],
                }
            )
            await asyncio.sleep(0.5)
            await self.async_request_update()
            self.last_stage = "retry_subscribe_read_sent"
            self._notify()
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - main listener handles reconnect
            self.last_error = f"读取回退失败: {type(err).__name__}: {err}"
            _LOGGER.debug("Read fallback failed: %s", self.last_error)
            self._notify()

    async def async_set_power(self, power: bool) -> None:
        """Send the captured power command; state updates only from s2c_raw."""
        await self.async_set_raw_command(power_raw(power), "开关机")

    async def async_set_mode(self, mode: int) -> None:
        """Send a captured mode command; state updates only from s2c_raw."""
        await self.async_set_raw_command(mode_raw(mode), "切换模式")

    async def async_set_fan_speed(self, speed: int) -> None:
        """Send a captured fan-speed command."""
        await self.async_set_raw_command(fan_speed_raw(speed), "调整风速")

    async def async_set_controls(self, controls: dict[str, Any]) -> None:
        """Apply a control set in the same config-driven way as the AC mapping.

        The device accepts one five-byte raw command at a time, so a mode
        control set is split into its power and mode commands here.  When a
        mode requires power-on, wait for the status frame to report power on
        before sending the mode command.
        """
        allowed = {"power", "mode", "fan_speed", "swing"}
        unknown = set(controls) - allowed
        if unknown:
            raise ValueError(f"Unsupported control fields: {sorted(unknown)}")
        if not controls:
            return

        if "power" in controls:
            power = bool(controls["power"])
            await self.async_set_power(power)
            if not power:
                return
            if "mode" in controls:
                for _ in range(20):
                    if self.status.get("power") == 1:
                        break
                    await asyncio.sleep(0.15)
                await asyncio.sleep(0.2)

        if "mode" in controls:
            await self.async_set_mode(int(controls["mode"]))
        if "fan_speed" in controls:
            await self.async_set_fan_speed(int(controls["fan_speed"]))
        if "swing" in controls:
            raw = SWING_ON_RAW if controls["swing"] else SWING_OFF_RAW
            action = "开启摆风" if controls["swing"] else "关闭摆风"
            await self.async_set_raw_command(raw, action)

    async def async_set_raw_command(self, raw: str, action: str) -> None:
        """Send one validated five-byte raw command."""
        if not self.is_connected:
            raise RuntimeError(f"云端未连接，无法{action}")
        try:
            command = bytes.fromhex(raw)
        except ValueError as err:
            raise ValueError(f"无效的五字节指令: {raw}") from err
        if len(command) != 5:
            raise ValueError(f"无效的五字节指令: {raw}")
        await self._send_json(
            {
                "cmd": "c2s_raw",
                "data": {"did": self.device_id, "raw": raw},
            }
        )

    async def async_request_update(self, include_names: bool = True) -> None:
        """Send the captured read shape, or read all fields as a fallback."""
        if self._ws is None or self._ws.state != State.OPEN:
            return
        data: dict[str, Any] = {"did": self.device_id}
        if include_names:
            data["names"] = READ_NAMES
        await self._send_json({"cmd": "c2s_read", "data": data})

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            return
        # Never log the payload: it can contain the DID or user credentials.
        await self._ws.send(json.dumps(payload, separators=(",", ":")))
