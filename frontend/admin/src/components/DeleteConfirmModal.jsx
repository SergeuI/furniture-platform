import { useEffect, useState } from "react";
import { X } from "lucide-react";

export default function DeleteConfirmModal({
  open = false,
  title = "",
  message = "",
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  loadingLabel = "Deleting...",
  onCancel,
  onConfirm,
}) {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!open) {
      setLoading(false);
      setErrorMessage("");
    }
  }, [open]);

  if (!open) {
    return null;
  }

  async function handleConfirm() {
    if (loading) {
      return;
    }

    setLoading(true);
    setErrorMessage("");

    try {
      await onConfirm?.();
    } catch (error) {
      setErrorMessage(error?.message || "Request failed");
      setLoading(false);
      return;
    }

    setLoading(false);
    onCancel?.();
  }

  function handleCancel() {
    if (loading) {
      return;
    }

    onCancel?.();
  }

  return (
    <div aria-modal="true" className="modal-backdrop" onClick={handleCancel} role="dialog">
      <section className="confirm-modal" onClick={(event) => event.stopPropagation()}>
        <header className="confirm-header">
          <div>
            <h2>{title}</h2>
          </div>
          <button
            aria-label="Close confirmation"
            className="icon-button"
            disabled={loading}
            onClick={handleCancel}
            type="button"
          >
            <X size={18} />
          </button>
        </header>
        <p>{message}</p>
        {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
        <div className="confirm-actions">
          <button className="ghost-button" disabled={loading} onClick={handleCancel} type="button">
            {cancelLabel}
          </button>
          <button className="danger-button" disabled={loading} onClick={handleConfirm} type="button">
            {loading ? loadingLabel : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
