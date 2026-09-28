"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="p-8 text-center space-y-3">
      <h2 className="text-lg font-semibold">Something went wrong on this page</h2>
      <p className="text-sm text-secondary">{error.message}</p>
      <button onClick={reset} className="underline">Try again</button>
    </div>
  );
}
