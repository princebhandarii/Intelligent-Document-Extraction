const processButton = document.getElementById("process-button");
const uploadStatus = document.getElementById("upload-status");
const documentTypeSelect = document.getElementById("document-type");
const documentFileInput = document.getElementById("document-file");

processButton.addEventListener("click", async () => {
  const file = documentFileInput.files[0];
  if (!file) {
    uploadStatus.textContent = "Select a file before processing.";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentTypeSelect.value);

  processButton.disabled = true;
  uploadStatus.textContent = "Processing document...";

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/process`, {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();

    if (!response.ok) {
      const message = payload && payload.error ? payload.error.message : "Processing failed.";
      uploadStatus.textContent = `Error: ${message}`;
      return;
    }

    uploadStatus.textContent = `Processed successfully in ${payload.processing_metadata.processing_time_ms}ms.`;
    documentFileInput.value = "";
    if (typeof loadDashboard === "function") {
      loadDashboard();
    }
  } catch (error) {
    uploadStatus.textContent = "Network error while contacting the backend.";
  } finally {
    processButton.disabled = false;
  }
});
