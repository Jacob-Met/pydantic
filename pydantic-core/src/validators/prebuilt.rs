use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::build_tools::schema_or_config_same;
use crate::common::prebuilt::get_prebuilt;
use crate::errors::ValResult;
use crate::input::Input;

use super::ValidationState;
use super::{CombinedValidator, SchemaValidator, Validator};

#[derive(Debug)]
pub struct PrebuiltValidator {
    schema_validator: Py<SchemaValidator>,
    nested_strict: Option<bool>,
}

impl PrebuiltValidator {
    pub fn try_get_from_schema(
        type_: &str,
        schema: &Bound<'_, PyDict>,
        parent_config: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<CombinedValidator>> {
        // Prebuilt model validators otherwise bypass ModelValidator::build.
        // Carry the field/parent strictness into the reused compiled validator
        // without rebuilding the model schema or mutating the prebuilt object.
        let nested_strict = if type_ == "model" && parent_config.is_some() {
            match schema_or_config_same::<bool>(schema, parent_config, intern!(schema.py(), "strict"))? {
                Some(value) if schema.contains(intern!(schema.py(), "strict"))? => Some(value),
                Some(true) => Some(true),
                _ => None,
            }
        } else {
            None
        };
        get_prebuilt(type_, schema, "__pydantic_validator__", |py_any| {
            let schema_validator: Py<SchemaValidator> = match py_any.extract() {
                Ok(schema_validator) => schema_validator,
                // `__pydantic_validator__` may be a `PluggableSchemaValidator` instance (from `pydantic.plugin`),
                // which exposes the underlying `SchemaValidator` through this property:
                Err(_) => match py_any.getattr(intern!(py_any.py(), "__pydantic_schema_validator__")) {
                    Ok(inner) => match inner.extract() {
                        Ok(schema_validator) => schema_validator,
                        Err(_) => return Ok(None),
                    },
                    Err(_) => return Ok(None),
                },
            };
            if matches!(
                schema_validator.get().validator.as_ref(),
                CombinedValidator::FunctionWrap(_) | CombinedValidator::FunctionAfter(_)
            ) {
                return Ok(None);
            }
            Ok(Some(
                Self {
                    schema_validator,
                    nested_strict,
                }
                .into(),
            ))
        })
    }
}

impl_py_gc_traverse!(PrebuiltValidator { schema_validator });

impl Validator for PrebuiltValidator {
    fn validate<'py>(
        &self,
        py: Python<'py>,
        input: &(impl Input<'py> + ?Sized),
        state: &mut ValidationState<'_, 'py>,
    ) -> ValResult<Py<PyAny>> {
        if let Some(strict) = self.nested_strict
            && state.extra().strict.is_none()
        {
            let state = &mut state.rebind_extra(|extra| extra.strict = Some(strict));
            return self.schema_validator.get().validator.validate(py, input, state);
        }
        self.schema_validator.get().validator.validate(py, input, state)
    }

    fn get_name(&self) -> &str {
        self.schema_validator.get().validator.get_name()
    }
}
