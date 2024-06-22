from dataclasses import dataclass
from typing import Any, Optional, Union, TYPE_CHECKING, Tuple
import logging

if TYPE_CHECKING:
    from ..device import XDevice


@dataclass
class Converter:
    attr: str  # hass attribute
    domain: Optional[str] = None  # hass domain

    prop: Optional[str] = None
    parent: Optional[str] = None

    enabled: Optional[bool] = True  # support: True, False, None (lazy setup)
    poll: bool = False  # hass should_poll

    # don't init with dataclass because no type:
    childs = None  # set or dict? of children attributes

    def decode(self, device: "XDevice", payload: dict, value: Any):
        payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: Any):
        payload[self.prop or self.attr] = value

    def read(self, device: "XDevice", payload: dict):
        if not self.prop:
            return
        return payload.get(self.prop, None)


class BoolConv(Converter):
    def decode(self, device: "XDevice", payload: dict, value: Union[bool, int]):
        payload[self.attr] = bool(value)

    def encode(self, device: "XDevice", payload: dict, value: Union[bool, int]):
        super().encode(device, payload, bool(value))


@dataclass
class MapConv(Converter):
    map: dict = None

    def decode(self, device: "XDevice", payload: dict, value: Union[str, int]):
        payload[self.attr] = self.map.get(value)

    def encode(self, device: "XDevice", payload: dict, value: Any):
        value = next(k for k, v in self.map.items() if v == value)
        super().encode(device, payload, value)


@dataclass
class DurationConv(Converter):
    min: float = 0
    max: float = 3600
    step: float = 1
    readable: bool = True

    def decode(self, device: "XDevice", payload: dict, value: Union[int, float, str, None]):
        if self.readable and value is not None:
            payload[self.attr] = int(float(value) / 1000)

    def encode(self, device: "XDevice", payload: dict, value: Union[int, float, str, None]):
        if value is not None:
            super().encode(device, payload, int(float(value) * 1000))


class PropConv(Converter):
    pass


class PropBoolConv(BoolConv, PropConv):
    pass


class PropMapConv(MapConv, PropConv):
    pass


@dataclass
class BrightnessConv(PropConv):
    max: float = 100.0

    def decode(self, device: "XDevice", payload: dict, value: int):
        payload[self.attr] = round(value / self.max * 255.0)

    def encode(self, device: "XDevice", payload: dict, value: float):
        value = round(value / 255.0 * self.max)
        super().encode(device, payload, int(value))


@dataclass
class ColorTempKelvin(PropConv):
    # 2700..6500 => 370..153
    mink: int = 2700
    maxk: int = 6500

    def decode(self, device: "XDevice", payload: dict, value: int):
        """Convert degrees kelvin to mired shift."""
        payload[self.attr] = int(1000000.0 / value)
        payload['color_temp_kelvin'] = value

    def encode(self, device: "XDevice", payload: dict, value: int):
        value = int(1000000.0 / value)
        if value < self.mink:
            value = self.mink
        if value > self.maxk:
            value = self.maxk
        super().encode(device, payload, value)


class ColorRgbConv(PropConv):
    def decode(self, device: "XDevice", payload: dict, value: int):
        red = (value >> 16) & 0xFF
        green = (value >> 8) & 0xFF
        blue = value & 0xFF
        payload[self.attr] = (red, green, blue)

    def encode(self, device: "XDevice", payload: dict, value: tuple):
        value = (value[0] << 16) | (value[1] << 8) | value[2]
        super().encode(device, payload, value)


@dataclass
class EventConv(Converter):
    event: str = ''

    def decode(self, device: "XDevice", payload: dict, value: dict):
        key, val = self.attr, None
        if '.' in self.attr:
            key, val = self.attr.split('.', 1)
        if key in ['motion', 'contact']:
            payload.update({
                key: val in ['true', 'open'],
                **value,
            })
        elif self.attr in ['panel.click', 'panel.hold', 'panel.release', 'keyClick']:
            key = value.get('key', '')
            cnt = value.get('count', None)
            btn = f'button{key}'
            if cnt is not None:
                typ = {1: 'single', 2: 'double', 3: 'triple'}.get(cnt, val)
            else:
                typ = val
            if typ:
                btn += f'_{typ}'
            payload.update({
                'action': btn,
                'event': self.attr,
                'button': key,
                **value,
            })
        elif self.attr in ['knob.spin']:
            for typ in ['free_spin', 'hold_spin']:
                if value.get(typ) in [None, 0]:
                    continue
                payload.update({
                    'action': typ,
                    'event': self.attr,
                    **value,
                })

    def encode(self, device: "XDevice", payload: dict, value: dict):
        super().encode(device, payload, value)


@dataclass
class MotorConv(Converter):
    readable: bool = False

    def decode(self, device: "XDevice", payload: dict, value: Any):
        if self.readable and value is not None:
            payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: Any):
        if value is not None:
            super().encode(device, payload, {
                'action': {
                    'motorAdjust': {
                        'type': value,
                    },
                },
            })


@dataclass
class SceneConv(Converter):
    node: dict = None


@dataclass
class IntNormalizationConv(PropConv):
    attr_range: Tuple[int, int] = (0, 100)
    prop_range: Tuple[int, int] = (0, 100)

    def decode(self, device: "XDevice", payload: dict, value: int):
        """device prop -> hass attrib & normalize"""
        super().decode(device, payload, self._normalize(value, self.prop_range, self.attr_range))

    def encode(self, device: "XDevice", payload: dict, value: int):
        super().encode(device, payload, self._normalize(value, self.attr_range, self.prop_range))

    def _normalize(self, value: int, from_range: Tuple[int, int], to_range: Tuple[int, int]) -> int:
        # auto fix overflow
        value = min(max(*from_range), value)
        value = max(min(*from_range), value)
        # normalize
        ret = (value - from_range[0]) / (from_range[1] - from_range[0]) * (to_range[1] - to_range[0]) + to_range[0]
        return int(ret)
