"""Pure-logic tests for the Jura core (no BLE hardware, no HA runtime)."""

import asyncio
from pathlib import Path
from zipfile import ZipFile

import pytest

from jura.core.device import Device, EmptyModel, UnsupportedModel, get_machine
from jura.core.entity import JuraEntity, sanitize

RESOURCES = Path(__file__).parent.parent / "jura" / "core" / "resources.zip"


def _adv_for_model(model_id: int) -> bytes:
    return b"\x00\x00\x00\x00" + model_id.to_bytes(2, "little") + b"\x00" * 8


def _any_real_model_id() -> int:
    with ZipFile(RESOURCES) as archive:
        with archive.open("JOE_MACHINES.TXT") as txt:
            for line in txt:
                first = line.decode().split(";")[0].strip()
                if first.isdigit():
                    return int(first)
    raise AssertionError("no model id found in JOE_MACHINES.TXT")


class FakeClient:
    """Stands in for the BLE client so tests never touch hardware."""

    def __init__(self):
        self.device = type("BLEDevice", (), {"address": "AA:BB:CC:DD:EE:FF"})()
        self.address = "AA:BB:CC:DD:EE:FF"
        self.key = 7
        self.pings = 0
        self.sent = []

    def ping(self):
        self.pings += 1

    def ping_cancel(self):
        pass

    def send(self, data, uuid=None):
        self.sent.append(data)


def make_device(products):
    async def build():
        fake = type("BLEDevice", (), {"address": "AA:BB:CC:DD:EE:FF"})()
        return Device("Kitchen", "TestModel", products, {1: "Tray full"}, 7, fake)

    device = asyncio.run(build())
    device.client = FakeClient()  # replace before anything dials BLE
    return device


PRODUCTS = [
    {
        "@Name": "Espresso",
        "@Code": "1",
        "@Active": "true",
        "COFFEE_STRENGTH": {
            "@Argument": "a3",
            "@Default": "2",
            "@Min": "1",
            "@Max": "4",
            "@Step": "1",
            "ITEM": [
                {"@Name": "Mild", "@Value": "1"},
                {"@Name": "Strong", "@Value": "4"},
            ],
        },
        "WATER_AMOUNT": {"@Argument": "a5", "@Value": "40"},
    }
]


def test_get_machine_resolves_a_real_model():
    machine = get_machine(_adv_for_model(_any_real_model_id()))
    assert machine["model"]
    assert isinstance(machine["products"], list)
    assert machine["products"]
    assert "alerts" in machine and "key" in machine


def test_get_machine_empty_model():
    with pytest.raises(EmptyModel):
        get_machine(_adv_for_model(0))


def test_get_machine_unsupported_model():
    with pytest.raises(UnsupportedModel):
        get_machine(_adv_for_model(0xBEEF))


def test_selects_and_numbers_filter_on_products():
    device = make_device(PRODUCTS)
    assert device.selects() == ["coffee_strength"]
    assert device.numbers() == ["water_amount"]


def test_attribute_connection():
    device = make_device(PRODUCTS)
    attribute = device.attribute("connection")
    assert attribute["is_on"] is False
    assert attribute["extra"]["mac"] == "AA:BB:CC:DD:EE:FF"


def test_select_option_updates_values_and_pings():
    device = make_device(PRODUCTS)
    device.select_product("Espresso")  # option changes need a selected product
    pings_after_select_product = device.client.pings
    device.select_option("coffee_strength", "Strong")
    assert device.values["coffee_strength"] == 4
    assert device.client.pings == pings_after_select_product + 1


def test_command_layout_encodes_key_and_arguments():
    device = make_device(PRODUCTS)
    device.select_product("Espresso")
    device.select_option("coffee_strength", "Strong")
    data = device.command()
    assert len(data) == 18
    assert data[1] == 1  # product @Code
    assert data[3] == 4  # coffee_strength @Argument a3 = Strong
    assert data[5] == 40  # water_amount @Argument a5 = @Value 40
    assert data[17] == 7  # client key

    device.start_product()  # sending requires a selected product
    assert device.client.sent == [bytes(data)]


def test_sanitize_strips_invalid_characters():
    assert sanitize("AA:BB:CC:DD:EE:FF_make") == "aabbccddeeff_make"


def test_entity_registers_for_updates_and_names_itself():
    device = make_device(PRODUCTS)
    entity = JuraEntity(device, "coffee_strength")
    assert entity._attr_name == "Kitchen Coffee Strength"
    assert entity._attr_unique_id == "AABBCCDDEEFF_coffee_strength"
    assert entity.suggested_object_id == "aabbccddeeff_coffee_strength"

    # product selection dispatches to registered product listeners
    device.select_product("Espresso")
    assert device.product["@Name"] == "Espresso"
