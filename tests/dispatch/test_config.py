import os
import pickle
from unittest import mock

from dispatch.config import NamedValueFromEnvironment


def test_value_preset():
    v = NamedValueFromEnvironment("FOO", "foo", "bar")
    assert v.name == "foo"
    assert v.value == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar"})
def test_value_from_envvar():
    v = NamedValueFromEnvironment("FOO", "foo")
    assert v.name == "FOO"
    assert v.value == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar"})
def test_value_pickle_reload_from_preset():
    v = NamedValueFromEnvironment("FOO", "foo", "hi!")
    assert v.name == "foo"
    assert v.value == "hi!"

    s = pickle.dumps(v)
    v = pickle.loads(s)
    assert v.name == "foo"
    assert v.value == "hi!"


@mock.patch.dict(os.environ, {"FOO": "bar"})
def test_value_pickle_reload_from_envvar():
    v = NamedValueFromEnvironment("FOO", "foo")
    assert v.name == "FOO"
    assert v.value == "bar"

    s = pickle.dumps(v)
    os.environ["FOO"] = "baz"

    v = pickle.loads(s)
    assert v.name == "FOO"
    assert v.value == "baz"
