"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, pretty, list } from "@/lib/api";
import {
  Heading,
  ErrorBox,
  Loading,
  Empty,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
} from "./ui";
type Settings = {
  mode: string;
  auto_prepare: boolean;
  phone: string;
  software_resume_id: string | null;
  design_resume_id: string | null;
  countries: string[];
  companies: string[];
  minimum_score: number;
  daily_limit: number;
  answers: Record<string, string>;
};
type Packet = {
  name: string;
  email: string;
  phone: string;
  links: Record<string, string>;
  cover_letter: string;
  answers: Record<string, string>;
  resume_name: string | null;
  resume_sha256: string | null;
};
type Draft = {
  id: string;
  job_id: string;
  status: string;
  title: string;
  company: string;
  url: string;
  score: number;
  eligibility: { state: string; reasons: string[] };
  blockers: string[];
  packet: Packet;
  supported: boolean;
  result?: { reason: string; confirmation?: string };
};
type Desk = { settings: Settings; drafts: Draft[] };
export default function ApplicationDesk() {
  const q = useQuery({
    queryKey: ["application-desk"],
    queryFn: () => api<Desk>("/application-desk"),
    refetchInterval: (q) => (q.state.error ? false : 10000),
  });
  return (
    <>
      <Heading
        eyebrow="YOUR FACTS. YOUR APPLICATIONS."
        title="Application desk"
      >
        Prepare software and design applications, review the exact packet, and
        track confirmed outcomes.
      </Heading>
      <div className="notice">
        Local browser submission currently supports standard Lever forms. It
        pauses for challenges, unknown required questions and other sites.
        Approved applications run only while the separate local application
        runner is running.
      </div>
      <ErrorBox error={q.error} />
      {q.isPending ? (
        <Loading />
      ) : (
        q.data && (
          <>
            <SettingsForm settings={q.data.settings} />
            <div className="section-heading spaced">
              <h2>Prepared applications</h2>
              <Link href="/research">Find an opportunity</Link>
            </div>
            {q.data.drafts.length ? (
              q.data.drafts.map((d) => (
                <DraftCard
                  key={d.id + JSON.stringify(d.packet) + d.status}
                  draft={d}
                />
              ))
            ) : (
              <Empty title="Your application queue is empty">
                Choose Prepare application from a research result or
                opportunity. You can enable automatic draft preparation below.
              </Empty>
            )}
          </>
        )
      )}
      <details className="panel spaced">
        <summary>Start the local application runner</summary>
        <p>
          First, in apps/web, run <code>npx playwright install chromium</code>.
          Then from the project folder:
        </p>
        <pre>
          <code>
            {
              ".\\.venv\\Scripts\\python.exe -m careeros.apply_runner --email YOUR_ACCOUNT_EMAIL --submit --watch"
            }
          </code>
        </pre>
        <p>
          Replace YOUR_ACCOUNT_EMAIL with your CareerOS login email. Omit
          --submit to check form filling without submitting. The runner records
          ambiguous attempts as Uncertain and does not retry them automatically.
          Keep this terminal open; Ctrl+C stops it.
        </p>
      </details>
    </>
  );
}
function SettingsForm({ settings: s }: { settings: Settings }) {
  const client = useQueryClient(),
    action = useAction();
  const [answers, setAnswers] = useState(JSON.stringify(s.answers, null, 2));
  const resumes = useQuery({
    queryKey: ["resumes"],
    queryFn: () =>
      api<{ id: string; name: string; sha256?: string }[]>("/resumes"),
  });
  return (
    <details className="panel spaced">
      <summary>Application preferences & automation</summary>
      <Form
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            await send(
              "/application-settings",
              {
                mode: f.get("mode"),
                auto_prepare: !!f.get("auto_prepare"),
                phone: f.get("phone"),
                software_resume_id: f.get("software_resume_id") || null,
                design_resume_id: f.get("design_resume_id") || null,
                countries: list(String(f.get("countries"))),
                companies: list(String(f.get("companies"))),
                minimum_score: Number(f.get("minimum_score")),
                daily_limit: Number(f.get("daily_limit")),
                answers: JSON.parse(answers),
              },
              "PUT",
            );
            await client.invalidateQueries();
          }, "Preferences saved. Existing approvals need review if these facts changed.");
        }}
      >
        <div className="two-col">
          <Field label="Submission mode">
            <select name="mode" defaultValue={s.mode}>
              <option value="prepare">
                Review and approve each application
              </option>
              <option value="auto_submit">
                Automatically approve within my saved rules
              </option>
            </select>
          </Field>
          <Field label="Phone">
            <input name="phone" defaultValue={s.phone} />
          </Field>
          {(["software_resume_id", "design_resume_id"] as const).map((k) => (
            <Field
              key={k}
              label={
                k === "design_resume_id"
                  ? "Product-design resume"
                  : "Software resume"
              }
            >
              <select name={k} defaultValue={s[k] || ""}>
                <option value="">Choose a resume</option>
                {resumes.data?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                    {r.sha256 ? " · PDF uploaded" : " · upload PDF first"}
                  </option>
                ))}
              </select>
            </Field>
          ))}
          <Field label="Allowed countries">
            <input name="countries" defaultValue={s.countries.join(", ")} />
          </Field>
          <Field
            label="Companies allowed for automatic approval"
            hint="Exact company names, comma separated. Empty means none."
          >
            <input name="companies" defaultValue={s.companies.join(", ")} />
          </Field>
          <Field label="Minimum match score">
            <input
              name="minimum_score"
              type="number"
              min="0"
              max="100"
              defaultValue={s.minimum_score}
            />
          </Field>
          <Field label="Daily submission-attempt limit">
            <input
              name="daily_limit"
              type="number"
              min="1"
              max="10"
              defaultValue={s.daily_limit}
            />
          </Field>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            name="auto_prepare"
            defaultChecked={s.auto_prepare}
          />
          Automatically prepare matching drafts during discovery
        </label>
        <p className="muted">
          Automatic approval additionally requires an eligible, human-reviewed
          posting, your chosen PDF, and a portfolio for design roles. Review
          internship availability and requirements when editing the posting. No
          unknown answers are invented.
        </p>
        <Field
          label="Saved application answers"
          hint='Exact form question → your truthful answer, e.g. {"Available from": "June 2027"}. Agreements, radio buttons and checkboxes require manual completion.'
        >
          <textarea
            rows={5}
            value={answers}
            onChange={(e) => setAnswers(e.target.value)}
          />
        </Field>
        <Link href="/profile">
          Upload resumes and add your portfolio in My profile
        </Link>
        <Feedback {...action} />
        <Submit busy={action.busy}>Save application preferences</Submit>
      </Form>
    </details>
  );
}
function DraftCard({ draft: d }: { draft: Draft }) {
  const client = useQueryClient(),
    action = useAction();
  const [letter, setLetter] = useState(d.packet.cover_letter),
    [answers, setAnswers] = useState(JSON.stringify(d.packet.answers, null, 2)),
    [reviewed, setReviewed] = useState(false);
  const dirty =
    letter !== d.packet.cover_letter ||
    answers !== JSON.stringify(d.packet.answers, null, 2);
  function download() {
    const blob = new Blob([JSON.stringify(d, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `CareerOS-application-${d.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <article className="panel spaced">
      <div className="section-heading">
        <div>
          <span className="eyebrow">{d.company}</span>
          <h3>{d.title}</h3>
        </div>
        <b>{pretty(d.status)}</b>
      </div>
      <p>
        {pretty(d.eligibility.state)} · {d.score}% match
      </p>
      <p>{d.eligibility.reasons.join(". ")}</p>
      {d.result && (
        <div className="notice">
          {d.result.reason}
          {d.result.confirmation && (
            <p>Confirmation: {d.result.confirmation}</p>
          )}
        </div>
      )}
      {d.blockers.length > 0 && (
        <div className="error-box">{d.blockers.join(" ")}</div>
      )}
      {!d.supported && (
        <p className="muted">
          This site requires manual submission. Use the prepared packet and
          original application link.
        </p>
      )}
      <details open={d.status === "DRAFT"}>
        <summary>Review application packet</summary>
        <p>
          <b>Candidate:</b> {d.packet.name} · {d.packet.email} ·{" "}
          {d.packet.phone || "Phone not provided"}
        </p>
        <p>
          <b>Resume:</b> {d.packet.resume_name || "Not selected"}{" "}
          {d.packet.resume_sha256 ? "· PDF attached" : "· PDF missing"}
        </p>
        <ul>
          {Object.entries(d.packet.links).map(([k, v]) => (
            <li key={k}>
              {k}:{" "}
              <a href={v} target="_blank" rel="noreferrer">
                {v}
              </a>
            </li>
          ))}
        </ul>
        <Field label="Cover letter">
          <textarea
            rows={8}
            value={letter}
            disabled={d.status !== "DRAFT"}
            onChange={(e) => setLetter(e.target.value)}
          />
        </Field>
        <Field label="Answers to exact form questions">
          <textarea
            rows={4}
            value={answers}
            disabled={d.status !== "DRAFT"}
            onChange={(e) => setAnswers(e.target.value)}
          />
        </Field>
        {d.status === "DRAFT" && (
          <>
            <button
              className="button"
              disabled={action.busy || !dirty}
              onClick={() =>
                action.run(async () => {
                  await send(
                    `/application-desk/${d.id}`,
                    { cover_letter: letter, answers: JSON.parse(answers) },
                    "PUT",
                  );
                  await client.invalidateQueries();
                }, "Draft saved")
              }
            >
              Save draft changes
            </button>
            <label className="checkbox spaced">
              <input
                type="checkbox"
                checked={reviewed}
                onChange={(e) => setReviewed(e.target.checked)}
              />
              I reviewed this exact packet, the resume, eligibility and
              internship availability. I authorize its submission.
            </label>
          </>
        )}
      </details>
      <div className="form-actions">
        <a className="button" href={d.url} target="_blank" rel="noreferrer">
          Open employer application
        </a>
        <button className="button" onClick={download}>
          Download packet
        </button>
        {d.status === "DRAFT" && (
          <button
            className="button primary"
            disabled={
              action.busy || !reviewed || dirty || d.blockers.length > 0
            }
            onClick={() =>
              action.run(async () => {
                await send(`/application-desk/${d.id}/approve`, { reviewed });
                await client.invalidateQueries();
              }, "Approved. The local runner can now process this application.")
            }
          >
            Approve this application
          </button>
        )}
        {!["SUBMITTED", "SUBMITTING", "UNCERTAIN"].includes(d.status) && (
          <>
            <button
              className="button"
              onClick={() =>
                action.run(async () => {
                  await send("/application-desk/prepare", { job_id: d.job_id });
                  await client.invalidateQueries();
                })
              }
            >
              Prepare again
            </button>
            <button
              className="text-button"
              onClick={() =>
                action.run(async () => {
                  await send(`/application-desk/${d.id}/cancel`, {});
                  await client.invalidateQueries();
                })
              }
            >
              Cancel
            </button>
          </>
        )}
      </div>
      <Feedback {...action} />
    </article>
  );
}
