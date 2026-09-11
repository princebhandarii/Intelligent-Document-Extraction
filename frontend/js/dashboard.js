const dashboardContainer = document.getElementById("dashboard-container");

function formatTimestamp(isoString) {
  const date = new Date(isoString);
  return date.toLocaleString();
}

function renderDashboard(documents) {
  if (!documents.length) {
    dashboardContainer.innerHTML = '<div class="empty-state">No documents processed yet.</div>';
    return;
  }

  const rows = documents
    .map(
      (doc) => `
        <tr onclick="window.location.href='result.html?name=${encodeURIComponent(doc.document_name)}'">
          <td>${doc.document_name}</td>
          <td>${doc.document_type}</td>
          <td><span class="badge ${doc.processing_status === "completed" ? "badge-pass" : "badge-fail"}">${doc.processing_status}</span></td>
          <td>${formatTimestamp(doc.processed_at)}</td>
          <td>
            ${
              doc.processing_status === "completed"
                ? `<a href="result.html?name=${encodeURIComponent(doc.document_name)}&autoprint=1"
                     target="_blank" class="download-link" onclick="event.stopPropagation()">Download PDF</a>`
                : "—"
            }
          </td>
        </tr>`
    )
    .join("");

  dashboardContainer.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Status</th>
          <th>Processed At</th>
          <th>Download</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function loadDashboard() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents`);
    if (!response.ok) {
      dashboardContainer.innerHTML = '<div class="empty-state">Could not load documents.</div>';
      return;
    }
    const documents = await response.json();
    renderDashboard(documents);
  } catch (error) {
    dashboardContainer.innerHTML = '<div class="empty-state">Could not reach the backend.</div>';
  }
}

loadDashboard();