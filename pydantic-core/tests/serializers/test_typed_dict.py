import json
from typing import Any

import pytest
from dirty_equals import IsStrictDict
from typing_extensions import TypedDict

from pydantic_core import SchemaSerializer, core_schema


@pytest.mark.parametrize('extra_behavior_kw', [{}, {'extra_behavior': 'ignore'}, {'extra_behavior': None}])
def test_typed_dict(extra_behavior_kw: dict[str, Any]):
    v = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'foo': core_schema.typed_dict_field(core_schema.int_schema()),
                'bar': core_schema.typed_dict_field(core_schema.bytes_schema()),
            },
            **extra_behavior_kw,
        )
    )
    assert v.to_python({'foo': 1, 'bar': b'more'}) == IsStrictDict(foo=1, bar=b'more')
    assert v.to_python({'bar': b'more', 'foo': 1}) == IsStrictDict(bar=b'more', foo=1)
    assert v.to_python({'foo': 1, 'bar': b'more', 'c': 3}) == IsStrictDict(foo=1, bar=b'more')
    assert v.to_python({'bar': b'more', 'foo': 1, 'c': 3}, mode='json') == IsStrictDict(bar='more', foo=1)

    assert v.to_json({'bar': b'more', 'foo': 1, 'c': 3}) == b'{"bar":"more","foo":1}'


def test_typed_dict_fields_has_type():
    typed_dict_field = core_schema.typed_dict_field(core_schema.bytes_schema())

    assert typed_dict_field['type'] == 'typed-dict-field'


def test_typed_dict_allow_extra():
    v = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'foo': core_schema.typed_dict_field(core_schema.int_schema()),
                'bar': core_schema.typed_dict_field(core_schema.bytes_schema()),
            },
            extra_behavior='allow',
        )
    )
    # extra fields go last but retain their order
    assert v.to_python({'bar': b'more', 'b': 3, 'foo': 1, 'a': 4}) == IsStrictDict(bar=b'more', b=3, foo=1, a=4)
    assert v.to_python({'bar': b'more', 'c': 3, 'foo': 1}, mode='json') == IsStrictDict(bar='more', c=3, foo=1)

    assert v.to_json({'bar': b'more', 'c': 3, 'foo': 1, 'cc': 4}) == b'{"bar":"more","c":3,"foo":1,"cc":4}'


@pytest.mark.parametrize(
    'params',
    [
        {'include': None, 'exclude': None, 'expected': {'0': 0, '1': 1, '2': 2, '3': 3}},
        {'include': {'0', '1'}, 'exclude': None, 'expected': {'0': 0, '1': 1}},
        {'include': {'0': ..., '1': ...}, 'exclude': None, 'expected': {'0': 0, '1': 1}},
        {'include': {'0': {1}, '1': {1}}, 'exclude': None, 'expected': {'0': 0, '1': 1}},
        {'include': None, 'exclude': {'0', '1'}, 'expected': {'2': 2, '3': 3}},
        {'include': None, 'exclude': {'0': ..., '1': ...}, 'expected': {'2': 2, '3': 3}},
        {'include': {'0', '1'}, 'exclude': {'1', '2'}, 'expected': {'0': 0}},
        {'include': None, 'exclude': {'3': {1}}, 'expected': {'0': 0, '1': 1, '2': 2, '3': 3}},
        {'include': {'0', '1'}, 'exclude': {'3': {1}}, 'expected': {'0': 0, '1': 1}},
        {'include': {'0', '1'}, 'exclude': {'1': {1}}, 'expected': {'0': 0, '1': 1}},
        {'include': {'0', '1'}, 'exclude': {'1': ...}, 'expected': {'0': 0}},
    ],
)
def test_include_exclude_args(params):
    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                '0': core_schema.typed_dict_field(core_schema.int_schema()),
                '1': core_schema.typed_dict_field(core_schema.int_schema()),
                '2': core_schema.typed_dict_field(core_schema.int_schema()),
                '3': core_schema.typed_dict_field(core_schema.int_schema()),
            }
        )
    )

    # user IsStrictDict to check dict order
    include, exclude, expected = params['include'], params['exclude'], IsStrictDict(params['expected'])
    value = {'0': 0, '1': 1, '2': 2, '3': 3}
    assert s.to_python(value, include=include, exclude=exclude) == expected
    assert s.to_python(value, mode='json', include=include, exclude=exclude) == expected
    assert json.loads(s.to_json(value, include=include, exclude=exclude)) == expected


def test_include_exclude_schema():
    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                '0': core_schema.typed_dict_field(core_schema.int_schema(), serialization_exclude=True),
                '1': core_schema.typed_dict_field(core_schema.int_schema()),
                '2': core_schema.typed_dict_field(
                    core_schema.int_schema(), serialization_exclude=True, serialization_exclude_if=lambda x: x < 0
                ),
                '3': core_schema.typed_dict_field(
                    core_schema.int_schema(), serialization_exclude=False, serialization_exclude_if=lambda x: x < 0
                ),
            }
        )
    )
    value = {'0': 0, '1': 1, '2': 2, '3': 3}
    assert s.to_python(value) == {'1': 1, '3': 3}
    assert s.to_python(value, mode='json') == {'1': 1, '3': 3}
    assert json.loads(s.to_json(value)) == {'1': 1, '3': 3}

    value = {'0': 0, '1': 1, '2': 2, '3': -3}
    assert s.to_python(value) == {'1': 1}
    assert s.to_python(value, mode='json') == {'1': 1}
    assert json.loads(s.to_json(value)) == {'1': 1}


def test_alias():
    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'cat': core_schema.typed_dict_field(core_schema.int_schema(), serialization_alias='Meow'),
                'dog': core_schema.typed_dict_field(core_schema.int_schema(), serialization_alias='Woof'),
                'bird': core_schema.typed_dict_field(core_schema.int_schema()),
            }
        )
    )
    value = {'cat': 0, 'dog': 1, 'bird': 2}
    assert s.to_python(value, by_alias=True) == IsStrictDict(Meow=0, Woof=1, bird=2)
    assert s.to_python(value, exclude={'dog'}, by_alias=True) == IsStrictDict(Meow=0, bird=2)
    assert s.to_python(value, by_alias=False) == IsStrictDict(cat=0, dog=1, bird=2)

    assert s.to_python(value, mode='json', by_alias=True) == IsStrictDict(Meow=0, Woof=1, bird=2)
    assert s.to_python(value, mode='json', include={'cat'}, by_alias=True) == IsStrictDict(Meow=0)
    assert s.to_python(value, mode='json', by_alias=False) == IsStrictDict(cat=0, dog=1, bird=2)

    assert json.loads(s.to_json(value, by_alias=True)) == IsStrictDict(Meow=0, Woof=1, bird=2)
    assert json.loads(s.to_json(value, include={'cat', 'bird'}, by_alias=True)) == IsStrictDict(Meow=0, bird=2)
    assert json.loads(s.to_json(value, by_alias=False)) == IsStrictDict(cat=0, dog=1, bird=2)


def test_exclude_none():
    v = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'foo': core_schema.typed_dict_field(core_schema.nullable_schema(core_schema.int_schema())),
                'bar': core_schema.typed_dict_field(core_schema.bytes_schema()),
            },
            extra_behavior='allow',
        )
    )
    assert v.to_python({'foo': 1, 'bar': b'more', 'c': 3}) == {'foo': 1, 'bar': b'more', 'c': 3}
    assert v.to_python({'foo': None, 'bar': b'more', 'c': None}) == {'foo': None, 'bar': b'more', 'c': None}
    assert v.to_python({'foo': None, 'bar': b'more', 'c': None}, exclude_none=True) == {'bar': b'more'}

    assert v.to_python({'foo': None, 'bar': b'more', 'c': None}, mode='json') == {'foo': None, 'bar': 'more', 'c': None}
    assert v.to_python({'foo': None, 'bar': b'more', 'c': None}, mode='json', exclude_none=True) == {'bar': 'more'}

    assert v.to_json({'foo': 1, 'bar': b'more', 'c': None}) == b'{"foo":1,"bar":"more","c":null}'
    assert v.to_json({'foo': None, 'bar': b'more'}) == b'{"foo":null,"bar":"more"}'
    assert v.to_json({'foo': None, 'bar': b'more', 'c': None}, exclude_none=True) == b'{"bar":"more"}'


def test_exclude_default():
    v = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'foo': core_schema.typed_dict_field(core_schema.nullable_schema(core_schema.int_schema())),
                'bar': core_schema.typed_dict_field(
                    core_schema.with_default_schema(core_schema.bytes_schema(), default=b'[default]')
                ),
            }
        )
    )
    assert v.to_python({'foo': 1, 'bar': b'x'}) == {'foo': 1, 'bar': b'x'}
    assert v.to_python({'foo': 1, 'bar': b'[default]'}) == {'foo': 1, 'bar': b'[default]'}
    assert v.to_python({'foo': 1, 'bar': b'[default]'}, exclude_defaults=True) == {'foo': 1}
    assert v.to_python({'foo': 1, 'bar': b'[default]'}, mode='json') == {'foo': 1, 'bar': '[default]'}
    assert v.to_python({'foo': 1, 'bar': b'[default]'}, exclude_defaults=True, mode='json') == {'foo': 1}

    assert v.to_json({'foo': 1, 'bar': b'[default]'}) == b'{"foo":1,"bar":"[default]"}'
    assert v.to_json({'foo': 1, 'bar': b'[default]'}, exclude_defaults=True) == b'{"foo":1}'


def test_exclude_default_keeps_distinct_numeric_values():
    serializer = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'flag': core_schema.typed_dict_field(
                    core_schema.with_default_schema(
                        core_schema.union_schema([core_schema.bool_schema(), core_schema.int_schema()]), default=False
                    )
                ),
                'code': core_schema.typed_dict_field(
                    core_schema.with_default_schema(
                        core_schema.union_schema([core_schema.int_schema(), core_schema.bool_schema()]), default=1
                    )
                ),
                'num': core_schema.typed_dict_field(
                    core_schema.with_default_schema(
                        core_schema.union_schema([core_schema.int_schema(), core_schema.float_schema()]), default=0
                    )
                ),
                'z': core_schema.typed_dict_field(
                    core_schema.with_default_schema(core_schema.float_schema(), default=0.0)
                ),
            }
        )
    )
    values = {'flag': 0, 'code': True, 'num': 0.0, 'z': -0.0}
    assert serializer.to_python(values, exclude_defaults=True) == values
    assert serializer.to_python(values, exclude_defaults=True, mode='json') == values
    assert serializer.to_json(values, exclude_defaults=True) == b'{"flag":0,"code":true,"num":0.0,"z":-0.0}'

    defaults = {'flag': False, 'code': 1, 'num': 0, 'z': 0.0}
    assert serializer.to_python(defaults, exclude_defaults=True) == {}
    assert serializer.to_json(defaults, exclude_defaults=True) == b'{}'

    # The inverse signed-zero difference must also be preserved.
    negative_zero_default = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'z': core_schema.typed_dict_field(
                    core_schema.with_default_schema(core_schema.float_schema(), default=-0.0)
                )
            }
        )
    )
    assert negative_zero_default.to_json({'z': 0.0}, exclude_defaults=True) == b'{"z":0.0}'
    assert negative_zero_default.to_json({'z': -0.0}, exclude_defaults=True) == b'{}'


def test_exclude_defaults_function_serializer_on_default_schema():
    """https://github.com/pydantic/pydantic/issues/14275"""
    plain = core_schema.with_default_schema(
        core_schema.int_schema(),
        default=1,
        serialization=core_schema.plain_serializer_function_ser_schema(lambda v: str(v)),
    )
    serializer = SchemaSerializer(core_schema.typed_dict_schema({'value': core_schema.typed_dict_field(plain)}))
    assert serializer.to_json({'value': 1}, exclude_defaults=True) == b'{}'
    assert serializer.to_python({'value': 1}, exclude_defaults=True) == {}
    assert serializer.to_json({'value': 2}, exclude_defaults=True) == b'{"value":"2"}'


def test_exclude_defaults_equal_custom_values_without_json_serializer():
    """https://github.com/pydantic/pydantic/issues/14275"""

    class Custom:
        def __init__(self, tag):
            self.tag = tag

        def __eq__(self, other):
            return isinstance(other, Custom) and self.tag[0] == other.tag[0]

    serializer = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'obj': core_schema.typed_dict_field(
                    core_schema.with_default_schema(core_schema.any_schema(), default=Custom('a1'))
                )
            }
        )
    )
    equal = Custom('a2')
    assert serializer.to_python({'obj': equal}, exclude_defaults=True) == {}
    assert serializer.to_json({'obj': equal}, exclude_defaults=True) == b'{}'

    # With an actual JSON fallback, equal Python values can serialize differently.
    fallback = lambda obj: {'tag': obj.tag}
    assert serializer.to_json({'obj': equal}, exclude_defaults=True, fallback=fallback) == b'{"obj":{"tag":"a2"}}'
    assert serializer.to_python({'obj': equal}, mode='json', exclude_defaults=True, fallback=fallback) == {
        'obj': {'tag': 'a2'}
    }
    assert serializer.to_json({'obj': Custom('a1')}, exclude_defaults=True, fallback=fallback) == b'{}'


@pytest.mark.parametrize('container', [set, frozenset])
def test_exclude_defaults_custom_set_serializer_preserves_python_list_order(container):
    """https://github.com/pydantic/pydantic/issues/14275"""

    class CollidingStr(str):
        def __hash__(self):
            return 23

    first, second = CollidingStr('first'), CollidingStr('second')
    default = container([first, second])
    changed = container([second, first])
    assert default == changed
    assert list(default) != list(changed)

    item_schema = (
        core_schema.set_schema(core_schema.any_schema())
        if container is set
        else core_schema.frozenset_schema(core_schema.any_schema())
    )
    item_schema['serialization'] = core_schema.plain_serializer_function_ser_schema(lambda items: list(items))
    serializer = SchemaSerializer(
        core_schema.typed_dict_schema(
            {'items': core_schema.typed_dict_field(core_schema.with_default_schema(item_schema, default=default))}
        )
    )

    assert serializer.to_python({'items': changed}, exclude_defaults=True) == {'items': list(changed)}
    assert serializer.to_python({'items': default}, exclude_defaults=True) == {}
    assert serializer.to_json({'items': changed}, exclude_defaults=True) == serializer.to_json({'items': changed})


@pytest.mark.parametrize('container', [set, frozenset])
def test_exclude_defaults_preserves_set_json_element_order(container):
    """https://github.com/pydantic/pydantic/issues/14275"""

    class CollidingStr(str):
        def __hash__(self):
            return 23

    first, second = CollidingStr('first'), CollidingStr('second')
    default = container([first, second])
    changed = container([second, first])
    assert default == changed
    assert list(default) != list(changed)

    item_schema = (
        core_schema.set_schema(core_schema.any_schema())
        if container is set
        else core_schema.frozenset_schema(core_schema.any_schema())
    )
    serializer = SchemaSerializer(
        core_schema.typed_dict_schema(
            {'items': core_schema.typed_dict_field(core_schema.with_default_schema(item_schema, default=default))}
        )
    )

    assert serializer.to_python({'items': changed}, exclude_defaults=True) == {}
    assert serializer.to_json({'items': default}, exclude_defaults=True) == b'{}'
    assert serializer.to_json({'items': changed}, exclude_defaults=True) == serializer.to_json({'items': changed})
    assert serializer.to_python({'items': changed}, mode='json', exclude_defaults=True) == {'items': list(changed)}


def test_exclude_defaults_preserves_equal_but_distinct_nested_wire_values():
    """https://github.com/pydantic/pydantic/issues/14275"""
    from datetime import UTC, datetime, timedelta, timezone
    from decimal import Decimal

    serializer = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'items': core_schema.typed_dict_field(
                    core_schema.with_default_schema(core_schema.list_schema(core_schema.any_schema()), default=[0])
                ),
                'mapping': core_schema.typed_dict_field(
                    core_schema.with_default_schema(
                        core_schema.dict_schema(core_schema.str_schema(), core_schema.any_schema()), default={'x': 0.0}
                    )
                ),
                'amount': core_schema.typed_dict_field(
                    core_schema.with_default_schema(core_schema.decimal_schema(), default=Decimal('1.0'))
                ),
                'at': core_schema.typed_dict_field(
                    core_schema.with_default_schema(
                        core_schema.datetime_schema(), default=datetime(2020, 1, 1, tzinfo=UTC)
                    )
                ),
            }
        )
    )
    values = {
        'items': [False],
        'mapping': {'x': -0.0},
        'amount': Decimal('1.00'),
        'at': datetime(2020, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
    }
    assert serializer.to_json(values, exclude_defaults=True) == (
        b'{"items":[false],"mapping":{"x":-0.0},"amount":"1.00","at":"2020-01-01T01:00:00+01:00"}'
    )
    assert serializer.to_python(values, mode='json', exclude_defaults=True) == {
        'items': [False],
        'mapping': {'x': -0.0},
        'amount': '1.00',
        'at': '2020-01-01T01:00:00+01:00',
    }
    # Mapping equality also conflates differently serialized keys.
    key_serializer = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'map': core_schema.typed_dict_field(
                    core_schema.with_default_schema(
                        core_schema.dict_schema(core_schema.any_schema(), core_schema.any_schema()), default={0: 'x'}
                    )
                )
            }
        )
    )
    assert key_serializer.to_json({'map': {False: 'x'}}, exclude_defaults=True) == b'{"map":{"false":"x"}}'
    assert key_serializer.to_json({'map': {0: 'x'}}, exclude_defaults=True) == b'{}'

    assert (
        serializer.to_json(
            {
                'items': [0],
                'mapping': {'x': 0.0},
                'amount': Decimal('1.0'),
                'at': datetime(2020, 1, 1, tzinfo=UTC),
            },
            exclude_defaults=True,
        )
        == b'{}'
    )


def test_function_plain_field_serializer_to_python():
    class Model(TypedDict):
        x: int

    def ser_x(data: Model, v: Any, _) -> str:
        assert data['x'] == 1_000
        return f'{v:_}'

    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'x': core_schema.typed_dict_field(
                    core_schema.int_schema(
                        serialization=core_schema.plain_serializer_function_ser_schema(
                            ser_x, is_field_serializer=True, info_arg=True
                        )
                    )
                )
            }
        )
    )
    assert s.to_python(Model(x=1000)) == {'x': '1_000'}


def test_function_wrap_field_serializer_to_python():
    class Model(TypedDict):
        x: int

    def ser_x(data: Model, v: Any, serializer: core_schema.SerializerFunctionWrapHandler, _) -> str:
        x = serializer(v)
        assert data['x'] == 1_000
        return f'{x:_}'

    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'x': core_schema.typed_dict_field(
                    core_schema.int_schema(
                        serialization=core_schema.wrap_serializer_function_ser_schema(
                            ser_x, is_field_serializer=True, info_arg=True, schema=core_schema.any_schema()
                        )
                    )
                )
            }
        )
    )
    assert s.to_python(Model(x=1000)) == {'x': '1_000'}


def test_function_plain_field_serializer_to_json():
    class Model(TypedDict):
        x: int

    def ser_x(data: Model, v: Any, info: core_schema.FieldSerializationInfo) -> str:
        assert data['x'] == 1_000
        return f'{v:_}-{info.field_name}'

    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'x': core_schema.typed_dict_field(
                    core_schema.int_schema(
                        serialization=core_schema.plain_serializer_function_ser_schema(
                            ser_x, is_field_serializer=True, info_arg=True
                        )
                    )
                )
            }
        )
    )
    assert json.loads(s.to_json(Model(x=1000))) == {'x': '1_000-x'}


def test_function_plain_field_serializer_to_json_no_info():
    class Model(TypedDict):
        x: int

    def ser_x(data: Model, v: Any) -> str:
        assert data['x'] == 1_000
        return f'{v:_}'

    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'x': core_schema.typed_dict_field(
                    core_schema.int_schema(
                        serialization=core_schema.plain_serializer_function_ser_schema(ser_x, is_field_serializer=True)
                    )
                )
            }
        )
    )
    assert json.loads(s.to_json(Model(x=1000))) == {'x': '1_000'}


def test_function_wrap_field_serializer_to_json():
    class Model(TypedDict):
        x: int

    def ser_x(
        data: Model,
        v: Any,
        serializer: core_schema.SerializerFunctionWrapHandler,
        info: core_schema.FieldSerializationInfo,
    ) -> str:
        assert data['x'] == 1_000
        x = serializer(v)
        return f'{x:_}-{info.field_name}'

    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'x': core_schema.typed_dict_field(
                    core_schema.int_schema(
                        serialization=core_schema.wrap_serializer_function_ser_schema(
                            ser_x, is_field_serializer=True, info_arg=True, schema=core_schema.any_schema()
                        )
                    )
                )
            }
        )
    )
    assert json.loads(s.to_json(Model(x=1000))) == {'x': '1_000-x'}


def test_function_wrap_field_serializer_to_json_no_info():
    class Model(TypedDict):
        x: int

    def ser_x(data: Model, v: Any, serializer: core_schema.SerializerFunctionWrapHandler) -> str:
        assert data['x'] == 1_000
        x = serializer(v)
        return f'{x:_}'

    s = SchemaSerializer(
        core_schema.typed_dict_schema(
            {
                'x': core_schema.typed_dict_field(
                    core_schema.int_schema(
                        serialization=core_schema.wrap_serializer_function_ser_schema(
                            ser_x, is_field_serializer=True, schema=core_schema.any_schema()
                        )
                    )
                )
            }
        )
    )
    assert json.loads(s.to_json(Model(x=1000))) == {'x': '1_000'}


def test_extra_custom_serializer():
    schema = core_schema.typed_dict_schema(
        {},
        extra_behavior='allow',
        extras_schema=core_schema.any_schema(
            serialization=core_schema.plain_serializer_function_ser_schema(lambda v: v + ' bam!')
        ),
    )
    s = SchemaSerializer(schema)

    m = {'extra': 'extra'}

    assert s.to_python(m) == {'extra': 'extra bam!'}


@pytest.mark.parametrize(
    'config,runtime,expected',
    [
        (True, True, {'my_alias': 1}),
        (True, False, {'my_field': 1}),
        (True, None, {'my_alias': 1}),
        (False, True, {'my_alias': 1}),
        (False, False, {'my_field': 1}),
        (False, None, {'my_field': 1}),
        (None, True, {'my_alias': 1}),
        (None, False, {'my_field': 1}),
        (None, None, {'my_field': 1}),
    ],
)
def test_by_alias_and_name_config_interaction(config, runtime, expected) -> None:
    """This test reflects the priority that applies for config vs runtime serialization alias configuration.

    If the runtime value (by_alias) is set, that value is used.
    If the runtime value is unset, the config value (serialize_by_alias) is used.
    If neither are set, the default, False, is used.
    """

    class Model(TypedDict):
        my_field: int

    schema = core_schema.typed_dict_schema(
        {
            'my_field': core_schema.typed_dict_field(core_schema.int_schema(), serialization_alias='my_alias'),
        },
    )
    s = SchemaSerializer(schema, config=core_schema.CoreConfig(serialize_by_alias=config or False))
    assert s.to_python(Model(my_field=1), by_alias=runtime) == expected


def test_nested_typed_dict_field_serializers():
    class Model(TypedDict):
        x: Any

    class OuterModel(TypedDict):
        model: Model

    schema = core_schema.typed_dict_schema(
        {
            'x': core_schema.typed_dict_field(
                core_schema.any_schema(
                    serialization=core_schema.wrap_serializer_function_ser_schema(
                        # in an incorrect core implementation, self could be OuterModel here
                        lambda self, v, serializer: f'{list(self.keys())}',
                        is_field_serializer=True,
                        schema=core_schema.any_schema(),
                    )
                )
            )
        }
    )
    outer_schema = core_schema.typed_dict_schema({'model': core_schema.typed_dict_field(schema)})

    s = SchemaSerializer(schema)
    assert s.to_python(Model(x=None)) == {'x': "['x']"}

    outer_s = SchemaSerializer(outer_schema)
    # if the inner field serializer incorrectly receives OuterModel as self, the keys
    # will be ['model'] instead of ['x']
    assert outer_s.to_python(OuterModel(model=Model(x=None))) == {'model': {'x': "['x']"}}
