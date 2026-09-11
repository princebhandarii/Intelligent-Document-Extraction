import json

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.exceptions import ExtractionError

settings = get_settings()
logger = get_logger(__name__)

FIELD_VALUE_SHAPE = (
    '{"value": <parsed value or null>, "source_text": <verbatim snippet or null>, '
    '"page_number": <int or null>, "confidence": <float 0-1 or null>}'
)

SCHEMA_INSTRUCTIONS = {
    "invoice": f"""
Return strict JSON with this exact shape, wrapping every scalar field as {FIELD_VALUE_SHAPE}:
{{
  "invoice_number": <field>, "invoice_date": <field>, "vendor_name": <field>,
  "customer_name": <field>, "currency": <field>, "subtotal": <field>,
  "tax_amount": <field>, "discount": <field>, "total_amount": <field>,
  "cash_paid": <field>, "change": <field>,
  "line_items": [{{"description": <field>, "quantity": <field>, "unit_price": <field>, "amount": <field>}}],
  "additional_fields": {{"<any other visible field name>": <raw value>}}
}}
""",
    "balance_sheet": f"""
Return strict JSON with this exact shape, wrapping every scalar field as {FIELD_VALUE_SHAPE}:
{{
  "company_name": <field>, "report_date": <field>, "currency": <field>,
  "periods": [
    {{"period_label": "<e.g. FY2024>", "line_items": {{"total_assets": <field>, "total_liabilities": <field>,
      "total_equity": <field>, "<any other visible line item>": <field>}}}}
  ],
  "additional_fields": {{}}
}}
""",
    "profit_and_loss": f"""
Return strict JSON with this exact shape, wrapping every scalar field as {FIELD_VALUE_SHAPE}:
{{
  "company_name": <field>, "report_date": <field>, "currency": <field>,
  "periods": [
    {{"period_label": "<e.g. FY2024>", "line_items": {{"revenue": <field>, "cost_of_sales": <field>,
      "gross_profit": <field>, "operating_expenses": <field>, "operating_profit": <field>,
      "tax": <field>, "net_profit": <field>, "<any other visible line item>": <field>}}}}
  ],
  "additional_fields": {{}}
}}
""",
    "cash_flow_statement": f"""
Return strict JSON with this exact shape, wrapping every scalar field as {FIELD_VALUE_SHAPE}:
{{
  "company_name": <field>, "report_date": <field>, "currency": <field>,
  "periods": [
    {{"period_label": "<e.g. FY2024>", "line_items": {{"operating_cash_flow": <field>,
      "investing_cash_flow": <field>, "financing_cash_flow": <field>, "opening_cash": <field>,
      "net_change_in_cash": <field>, "closing_cash": <field>, "<any other visible line item>": <field>}}}}
  ],
  "additional_fields": {{}}
}}
""",
}

SYSTEM_PROMPT = (
    "You are a financial document extraction engine. You are given raw OCR or PDF text "
    "from a scanned or native document. Extract only values that are actually present in "
    "the text. Never invent, infer, or estimate a value. If a field is not present, set its "
    "value to null. Respond with valid JSON only, no markdown fences, no commentary.\n\n"
    "Financial statement lines are frequently followed by a schedule or note reference "
    "number before the actual amount, for example 'Interest earned 13 348,615.15' or "
    "'Provisions and contingencies 18 (9) 49,578.21'. The small integer(s) immediately "
    "after the label (with no thousands separator or decimal point) are schedule/note "
    "references, not part of the amount — do not prepend, append, or merge them into the "
    "numeric value. The actual amount is the number formatted with a thousands separator "
    "and/or decimal point (e.g. 348,615.15), or a plain decimal number if the source has "
    "no separators. When a line has multiple numbers before the real amount, only the "
    "properly formatted currency number is the value; skip standalone small integers, "
    "parenthesized note numbers, and stray punctuation.\n\n"
    "Statements that show two or more years/periods side by side as separate columns are "
    "a common source of error: OCR text can lose the spacing that separates columns, "
    "causing a value to appear next to the wrong year. Before assigning a number to a "
    "period, check its horizontal position relative to the column headers in the raw text "
    "(the value closest to that period's header, in reading order, belongs to it). Where "
    "the same figure should logically carry across periods (for example, one period's "
    "closing cash balance is usually the next period's opening cash balance), use that as "
    "a consistency check. If you cannot confidently tell which column a number belongs to, "
    "set that field to null for the uncertain period rather than guessing — a missing value "
    "is safer than a value attributed to the wrong period."
)


def extract_structured_data(document_type: str, raw_text: str) -> dict:
    if not settings.llm_api_key:
        raise ExtractionError(
            "LLM_API_KEY is not configured on the server. Set it in your environment to enable extraction."
        )

    schema_instructions = SCHEMA_INSTRUCTIONS.get(document_type)
    if not schema_instructions:
        raise ExtractionError(f"No extraction schema configured for document type '{document_type}'")

    user_prompt = (
        f"Document type: {document_type}\n\n"
        f"Schema to follow:\n{schema_instructions}\n\n"
        f"Raw document text:\n{raw_text[:12000]}"
    )

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("LLM extraction call failed: %s", exc)
        raise ExtractionError("Failed to reach the extraction model provider") from exc

    body = response.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ExtractionError("Extraction model returned an unexpected response shape") from exc

    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse extraction model output: %s", content[:500])
        raise ExtractionError("Extraction model returned invalid JSON") from exc