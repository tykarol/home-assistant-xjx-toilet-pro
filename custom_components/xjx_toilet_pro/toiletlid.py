"""Support for Xiaomi Whale Smart Toilet Cover."""
import enum
import asyncio
from functools import partial
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
DATA_KEY = "xjx_toilet_pro"

DOMAIN = "xjx_toilet_pro"
CONF_MODEL = "model"
MODEL_TOILETLID_XJX_TOILET_PRO = "xjx.toilet.pro"

AVAILABLE_ATTRIBUTES_TOILETLID = [
    "seating",
    "air_filter",
    "led",
    "self_clean",
]

AVAILABLE_PROPERTIES = {
    MODEL_TOILETLID_XJX_TOILET_PRO: [
        # "fan_temp", # timeout
        # "left_day", # => [1109] for 109 days left in app
        # "massage", # timeout
        # "moving", # timeout
        "seating",
        # "seat_temp" # => [0]
        "status_airfilter",
        "status_led",
        "status_selfclean",
        # "status_tunwash", # => [0, 2, 3, 2, 0, 0]
        # "status_warmdry", # => [0, 2]
        # "status_womenwash", # => [0, 2, 2, 2, 0, 0]
        # "water_pos_t", # timeout
        # "water_pos_w", # timeout
        # "water_strong_t", # timeout
        # "water_strong_w", # timeout
        # "water_temp_t", # timeout
        # "water_temp_w", # timeout
        # "fw_ver", # => [1021]
    ]
}

STATE_OCCUPIED = "occupied"

SUCCESS = ["ok"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In([MODEL_TOILETLID_XJX_TOILET_PRO]),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SELF_CLEAN_ON = "self_clean_on"
SERVICE_SELF_CLEAN_OFF = "self_clean_off"
SERVICE_LED_OFF = "led_on"
SERVICE_LED_ON = "led_off"
ATTR_COMMAND = "command"
ATTR_PARAMS = "params"

TOILETLID_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SERVICE_SCHEMA_SEND_COMMAND = TOILETLID_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(ATTR_PARAMS): vol.Any(dict, cv.ensure_list),
    }
)
SERVICE_TO_METHOD = {
    SERVICE_SEND_COMMAND: {
        "method": "async_send_command",
        "schema": SERVICE_SCHEMA_SEND_COMMAND,
    },
    SERVICE_SELF_CLEAN_ON: {"method": "async_self_clean_on"},
    SERVICE_SELF_CLEAN_OFF: {"method": "async_self_clean_off"},
    SERVICE_LED_OFF: {"method": "async_led_on"},
    SERVICE_LED_ON: {"method": "async_led_off"},
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Xiaomi Whale Smart Toilet device platform."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    model = config.get(CONF_MODEL)

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = miio_device.info()
        model = device_info.model or model or MODEL_TOILETLID_XJX_TOILET_PRO
        unique_id = "{}-{}".format(model, device_info.mac_address)
    except DeviceException:
        raise PlatformNotReady

    toiletlid = Toiletlid(host, token, model=model)
    device = ToiletlidEntity(name, toiletlid, model, unique_id)
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
            update_tasks.append(asyncio.create_task(device.async_update_ha_state(True)))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for toiletlid_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[toiletlid_service].get(
            "schema", TOILETLID_SERVICE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, toiletlid_service, async_service_handler, schema=schema
        )


class ToiletlidEntity(Entity):
    """Representation of the device."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the device handler."""
        self._name = name
        self._device: Toiletlid = device
        self._model = model
        self._unique_id = unique_id

        self._state = None
        self._available = False

        self._state_attrs = {}
        self._state_attrs.update(
            {attribute: None for attribute in AVAILABLE_ATTRIBUTES_TOILETLID }
        )

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_UNAVAILABLE if not self.available else STATE_OCCUPIED if self.is_on else STATE_IDLE

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

            for key in AVAILABLE_ATTRIBUTES_TOILETLID:
                value = getattr(state, key)
                if isinstance(value, enum.Enum):
                    value = value.name
                self._state_attrs.update({key: value})

            self._state = state.is_on

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            return await self.hass.async_add_executor_job(partial(func, *args, **kwargs)) == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_send_command(self, command, params=None):
        # Home Assistant templating always returns a string, even if array is outputted, fix this so we can use templating in scripts.
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], str):
            if params[0].find('[') > -1 and params[0].find(']') > -1:
                params = eval(params[0])
            elif params[0].isnumeric():
                params[0] = int(params[0])

        """Send raw command."""
        await self._try_command(
            "Unable to send raw command to the device: %s",
            self._device.raw_command,
            command,
            params,
        )

    async def async_self_clean_on(self) -> bool:
        """Turn the self clean on."""
        await self._try_command("Unable to set self clean on: %s", self._device.set_self_clean, True)

    async def async_self_clean_off(self) -> bool:
        """Turn the self clean off."""
        await self._try_command("Unable to set self clean off: %s", self._device.set_self_clean, False)

    async def async_led_on(self) -> bool:
        """Turn the led on."""
        await self._try_command("Unable to set led on: %s", self._device.set_led, True)

    async def async_led_off(self) -> bool:
        """Turn the led off."""
        await self._try_command("Unable to set led off: %s", self._device.set_led, False)


class ToiletlidStatus:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data

    @property
    def is_on(self) -> bool:
        return self.seating

    @property
    def seating(self) -> bool:
        return bool(int(self.data["seating"]))

    @property
    def air_filter(self) -> bool:
        return bool(int(self.data["status_airfilter"]))

    @property
    def led(self) -> bool:
        return bool(int(self.data["status_led"]))

    @property
    def self_clean(self) -> bool:
        return bool(int(self.data["status_selfclean"]))


class Toiletlid(Device):
    def __init__(
        self,
        ip: str = None,
        token: str = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        model: str = MODEL_TOILETLID_XJX_TOILET_PRO,
    ) -> None:
        super().__init__(ip, token, start_id, debug, lazy_discover, model=model)

        if model not in AVAILABLE_PROPERTIES:
            self._model = MODEL_TOILETLID_XJX_TOILET_PRO

    # https://github.com/rytilahti/python-miio/issues/815#issuecomment-761765046
    def status(self) -> ToiletlidStatus:
        """Retrieve properties."""
        properties = AVAILABLE_PROPERTIES[self._model]
        values = self.get_properties(properties, max_properties=1)

        return ToiletlidStatus(dict(zip(properties, values)))

    def set_self_clean(self, state: bool):
        """Turn the self clean on/off."""
        if state:
            return self.send("self_clean_on")
        else:
            return self.send("func_off", ["self_clean"])

    def set_led(self, state: bool):
        """Turn the led on/off."""
        if state:
            return self.send("night_led_on")
        else:
            return self.send("func_off", ["night_led"])
