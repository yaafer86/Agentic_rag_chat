"""Custom KPI CRUD + evaluation endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.core.rbac import DB, CurrentUser, CurrentWorkspace, require_role
from app.models.db import AuditLog, CustomKPI, Role
from app.models.schemas import CustomKPICreate, CustomKPIOut
from app.services.kpi import (
    FormulaError,
    evaluate_formula,
    validate_arithmetic_consistency,
    validate_formula_shape,
)

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


@router.post(
    "",
    response_model=CustomKPIOut,
    status_code=201,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def create_kpi(
    body: CustomKPICreate,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> CustomKPI:
    ws, _ = ctx
    # Quick shape check with neutral sample values (0 for every variable used).
    sample = _extract_variable_names(body.formula)
    try:
        evaluate_formula(body.formula, dict.fromkeys(sample, 1))
    except FormulaError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid formula: {e}") from e

    kpi = CustomKPI(
        workspace_id=ws.id,
        name=body.name,
        formula=body.formula,
        unit=body.unit,
        filters=body.filters,
        thresholds=body.thresholds,
        source_document_ids=body.source_document_ids,
    )
    db.add(kpi)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="kpi.create",
            target_type="kpi",
            target_id=kpi.id,
            payload={"name": body.name, "formula": body.formula},
        )
    )
    await db.commit()
    await db.refresh(kpi)
    return kpi


@router.get("", response_model=list[CustomKPIOut])
async def list_kpis(ctx: CurrentWorkspace, db: DB) -> list[CustomKPI]:
    ws, _ = ctx
    rows = (await db.execute(select(CustomKPI).where(CustomKPI.workspace_id == ws.id))).scalars()
    return list(rows.all())


@router.delete(
    "/{kpi_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value))],
)
async def delete_kpi(
    kpi_id: str, ctx: CurrentWorkspace, user: CurrentUser, db: DB
) -> None:
    ws, _ = ctx
    kpi = (
        await db.execute(
            select(CustomKPI).where(CustomKPI.id == kpi_id, CustomKPI.workspace_id == ws.id)
        )
    ).scalar_one_or_none()
    if not kpi:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "kpi not found")
    await db.delete(kpi)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="kpi.delete",
            target_type="kpi",
            target_id=kpi_id,
            payload={},
        )
    )
    await db.commit()


@router.post("/evaluate")
async def evaluate_kpi(
    body: dict[str, Any],
    _ctx: CurrentWorkspace,
    _user: CurrentUser,
) -> dict[str, Any]:
    """Evaluate a formula against inline values.

    Body: {"formula": "...", "variables": {...}, "cases": [{...}, ...]}
    """
    formula = body.get("formula")
    variables = body.get("variables") or {}
    cases = body.get("cases") or []
    if not isinstance(formula, str) or not formula:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "formula required")
    if not isinstance(variables, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "variables must be an object")

    shape = validate_formula_shape(formula, variables if variables else {"x": 1, "y": 1})
    arithmetic = validate_arithmetic_consistency(formula, cases) if cases else []

    value: Any = None
    if not any(i.level == "error" for i in shape):
        try:
            value = evaluate_formula(formula, variables)
        except FormulaError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    return {
        "value": value,
        "issues": [
            {"layer": i.layer, "level": i.level, "message": i.message}
            for i in [*shape, *arithmetic]
        ],
    }


def _extract_variable_names(formula: str) -> set[str]:
    """Best-effort extraction of identifier tokens that are not known functions."""
    import ast as _ast

    try:
        tree = _ast.parse(formula, mode="eval")
    except SyntaxError:
        return set()
    names: set[str] = set()
    known_funcs = {"min", "max", "sum", "abs", "round", "avg", "sqrt"}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Name) and node.id not in known_funcs:
            names.add(node.id)
    return names
