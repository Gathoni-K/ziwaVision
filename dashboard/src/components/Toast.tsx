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
    <div
      className="toast-container"
      role="region"
      aria-label="Notification alerts"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((t) => {
        const icon = t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : 'ℹ️';
        return (
          <div
            key={t.id}
            className={`toast ${t.type}`}
            onClick={() => onDismiss(t.id)}
            style={{ cursor: 'pointer' }}
            title="Click to dismiss"
          >
            <span className="toast-icon" aria-hidden="true">
              {icon}
            </span>
            <span>{t.message}</span>
          </div>
        );
      })}
    </div>
  );
};
