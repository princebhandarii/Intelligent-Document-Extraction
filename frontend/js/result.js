const resultContainer = document.getElementById("result-container");

function getDocumentNameFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("name");
}

function isFieldValue(value) {
  return value && typeof value === "object" && "value" in value && !Array.isArray(value);
}

function renderFieldCard(label, fieldValue) {
  const value = fieldValue && fieldValue.value !== null && fieldValue.value !== undefined
    ? fieldValue.value
    : null;
  const isMissing = value === null;
  return `
    <div class="field-card ${isMissing ? "field-missing" : ""}">
      <div class="field-label">${label.replace(/_/g, " ")}</div>
      <div class="field-value">${isMissing ? "Not found" : value}</div>
    </div>`;
}

function renderScalarFields(data) {
  const cards = Object.entries(data)
    .filter(([, value]) => isFieldValue(value))
    .map(([key, value]) => renderFieldCard(key, value))
    .join("");
  return cards ? `<div class="field-grid">${cards}</div>` : "";
}

function renderLineItems(lineItems) {
  if (!lineItems || !lineItems.length) return "";
  const rows = lineItems
    .map((item) => {
      const description = item.description?.value ?? "—";
      const quantity = item.quantity?.value ?? "—";
      const unitPrice = item.unit_price?.value ?? "—";
      const amount = item.amount?.value ?? "—";
      return `<tr><td>${description}</td><td>${quantity}</td><td>${unitPrice}</td><td>${amount}</td></tr>`;
    })
    .join("");

  return `
    <table>
      <thead><tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderPeriods(periods) {
  if (!periods || !periods.length) return "";
  return periods
    .map((period) => {
      const items = period.line_items || {};
      const cards = Object.entries(items)
        .map(([key, value]) => renderFieldCard(key, value))
        .join("");
      return `
        <div style="margin-bottom: 24px;">
          <h3 style="font-size: 13px; text-transform: uppercase; margin-bottom: 12px; color: var(--gray-700);">
            ${period.period_label || "Period"}
          </h3>
          <div class="field-grid">${cards}</div>
        </div>`;
    })
    .join("");
}

function renderExtractedData(extractedData) {
  let html = renderScalarFields(extractedData);
  if (extractedData.line_items) {
    html += `<h3 style="font-size: 13px; text-transform: uppercase; margin: 20px 0 12px;">Line Items</h3>`;
    html += renderLineItems(extractedData.line_items);
  }
  if (extractedData.periods) {
    html += renderPeriods(extractedData.periods);
  }
  return html;
}

function badgeClass(status) {
  if (status === "PASS") return "badge-pass";
  if (status === "FAIL") return "badge-fail";
  return "badge-na";
}

function renderValidation(validation) {
  if (!validation.checks || !validation.checks.length) {
    return '<div class="empty-state">No validation checks were applicable.</div>';
  }

  const rows = validation.checks
    .map(
      (check) => `
        <tr>
          <td>${check.name.replace(/_/g, " ")}${check.period_label ? ` (${check.period_label})` : ""}</td>
          <td>${check.formula}</td>
          <td>${check.calculated_value ?? "—"}</td>
          <td>${check.reported_value ?? "—"}</td>
          <td>${check.variance ?? "—"}</td>
          <td><span class="badge ${badgeClass(check.status)}">${check.status}</span></td>
        </tr>`
    )
    .join("");

  return `
    <p style="margin-bottom: 16px;">
      Overall status: <span class="badge ${badgeClass(validation.overall_status)}">${validation.overall_status}</span>
    </p>
    <table>
      <thead>
        <tr><th>Check</th><th>Formula</th><th>Calculated</th><th>Reported</th><th>Variance</th><th>Status</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function loadResult() {
  const documentName = getDocumentNameFromUrl();
  if (!documentName) {
    resultContainer.innerHTML = '<div class="empty-state">No document specified.</div>';
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/${encodeURIComponent(documentName)}`);
    if (!response.ok) {
      resultContainer.innerHTML = '<div class="empty-state">Document not found.</div>';
      return;
    }
    const doc = await response.json();

    resultContainer.innerHTML = `
      <div class="doc-title">${doc.document_name}</div>
      <div class="doc-meta">
        ${doc.document_type} &middot; ${doc.processing_status} &middot;
        OCR used: ${doc.processing_metadata.ocr_used} &middot;
        ${doc.processing_metadata.processing_time_ms}ms
      </div>

      <section>
        <h2>Extracted Fields</h2>
        ${renderExtractedData(doc.extracted_data)}
      </section>

      <section>
        <h2>Validation Results</h2>
        ${renderValidation(doc.validation)}
      </section>

      <section>
        <h2>Raw JSON</h2>
        <pre class="raw-json">${JSON.stringify(doc, null, 2)}</pre>
      </section>
    `;

    document.title = `${doc.document_name} — Document Intelligence Platform`;

    if (new URLSearchParams(window.location.search).get("autoprint") === "1") {
      setTimeout(() => window.print(), 300);
    }
  } catch (error) {
    resultContainer.innerHTML = '<div class="empty-state">Could not reach the backend.</div>';
  }
}

const downloadPdfButton = document.getElementById("download-pdf-button");
if (downloadPdfButton) {
  downloadPdfButton.addEventListener("click", () => window.print());
}

loadResult();