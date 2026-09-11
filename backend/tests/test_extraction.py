from app.schemas.document import ValidationStatus
from app.services.financial_validation_service import validate_balance_sheet, validate_invoice


def test_invoice_line_item_and_total_validation_passes():
    data = {
        "line_items": [
            {
                "quantity": {"value": 2},
                "unit_price": {"value": 50},
                "amount": {"value": 100},
            }
        ],
        "subtotal": {"value": 100},
        "tax_amount": {"value": 10},
        "discount": {"value": 0},
        "total_amount": {"value": 110},
    }

    summary = validate_invoice(data)

    line_check = next(c for c in summary.checks if c.name == "line_item_1_total")
    total_check = next(c for c in summary.checks if c.name == "subtotal_tax_discount_vs_total")

    assert line_check.status == ValidationStatus.pass_
    assert total_check.status == ValidationStatus.pass_


def test_invoice_validation_fails_on_mismatch():
    data = {
        "line_items": [],
        "subtotal": {"value": 100},
        "tax_amount": {"value": 10},
        "discount": {"value": 0},
        "total_amount": {"value": 999},
    }

    summary = validate_invoice(data)
    total_check = next(c for c in summary.checks if c.name == "subtotal_tax_discount_vs_total")

    assert total_check.status == ValidationStatus.fail


def test_balance_sheet_validation_not_applicable_when_missing_fields():
    data = {"periods": [{"period_label": "FY2024", "line_items": {}}]}

    summary = validate_balance_sheet(data)

    assert summary.overall_status == ValidationStatus.not_applicable
