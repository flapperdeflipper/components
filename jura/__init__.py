from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .core import DOMAIN
from .core.device import Device, EmptyModel, UnsupportedModel, get_machine

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "button", "number", "select", "switch", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    devices: dict[str, Device] = hass.data.setdefault(DOMAIN, {})

    async def setup_device(
        service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Resolve the machine model and forward platforms once it is seen."""
        manufacturer_data = service_info.advertisement.manufacturer_data.get(171)
        if manufacturer_data is None:
            return
        try:
            # Model resolution unzips and XML-parses resources.zip - keep that
            # work off the event loop.
            machine = await hass.async_add_executor_job(get_machine, manufacturer_data)
        except EmptyModel:
            return
        except UnsupportedModel as e:
            _LOGGER.error("Unsupported model: %s", *e.args)
            return

        if entry.entry_id in devices:
            return  # a previous callback already set the device up

        device = Device(
            entry.title,
            machine["model"],
            machine["products"],
            machine["alerts"],
            machine["key"],
            service_info.device,
        )
        device.update_ble(service_info.advertisement)
        devices[entry.entry_id] = device

        try:
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        except Exception:
            devices.pop(entry.entry_id, None)
            _LOGGER.exception("Failed to set up platforms for %s", entry.title)

    @callback
    def update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        _LOGGER.debug("%s %s", change, service_info.advertisement)

        if device := devices.get(entry.entry_id):
            device.update_ble(service_info.advertisement)
            return

        hass.async_create_task(setup_device(service_info))

    # https://developers.home-assistant.io/docs/core/bluetooth/api/
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            update_ble,
            {"address": entry.data["mac"], "manufacturer_id": 171, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device = hass.data[DOMAIN].pop(entry.entry_id, None)
    if device is None:
        return True

    # stop the BLE heartbeat loop, otherwise it keeps running detached
    device.client.ping_cancel()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
