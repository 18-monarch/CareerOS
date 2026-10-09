"use client";
import Link from "next/link";
import { useState } from "react";
import JobForm from "./job-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { api, send, pretty, date } from "@/lib/api";
import { Job } from "@/lib/types";
import {
  Badge,
  StateBadge,
  Loading,
  ErrorBox,
  Modal,
  useAction,
  Feedback,
} from "./ui";
export default function JobDetail({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const {
    data: job,
    error,
    isPending,
  } = useQuery({
    queryKey: ["job", id],
    queryFn: () => api<Job>(`/jobs/${id}`),
  });
  const action = useAction();
  const [editing, setEditing] = useState(false);
  if (editing && job)
    return (
      <JobForm
        editId={job.id}
        initial={job as unknown as Record<string, unknown>}
        onClose={() => setEditing(false)}
        onSaved={() => {
          setEditing(false);
          client.invalidateQueries();
        }}
      />
    );
  return (
    <Modal title="Opportunity details" onClose={onClose}>
      {isPending ? (
        <Loading />
      ) : job ? (
        <>
          <div className="inline">
            <span className="eyebrow">{job.company_name}</span>
            {job.is_demo && <Badge>Demo · not a live vacancy</Badge>}
          </div>
          {!job.is_demo && job.is_active && (
            <div className="form-actions">
              <button
                className="button primary"
                disabled={action.busy}
                onClick={() =>
                  action.run(async () => {
                    await send("/application-desk/prepare", { job_id: job.id });
                    await client.invalidateQueries({
                      queryKey: ["application-desk"],
                    });
                  }, "Draft prepared. Open Application desk to review it.")
                }
              >
                Prepare application
              </button>
              <Link href="/application-desk">Application desk</Link>
            </div>
          )}
          <h2 className="detail-title">{job.title}</h2>
          <p className="muted">
            {job.locations.join(", ")} · {job.country} · Closes{" "}
            {date(job.application_deadline)}
          </p>
          <div className="detail-summary">
            <div className="score large">
              <b>{job.match.score}%</b>
              <span>explainable match</span>
            </div>
            <div>
              <StateBadge state={job.match.eligibility.state} />
              <p>{job.match.eligibility.reasons.join(". ")}</p>
            </div>
          </div>
          {job.match.eligibility.checks.length > 0 && (
            <div className="notice">
              <b>Checked against your profile</b>
              <ul>
                {job.match.eligibility.checks.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="two-col">
            <div>
              <h3>What you bring</h3>
              <div className="skill-chips">
                {job.match.strong_matches.map((s) => (
                  <Badge key={s} tone="green">
                    {s}
                  </Badge>
                ))}
              </div>
              <h3>Missing required skills</h3>
              <p>
                {job.match.missing_required.join(", ") ||
                  "None in the structured posting"}
              </p>
              <h3>Preferred, not mandatory</h3>
              <p>{job.match.missing_preferred.join(", ") || "None missing"}</p>
              <h3>Project evidence</h3>
              <p>
                {job.match.project_evidence.join(", ") ||
                  "No verified project evidence linked yet."}
              </p>
            </div>
            <div>
              <h3>How the score adds up</h3>
              {Object.entries(job.match.breakdown).map(([key, v]) => (
                <div className="score-row" key={key}>
                  <span>{pretty(key)}</span>
                  <span>
                    {v.points} / {v.weight}
                  </span>
                  <progress max={v.weight || 1} value={v.points} />
                </div>
              ))}
              {job.match.score_suppressed && (
                <p className="footnote">
                  Score set to 0 because a hard rule failed or this job is
                  closed. Raw factors above are shown for transparency.
                </p>
              )}
            </div>
          </div>
          {job.match.preparation.length > 0 && (
            <>
              <h3>Before you apply</h3>
              <ul>
                {job.match.preparation.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </>
          )}
          <h3>Job description</h3>
          <p className="pre-wrap">{job.description}</p>
          {job.stipend && <p>{job.stipend}</p>}
          <details>
            <summary>Requirements and extraction evidence</summary>
            <pre>
              {JSON.stringify(
                { requirements: job.requirements, provenance: job.provenance },
                null,
                2,
              )}
            </pre>
          </details>
          <details>
            <summary>Source references</summary>
            {job.occurrences?.map((o) => (
              <p key={o.source_id + o.external_id}>
                {o.external_id} · Last seen {date(o.last_seen_at)} ·{" "}
                {o.is_active ? "Listed" : "No longer listed"}{" "}
                {o.source_url && (
                  <a href={o.source_url} target="_blank" rel="noreferrer">
                    Original source
                  </a>
                )}
              </p>
            ))}
          </details>
          <Feedback {...action} />
          <div className="form-actions">
            <button className="button" onClick={() => setEditing(true)}>
              Review / edit facts
            </button>
            <button
              className="button primary"
              disabled={action.busy || !!job.application}
              onClick={() =>
                action.run(async () => {
                  await send("/applications", {
                    job_id: job.id,
                    status: "SAVED",
                  });
                  await client.invalidateQueries();
                }, "Saved to applications")
              }
            >
              {job.application
                ? `Tracked: ${pretty(job.application.status)}`
                : "Save opportunity"}
            </button>
            {job.application_url && !job.is_demo && (
              <a
                className="button"
                href={job.application_url}
                target="_blank"
                rel="noreferrer"
              >
                Visit application page
                <ExternalLink size={15} />
              </a>
            )}
            <button
              className="button quiet"
              disabled={
                action.busy || (!job.is_active && !job.manually_archived)
              }
              onClick={() =>
                action.run(
                  async () => {
                    await api(
                      `/jobs/${job.id}/${job.manually_archived ? "restore" : "archive"}`,
                      { method: "PATCH" },
                    );
                    await client.invalidateQueries();
                  },
                  job.manually_archived
                    ? "Opportunity restored; eligibility reevaluated"
                    : "Opportunity archived",
                )
              }
            >
              {job.manually_archived ? "Restore" : "Archive"}
            </button>
          </div>
        </>
      ) : (
        <ErrorBox error={error} />
      )}
    </Modal>
  );
}
