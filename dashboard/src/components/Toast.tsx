import React from 'react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const Toast: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  return (
    <section
      className="toast-container"
      aria-label="Notification alerts"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((t) => {
        const icon = t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : 'ℹ️';
        return (
          <button
            key={t.id}
            type="button"
            className={`toast ${t.type}`}
            onClick={() => onDismiss(t.id)}
            title="Click to dismiss"
            aria-label={`Dismiss notification: ${t.message}`}
          >
            <span className="toast-icon" aria-hidden="true">
              {icon}
            </span>
            <span>{t.message}</span>
          </button>
        );
      })}
    </section>
  );
};
