import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class NamedValueFromEnvironment:
    _envvar: str
    _name: str
    _value: str
    _from_envvar: bool

    def __init__(
        self,
        envvar: str,
        name: str,
        value: Optional[str] = None,
        from_envvar: bool = False,
    ):
        self._envvar = envvar
        self._name = name
        self._from_envvar = from_envvar
        if value is None:
            self._value = os.environ.get(envvar) or ""
            self._from_envvar = True
        else:
            self._value = value

    def __str__(self):
        return self.value

    def __getstate__(self):
        return (self._envvar, self._name, self._value, self._from_envvar)

    def __setstate__(self, state):
        (self._envvar, self._name, self._value, self._from_envvar) = state
        if self._from_envvar:
            self._value = os.environ.get(self._envvar) or ""
            self._from_envvar = True

    @property
    def name(self) -> str:
        return self._envvar if self._from_envvar else self._name

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str):
        self._value = value
        self._from_envvar = False
