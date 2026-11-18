"""Config and options flows for the AIRSPA AI climate integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_APPID,
    CONF_DEVICE_ID,
    CONF_SERVER_URL,
    CONF_WS_URL,
    DEFAULT_DEVICE_NAME,
    DEFAULT_SERVER_URL,
    DOMAIN,
    build_ws_url,
    is_valid_ws_url,
    server_base_from_ws_url,
)


def _schema(defaults: dict, include_device: bool) -> vol.Schema:
    """Build the setup or options form without a DID placeholder in labels."""
    did = defaults.get(CONF_DEVICE_ID, "")
    server_default = server_base_from_ws_url(
        defaults.get(CONF_WS_URL, ""),
        did,
    )

    fields = {
        vol.Required(
            CONF_APPID, default=defaults.get(CONF_APPID, "")
        ): str,
    }
    if include_device:
        fields[
            vol.Required(CONF_DEVICE_ID, default=did)
        ] = str
    fields.update(
        {
            vol.Optional(
                CONF_SERVER_URL, default=server_default
            ): str,
        }
    )
    return vol.Schema(fields)


def _prepare_input(
    user_input: dict,
    device_id: str,
    errors: dict,
) -> dict:
    """Normalize text fields and append the DID to the server address."""
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in user_input.items()
    }
    server_url = cleaned.get(CONF_SERVER_URL) or DEFAULT_SERVER_URL
    resolved = build_ws_url(server_url, device_id)
    if not is_valid_ws_url(resolved):
        errors[CONF_SERVER_URL] = "invalid_ws_url"
    cleaned[CONF_DEVICE_ID] = device_id
    cleaned[CONF_SERVER_URL] = server_url
    cleaned[CONF_WS_URL] = resolved
    return cleaned


class AirspaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one device without hardcoding private capture values."""

    VERSION = 5

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            prepared = {
                key: value.strip() if isinstance(value, str) else value
                for key, value in user_input.items()
            }
            if not prepared.get(CONF_APPID):
                errors[CONF_APPID] = "required"
            if not prepared.get(CONF_DEVICE_ID):
                errors[CONF_DEVICE_ID] = "required"

            if not errors:
                prepared = _prepare_input(
                    prepared,
                    prepared[CONF_DEVICE_ID],
                    errors,
                )
                if not errors:
                    await self.async_set_unique_id(prepared[CONF_DEVICE_ID])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=DEFAULT_DEVICE_NAME,
                        data=prepared,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}, include_device=True),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return AirspaOptionsFlow(config_entry)


class AirspaOptionsFlow(config_entries.OptionsFlow):
    """Allow endpoint and credential changes without editing source files."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        current = {**self._config_entry.data, **self._config_entry.options}
        if user_input is not None:
            device_id = user_input.get(CONF_DEVICE_ID, "")
            if not user_input.get(CONF_APPID):
                errors[CONF_APPID] = "required"
            if not device_id:
                errors[CONF_DEVICE_ID] = "required"
            elif device_id != current.get(CONF_DEVICE_ID):
                errors[CONF_DEVICE_ID] = "device_id_read_only"
            if not errors:
                prepared = _prepare_input(
                    user_input,
                    device_id,
                    errors,
                )
                if not errors:
                    return self.async_create_entry(title="", data=prepared)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current, include_device=True),
            errors=errors,
            description_placeholders={
                CONF_DEVICE_ID: current.get(CONF_DEVICE_ID, "")
            },
        )
