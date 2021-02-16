"""Support for Xiaomi Whale Smart Toilet Cover."""
import enum
import asyncio
import logging

from typing import Any, Dict
import voluptuous as vol

from miio import Device, DeviceException
from homeassistant.const import STATE_UNAVAILABLE, STATE_IDLE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_TOKEN, ATTR_ENTITY_ID
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Whale Smart Toilet Cover"
DOMAIN = "xjx_toilet_pro"
DATA_KEY = "xjx_toilet_pro"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SELF_CLEAN_ON = "self_clean_on"
SERVICE_SELF_CLEAN_OFF = "self_clean_off"
SERVICE_LIGHT_OFF = "light_on"
SERVICE_LIGHT_ON = "light_off"
ATTR_COMMAND = "command"
ATTR_COMMAN_PARAMS = "params"

ALL_PROPS = [
    "is_on",
    "self_clean",
    "light"
]

SUCCESS = ["ok"]

TOILETLID_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SERVICE_SCHEMA_SEND_COMMAND = TOILETLID_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(ATTR_COMMAN_PARAMS): cv.string
    }
)
SERVICE_TO_METHOD = {
    SERVICE_SEND_COMMAND: {
        "method": "async_send_command",
        "schema": SERVICE_SCHEMA_SEND_COMMAND,
    },
    SERVICE_SELF_CLEAN_ON: {"method": "async_self_clean_on"},
    SERVICE_SELF_CLEAN_OFF: {"method": "async_self_clean_off"},
    SERVICE_LIGHT_OFF: {"method": "async_light_on"},
    SERVICE_LIGHT_ON: {"method": "async_light_off"},
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Xiaomi Whale Smart Toilet device platform."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = miio_device.info()
    except DeviceException:
        raise PlatformNotReady

    toiletlid = Toiletlid(host, token)
    device = XiaomiToiletlid(name, toiletlid)
    hass.data[DATA_KEY][host] = device

    async_add_entities([device], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on Xiaomi Whale Smart Toilet."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()
        entity_ids = params.pop(ATTR_ENTITY_ID, hass.data[DATA_KEY].values())
        update_tasks = []

        for device in filter(
                lambda x: x.entity_id in entity_ids, hass.data[DATA_KEY].values()
        ):
            if not hasattr(device, method["method"]):
                continue
            await getattr(device, method["method"])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for toiletlid_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[toiletlid_service].get(
            "schema", TOILETLID_SERVICE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, toiletlid_service, async_service_handler, schema=schema
        )


class XiaomiToiletlid(Entity):
    def __init__(self, name, device):
        """Initialize the generic Xiaomi device."""
        self._name = name
        self._device: Toiletlid = device

        self._state = None
        self._available = False

        self._state_attrs = {}
        self._state_attrs.update(
            {attribute: None for attribute in ALL_PROPS}
        )

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_UNAVAILABLE if self.is_on else STATE_IDLE

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:toilet"

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    async def async_update(self):
        """Fetch state from the device."""
        try:
            state: ToiletlidStatus = await self.hass.async_add_executor_job(
                self._device.status
            )
            _LOGGER.debug("Got new state: %s", state)

            self._available = True

            for key in ALL_PROPS:
                value = getattr(state, key)
                if isinstance(value, enum.Enum):
                    value = value.name
                self._state_attrs.update({key: value})

            self._state = state.is_on

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_send_command(self, command, params=None):
        # Home Assistant templating always returns a string, even if array is outputted, fix this so we can use templating in scripts.
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], str):
            if params[0].find('[') > -1 and params[0].find(']') > -1:
                params = eval(params[0])
            elif params[0].isnumeric():
                params[0] = int(params[0])

        """Send raw command."""
        try:
            return (
                await self.hass.async_add_executor_job(
                    lambda: self._device.send_command(command, params)
                )
            )
        except DeviceException as exc:
            _LOGGER.error("Call send_command failure: %s", exc)
            # self._available = False
            return False

    async def async_self_clean_on(self) -> bool:
        """Start nozzle cleaning."""
        try:
            return (
                await self.hass.async_add_executor_job(self._device.self_clean_on) == SUCCESS
            )
        except DeviceException as exc:
            _LOGGER.error("Call self_clean_on failure: %s", exc)
            self._available = False
            return False

    async def async_self_clean_off(self) -> bool:
        """Stop nozzle cleaning."""
        try:
            return (
                await self.hass.async_add_executor_job(self._device.self_clean_off) == SUCCESS
            )
        except DeviceException as exc:
            _LOGGER.error("Call self_clean_off failure: %s", exc)
            self._available = False
            return False

    async def async_light_on(self) -> bool:
        """Turn on the night light."""
        try:
            return (
                await self.hass.async_add_executor_job(self._device.light_on) == SUCCESS
            )
        except DeviceException as exc:
            _LOGGER.error("Call light_on failure: %s", exc)
            self._available = False
            return False

    async def async_light_off(self) -> bool:
        """Turn on the night light."""
        try:
            return (
                await self.hass.async_add_executor_job(self._device.light_off) == SUCCESS
            )
        except DeviceException as exc:
            _LOGGER.error("Call light_off failure: %s", exc)
            self._available = False
            return False


class ToiletlidStatus:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data

    @property
    def is_on(self) -> bool:
        return int(self.data["seating"]) == 1

    @property
    def self_clean(self) -> bool:
        """Nozzle cleaning in progress."""
        return bool(int(self.data["status_selfclean"]))

    @property
    def light(self) -> bool:
        """Night light is on."""
        return bool(int(self.data["status_led"]))


class Toiletlid(Device):
    def __init__(
        self,
        ip: str = None,
        token: str = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
    ) -> None:
        super().__init__(ip, token, start_id, debug, lazy_discover)

    # https://github.com/rytilahti/python-miio/issues/815#issuecomment-761765046
    def status(self) -> ToiletlidStatus:
        """Retrieve properties."""
        properties = [
            "seating",
            "status_led",
            "status_selfclean"
        ]
        values = self.get_properties(properties, max_properties=1)

        return ToiletlidStatus(dict(zip(properties, values)))

    def send_command(self, command: str, props: str):
        """Send raw command."""
        return self.send(command, props)

    def self_clean_on(self):
        """Start nozzle cleaning."""
        return self.send("self_clean_on")

    def self_clean_off(self):
        """Stop nozzle cleaning."""
        return self.send("func_off", ["self_clean"])

    def light_on(self):
        """Turn on the night light."""
        return self.send("night_led_on")

    def light_off(self):
        """Turn off the night light."""
        return self.send("func_off", ["night_led"])
