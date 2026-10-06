"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="empty">
      <h1>This view could not load</h1>
      <p>Your saved data is stored on the server.</p>
      <button className="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
