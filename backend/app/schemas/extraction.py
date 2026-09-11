from typing import List, Optional

from pydantic import BaseModel


class FieldValue(BaseModel):
    value: Optional[object] = None
    source_text: Optional[str] = None
    page_number: Optional[int] = None
    confidence: Optional[float] = None


class LineItem(BaseModel):
    description: Optional[FieldValue] = None
    quantity: Optional[FieldValue] = None
    unit_price: Optional[FieldValue] = None
    amount: Optional[FieldValue] = None


class InvoiceExtraction(BaseModel):
    invoice_number: Optional[FieldValue] = None
    invoice_date: Optional[FieldValue] = None
    vendor_name: Optional[FieldValue] = None
    customer_name: Optional[FieldValue] = None
    currency: Optional[FieldValue] = None
    subtotal: Optional[FieldValue] = None
    tax_amount: Optional[FieldValue] = None
    discount: Optional[FieldValue] = None
    total_amount: Optional[FieldValue] = None
    cash_paid: Optional[FieldValue] = None
    change: Optional[FieldValue] = None
    line_items: List[LineItem] = []
    additional_fields: dict = {}


class PeriodFinancials(BaseModel):
    period_label: Optional[str] = None
    line_items: dict = {}


class BalanceSheetExtraction(BaseModel):
    company_name: Optional[FieldValue] = None
    report_date: Optional[FieldValue] = None
    currency: Optional[FieldValue] = None
    periods: List[PeriodFinancials] = []
    additional_fields: dict = {}


class ProfitAndLossExtraction(BaseModel):
    company_name: Optional[FieldValue] = None
    report_date: Optional[FieldValue] = None
    currency: Optional[FieldValue] = None
    periods: List[PeriodFinancials] = []
    additional_fields: dict = {}


class CashFlowExtraction(BaseModel):
    company_name: Optional[FieldValue] = None
    report_date: Optional[FieldValue] = None
    currency: Optional[FieldValue] = None
    periods: List[PeriodFinancials] = []
    additional_fields: dict = {}
