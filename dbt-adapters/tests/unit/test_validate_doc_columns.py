from pathlib import Path
from types import SimpleNamespace

import dbt.include.global_project
import jinja2
import pytest

PERSIST_DOCS = (
    Path(dbt.include.global_project.__path__[0]) / "macros" / "adapters" / "persist_docs.sql"
)


class _Return(Exception):
    """Mirrors how dbt's ``return`` hands a macro result back to its caller."""

    def __init__(self, value):
        self.value = value


def _return(value):
    raise _Return(value)


class _Relation:
    def render(self):
        return "db.schema.tbl"


def _validate_doc_columns(which, column_dict, existing_columns):
    warnings = []
    environment = jinja2.Environment(extensions=["jinja2.ext.do"])
    module = environment.from_string(PERSIST_DOCS.read_text()).make_module(
        {
            "exceptions": SimpleNamespace(warn=warnings.append),
            "flags": SimpleNamespace(WHICH=which),
            "return": _return,
        }
    )
    with pytest.raises(_Return) as returned:
        module.validate_doc_columns(_Relation(), column_dict, existing_columns)
    return returned.value.value, warnings


COLUMNS = {"id": {"quote": False}, "new_column": {"quote": False}}


@pytest.mark.parametrize("which", ["run", "build", "seed"])
def test_missing_documented_column_warns(which):
    # persisted docs for a column the relation does not have is reported
    filtered, warnings = _validate_doc_columns(which, COLUMNS, ["ID"])

    assert list(filtered) == ["id"]
    assert len(warnings) == 1
    assert "new_column" in warnings[0]


def test_missing_documented_column_is_not_reported_by_clone():
    # a clone is a copy of the state's relation, which predates the new column
    filtered, warnings = _validate_doc_columns("clone", COLUMNS, ["ID"])

    assert list(filtered) == ["id"]
    assert warnings == []
