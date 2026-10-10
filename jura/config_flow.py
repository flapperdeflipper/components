from __future__ import annotations

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow

from .core import DOMAIN

# Jura's Bluetooth SIG company identifier (0x00AB) in BLE manufacturer data
JURA_MANUFACTURER_ID = 171


class FlowHandler(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        macs = sorted(
            {
                service_info.address
                for service_info in bluetooth.async_discovered_service_info(self.hass)
                if JURA_MANUFACTURER_ID in service_info.advertisement.manufacturer_data
            }
        )

        if not macs:
            return self.async_show_form(step_id="user", errors={"base": "no_devices"})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("mac"): vol.In(macs),
                }
            ),
        )
