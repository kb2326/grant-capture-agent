import type { ApiError } from "../api";

export function ErrorBox({ e }: { e: ApiError | null }) {
  if (!e) return null;
  return (
    <div className="error" role="alert">
      <strong>{e.error}</strong>
      <div>{e.hint}</div>
    </div>
  );
}
