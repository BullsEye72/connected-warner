"use client";

import { useFormStatus } from "react-dom";

export function SubmitButton({ children, pendingText = "En cours…", className = "primary-button" }: {
  children: React.ReactNode;
  pendingText?: string;
  className?: string;
}) {
  const { pending } = useFormStatus();
  return <button type="submit" className={className} disabled={pending}>{pending ? pendingText : children}</button>;
}
