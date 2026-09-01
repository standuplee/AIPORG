import ast
from pathlib import Path

from app.models import Base


REVISION_PATH = (
    Path(__file__).parents[2]
    / "alembic_v2"
    / "versions"
    / "20260814_000001_initial_phase0.py"
)


def _table_names(function: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            names.add(node.args[0].value)
    return names


def test_initial_revision_declares_every_phase_zero_table() -> None:
    module = ast.parse(REVISION_PATH.read_text(encoding="utf-8"))
    upgrade = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )

    assert _table_names(upgrade) == set(Base.metadata.tables)


def test_alembic_v2_isolated_configuration_points_to_its_script_directory() -> None:
    config = (REVISION_PATH.parents[2] / "alembic_v2.ini").read_text(encoding="utf-8")

    assert "script_location = alembic_v2" in config
    assert "aiporg2.db" in config


def test_revision_has_no_parent_and_drops_all_phase_zero_tables() -> None:
    module = ast.parse(REVISION_PATH.read_text(encoding="utf-8"))
    revision_assignments = {}
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.value, ast.Constant):
                revision_assignments[node.target.id] = node.value.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant):
                revision_assignments[node.targets[0].id] = node.value.value

    assert revision_assignments["down_revision"] is None

    downgrade = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    )
    dropped = set()
    for node in ast.walk(downgrade):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Tuple):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "table_name":
            continue
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "drop_table"
            for call in ast.walk(node)
        ):
            dropped = {
                element.value
                for element in node.iter.elts
                if isinstance(element, ast.Constant)
            }
            break

    assert dropped == set(Base.metadata.tables)
