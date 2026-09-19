"""Minimal homeassistant stubs so pure-logic tests can import the package.

Only covers what jura/core and jura/platform modules touch at import time.
Integration-level coverage belongs on a dev machine with
pytest-homeassistant-custom-component.
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


ha = _module("homeassistant")
ha_components = _module("homeassistant.components")
bluetooth = _module("homeassistant.components.bluetooth")
bluetooth.BluetoothServiceInfoBleak = type("BluetoothServiceInfoBleak", (), {})
bluetooth.BluetoothChange = type("BluetoothChange", (), {})
bluetooth.BluetoothScanningMode = type("BluetoothScanningMode", (), {})
bluetooth.async_register_callback = lambda *args, **kwargs: (lambda: None)
ha_components.bluetooth = bluetooth
ha.components = ha_components

ha_config_entries = _module("homeassistant.config_entries")
ha_config_entries.ConfigEntry = type("ConfigEntry", (), {})
ha.config_entries = ha_config_entries

ha_core = _module("homeassistant.core")
ha_core.HomeAssistant = type("HomeAssistant", (), {})
ha_core.callback = lambda func: func
ha.core = ha_core

ha_helpers = _module("homeassistant.helpers")
ha_dr = _module("homeassistant.helpers.device_registry")
ha_dr.CONNECTION_NETWORK_MAC = "mac"
ha_entity = _module("homeassistant.helpers.entity")


class DeviceInfo(dict):
    pass


class Entity:
    hass = None
    _attr_unique_id = None

    @property
    def unique_id(self):
        return self._attr_unique_id

    def _async_write_ha_state(self) -> None:
        pass


ha_entity.DeviceInfo = DeviceInfo
ha_entity.Entity = Entity
ha_helpers.device_registry = ha_dr
ha_helpers.entity = ha_entity
ha.helpers = ha_helpers
