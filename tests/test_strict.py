from typing import Annotated, Any

import pytest

from pydantic import BaseModel, ConfigDict, Field, ValidationError


@pytest.fixture(scope='session', name='ModelWithStrictField')
def model_with_strict_field():
    class ModelWithStrictField(BaseModel):
        a: Annotated[int, Field(strict=True)]

    return ModelWithStrictField


@pytest.mark.parametrize(
    'value',
    [
        '1',
        True,
        1.0,
    ],
)
def test_parse_strict_mode_on_field_invalid(value: Any, ModelWithStrictField: type[BaseModel]) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ModelWithStrictField(a=value)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('a',), 'msg': 'Input should be a valid integer', 'input': value}
    ]


def test_parse_strict_mode_on_field_valid(ModelWithStrictField: type[BaseModel]) -> None:
    value = ModelWithStrictField(a=1)
    assert value.model_dump() == {'a': 1}


@pytest.fixture(scope='session', name='ModelWithStrictConfig')
def model_with_strict_config_false():
    class ModelWithStrictConfig(BaseModel):
        a: int
        # strict=False overrides the Config
        b: Annotated[int, Field(strict=False)]
        # strict=None or not including it is equivalent
        # lets this field be overridden by the Config
        c: Annotated[int, Field(strict=None)]
        d: Annotated[int, Field()]

        model_config = ConfigDict(strict=True)

    return ModelWithStrictConfig


def test_parse_model_with_strict_config_enabled(ModelWithStrictConfig: type[BaseModel]) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ModelWithStrictConfig(a='1', b=2, c=3, d=4)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('a',), 'msg': 'Input should be a valid integer', 'input': '1'}
    ]
    with pytest.raises(ValidationError) as exc_info:
        ModelWithStrictConfig(a=1, b=2, c='3', d=4)
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('c',), 'msg': 'Input should be a valid integer', 'input': '3'}
    ]
    with pytest.raises(ValidationError) as exc_info:
        ModelWithStrictConfig(a=1, b=2, c=3, d='4')
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'int_type', 'loc': ('d',), 'msg': 'Input should be a valid integer', 'input': '4'}
    ]
    values = [
        ModelWithStrictConfig(a=1, b='2', c=3, d=4),
        ModelWithStrictConfig(a=1, b=2, c=3, d=4),
    ]
    assert all(v.model_dump() == {'a': 1, 'b': 2, 'c': 3, 'd': 4} for v in values)


def test_parse_model_with_strict_config_disabled(ModelWithStrictConfig: type[BaseModel]) -> None:
    class Model(ModelWithStrictConfig):
        model_config = ConfigDict(strict=False)

    values = [
        Model(a='1', b=2, c=3, d=4),
        Model(a=1, b=2, c='3', d=4),
        Model(a=1, b=2, c=3, d='4'),
        Model(a=1, b='2', c=3, d=4),
        Model(a=1, b=2, c=3, d=4),
    ]
    assert all(v.model_dump() == {'a': 1, 'b': 2, 'c': 3, 'd': 4} for v in values)


@pytest.mark.parametrize('strict_scope', ['field', 'annotated', 'config'])
def test_nested_model_strict_respects_call_field_and_config(strict_scope: str) -> None:
    """https://github.com/pydantic/pydantic/issues/14269"""
    import json
    from types import MappingProxyType

    from pydantic import Strict

    class Inner(BaseModel):
        x: int

    class FieldOuter(BaseModel):
        inner: Inner = Field(strict=True)

    class AnnotatedOuter(BaseModel):
        inner: Annotated[Inner, Strict()]

    class ConfigOuter(BaseModel):
        model_config = ConfigDict(strict=True)
        inner: Inner

    outer = {'field': FieldOuter, 'annotated': AnnotatedOuter, 'config': ConfigOuter}[strict_scope]

    # Python dicts remain valid model inputs, as for call-level strict=True.
    for validate in (lambda value: outer(inner=value), lambda value: outer.model_validate({'inner': value})):
        assert validate({'x': 1}).inner.x == 1
        assert validate(Inner(x=1)).inner.x == 1
        with pytest.raises(ValidationError) as e:
            validate({'x': '1'})
        assert e.value.errors()[0]['type'] == 'int_type'
        with pytest.raises(ValidationError) as e:
            validate(MappingProxyType({'x': 1}))
        assert e.value.errors()[0]['type'] == 'model_type'

    with pytest.raises(ValidationError, match='int_type'):
        outer.model_validate_json(json.dumps({'inner': {'x': '1'}}))
    assert outer.model_validate_json(json.dumps({'inner': {'x': 1}})).inner.x == 1

    # An explicit strict=False validation call overrides the default.
    assert outer.model_validate({'inner': {'x': '1'}}, strict=False).inner.x == 1
    assert outer.model_validate({'inner': MappingProxyType({'x': 1})}, strict=False).inner.x == 1


def test_nested_strict_config_can_be_relaxed_per_field() -> None:
    """https://github.com/pydantic/pydantic/issues/14269"""

    class Inner(BaseModel):
        x: int

    class Outer(BaseModel):
        model_config = ConfigDict(strict=True)
        strict_inner: Inner
        lax_inner: Inner = Field(strict=False)

    instance = Outer(strict_inner={'x': 1}, lax_inner={'x': '2'})
    assert instance.strict_inner.x == 1
    assert instance.lax_inner.x == 2
    with pytest.raises(ValidationError, match='int_type'):
        Outer(strict_inner={'x': '1'}, lax_inner={'x': '2'})


def test_nested_strict_config_propagates_into_recursive_model() -> None:
    """https://github.com/pydantic/pydantic/issues/14269"""

    class Tree(BaseModel):
        value: int
        child: 'Tree | None' = None

    class StrictContainer(BaseModel):
        model_config = ConfigDict(strict=True)
        tree: Tree

    with pytest.raises(ValidationError, match='int_type'):
        StrictContainer.model_validate({'tree': {'value': 1, 'child': {'value': '2'}}})

    assert StrictContainer.model_validate({'tree': {'value': 1, 'child': {'value': 2}}}).tree.child.value == 2


def test_lax_parent_config_does_not_weaken_strict_nested_model() -> None:
    """https://github.com/pydantic/pydantic/issues/14269"""

    class Inner(BaseModel):
        model_config = ConfigDict(strict=True)
        x: int

    class Outer(BaseModel):
        model_config = ConfigDict(strict=False)
        inner: Inner

    with pytest.raises(ValidationError, match='int_type'):
        Outer(inner={'x': '1'})
    assert Outer(inner={'x': 1}).inner.x == 1
    assert Outer.model_validate({'inner': {'x': '1'}}, strict=False).inner.x == 1
