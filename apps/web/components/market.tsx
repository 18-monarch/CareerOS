"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, date, pretty, list } from "@/lib/api";
import {
  Heading,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
  Empty,
  ErrorBox,
  Badge,
  JSONEditor,
} from "./ui";
interface MarketReport {
  id: string;
  market: string;
  period: string;
  source_references: string[];
  important_skills: string[];
  [key: string]: unknown;
}
interface Visa {
  id: string;
  country: string;
  last_verified: string;
  stale: boolean;
  source_url: string;
  notes: string;
  [key: string]: unknown;
}
const markets = [
  "India",
  "USA",
  "Germany",
  "Netherlands",
  "Ireland",
  "UK",
  "Singapore",
  "Australia",
  "UAE",
];
const trendFields = [
  "software_hiring_trend",
  "backend_trend",
  "ai_trend",
  "data_trend",
  "cloud_platform_trend",
  "cybersecurity_trend",
  "fresher_trend",
  "salary_observations",
  "visa_changes",
  "major_hiring_expansions",
  "major_layoffs",
];
export default function Market() {
  const client = useQueryClient(),
    action = useAction();
  const [visaJSON, setVisaJSON] = useState(
    JSON.stringify(
      {
        visa_sponsorship_available: null,
        work_authorization_required: null,
        minimum_salary_threshold: null,
        salary_currency: null,
        experience_requirement: "",
        graduate_eligibility: "",
        language_requirement: "",
        recognized_employer_requirement: "",
        notes: "",
      },
      null,
      2,
    ),
  );
  const reports = useQuery({
    queryKey: ["market"],
    queryFn: () => api<MarketReport[]>("/market-reports"),
  });
  const visas = useQuery({
    queryKey: ["visas"],
    queryFn: () => api<Visa[]>("/visa-rules"),
  });
  return (
    <>
      <Heading
        title="Context for your next move"
        eyebrow="MARKET & INTERNATIONAL"
      >
        Keep sourced observations. Recheck assumptions before making decisions.
      </Heading>
      <Feedback {...action} />
      <ErrorBox error={reports.error || visas.error} />
      <div className="opportunity-grid">
        {reports.data?.map((r) => (
          <section className="panel" key={r.id}>
            <div className="inline">
              <Badge>{r.market}</Badge>
              <span>{r.period}</span>
            </div>
            <h2>{r.market} · market notes</h2>
            {trendFields
              .filter((k) => r[k])
              .map((k) => (
                <div key={k}>
                  <h3>{pretty(k)}</h3>
                  <p>{String(r[k])}</p>
                </div>
              ))}
            <p>Skills: {r.important_skills.join(", ") || "Not recorded"}</p>
            {r.source_references.map((u, i) => (
              <p key={u}>
                <a href={u} target="_blank" rel="noreferrer">
                  Source {i + 1}
                </a>
              </p>
            ))}
            <button
              className="text-button danger"
              onClick={() =>
                action.run(async () => {
                  await api(`/market-reports/${r.id}`, { method: "DELETE" });
                  await client.invalidateQueries();
                })
              }
            >
              Remove report
            </button>
          </section>
        ))}
      </div>
      {reports.data?.length === 0 && (
        <Empty title="No market claims without sources">
          Add your first report from trusted references. CareerOS does not
          invent hiring or salary statistics.
        </Empty>
      )}
      <details className="panel spaced">
        <summary>Add monthly market notes</summary>
        <Form
          onSubmit={(e) => {
            const f = new FormData(e.currentTarget);
            action.run(async () => {
              await send("/market-reports", {
                market: f.get("market"),
                period: f.get("period"),
                ...Object.fromEntries(
                  trendFields.map((k) => [k, String(f.get(k) || "")]),
                ),
                important_skills: list(String(f.get("important_skills"))),
                source_references: String(f.get("source_references"))
                  .split("\n")
                  .filter(Boolean),
              });
              await client.invalidateQueries();
            });
          }}
        >
          <div className="two-col">
            <Field label="Market">
              <select name="market">
                {markets.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </Field>
            <Field label="Report month">
              <input type="month" name="period" required />
            </Field>
            {trendFields.map((k) => (
              <Field key={k} label={pretty(k)}>
                <textarea name={k} rows={2} />
              </Field>
            ))}
          </div>
          <Field label="Important skills (comma separated)">
            <input name="important_skills" />
          </Field>
          <Field label="Source URLs (one per line)">
            <textarea name="source_references" required />
          </Field>
          <Submit busy={action.busy}>Save sourced report</Submit>
        </Form>
      </details>
      <div className="section-heading">
        <h2>International requirements notebook</h2>
      </div>
      <p className="notice">
        These notes support research; they do not establish visa eligibility.
        Records older than 90 days are marked stale.
      </p>
      <div className="opportunity-grid">
        {visas.data?.map((v) => (
          <section className="panel" key={v.id}>
            <div className="inline">
              <h3>{v.country}</h3>
              <Badge tone={v.stale ? "amber" : "neutral"}>
                {v.stale ? "Needs re-verification" : "Recently verified"}
              </Badge>
            </div>
            <p>Last checked {date(v.last_verified)}</p>
            <p>{v.notes}</p>
            <details>
              <summary>All requirements</summary>
              <pre>{JSON.stringify(v, null, 2)}</pre>
            </details>
            <a href={v.source_url} target="_blank" rel="noreferrer">
              Official reference
            </a>
            <button
              className="text-button danger"
              onClick={() =>
                action.run(async () => {
                  await api(`/visa-rules/${v.id}`, { method: "DELETE" });
                  await client.invalidateQueries();
                })
              }
            >
              Remove note
            </button>
          </section>
        ))}
      </div>
      <details className="panel spaced">
        <summary>Add international requirement</summary>
        <Form
          onSubmit={(e) => {
            const f = new FormData(e.currentTarget);
            action.run(async () => {
              await send("/visa-rules", {
                country: f.get("country"),
                last_verified: new Date(
                  String(f.get("last_verified")),
                ).toISOString(),
                source_url: f.get("source_url"),
                ...JSON.parse(visaJSON),
              });
              await client.invalidateQueries();
            });
          }}
        >
          <div className="two-col">
            <Field label="Country">
              <select name="country">
                {markets.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </Field>
            <Field label="Last verified">
              <input type="date" name="last_verified" required />
            </Field>
          </div>
          <Field label="Official reference URL">
            <input type="url" name="source_url" required />
          </Field>
          <JSONEditor
            label="Requirements and notes"
            value={visaJSON}
            onChange={setVisaJSON}
          />
          <Submit busy={action.busy}>Save requirement note</Submit>
        </Form>
      </details>
    </>
  );
}
