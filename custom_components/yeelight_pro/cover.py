"""Support for cover."""
import logging
from typing import Any

from homeassistant.core import callback
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    DOMAIN as ENTITY_DOMAIN,
    STATE_OPENING,
    STATE_CLOSING,
    ATTR_POSITION,
    ATTR_CURRENT_POSITION,
    ATTR_TILT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    XDevice,
    XEntity,
    Converter,
    async_add_setuper,
)

_LOGGER = logging.getLogger(__name__)


def setuper(add_entities):
    def setup(device: XDevice, conv: Converter):
        if not (entity := device.entities.get(conv.attr)):
            entity = XCoverEntity(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class XCoverEntity(XEntity, CoverEntity, RestoreEntity):
    _attr_is_closed = None

    @callback
    def async_set_state(self, data: dict):
        if 'run_state' in data:
            self._attr_state = data['run_state']
            self._attr_is_opening = self._attr_state == STATE_OPENING
            self._attr_is_closing = self._attr_state == STATE_CLOSING
        if ATTR_CURRENT_POSITION in data:
            self._attr_current_cover_position = data[ATTR_CURRENT_POSITION]
            self._attr_is_closed = self._attr_current_cover_position <= 3
        if ATTR_CURRENT_TILT_POSITION in data:
            self._attr_current_cover_tilt_position = data[ATTR_CURRENT_TILT_POSITION]
            if self._attr_current_cover_tilt_position < 100:
                self._attr_is_closed = True

    @callback
    def async_restore_last_state(self, state: str, attrs: dict):
        if state:
            self.async_set_state({'run_state': state})
        if ATTR_CURRENT_POSITION in attrs:
            self.async_set_state({ATTR_CURRENT_POSITION: attrs[ATTR_CURRENT_POSITION]})
        if ATTR_CURRENT_TILT_POSITION in attrs:
            self.async_set_state({ATTR_CURRENT_TILT_POSITION: attrs[ATTR_CURRENT_TILT_POSITION]})

    async def async_open_cover(self, **kwargs):
        kwargs[ATTR_POSITION] = 100
        await self.async_set_cover_position(**kwargs)

    async def async_close_cover(self, **kwargs):
        kwargs[ATTR_POSITION] = 0
        if self.supported_features & CoverEntityFeature.SET_TILT_POSITION:
            kwargs[ATTR_TILT_POSITION] = 0
        await self.async_set_cover_position(**kwargs)

    async def async_stop_cover(self, **kwargs):
        await self.device_send_props({self._name: 'pause'})

    async def async_set_cover_position(self, **kwargs):
        if ATTR_POSITION in kwargs:
            if self.supported_features & CoverEntityFeature.SET_TILT_POSITION:
                if int(kwargs[ATTR_POSITION]) > 0:
                    kwargs[ATTR_TILT_POSITION] = 100
                else:
                    kwargs[ATTR_POSITION] = 0
                    kwargs[ATTR_TILT_POSITION] = 0
        await self.device_send_props(kwargs)
    
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        kwargs[ATTR_TILT_POSITION] = 100
        await self.async_set_cover_tilt_position(**kwargs)
    
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        kwargs[ATTR_TILT_POSITION] = 0
        await self.async_set_cover_tilt_position(**kwargs)
    
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        if ATTR_TILT_POSITION in kwargs:
            if kwargs[ATTR_TILT_POSITION] != 100:
                kwargs[ATTR_POSITION] = 0
        await self.device_send_props(kwargs)

    @property
    def supported_features(self) -> CoverEntityFeature:
        if self.device.pid == 1443840 or self.device.pid == '1443840':
            return (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.SET_POSITION
                | CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )
        return super().supported_features
