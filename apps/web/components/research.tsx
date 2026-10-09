"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, date, pretty } from "@/lib/api";
import {
  Heading,
  ErrorBox,
  Loading,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
  StateBadge,
  Empty,
} from "./ui";
import DiscoveryPanel from "./discovery";
import JobDetail from "./job-detail";

type Brief = {
  id: string;
  title: string;
  company: string;
  country: string;
  score: number;
  why: string;
  next_step: string;
  projects: string[];
  eligibility: { state: string; reasons: string[] };
  classification: string;
  application_url: string;
  deadline: string | null;
  first_discovered: string;
  posted_at: string | null;
  last_checked: string;
};
type Lead = {
  id: string;
  url: string;
  title: string;
  status: string;
  snippet?: string;
  verification_note?: string;
  job_id?: string;
  first_discovered: string;
};
type Research = {
  search_configured: boolean;
  query_limit: number;
  queries: { category: string; query: string }[];
  groups: { id: string; label: string; items: Brief[] }[];
  leads: Lead[];
};
export default function Research() {
  const client = useQueryClient(),
    action = useAction();
  const [category, setCategory] = useState(""),
    [selected, setSelected] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["research"],
    queryFn: () => api<Research>("/research"),
    refetchInterval: (q) => (q.state.error ? false : 15000),
  });
  const data = query.data;
  return (
    <>
      <Heading
        eyebrow="RESEARCH → DECISION → ACTION"
        title="Your internship brief"
      >
        Software and product design, organized around your profile. Every
        recommendation keeps its source.
      </Heading>
      <DiscoveryPanel compact />
      <ErrorBox error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="notice">
              <b>
                {data.search_configured
                  ? "Broad web search connected"
                  : "Company feeds active · broad web search not connected"}
              </b>
              <p>
                {data.search_configured
                  ? `Up to ${data.query_limit} searches per discovery cycle. Public ATS postings are checked; other results remain leads to review.`
                  : "The free employer feeds work without a key. Add BRAVE_SEARCH_API_KEY to your backend .env and restart to search beyond connected boards. You can also inspect a posting URL below."}
              </p>
            </div>
            <div className="filter-bar">
              <Field label="Career category">
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">All career categories</option>
                  {data.groups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.label} ({g.items.length})
                    </option>
                  ))}
                </select>
              </Field>
              <Link className="button" href="/profile">
                Set my interests
              </Link>
              <Link className="button" href="/application-desk">
                Application desk
              </Link>
            </div>
            {data.groups
              .filter((g) => !category || g.id === category)
              .map((g) => (
                <section className="spaced" key={g.id}>
                  <div className="section-heading">
                    <h2>{g.label}</h2>
                    <span>{g.items.length} active matches</span>
                  </div>
                  {g.items.length ? (
                    <div className="opportunity-grid">
                      {g.items.slice(0, 6).map((j) => (
                        <article className="panel" key={j.id}>
                          <span className="eyebrow">
                            {j.company} · {j.country}
                          </span>
                          <h3>
                            <button
                              className="job-title"
                              onClick={() => setSelected(j.id)}
                            >
                              {j.title}
                            </button>
                          </h3>
                          <StateBadge state={j.eligibility.state} />
                          <p>{j.why}</p>
                          {j.projects.length > 0 && (
                            <p>
                              <b>Relevant evidence:</b> {j.projects.join(", ")}
                            </p>
                          )}
                          <p>
                            <b>Next action:</b> {j.next_step}
                          </p>
                          <small>
                            Discovered {date(j.first_discovered)} · Posted{" "}
                            {date(j.posted_at)} · Checked {date(j.last_checked)}{" "}
                            · Deadline {date(j.deadline)}
                          </small>
                          <p className="muted">
                            {j.eligibility.reasons.join(". ")}
                          </p>
                          <div className="form-actions">
                            <button
                              className="button"
                              onClick={() => setSelected(j.id)}
                            >
                              Review opportunity
                            </button>
                            <button
                              className="button primary"
                              disabled={action.busy}
                              onClick={() =>
                                action.run(async () => {
                                  await send("/application-desk/prepare", {
                                    job_id: j.id,
                                  });
                                  await client.invalidateQueries({
                                    queryKey: ["application-desk"],
                                  });
                                }, "Draft prepared. Open Application desk to review it.")
                              }
                            >
                              Prepare application
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="muted">
                      No active matches found in this category yet. This does
                      not mean no openings exist elsewhere.
                    </p>
                  )}
                </section>
              ))}
            <Feedback {...action} />
            <section className="panel spaced">
              <h2>Inspect an internship link</h2>
              <p>
                Greenhouse, Lever and Ashby postings can be verified
                automatically. Other links are saved as leads for you to check.
              </p>
              <Form
                onSubmit={(e) => {
                  const form = e.currentTarget;
                  const f = new FormData(form);
                  action.run(async () => {
                    await send("/research/leads", { url: f.get("url") });
                    form.reset();
                    await client.invalidateQueries();
                  }, "Posting checked; see the research inbox below.");
                }}
              >
                <Field label="Original posting URL">
                  <input
                    type="url"
                    name="url"
                    required
                    placeholder="https://jobs.lever.co/company/posting-id"
                  />
                </Field>
                <Submit busy={action.busy}>Inspect posting</Submit>
              </Form>
            </section>
            <section className="spaced">
              <h2>Research inbox</h2>
              <p className="muted">
                Search snippets are leads, not proof of eligibility. Previously
                discovered leads keep their original discovery date.
              </p>
              {data.leads.filter((l) => l.status !== "DISMISSED").length ? (
                data.leads
                  .filter((l) => l.status !== "DISMISSED")
                  .map((l) => (
                    <article className="panel spaced" key={l.id}>
                      <div className="section-heading">
                        <h3>
                          <a href={l.url} target="_blank" rel="noreferrer">
                            {l.title}
                          </a>
                        </h3>
                        <span>{pretty(l.status)}</span>
                      </div>
                      <p>{l.snippet}</p>
                      <p>{l.verification_note}</p>
                      <small>First discovered {date(l.first_discovered)}</small>
                      <div className="form-actions">
                        {l.job_id && (
                          <button
                            className="button"
                            onClick={() => setSelected(l.job_id!)}
                          >
                            View matched opportunity
                          </button>
                        )}
                        <button
                          className="button"
                          disabled={action.busy}
                          onClick={() =>
                            action.run(async () => {
                              await send(`/research/leads/${l.id}/verify`, {});
                              await client.invalidateQueries();
                            })
                          }
                        >
                          Check again
                        </button>
                        <button
                          className="text-button"
                          onClick={() =>
                            action.run(async () => {
                              await api(`/research/leads/${l.id}`, {
                                method: "DELETE",
                              });
                              await client.invalidateQueries();
                            })
                          }
                        >
                          Dismiss
                        </button>
                      </div>
                    </article>
                  ))
              ) : (
                <Empty title="No research leads yet">
                  Connected board results appear in your categories. Web-search
                  leads appear after a configured search runs.
                </Empty>
              )}
            </section>
            <details className="panel spaced">
              <summary>Search plan</summary>
              <ul>
                {data.queries.map((q) => (
                  <li key={q.category}>{q.query}</li>
                ))}
              </ul>
              <p>
                Search sends these public role/location queries to the provider.
                Your resume, email, and application answers are not included.
              </p>
            </details>
          </>
        )
      )}
      {selected && (
        <JobDetail id={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
