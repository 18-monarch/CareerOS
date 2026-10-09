"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send } from "@/lib/api";
import { ErrorBox, Feedback, useAction } from "./ui";

type Discovery = {
  enabled: boolean;
  scheduler_enabled: boolean;
  status: string;
  last_finished: string | null;
  next_run: string | null;
  interval_hours: number;
  error: string | null;
  summary: {
    added?: number;
    live_opportunities?: number;
    fetched?: number;
    skipped?: number;
    ready_to_apply?: number;
    review_required?: number;
    research?: {
      status: string;
      leads?: number;
      verified?: number;
      errors: number;
    };
  };
  catalog: { company: string; url: string }[];
};
const when = (value: string | null) =>
  value
    ? new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString()
    : "Not yet";

export default function DiscoveryPanel({
  compact = false,
}: {
  compact?: boolean;
}) {
  const client = useQueryClient(),
    action = useAction();
  const completed = useRef<string | null>(null);
  const { data, error } = useQuery({
    queryKey: ["discovery"],
    queryFn: () => api<Discovery>("/discovery"),
    refetchInterval: (q) => (q.state.error ? false : 5000),
  });
  useEffect(() => {
    if (data?.last_finished && completed.current !== data.last_finished) {
      completed.current = data.last_finished;
      void client.invalidateQueries({
        predicate: (q) => q.queryKey[0] !== "discovery",
      });
    }
  }, [data?.last_finished, client]);
  if (error) return <ErrorBox error={error} />;
  if (!data) return <p className="muted">Checking automatic discovery…</p>;
  const running = data.status === "RUNNING";
  const label = !data.enabled
    ? "Paused"
    : running
      ? "Checking the internet"
      : data.status === "FAILED"
        ? "Check failed"
        : data.status === "DEGRADED"
          ? "Some sources need attention"
          : data.last_finished
            ? "Automatic discovery is on"
            : "Your first check is queued";
  return (
    <section className="panel spaced" aria-label="Automatic discovery">
      <div className="section-heading">
        <div>
          <h2>{label}</h2>
          <p>
            Software, product design and other early-career roles from{" "}
            {data.catalog.length} public company boards. Checks every{" "}
            {data.interval_hours} hours while CareerOS is running.
          </p>
        </div>
        {compact && <Link href="/sources">Manage discovery</Link>}
      </div>
      {!data.scheduler_enabled && (
        <p className="error-text">
          The background checker is disabled in this installation. A scheduled
          discovery worker is required.
        </p>
      )}
      <p>
        {data.last_finished
          ? `Last check: ${when(data.last_finished)} · ${data.summary.added ?? 0} new · ${data.summary.live_opportunities ?? 0} live opportunities`
          : "Starter sources are connected for you. Your first check should start within 30 seconds; it may take a few minutes."}
      </p>
      {data.enabled && data.next_run && (
        <p className="muted">
          Next check: {when(data.next_run)}. Missed checks run when the backend
          starts again.
        </p>
      )}
      {data.error && <p className="error-text">{data.error}</p>}
      {data.summary.research &&
        data.summary.research.status !== "NOT_CONFIGURED" && (
          <p>
            Web search: {data.summary.research.status.toLowerCase()} ·{" "}
            {data.summary.research.leads ?? 0} leads ·{" "}
            {data.summary.research.verified ?? 0} verified postings ·{" "}
            {data.summary.research.errors} check errors. See Internship brief.
          </p>
        )}
      {!compact && (
        <>
          <p>
            {data.summary.fetched ?? 0} postings checked ·{" "}
            {data.summary.skipped ?? 0} outside the starter-feed focus ·{" "}
            {data.summary.ready_to_apply ?? 0} ready to apply ·{" "}
            {data.summary.review_required ?? 0} need review
          </p>
          <div className="form-actions">
            <button
              className="button primary"
              disabled={
                action.busy ||
                running ||
                !data.enabled ||
                !data.scheduler_enabled
              }
              onClick={() =>
                action.run(async () => {
                  await send("/discovery/refresh", {});
                  await client.invalidateQueries({ queryKey: ["discovery"] });
                }, "Check queued. Results appear here automatically.")
              }
            >
              Check now
            </button>
            <button
              className="button"
              disabled={action.busy}
              onClick={() =>
                action.run(
                  async () => {
                    await send("/discovery", { enabled: !data.enabled }, "PUT");
                    await client.invalidateQueries({ queryKey: ["discovery"] });
                  },
                  data.enabled
                    ? "Discovery paused after the current source finishes."
                    : "Automatic discovery resumed.",
                )
              }
            >
              {data.enabled ? "Pause discovery" : "Resume discovery"}
            </button>
          </div>
          <Feedback {...action} />
          <details className="spaced">
            <summary>Included company boards and coverage</summary>
            <ul>
              {data.catalog.map((b) => (
                <li key={b.url}>
                  <a href={b.url} target="_blank" rel="noreferrer">
                    {b.company}
                  </a>
                </li>
              ))}
            </ul>
            <p>
              These boards run without API keys. Connect broad web search in the
              Internship brief to discover additional sources. Roles may be
              international; location, graduation year and authorization still
              need checking. Unknown requirements never become confirmed facts
              automatically.
            </p>
            <p>
              Discovery generates in-app reminders, daily digests and weekly
              summaries. Email requires a configured provider. Pause stops
              future checks; imported jobs remain available.
            </p>
          </details>
        </>
      )}
    </section>
  );
}
