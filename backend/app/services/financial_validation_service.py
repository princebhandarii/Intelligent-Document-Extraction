from typing import List, Optional

from app.core.config import get_settings
from app.schemas.document import ValidationCheck, ValidationStatus, ValidationSummary
from app.utils.numeric import is_close, parse_amount

settings = get_settings()
TOLERANCE = settings.financial_tolerance_percent


def _field_value(field: Optional[dict]) -> Optional[float]:
    if not field or not isinstance(field, dict):
        return None
    return parse_amount(field.get("value"))


def _make_check(
    name: str,
    formula: str,
    operands: dict,
    calculated: Optional[float],
    reported: Optional[float],
    period_label: Optional[str] = None,
) -> ValidationCheck:
    if calculated is None or reported is None:
        return ValidationCheck(
            name=name,
            formula=formula,
            operands=operands,
            calculated_value=calculated,
            reported_value=reported,
            variance=None,
            status=ValidationStatus.not_applicable,
            period_label=period_label,
        )

    variance = round(calculated - reported, 2)
    status = ValidationStatus.pass_ if is_close(calculated, reported, TOLERANCE) else ValidationStatus.fail

    return ValidationCheck(
        name=name,
        formula=formula,
        operands=operands,
        calculated_value=round(calculated, 2),
        reported_value=round(reported, 2),
        variance=variance,
        status=status,
        period_label=period_label,
    )


def _overall_status(checks: List[ValidationCheck]) -> ValidationStatus:
    if not checks:
        return ValidationStatus.not_applicable
    if any(check.status == ValidationStatus.fail for check in checks):
        return ValidationStatus.fail
    if all(check.status == ValidationStatus.not_applicable for check in checks):
        return ValidationStatus.not_applicable
    return ValidationStatus.pass_


def validate_invoice(data: dict) -> ValidationSummary:
    checks: List[ValidationCheck] = []

    line_items = data.get("line_items") or []
    line_total_sum = 0.0
    any_line_amount = False
    for index, item in enumerate(line_items):
        qty = _field_value(item.get("quantity"))
        price = _field_value(item.get("unit_price"))
        amount = _field_value(item.get("amount"))
        calculated = qty * price if qty is not None and price is not None else None
        checks.append(
            _make_check(
                name=f"line_item_{index + 1}_total",
                formula="quantity * unit_price ≈ amount",
                operands={"quantity": qty, "unit_price": price},
                calculated=calculated,
                reported=amount,
            )
        )
        if amount is not None:
            line_total_sum += amount
            any_line_amount = True

    subtotal = _field_value(data.get("subtotal"))
    tax = _field_value(data.get("tax_amount"))
    discount = _field_value(data.get("discount")) or 0.0
    total = _field_value(data.get("total_amount"))
    line_sum = line_total_sum if any_line_amount else None

    matches_subtotal = is_close(line_sum, subtotal, TOLERANCE) if line_sum is not None else False
    matches_total = is_close(line_sum, total, TOLERANCE) if line_sum is not None else False

    if not matches_subtotal and matches_total:
        checks.append(
            _make_check(
                name="line_items_sum_vs_total_tax_inclusive",
                formula="sum(line_item.amount) ≈ total_amount (line items are tax-inclusive)",
                operands={"line_item_sum": line_sum},
                calculated=line_sum,
                reported=total,
            )
        )
    else:
        checks.append(
            _make_check(
                name="line_items_sum_vs_subtotal",
                formula="sum(line_item.amount) ≈ subtotal",
                operands={"line_item_sum": line_sum},
                calculated=line_sum,
                reported=subtotal,
            )
        )

    calculated_total = None
    if subtotal is not None and tax is not None:
        calculated_total = subtotal + tax - discount
    checks.append(
        _make_check(
            name="subtotal_tax_discount_vs_total",
            formula="subtotal + tax_amount - discount ≈ total_amount",
            operands={"subtotal": subtotal, "tax_amount": tax, "discount": discount},
            calculated=calculated_total,
            reported=total,
        )
    )

    cash_paid = _field_value(data.get("cash_paid"))
    change = _field_value(data.get("change"))
    calculated_change = None
    if cash_paid is not None and total is not None:
        calculated_change = cash_paid - total
    checks.append(
        _make_check(
            name="cash_paid_vs_change",
            formula="cash_paid - total_amount ≈ change",
            operands={"cash_paid": cash_paid, "total_amount": total},
            calculated=calculated_change,
            reported=change,
        )
    )

    return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


def validate_balance_sheet(data: dict) -> ValidationSummary:
    checks: List[ValidationCheck] = []

    for period in data.get("periods") or []:
        label = period.get("period_label")
        items = period.get("line_items") or {}

        assets = _field_value(items.get("total_assets"))
        liabilities = _field_value(items.get("total_liabilities"))
        equity = _field_value(items.get("total_equity"))
        calculated = liabilities + equity if liabilities is not None and equity is not None else None

        checks.append(
            _make_check(
                name="liabilities_plus_equity_vs_assets",
                formula="total_liabilities + total_equity ≈ total_assets",
                operands={"total_liabilities": liabilities, "total_equity": equity},
                calculated=calculated,
                reported=assets,
                period_label=label,
            )
        )

        equity_component_keys = ["capital", "reserves_and_surplus", "minority_interest"]
        liability_component_keys = ["deposits", "borrowings", "other_liabilities_and_provisions"]
        equity_and_liability_components = {
            key: _field_value(items.get(key)) for key in equity_component_keys + liability_component_keys
        }
        if all(value is not None for value in equity_and_liability_components.values()):
            calculated_from_components = sum(equity_and_liability_components.values())
        else:
            calculated_from_components = None
        checks.append(
            _make_check(
                name="equity_and_liability_components_vs_total_assets",
                formula=(
                    "capital + reserves_and_surplus + minority_interest + deposits + "
                    "borrowings + other_liabilities_and_provisions ≈ total_assets"
                ),
                operands=equity_and_liability_components,
                calculated=calculated_from_components,
                reported=assets,
                period_label=label,
            )
        )

        asset_component_keys = [
            "cash_and_balances_with_reserve_bank_of_india",
            "balances_with_banks_and_money_at_call_and_short_notice",
            "investments",
            "advances",
            "fixed_assets",
            "other_assets",
        ]
        asset_components = {key: _field_value(items.get(key)) for key in asset_component_keys}
        if all(value is not None for value in asset_components.values()):
            calculated_assets_from_components = sum(asset_components.values())
        else:
            calculated_assets_from_components = None
        checks.append(
            _make_check(
                name="asset_components_vs_total_assets",
                formula=(
                    "cash_and_balances_with_reserve_bank_of_india + "
                    "balances_with_banks_and_money_at_call_and_short_notice + investments + "
                    "advances + fixed_assets + other_assets ≈ total_assets"
                ),
                operands=asset_components,
                calculated=calculated_assets_from_components,
                reported=assets,
                period_label=label,
            )
        )

    return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


def validate_profit_and_loss(data: dict) -> ValidationSummary:
    checks: List[ValidationCheck] = []

    for period in data.get("periods") or []:
        label = period.get("period_label")
        items = period.get("line_items") or {}

        revenue = _field_value(items.get("revenue"))
        cogs = _field_value(items.get("cost_of_sales")) or _field_value(items.get("cogs"))
        gross_profit = _field_value(items.get("gross_profit"))
        calculated_gross = revenue - cogs if revenue is not None and cogs is not None else None
        checks.append(
            _make_check(
                name="revenue_minus_cogs_vs_gross_profit",
                formula="revenue - cost_of_sales ≈ gross_profit",
                operands={"revenue": revenue, "cost_of_sales": cogs},
                calculated=calculated_gross,
                reported=gross_profit,
                period_label=label,
            )
        )

        opex = _field_value(items.get("operating_expenses"))
        operating_profit = _field_value(items.get("operating_profit"))
        calculated_operating = None
        if gross_profit is not None and opex is not None:
            calculated_operating = gross_profit - opex
        checks.append(
            _make_check(
                name="gross_profit_minus_opex_vs_operating_profit",
                formula="gross_profit - operating_expenses ≈ operating_profit",
                operands={"gross_profit": gross_profit, "operating_expenses": opex},
                calculated=calculated_operating,
                reported=operating_profit,
                period_label=label,
            )
        )

        tax = _field_value(items.get("tax"))
        net_profit = _field_value(items.get("net_profit"))
        calculated_net = None
        if operating_profit is not None and tax is not None:
            calculated_net = operating_profit - tax
        checks.append(
            _make_check(
                name="operating_profit_minus_tax_vs_net_profit",
                formula="operating_profit - tax ≈ net_profit",
                operands={"operating_profit": operating_profit, "tax": tax},
                calculated=calculated_net,
                reported=net_profit,
                period_label=label,
            )
        )

        interest_earned = _field_value(items.get("interest_earned"))
        other_income = _field_value(items.get("other_income"))
        total_income = revenue
        calculated_total_income = None
        if interest_earned is not None and other_income is not None:
            calculated_total_income = interest_earned + other_income
        checks.append(
            _make_check(
                name="interest_and_other_income_vs_total_income",
                formula="interest_earned + other_income ≈ total_income",
                operands={"interest_earned": interest_earned, "other_income": other_income},
                calculated=calculated_total_income,
                reported=total_income,
                period_label=label,
            )
        )

        interest_expended = _field_value(items.get("interest_expended"))
        provisions = _field_value(items.get("provisions_and_contingencies")) or _field_value(
            items.get("provisions")
        )
        total_expenditure = _field_value(items.get("total_expenditure"))
        calculated_total_expenditure = None
        if interest_expended is not None and opex is not None and provisions is not None:
            calculated_total_expenditure = interest_expended + opex + provisions
        checks.append(
            _make_check(
                name="interest_opex_provisions_vs_total_expenditure",
                formula="interest_expended + operating_expenses + provisions ≈ total_expenditure",
                operands={
                    "interest_expended": interest_expended,
                    "operating_expenses": opex,
                    "provisions": provisions,
                },
                calculated=calculated_total_expenditure,
                reported=total_expenditure,
                period_label=label,
            )
        )

        net_profit_before_minority = _field_value(items.get("net_profit_before_minority_interest"))
        calculated_before_minority = None
        if total_income is not None and total_expenditure is not None:
            calculated_before_minority = total_income - total_expenditure
        checks.append(
            _make_check(
                name="total_income_minus_total_expenditure_vs_net_profit_before_minority",
                formula="total_income - total_expenditure ≈ net_profit_before_minority_interest",
                operands={"total_income": total_income, "total_expenditure": total_expenditure},
                calculated=calculated_before_minority,
                reported=net_profit_before_minority,
                period_label=label,
            )
        )

        minority_interest = _field_value(items.get("minority_interest"))
        net_profit_attributable = net_profit
        calculated_attributable = None
        if net_profit_before_minority is not None and minority_interest is not None:
            calculated_attributable = net_profit_before_minority - minority_interest
        checks.append(
            _make_check(
                name="net_profit_before_minority_minus_minority_interest_vs_net_profit_attributable",
                formula="net_profit_before_minority_interest - minority_interest ≈ net_profit_attributable_to_group",
                operands={
                    "net_profit_before_minority_interest": net_profit_before_minority,
                    "minority_interest": minority_interest,
                },
                calculated=calculated_attributable,
                reported=net_profit_attributable,
                period_label=label,
            )
        )

        current_profit = _field_value(items.get("current_profit"))
        brought_forward_profit = _field_value(items.get("brought_forward_profit"))
        total_available_for_appropriation = _field_value(items.get("total_available_for_appropriation"))
        calculated_appropriation = None
        if current_profit is not None and brought_forward_profit is not None:
            calculated_appropriation = current_profit + brought_forward_profit
        checks.append(
            _make_check(
                name="current_plus_brought_forward_profit_vs_total_available_for_appropriation",
                formula="current_profit + brought_forward_profit ≈ total_available_for_appropriation",
                operands={"current_profit": current_profit, "brought_forward_profit": brought_forward_profit},
                calculated=calculated_appropriation,
                reported=total_available_for_appropriation,
                period_label=label,
            )
        )

    return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


def validate_cash_flow(data: dict) -> ValidationSummary:
    checks: List[ValidationCheck] = []

    for period in data.get("periods") or []:
        label = period.get("period_label")
        items = period.get("line_items") or {}

        operating = _field_value(items.get("operating_cash_flow"))
        investing = _field_value(items.get("investing_cash_flow"))
        financing = _field_value(items.get("financing_cash_flow"))
        net_change = _field_value(items.get("net_change_in_cash"))
        calculated_net_change = None
        if operating is not None and investing is not None and financing is not None:
            calculated_net_change = operating + investing + financing

        checks.append(
            _make_check(
                name="operating_investing_financing_vs_net_change",
                formula="operating_cash_flow + investing_cash_flow + financing_cash_flow ≈ net_change_in_cash",
                operands={"operating_cash_flow": operating, "investing_cash_flow": investing, "financing_cash_flow": financing},
                calculated=calculated_net_change,
                reported=net_change,
                period_label=label,
            )
        )

        opening = _field_value(items.get("opening_cash"))
        closing = _field_value(items.get("closing_cash"))
        calculated_closing = None
        if opening is not None and net_change is not None:
            calculated_closing = opening + net_change
        checks.append(
            _make_check(
                name="opening_cash_plus_net_change_vs_closing_cash",
                formula="opening_cash + net_change_in_cash ≈ closing_cash",
                operands={"opening_cash": opening, "net_change_in_cash": net_change},
                calculated=calculated_closing,
                reported=closing,
                period_label=label,
            )
        )

    return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


VALIDATORS = {
    "invoice": validate_invoice,
    "balance_sheet": validate_balance_sheet,
    "profit_and_loss": validate_profit_and_loss,
    "cash_flow_statement": validate_cash_flow,
}


def run_validation(document_type: str, extracted_data: dict) -> ValidationSummary:
    validator = VALIDATORS.get(document_type)
    if not validator:
        return ValidationSummary(checks=[], overall_status=ValidationStatus.not_applicable)
    return validator(extracted_data)


# from typing import List, Optional

# from app.core.config import get_settings
# from app.schemas.document import ValidationCheck, ValidationStatus, ValidationSummary
# from app.utils.numeric import is_close, parse_amount

# settings = get_settings()
# TOLERANCE = settings.financial_tolerance_percent


# def _field_value(field: Optional[dict]) -> Optional[float]:
#     if not field or not isinstance(field, dict):
#         return None
#     return parse_amount(field.get("value"))


# def _make_check(
#     name: str,
#     formula: str,
#     operands: dict,
#     calculated: Optional[float],
#     reported: Optional[float],
#     period_label: Optional[str] = None,
# ) -> ValidationCheck:
#     if calculated is None or reported is None:
#         return ValidationCheck(
#             name=name,
#             formula=formula,
#             operands=operands,
#             calculated_value=calculated,
#             reported_value=reported,
#             variance=None,
#             status=ValidationStatus.not_applicable,
#             period_label=period_label,
#         )

#     variance = round(calculated - reported, 2)
#     status = ValidationStatus.pass_ if is_close(calculated, reported, TOLERANCE) else ValidationStatus.fail

#     return ValidationCheck(
#         name=name,
#         formula=formula,
#         operands=operands,
#         calculated_value=round(calculated, 2),
#         reported_value=round(reported, 2),
#         variance=variance,
#         status=status,
#         period_label=period_label,
#     )


# def _overall_status(checks: List[ValidationCheck]) -> ValidationStatus:
#     if not checks:
#         return ValidationStatus.not_applicable
#     if any(check.status == ValidationStatus.fail for check in checks):
#         return ValidationStatus.fail
#     if all(check.status == ValidationStatus.not_applicable for check in checks):
#         return ValidationStatus.not_applicable
#     return ValidationStatus.pass_


# def validate_invoice(data: dict) -> ValidationSummary:
#     checks: List[ValidationCheck] = []

#     line_items = data.get("line_items") or []
#     line_total_sum = 0.0
#     any_line_amount = False
#     for index, item in enumerate(line_items):
#         qty = _field_value(item.get("quantity"))
#         price = _field_value(item.get("unit_price"))
#         amount = _field_value(item.get("amount"))
#         calculated = qty * price if qty is not None and price is not None else None
#         checks.append(
#             _make_check(
#                 name=f"line_item_{index + 1}_total",
#                 formula="quantity * unit_price ≈ amount",
#                 operands={"quantity": qty, "unit_price": price},
#                 calculated=calculated,
#                 reported=amount,
#             )
#         )
#         if amount is not None:
#             line_total_sum += amount
#             any_line_amount = True

#     subtotal = _field_value(data.get("subtotal"))
#     tax = _field_value(data.get("tax_amount"))
#     discount = _field_value(data.get("discount")) or 0.0
#     total = _field_value(data.get("total_amount"))
#     line_sum = line_total_sum if any_line_amount else None

#     matches_subtotal = is_close(line_sum, subtotal, TOLERANCE) if line_sum is not None else False
#     matches_total = is_close(line_sum, total, TOLERANCE) if line_sum is not None else False

#     if not matches_subtotal and matches_total:
#         checks.append(
#             _make_check(
#                 name="line_items_sum_vs_total_tax_inclusive",
#                 formula="sum(line_item.amount) ≈ total_amount (line items are tax-inclusive)",
#                 operands={"line_item_sum": line_sum},
#                 calculated=line_sum,
#                 reported=total,
#             )
#         )
#     else:
#         checks.append(
#             _make_check(
#                 name="line_items_sum_vs_subtotal",
#                 formula="sum(line_item.amount) ≈ subtotal",
#                 operands={"line_item_sum": line_sum},
#                 calculated=line_sum,
#                 reported=subtotal,
#             )
#         )

#     calculated_total = None
#     if subtotal is not None and tax is not None:
#         calculated_total = subtotal + tax - discount
#     checks.append(
#         _make_check(
#             name="subtotal_tax_discount_vs_total",
#             formula="subtotal + tax_amount - discount ≈ total_amount",
#             operands={"subtotal": subtotal, "tax_amount": tax, "discount": discount},
#             calculated=calculated_total,
#             reported=total,
#         )
#     )

#     cash_paid = _field_value(data.get("cash_paid"))
#     change = _field_value(data.get("change"))
#     calculated_change = None
#     if cash_paid is not None and total is not None:
#         calculated_change = cash_paid - total
#     checks.append(
#         _make_check(
#             name="cash_paid_vs_change",
#             formula="cash_paid - total_amount ≈ change",
#             operands={"cash_paid": cash_paid, "total_amount": total},
#             calculated=calculated_change,
#             reported=change,
#         )
#     )

#     return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


# def validate_balance_sheet(data: dict) -> ValidationSummary:
#     checks: List[ValidationCheck] = []

#     for period in data.get("periods") or []:
#         label = period.get("period_label")
#         items = period.get("line_items") or {}

#         assets = _field_value(items.get("total_assets"))
#         liabilities = _field_value(items.get("total_liabilities"))
#         equity = _field_value(items.get("total_equity"))
#         calculated = liabilities + equity if liabilities is not None and equity is not None else None

#         checks.append(
#             _make_check(
#                 name="liabilities_plus_equity_vs_assets",
#                 formula="total_liabilities + total_equity ≈ total_assets",
#                 operands={"total_liabilities": liabilities, "total_equity": equity},
#                 calculated=calculated,
#                 reported=assets,
#                 period_label=label,
#             )
#         )

#     return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


# def validate_profit_and_loss(data: dict) -> ValidationSummary:
#     checks: List[ValidationCheck] = []

#     for period in data.get("periods") or []:
#         label = period.get("period_label")
#         items = period.get("line_items") or {}

#         revenue = _field_value(items.get("revenue"))
#         cogs = _field_value(items.get("cost_of_sales")) or _field_value(items.get("cogs"))
#         gross_profit = _field_value(items.get("gross_profit"))
#         calculated_gross = revenue - cogs if revenue is not None and cogs is not None else None
#         checks.append(
#             _make_check(
#                 name="revenue_minus_cogs_vs_gross_profit",
#                 formula="revenue - cost_of_sales ≈ gross_profit",
#                 operands={"revenue": revenue, "cost_of_sales": cogs},
#                 calculated=calculated_gross,
#                 reported=gross_profit,
#                 period_label=label,
#             )
#         )

#         opex = _field_value(items.get("operating_expenses"))
#         operating_profit = _field_value(items.get("operating_profit"))
#         calculated_operating = None
#         if gross_profit is not None and opex is not None:
#             calculated_operating = gross_profit - opex
#         checks.append(
#             _make_check(
#                 name="gross_profit_minus_opex_vs_operating_profit",
#                 formula="gross_profit - operating_expenses ≈ operating_profit",
#                 operands={"gross_profit": gross_profit, "operating_expenses": opex},
#                 calculated=calculated_operating,
#                 reported=operating_profit,
#                 period_label=label,
#             )
#         )

#         tax = _field_value(items.get("tax"))
#         net_profit = _field_value(items.get("net_profit"))
#         calculated_net = None
#         if operating_profit is not None and tax is not None:
#             calculated_net = operating_profit - tax
#         checks.append(
#             _make_check(
#                 name="operating_profit_minus_tax_vs_net_profit",
#                 formula="operating_profit - tax ≈ net_profit",
#                 operands={"operating_profit": operating_profit, "tax": tax},
#                 calculated=calculated_net,
#                 reported=net_profit,
#                 period_label=label,
#             )
#         )

#     return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


# def validate_cash_flow(data: dict) -> ValidationSummary:
#     checks: List[ValidationCheck] = []

#     for period in data.get("periods") or []:
#         label = period.get("period_label")
#         items = period.get("line_items") or {}

#         operating = _field_value(items.get("operating_cash_flow"))
#         investing = _field_value(items.get("investing_cash_flow"))
#         financing = _field_value(items.get("financing_cash_flow"))
#         net_change = _field_value(items.get("net_change_in_cash"))
#         calculated_net_change = None
#         if operating is not None and investing is not None and financing is not None:
#             calculated_net_change = operating + investing + financing

#         checks.append(
#             _make_check(
#                 name="operating_investing_financing_vs_net_change",
#                 formula="operating_cash_flow + investing_cash_flow + financing_cash_flow ≈ net_change_in_cash",
#                 operands={"operating_cash_flow": operating, "investing_cash_flow": investing, "financing_cash_flow": financing},
#                 calculated=calculated_net_change,
#                 reported=net_change,
#                 period_label=label,
#             )
#         )

#         opening = _field_value(items.get("opening_cash"))
#         closing = _field_value(items.get("closing_cash"))
#         calculated_closing = None
#         if opening is not None and net_change is not None:
#             calculated_closing = opening + net_change
#         checks.append(
#             _make_check(
#                 name="opening_cash_plus_net_change_vs_closing_cash",
#                 formula="opening_cash + net_change_in_cash ≈ closing_cash",
#                 operands={"opening_cash": opening, "net_change_in_cash": net_change},
#                 calculated=calculated_closing,
#                 reported=closing,
#                 period_label=label,
#             )
#         )

#     return ValidationSummary(checks=checks, overall_status=_overall_status(checks))


# VALIDATORS = {
#     "invoice": validate_invoice,
#     "balance_sheet": validate_balance_sheet,
#     "profit_and_loss": validate_profit_and_loss,
#     "cash_flow_statement": validate_cash_flow,
# }


# def run_validation(document_type: str, extracted_data: dict) -> ValidationSummary:
#     validator = VALIDATORS.get(document_type)
#     if not validator:
#         return ValidationSummary(checks=[], overall_status=ValidationStatus.not_applicable)
#     return validator(extracted_data)