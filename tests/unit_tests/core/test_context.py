from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import NoneType
from typing import Generic, TypeVar, Union
from unittest.mock import patch

import pytest
from bluesky.protocols import (
    Descriptor,
    Movable,
    Readable,
    Reading,
    Stoppable,
    SyncOrAsync,
)
from bluesky.run_engine import RunEngine
from bluesky.utils import MsgGenerator
from dodal.common import PlanGenerator, inject
from ophyd_async.core import (
    StandardDetector,
    StaticPathProvider,
    UUIDFilenameProvider,
    init_devices,
)
from ophyd_async.epics.adaravis import AravisDetector
from ophyd_async.epics.motor import Motor
from pydantic import TypeAdapter, ValidationError
from pydantic.json_schema import SkipJsonSchema
from pytest import LogCaptureFixture

from blueapi.config import (
    ApplicationConfig,
    EnvironmentConfig,
    MetadataConfig,
    Source,
    SourceKind,
    TiledConfig,
)
from blueapi.core import BlueskyContext, is_bluesky_compatible_device
from blueapi.core.context import DefaultFactory, generic_bounds, qualified_name
from blueapi.utils.connect_devices import _establish_device_connections

SIM_MOTOR_NAME = "sim"
ALT_MOTOR_NAME = "alt"
EXPECTED_PLANS = {
    "plan_a",
    "plan_b",
    "plan_c",
    "plan_d",
    "plan_e",
    "plan_f",
    "plan_g",
    "plan_h",
    "plan_i",
    "plan_j",
    "plan_k",
    "plan_l",
    "plan_m",
    "plan_n",
}


#
# Dummy plans
#


def has_no_params() -> MsgGenerator:
    yield from ()


def has_one_param(foo: int) -> MsgGenerator:
    yield from ()


def has_some_params(foo: int = 42, bar: str = "bar") -> MsgGenerator:
    yield from ()


def has_typeless_param(foo) -> MsgGenerator:
    yield from ()


def has_typed_and_typeless_params(foo: int, bar) -> MsgGenerator:
    yield from ()


def has_typeless_params(foo, bar) -> MsgGenerator:
    yield from ()


MOTOR: Movable = inject(SIM_MOTOR_NAME)


def has_default_reference(m: Movable = MOTOR) -> MsgGenerator:
    yield from []


MOVABLE_DEFAULT = [inject(SIM_MOTOR_NAME)]


def has_default_nested_reference(
    m: list[Movable] = MOVABLE_DEFAULT,
) -> MsgGenerator:
    yield from []


#
# Dummy devices
#


@pytest.fixture
def sim_motor(run_engine: RunEngine) -> Motor:
    with init_devices(mock=True):
        sim = Motor("FOO:")
    return sim


@pytest.fixture
def alt_motor(run_engine: RunEngine) -> Motor:
    with init_devices(mock=True):
        alt = Motor("BAR:")
    return alt


@pytest.fixture
def sim_detector(tmp_path: Path) -> StandardDetector:
    path_provider = StaticPathProvider(UUIDFilenameProvider(), tmp_path)
    with init_devices(mock=True):
        sim_det = AravisDetector("DET:", path_provider)
    return sim_det


@pytest.fixture
def empty_context() -> BlueskyContext:
    return BlueskyContext()


@pytest.fixture
def devicey_context(sim_motor: Motor, sim_detector: StandardDetector) -> BlueskyContext:
    ctx = BlueskyContext()
    ctx.register_device(sim_motor)
    ctx.register_device(sim_detector)
    return ctx


class SomeConfigurable:
    def read_configuration(self) -> SyncOrAsync[dict[str, Reading]]:
        return {}

    def describe_configuration(self) -> SyncOrAsync[dict[str, Descriptor]]:
        return {}


@pytest.fixture
def some_configurable() -> SomeConfigurable:
    return SomeConfigurable()


@pytest.mark.parametrize("plan", [has_no_params, has_one_param, has_some_params])
def test_add_plan(empty_context: BlueskyContext, plan: PlanGenerator):
    empty_context.register_plan(plan)
    assert plan.__name__ in empty_context.plans


def test_generated_schema(
    devicey_context: BlueskyContext,
):
    def demo_plan(foo: int, mov: Movable) -> MsgGenerator:
        yield from ()

    devicey_context.register_plan(demo_plan)
    schema = devicey_context.plans["demo_plan"].model.model_json_schema()
    assert schema["properties"] == {
        "foo": {"title": "Foo", "type": "integer"},
        "mov": {"title": "Mov", "type": "bluesky.protocols.Movable", "enum": ["sim"]},
    }


def test_generated_schema_with_generic_bounds(
    empty_context: BlueskyContext,
):
    def demo_plan(foo: int, mov: Movable[int]) -> MsgGenerator:
        yield from ()

    empty_context.register_plan(demo_plan)
    schema = empty_context.plans["demo_plan"].model.model_json_schema()
    assert schema["properties"] == {
        "foo": {"title": "Foo", "type": "integer"},
        "mov": {
            "title": "Mov",
            "type": "bluesky.protocols.Movable",
            "types": ["int"],
            "enum": [],
        },
    }


@pytest.mark.parametrize(
    "plan", [has_typeless_param, has_typed_and_typeless_params, has_typeless_params]
)
def test_add_invalid_plan(empty_context: BlueskyContext, plan: PlanGenerator):
    with pytest.raises(ValueError):
        empty_context.register_plan(plan)


def test_add_plan_from_module(empty_context: BlueskyContext):
    import tests.unit_tests.core.fake_plan_module as plan_module

    empty_context.with_plan_module(plan_module)
    assert EXPECTED_PLANS == empty_context.plans.keys()


def test_only_plans_from_source_module_detected(empty_context: BlueskyContext):
    import tests.unit_tests.core.fake_plan_module_with_imports as plan_module

    empty_context.with_plan_module(plan_module)
    assert {"plan_c", "plan_d"} == empty_context.plans.keys()


def test_only_plans_from_all_in_module_detected(empty_context: BlueskyContext):
    import tests.unit_tests.core.fake_plan_module_with_all as plan_module

    empty_context.with_plan_module(plan_module)
    assert {"plan_a", "plan_d"} == empty_context.plans.keys()


def test_add_named_device(empty_context: BlueskyContext, sim_motor: Motor):
    empty_context.register_device(sim_motor)
    assert empty_context.devices[SIM_MOTOR_NAME] is sim_motor


def test_add_nameless_device(
    empty_context: BlueskyContext, some_configurable: SomeConfigurable
):
    empty_context.register_device(some_configurable, "conf")
    assert empty_context.devices["conf"] is some_configurable


def test_add_nameless_device_without_override(
    empty_context: BlueskyContext,
    some_configurable: SomeConfigurable,
):
    with pytest.raises(KeyError):
        empty_context.register_device(some_configurable)


def test_override_device_name(empty_context: BlueskyContext, sim_motor: Motor):
    empty_context.register_device(sim_motor, "foo")
    assert empty_context.devices["foo"] is sim_motor


def test_add_devices_from_module(empty_context: BlueskyContext):
    import tests.unit_tests.core.fake_device_module as device_module

    empty_context.with_device_module(device_module)
    assert {
        "motor_x",
        "motor_y",
        "motor_bundle_a",
        "motor_bundle_b",
        "device_a",
        "ophyd_device",
        "ophyd_async_device",
    } == empty_context.devices.keys()


def test_add_failing_deivces_from_module(
    caplog: LogCaptureFixture, empty_context: BlueskyContext
):
    import tests.unit_tests.core.fake_device_module_failing as device_module

    caplog.set_level(10)
    empty_context.with_device_module(device_module)
    logs = caplog.get_records("call")

    assert any("TimeoutError: FooBar" in log.message for log in logs)
    assert len(empty_context.devices.keys()) == 0


def test_extra_kwargs_in_with_dodal_module_passed_to_make_all_devices(
    empty_context: BlueskyContext,
):
    """
    Note that this functionality is currently used by hyperion.
    """
    import tests.unit_tests.core.fake_device_module as device_module

    with patch(
        "blueapi.core.context.make_all_devices",
        return_value=({}, {}),
    ) as mock_make_all_devices:
        empty_context.with_dodal_module(
            device_module, some_argument=1, another_argument="two"
        )

        mock_make_all_devices.assert_called_once_with(
            device_module, some_argument=1, another_argument="two"
        )


def test_with_dodal_module_returns_connection_exceptions(empty_context: BlueskyContext):
    import tests.unit_tests.core.fake_device_module as device_module

    def connect_sim_backend(run_engine: RunEngine, devices, sim_backend):
        return _establish_device_connections(run_engine, devices, True)

    with patch(
        "blueapi.utils.connect_devices._establish_device_connections",
        side_effect=connect_sim_backend,
    ):
        names_to_devices, exceptions = empty_context.with_dodal_module(device_module)

    assert set(names_to_devices.keys()) == {
        "motor_y",
        "ophyd_async_device",
        "ophyd_device",
        "device_a",
        "motor_x",
        "motor_bundle_a",
        "motor_bundle_b",
    }
    assert len(exceptions) == 2
    assert isinstance(exceptions["ophyd_device"], RuntimeError)
    assert isinstance(exceptions["ophyd_async_device"], RuntimeError)


@pytest.mark.parametrize(
    "addr", ["sim", "sim_det", "sim.user_setpoint", ["sim"], ["sim", "user_setpoint"]]
)
def test_lookup_device(devicey_context: BlueskyContext, addr: str | list[str]):
    device = devicey_context.find_device(addr)
    assert is_bluesky_compatible_device(device)


def test_lookup_nonexistent_device(devicey_context: BlueskyContext):
    assert devicey_context.find_device("foo") is None


def test_lookup_nonexistent_device_child(devicey_context: BlueskyContext):
    assert devicey_context.find_device("sim.foo") is None


def test_lookup_non_device(devicey_context: BlueskyContext):
    with pytest.raises(ValueError):
        devicey_context.find_device("sim._set_success")


def test_add_non_plan(empty_context: BlueskyContext):
    with pytest.raises(TypeError):
        empty_context.register_plan("not a plan")  # type: ignore


def test_add_non_device(empty_context: BlueskyContext):
    with pytest.raises(TypeError):
        empty_context.register_device("not a device")  # type: ignore


def test_add_devices_and_plans_from_modules_with_config(
    empty_context: BlueskyContext,
):
    empty_context.with_config(
        EnvironmentConfig(
            sources=[
                Source(
                    kind=SourceKind.DEVICE_FUNCTIONS,
                    module="tests.unit_tests.core.fake_device_module",
                ),
                Source(
                    kind=SourceKind.PLAN_FUNCTIONS,
                    module="tests.unit_tests.core.fake_plan_module",
                ),
            ]
        )
    )
    assert {
        "motor_x",
        "motor_y",
        "motor_bundle_a",
        "motor_bundle_b",
        "device_a",
        "ophyd_device",
        "ophyd_async_device",
    } == empty_context.devices.keys()
    assert EXPECTED_PLANS == empty_context.plans.keys()


def test_add_metadata_with_config(
    empty_context: BlueskyContext,
):
    empty_context.with_config(
        EnvironmentConfig(metadata=MetadataConfig(instrument="p46"))
    )
    metadata = [("instrument", "p46")]

    for md in metadata:
        assert md in empty_context.run_engine.md.items()


def test_function_spec(empty_context: BlueskyContext):
    spec = empty_context._type_spec_for_function(has_some_params)
    assert spec["foo"][0] is int
    assert spec["foo"][1].default_factory == DefaultFactory(42)
    assert spec["bar"][0] is str
    assert spec["bar"][1].default_factory == DefaultFactory("bar")


def test_basic_type_conversion(empty_context: BlueskyContext):
    assert empty_context._convert_type(int) is int
    assert empty_context._convert_type(dict[str, int]) == dict[str, int]


def test_device_reference_cache(empty_context: BlueskyContext):
    assert empty_context._reference(Movable) is empty_context._reference(Movable)
    assert empty_context._reference(Movable) is not empty_context._reference(Readable)


def test_device_reference_cache_with_generics(empty_context: BlueskyContext):
    motor = Movable[float]
    assert empty_context._reference(motor) is empty_context._reference(motor)
    assert empty_context._reference(motor) is not empty_context._reference(Movable[int])
    assert empty_context._reference(motor) is not empty_context._reference(Movable)


def test_unregister_all_devices(devicey_context: BlueskyContext):
    assert len(devicey_context.devices) > 0
    devicey_context.unregister_all_devices()

    assert len(devicey_context.devices) == 0


def test_reference_type_conversion(empty_context: BlueskyContext):
    movable_ref: type = empty_context._reference(Movable)
    assert empty_context._convert_type(Movable) == movable_ref
    assert (
        empty_context._convert_type(dict[Movable, list[tuple[int, Movable]]])
        == dict[movable_ref, list[tuple[int, movable_ref]]]
    )


def test_generic_reference_type_conversion(empty_context: BlueskyContext):
    motor = Movable[float]
    motor_ref: type = empty_context._reference(motor)
    assert empty_context._convert_type(motor) == motor_ref
    assert (
        empty_context._convert_type(dict[motor, list[tuple[int, motor]]])
        == dict[motor_ref, list[tuple[int, motor_ref]]]
    )


def test_reference_type_conversion_union(empty_context: BlueskyContext):
    movable_ref: type = empty_context._reference(Movable)
    assert empty_context._convert_type(Movable) == movable_ref
    assert (
        empty_context._convert_type(Union[Movable, int]) == Union[movable_ref, int]  # noqa # type: ignore
    )


def test_reference_type_conversion_new_style_union(
    empty_context: BlueskyContext,
):
    movable_ref: type = empty_context._reference(Movable)
    assert empty_context._convert_type(Movable) == movable_ref
    assert empty_context._convert_type(Movable | int) == movable_ref | int


def test_reference_type_conversion_new_style_optional(
    empty_context: BlueskyContext,
):
    movable_ref: type = empty_context._reference(Movable)
    assert empty_context._convert_type(Movable) == movable_ref
    assert empty_context._convert_type(Movable | None) == movable_ref | None
    assert (
        empty_context._convert_type(Movable | None, no_default=False)
        == movable_ref | SkipJsonSchema[NoneType]
    )


def test_default_device_reference(empty_context: BlueskyContext):
    def default_movable(mov: Movable = inject("demo")) -> MsgGenerator:
        yield from ()

    spec = empty_context._type_spec_for_function(default_movable)
    movable_ref = empty_context._reference(Movable)
    assert spec["mov"][0] == movable_ref
    assert spec["mov"][1].default_factory == DefaultFactory("demo")


def test_generic_default_device_reference(empty_context: BlueskyContext):
    def default_movable(mov: Movable[float] = inject("demo")) -> MsgGenerator:
        yield from ()

    spec = empty_context._type_spec_for_function(default_movable)
    motor_ref = empty_context._reference(Movable[float])
    assert spec["mov"][0] == motor_ref
    assert spec["mov"][1].default_factory == DefaultFactory("demo")


class ConcreteStoppable(Stoppable):
    """Concrete implementation of a Bluesky protocol"""

    @property
    def name(self) -> str:
        return "Concrete"

    def stop(self, success: bool = True):
        pass


def test_concrete_type_conversion(empty_context: BlueskyContext):
    stoppable_ref = empty_context._reference(ConcreteStoppable)
    assert empty_context._convert_type(ConcreteStoppable) == stoppable_ref


def test_concrete_method_annotation(empty_context: BlueskyContext):
    stoppable_ref = empty_context._reference(ConcreteStoppable)

    def demo(named: ConcreteStoppable): ...

    spec = empty_context._type_spec_for_function(demo)
    assert spec["named"][0] is stoppable_ref
    assert spec["named"][1].default_factory is None


def test_str_default(empty_context: BlueskyContext, sim_motor: Motor, alt_motor: Motor):
    movable_ref = empty_context._reference(Movable)
    empty_context.register_device(sim_motor)
    empty_context.register_plan(has_default_reference)

    spec = empty_context._type_spec_for_function(has_default_reference)
    assert spec["m"][0] is movable_ref
    assert (df := spec["m"][1].default_factory) and df() == SIM_MOTOR_NAME  # type: ignore

    assert has_default_reference.__name__ in empty_context.plans
    model = empty_context.plans[has_default_reference.__name__].model
    adapter = TypeAdapter(model)
    assert adapter.validate_python({}).m is sim_motor  # type: ignore
    empty_context.register_device(alt_motor)
    assert adapter.validate_python({"m": ALT_MOTOR_NAME}).m is alt_motor  # type: ignore


def test_nested_str_default(
    empty_context: BlueskyContext, sim_motor: Motor, alt_motor: Motor
):
    movable_ref = empty_context._reference(Movable)
    empty_context.register_device(sim_motor)
    empty_context.register_plan(has_default_nested_reference)

    spec = empty_context._type_spec_for_function(has_default_nested_reference)
    assert spec["m"][0] == list[movable_ref]
    assert (df := spec["m"][1].default_factory) and df() == [SIM_MOTOR_NAME]  # type: ignore

    assert has_default_nested_reference.__name__ in empty_context.plans
    model = empty_context.plans[has_default_nested_reference.__name__].model
    adapter = TypeAdapter(model)

    assert adapter.validate_python({}).m == [sim_motor]  # type: ignore
    empty_context.register_device(alt_motor)
    assert adapter.validate_python({"m": [ALT_MOTOR_NAME]}).m == [alt_motor]  # type: ignore


def test_plan_models_not_auto_camelcased(empty_context: BlueskyContext):
    def a_plan(foo_bar: int, baz: str) -> MsgGenerator:
        if False:
            yield

    empty_context.register_plan(a_plan)
    with pytest.raises(ValidationError):
        empty_context.plans[a_plan.__name__].model(fooBar=1, baz="test")


def test_generic_bounds_with_generic_base():
    T = TypeVar("T")

    class Base(Generic[T]):
        pass

    class Derived(Base[int]):
        pass

    derived_instance = Derived()
    assert generic_bounds(derived_instance, Base) == (int,)  # type: ignore


def test_generic_bounds_with_multiple_bases():
    T = TypeVar("T")

    class Base1(Generic[T]):
        pass

    class Base2:
        pass

    class Derived(Base1[int], Base2):
        pass

    derived_instance = Derived()
    assert generic_bounds(derived_instance, Base1) == (int,)  # type: ignore
    assert generic_bounds(derived_instance, Base2) == ()  #  type: ignore


def test_generic_bounds_with_no_bases():
    class Base:
        pass

    class Derived:
        pass

    derived_instance = Derived()
    assert generic_bounds(derived_instance, Base) == ()  # type: ignore


T = TypeVar("T")


class CustomClass: ...


class GenericClass(Generic[T]): ...


@dataclass
class OuterClass:
    class InnerClass: ...


qualified_name_test_data = [
    (int, "int"),
    (float, "float"),
    (str, "str"),
    (list[GenericClass], "list"),
    (list[int], "list"),
    (dict[str, int], "dict"),
    (CustomClass, "core.test_context.CustomClass"),
    (T, "Any"),
    (GenericClass, "core.test_context.GenericClass"),
    (OuterClass.InnerClass, "core.test_context.OuterClass.InnerClass"),
]


@pytest.mark.parametrize("type,expected", qualified_name_test_data)
def test_qualified_name_with_types(type: type, expected: str):
    assert qualified_name(type) == expected


def test_optional_arg_generated_schema(
    empty_context: BlueskyContext,
):
    def demo_plan(foo: int | None = None) -> MsgGenerator:
        yield from ()

    empty_context.register_plan(demo_plan)
    schema = empty_context.plans["demo_plan"].model.model_json_schema()
    assert schema["properties"] == {
        "foo": {"title": "Foo", "type": "integer"},
    }
    assert "foo" not in schema.get("required", [])


def test_overloaded_arg_generated_schema(
    empty_context: BlueskyContext,
):
    def demo_plan(foo: int | str) -> MsgGenerator:
        yield from ()

    empty_context.register_plan(demo_plan)
    schema = empty_context.plans["demo_plan"].model.model_json_schema()
    assert schema["properties"] == {
        "foo": {"title": "Foo", "anyOf": [{"type": "integer"}, {"type": "string"}]}
    }
    assert "foo" in schema.get("required", [])


def test_optional_overloaded_arg_generated_schema(
    empty_context: BlueskyContext,
):
    def demo_plan(foo: int | str | None = None) -> MsgGenerator:
        yield from ()

    empty_context.register_plan(demo_plan)
    schema = empty_context.plans["demo_plan"].model.model_json_schema()
    assert schema["properties"] == {
        "foo": {"title": "Foo", "anyOf": [{"type": "integer"}, {"type": "string"}]}
    }
    assert "foo" not in schema.get("required", [])


def test_explicit_none_arg_generated_schema(
    empty_context: BlueskyContext,
):
    def demo_plan(foo: int | None) -> MsgGenerator:
        yield from ()

    empty_context.register_plan(demo_plan)
    schema = empty_context.plans["demo_plan"].model.model_json_schema()
    assert schema["properties"] == {
        "foo": {"title": "Foo", "anyOf": [{"type": "integer"}, {"type": "null"}]}
    }
    assert "foo" in schema.get("required", [])


def test_setup_without_tiled_not_makes_tiled_inserter():
    with patch("blueapi.core.context.from_uri") as from_uri:
        BlueskyContext(ApplicationConfig())

        assert from_uri.call_count == 0


def test_setup_with_tiled_makes_tiled_inserter():
    with patch("blueapi.core.context.from_uri") as from_uri:
        BlueskyContext(ApplicationConfig(tiled=TiledConfig(enabled=True)))

        assert from_uri.call_count == 1
        assert from_uri.call_args.args == ("http://localhost:8407/",)
        assert from_uri.call_args.kwargs == {"api_key": None}


def test_setup_with_tiled_api_key_makes_tiled_inserter():
    with patch("blueapi.core.context.from_uri") as from_uri:
        BlueskyContext(
            ApplicationConfig(tiled=TiledConfig(enabled=True, api_key="foobarbaz"))
        )

        assert from_uri.call_count == 1
        assert from_uri.call_args.args == ("http://localhost:8407/",)
        assert from_uri.call_args.kwargs == {"api_key": "foobarbaz"}
