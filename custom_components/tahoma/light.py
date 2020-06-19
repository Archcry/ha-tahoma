"""TaHoma light platform that implements dimmable TaHoma lights."""
from datetime import timedelta
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON
import homeassistant.util.color as color_util

from .const import (
    CORE_BLUE_COLOR_INTENSITY_STATE,
    CORE_GREEN_COLOR_INTENSITY_STATE,
    CORE_RED_COLOR_INTENSITY_STATE,
    DOMAIN,
    TAHOMA_TYPES,
)
from .tahoma_device import TahomaDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma lights from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]

    entities = []
    controller = data.get("controller")

    for device in data.get("devices"):
        if TAHOMA_TYPES[device.uiclass] == "light":
            entities.append(TahomaLight(device, controller))

    async_add_entities(entities)


class TahomaLight(TahomaDevice, LightEntity):
    """Representation of a Tahome light."""

    def __init__(self, tahoma_device, controller):
        """Initialize a device."""
        super().__init__(tahoma_device, controller)

        self._effect = None
        self._brightness = None
        self._state = None
        self._rgb = []

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int(self._brightness * (255 / 100))

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if self.supported_features & SUPPORT_COLOR:
            return color_util.color_RGB_to_hs(*self._rgb)
        return None

    @property
    def supported_features(self) -> int:
        """Flag supported features."""

        supported_features = 0

        if "setIntensity" in self.tahoma_device.command_definitions:
            supported_features |= SUPPORT_BRIGHTNESS

        if "wink" in self.tahoma_device.command_definitions:
            supported_features |= SUPPORT_EFFECT

        if "setRGB" in self.tahoma_device.command_definitions:
            supported_features |= SUPPORT_COLOR

        return supported_features

    def _apply_action(self, cmd_name, *args):
        """Apply an action and wait for it to complete."""
        exec_id = self.apply_action(cmd_name, *args)
        while exec_id in self.controller.get_current_executions():
            continue

    def turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        self._state = True

        _LOGGER.warning(f"light.turn_on kwargs: {kwargs}")

        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(kwargs[ATTR_HS_COLOR])
            self._rgb = [int(float(c)) for c in rgb]
            _LOGGER.warning(f"self._rgb: {self._rgb}")
            self._apply_action("setRGB", *self._rgb)

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = int(float(kwargs[ATTR_BRIGHTNESS]) / 255 * 100)
            self._apply_action("setIntensity", self._brightness)
        elif ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT]
            self._apply_action("wink", 100)
        else:
            self._apply_action("on")

        self.async_write_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._state = False
        self._apply_action("off")

        self.async_write_ha_state()

    @property
    def effect_list(self) -> list:
        """Return the list of supported effects."""
        return ["wink"]

    @property
    def effect(self) -> str:
        """Return the current effect."""
        return self._effect

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """

        self.controller.get_states([self.tahoma_device])

        _LOGGER.warning(f"light states:\n{self.tahoma_device.active_states}")

        if "core:LightIntensityState" in self.tahoma_device.active_states:
            self._brightness = self.tahoma_device.active_states.get(
                "core:LightIntensityState"
            )

        if self.tahoma_device.active_states.get("core:OnOffState") == "on":
            self._state = True
        else:
            self._state = False

        if CORE_RED_COLOR_INTENSITY_STATE in self.tahoma_device.active_states:
            self._rgb = [
                self.tahoma_device.active_states.get(CORE_RED_COLOR_INTENSITY_STATE),
                self.tahoma_device.active_states.get(CORE_GREEN_COLOR_INTENSITY_STATE),
                self.tahoma_device.active_states.get(CORE_BLUE_COLOR_INTENSITY_STATE),
            ]
