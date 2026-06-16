import React, { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info } from "lucide-react";

const ToastCtx = createContext(null);

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const ACCENT = {
  success: "text-emerald-400 border-emerald-400/30",
  error: "text-rose-400 border-rose-400/30",
  warning: "text-amber-400 border-amber-400/30",
  info: "text-cyan-glow border-cyan-glow/30",
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const push = useCallback((message, type = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800);
  }, []);

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
        {toasts.map((t) => {
          const Icon = ICONS[t.type] || Info;
          return (
            <div
              key={t.id}
              role="status"
              className={`glass animate-slide-in flex items-center gap-3 px-4 py-3 pr-5 ${ACCENT[t.type]}`}
            >
              <Icon size={18} />
              <span className="text-sm text-paper-100">{t.message}</span>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
