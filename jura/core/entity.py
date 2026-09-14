import re

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import DOMAIN
from .device import Device


def sanitize(entity_id: str) -> str:
    return re.sub(r"[^0-9a-z_]+", "", entity_id.lower())


class JuraEntity(Entity):
    _attr_should_poll = False

    def __init__(self, device: Device, attr: str):
        self.device = device
        self.attr = attr

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, device.mac)},
            manufacturer="Jura",
            model=device.model,
            name=device.name or "Jura",
        )
        self._attr_name = device.name + " " + attr.replace("_", " ").title()
        self._attr_unique_id = device.mac.replace(":", "") + "_" + attr

        self.internal_update()

        device.register_update(attr, self.internal_update)

    @property
    def suggested_object_id(self) -> str | None:
        return sanitize(self.unique_id)

    def internal_update(self):
        pass

    async def async_update(self):
        self.device.client.ping()
