"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, date, pretty, statuses, localDateTime } from "@/lib/api";
import { Application, Pipeline } from "@/lib/types";
import {
  Heading,
  Loading,
  ErrorBox,
  Empty,
  StateBadge,
  Modal,
  Form,
  Field,
  Submit,
  Feedback,
  useAction,
} from "./ui";
export default function Applications() {
  const [selected, setSelected] = useState<Application | null>(null);
  const { data, error, isPending } = useQuery({
    queryKey: ["applications"],
    queryFn: () => api<Application[]>("/applications"),
  });
  const metrics = useQuery({
    queryKey: ["metrics"],
    queryFn: () => api<Pipeline>("/applications/metrics"),
  });
  return (
    <>
      <Heading title="Application pipeline" eyebrow="KEEP THE MOMENTUM">
        Every stage recorded. Every next step within reach.
      </Heading>
      {metrics.data && (
        <>
          <div className="stats-grid">
            {["APPLIED", "OA_RECEIVED", "INTERVIEW", "OFFER"].map((s) => (
              <div className="stat" key={s}>
                <span>{pretty(s)}</span>
                <b>{metrics.data.counts[s]}</b>
              </div>
            ))}
          </div>
          <div className="notice">{metrics.data.recommendation}</div>
          <details className="panel compact">
            <summary>Conversion rates and definitions</summary>
            <div className="metrics-list">
              {Object.entries(metrics.data.rates).map(([k, v]) => (
                <p key={k}>
                  {pretty(k)}{" "}
                  <b>{v === null ? "Insufficient data" : `${v}%`}</b>
                </p>
              ))}
            </div>
            <small>{metrics.data.note}</small>
          </details>
        </>
      )}
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Opportunity</th>
                <th>Stage</th>
                <th>Applied</th>
                <th>Next action</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id}>
                  <td>
                    <b>{a.company_name}</b>
                    <span className="cell-sub">
                      {a.title}
                      {a.is_demo ? " · Demo" : ""}
                    </span>
                  </td>
                  <td>
                    <StateBadge state={a.status} />
                  </td>
                  <td>{date(a.applied_at)}</td>
                  <td>
                    {a.oa_deadline
                      ? `OA: ${date(a.oa_deadline)}`
                      : a.interview_dates[0]
                        ? `Interview: ${date(a.interview_dates[0])}`
                        : date(a.deadline)}
                  </td>
                  <td>
                    <button
                      className="button small"
                      onClick={() => setSelected(a)}
                    >
                      Update
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title="Make your first move">
          Save an opportunity to start tracking it here.
        </Empty>
      )}
      {selected && (
        <ApplicationEditor app={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
function ApplicationEditor({
  app,
  onClose,
}: {
  app: Application;
  onClose: () => void;
}) {
  const client = useQueryClient(),
    action = useAction();
  const resumes = useQuery({
    queryKey: ["resumes"],
    queryFn: () => api<{ id: string; name: string }[]>("/resumes"),
  });
  return (
    <Modal title={`${app.company_name} · Application`} onClose={onClose}>
      <Form
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            const fields: Record<string, unknown> = { job_id: app.job_id };
            for (const key of [
              "status",
              "notes",
              "referral",
              "recruiter",
              "result",
              "rejection_stage",
              "rejection_reason",
            ])
              fields[key] = String(f.get(key) || "");
            fields.resume_id = f.get("resume_id") || null;
            fields.oa_deadline = f.get("oa_deadline")
              ? new Date(String(f.get("oa_deadline"))).toISOString()
              : null;
            fields.interview_dates = String(f.get("interview_dates") || "")
              .split("\n")
              .filter(Boolean)
              .map((s) => new Date(s).toISOString());
            await send(`/applications/${app.id}`, fields, "PATCH");
            await client.invalidateQueries();
            onClose();
          });
        }}
      >
        <div className="two-col">
          <Field label="Status">
            <select name="status" defaultValue={app.status}>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {pretty(s)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Resume used">
            <select name="resume_id" defaultValue={app.resume_id || ""}>
              <option value="">Not recorded</option>
              {resumes.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Referral">
            <input name="referral" defaultValue={app.referral} />
          </Field>
          <Field label="Recruiter">
            <input name="recruiter" defaultValue={app.recruiter} />
          </Field>
          <Field label="OA deadline (local time)">
            <input
              type="datetime-local"
              name="oa_deadline"
              defaultValue={localDateTime(app.oa_deadline)}
            />
          </Field>
          <Field
            label="Interview dates"
            hint="One ISO date/time per line; include timezone, e.g. 2027-01-20T14:00:00+05:30"
          >
            <textarea
              name="interview_dates"
              defaultValue={app.interview_dates.join("\n")}
            />
          </Field>
        </div>
        <Field label="Notes">
          <textarea name="notes" rows={3} defaultValue={app.notes} />
        </Field>
        <div className="two-col">
          <Field label="Result">
            <input name="result" defaultValue={app.result} />
          </Field>
          <Field label="Rejection stage, if known">
            <input name="rejection_stage" defaultValue={app.rejection_stage} />
          </Field>
        </div>
        <Field label="Rejection reason, if known">
          <textarea
            name="rejection_reason"
            defaultValue={app.rejection_reason}
          />
        </Field>
        <Feedback {...action} />
        <Submit busy={action.busy}>Update application</Submit>
      </Form>
      <h3>Event history</h3>
      <ol className="timeline">
        {app.events.map((e) => (
          <li key={e.id}>
            <b>{pretty(e.status)}</b>
            <small>{date(e.created_at)}</small>
            {e.note && <p>{e.note}</p>}
          </li>
        ))}
      </ol>
    </Modal>
  );
}
