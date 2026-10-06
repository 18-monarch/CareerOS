"use client";
import {
  useEffect,
  useRef,
  useState,
  useId,
  Children,
  isValidElement,
  cloneElement,
  type FormEvent,
  type ReactNode,
  type ReactElement,
} from "react";
import { X, AlertCircle, Loader2 } from "lucide-react";
import { pretty } from "@/lib/api";
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function StateBadge({ state }: { state: string }) {
  return (
    <Badge
      tone={
        ["ELIGIBLE", "APPLY_NOW", "OFFER", "HEALTHY", "STRONG"].includes(state)
          ? "green"
          : ["NOT_ELIGIBLE", "CLOSED", "REJECTED", "FAILED"].includes(state)
            ? "red"
            : ["REVIEW_REQUIRED", "PREP_THEN_APPLY", "DEGRADED"].includes(state)
              ? "amber"
              : "neutral"
      }
    >
      {pretty(state)}
    </Badge>
  );
}
export function Loading() {
  return (
    <div className="skeleton-stack" aria-label="Loading">
      <div />
      <div />
      <div />
    </div>
  );
}
export function ErrorBox({ error }: { error: Error | null }) {
  return error ? (
    <div role="alert" className="error">
      <AlertCircle size={18} />
      {error.message}
    </div>
  ) : null;
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Heading({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {action}
    </header>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label className="field-control" htmlFor={id}>
        <span>{label}</span>
      </label>
      {Children.map(children, (child) =>
        isValidElement(child) &&
        typeof child.type === "string" &&
        ["input", "textarea", "select"].includes(child.type)
          ? cloneElement(
              child as ReactElement<{
                id: string;
                "aria-describedby"?: string;
              }>,
              { id, "aria-describedby": hint ? `${id}-hint` : undefined },
            )
          : child,
      )}
      {hint && <small id={`${id}-hint`}>{hint}</small>}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    d?.showModal();
    return () => d?.close();
  }, []);
  return (
    <dialog ref={ref} onCancel={onClose} className="modal">
      <div className="modal-title">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Submit({
  busy,
  children = "Save changes",
}: {
  busy: boolean;
  children?: ReactNode;
}) {
  return (
    <button type="submit" className="button primary" disabled={busy}>
      {busy && <Loader2 size={16} className="spin" />}
      {busy ? "Saving…" : children}
    </button>
  );
}
export function useAction() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [success, setSuccess] = useState("");
  async function run(action: () => Promise<unknown>, message = "Saved") {
    setBusy(true);
    setError(null);
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Request failed"));
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, success, run };
}
export function Feedback({
  error,
  success,
}: {
  error: Error | null;
  success: string;
}) {
  return (
    <>
      <ErrorBox error={error} />
      {success && (
        <p className="success" role="status">
          {success}
        </p>
      )}
    </>
  );
}
export function JSONEditor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (s: string) => void;
}) {
  return (
    <Field
      label={label}
      hint="Structured fields are editable as JSON. Invalid values are rejected when you save."
    >
      <textarea
        className="code-input"
        rows={10}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
      />
    </Field>
  );
}
export function Form({
  onSubmit,
  children,
}: {
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}) {
  return (
    <form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(e);
      }}
    >
      {children}
    </form>
  );
}
