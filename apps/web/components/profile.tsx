"use client";
import { careerCategories } from "@/lib/categories";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, list, pretty } from "@/lib/api";
import { Profile as ProfileData, Skill } from "@/lib/types";
import {
  Heading,
  Loading,
  ErrorBox,
  Field,
  Form,
  Submit,
  JSONEditor,
  Feedback,
  useAction,
} from "./ui";
export default function Profile() {
  const { data, error, isPending } = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<ProfileData>("/profile"),
  });
  return (
    <>
      <Heading title="Your career profile" eyebrow="THE SOURCE OF TRUTH">
        Keep this honest. Your recommendations depend on it.
      </Heading>
      <ErrorBox error={error} />
      {isPending ? <Loading /> : data && <ProfileForm profile={data} />}
      <Skills />
      <Resumes />
      <PasswordForm />
    </>
  );
}
function ProfileForm({ profile: p }: { profile: ProfileData }) {
  const client = useQueryClient(),
    action = useAction();
  const [links, setLinks] = useState(
      JSON.stringify(p.external_profiles, null, 2),
    ),
    [weights, setWeights] = useState(
      JSON.stringify(p.preferences.weights, null, 2),
    );
  return (
    <section className="panel">
      <h2>Education & preferences</h2>
      <Form
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            const data: Record<string, unknown> = {};
            for (const key of ["name", "university", "degree", "branch"])
              data[key] = f.get(key);
            for (const key of [
              "graduation_year",
              "cgpa",
              "semester",
              "experience_years",
            ])
              data[key] = f.get(key) === "" ? null : Number(f.get(key));
            const externalProfiles = JSON.parse(links);
            if (f.get("portfolio"))
              externalProfiles.portfolio = String(f.get("portfolio"));
            else delete externalProfiles.portfolio;
            await send(
              "/profile",
              {
                ...data,
                work_authorizations: list(String(f.get("work_authorizations"))),
                external_profiles: externalProfiles,
                preferences: {
                  ...p.preferences,
                  career_categories: f.getAll("career_categories"),
                  target_roles: list(String(f.get("target_roles"))),
                  countries: list(String(f.get("countries"))),
                  watchlist: list(String(f.get("watchlist"))),
                  preferred_companies: list(
                    String(f.get("preferred_companies")),
                  ),
                  deadline_days: list(String(f.get("deadline_days"))).map(
                    Number,
                  ),
                  email_enabled: !!f.get("email_enabled"),
                  weekly_plan: String(f.get("weekly_plan")),
                  weights: JSON.parse(weights),
                },
              },
              "PUT",
            );
            await client.invalidateQueries();
          });
        }}
      >
        <div className="filter-grid">
          {(
            [
              "name",
              "university",
              "degree",
              "branch",
              "graduation_year",
              "cgpa",
              "semester",
              "experience_years",
            ] as const
          ).map((k) => (
            <Field label={pretty(k)} key={k}>
              <input
                name={k}
                defaultValue={p[k] ?? ""}
                type={
                  [
                    "graduation_year",
                    "cgpa",
                    "semester",
                    "experience_years",
                  ].includes(k)
                    ? "number"
                    : "text"
                }
                step="any"
                required={k === "name"}
              />
            </Field>
          ))}
        </div>
        <div className="two-col">
          {[
            ["target_roles", p.preferences.target_roles],
            ["countries", p.preferences.countries],
            ["watchlist", p.preferences.watchlist],
            ["preferred_companies", p.preferences.preferred_companies],
            ["work_authorizations", p.work_authorizations],
            ["deadline_days", p.preferences.deadline_days],
          ].map(([k, v]) => (
            <Field
              key={String(k)}
              label={pretty(String(k))}
              hint={
                k === "work_authorizations"
                  ? "Only countries where you already have authorization to work."
                  : "Comma separated; put your highest priority first."
              }
            >
              <input
                name={String(k)}
                defaultValue={(v as (string | number)[]).join(", ")}
              />
            </Field>
          ))}
        </div>
        <fieldset className="panel spaced">
          <legend>Career interests</legend>
          <div className="filter-grid">
            {Object.entries(careerCategories).map(([k, v]) => (
              <label className="checkbox" key={k}>
                <input
                  type="checkbox"
                  name="career_categories"
                  value={k}
                  defaultChecked={(
                    p.preferences.career_categories || []
                  ).includes(k)}
                />
                {v}
              </label>
            ))}
          </div>
        </fieldset>
        <Field
          label="Portfolio URL"
          hint="Used for product-design applications. Add your actual portfolio or case studies."
        >
          <input
            type="url"
            name="portfolio"
            defaultValue={p.external_profiles.portfolio || ""}
            placeholder="https://your-portfolio.example"
          />
        </Field>
        <Field label="This week’s plan">
          <textarea
            name="weekly_plan"
            rows={3}
            defaultValue={p.preferences.weekly_plan}
          />
        </Field>
        <label className="checkbox">
          <input
            type="checkbox"
            name="email_enabled"
            defaultChecked={p.preferences.email_enabled}
          />
          Send alerts to my account email (requires configured email provider)
        </label>
        <details>
          <summary>External profiles & scoring weights</summary>
          <JSONEditor label="Profile links" value={links} onChange={setLinks} />
          <JSONEditor
            label="Score weights (must sum to 100)"
            value={weights}
            onChange={setWeights}
          />
        </details>
        <Feedback {...action} />
        <Submit busy={action.busy} />
      </Form>
    </section>
  );
}
function Skills() {
  const client = useQueryClient(),
    action = useAction();
  const { data, error } = useQuery({
    queryKey: ["skills"],
    queryFn: () => api<Skill[]>("/skills"),
  });
  const [editing, setEditing] = useState<Skill | null>(null);
  return (
    <section className="panel spaced">
      <h2>Skills & evidence</h2>
      <p className="muted">
        A project’s technology list alone does not prove a skill. Record your
        own confidence and evidence.
      </p>
      <ErrorBox error={error} />
      <div className="skill-list">
        {data?.map((s) => (
          <div key={s.id}>
            <div>
              <b>{s.name}</b>
              <span className="cell-sub">
                {s.category} · {s.proficiency}/5 proficiency · {s.confidence}/5
                confidence
              </span>
            </div>
            <button className="text-button" onClick={() => setEditing(s)}>
              Edit
            </button>
            <button
              className="text-button danger"
              onClick={() =>
                action.run(async () => {
                  await api(`/skills/${s.id}`, { method: "DELETE" });
                  await client.invalidateQueries();
                }, "Skill removed")
              }
            >
              Remove
            </button>
          </div>
        ))}
      </div>
      <Form
        key={editing?.id || "new"}
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            await send("/skills", {
              name: f.get("name"),
              category: f.get("category"),
              proficiency: Number(f.get("proficiency")),
              confidence: Number(f.get("confidence")),
              evidence: f.get("evidence"),
              learning_status: f.get("learning_status"),
              last_used: f.get("last_used") || null,
            });
            setEditing(null);
            await client.invalidateQueries();
          });
        }}
      >
        <h3>{editing ? "Edit self-assessment" : "Add a skill"}</h3>
        <div className="filter-grid">
          <Field label="Skill name">
            <input
              name="name"
              required
              defaultValue={editing?.name}
              readOnly={!!editing}
            />
          </Field>
          <Field label="Category">
            <select name="category" defaultValue={editing?.category}>
              {[
                "Product Design",
                "UX Research",
                "Programming",
                "Backend",
                "Frontend",
                "Database",
                "Cloud",
                "DevOps",
                "Testing",
                "CS Fundamentals",
                "DSA",
                "AI/ML",
                "Mobile",
                "Distributed Systems",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Proficiency (0–5)">
            <input
              name="proficiency"
              type="number"
              min={0}
              max={5}
              defaultValue={editing?.proficiency ?? 1}
            />
          </Field>
          <Field label="Confidence (0–5)">
            <input
              name="confidence"
              type="number"
              min={0}
              max={5}
              defaultValue={editing?.confidence ?? 1}
            />
          </Field>
          <Field label="Learning status">
            <select
              name="learning_status"
              defaultValue={editing?.learning_status || "LEARNING"}
            >
              {["NOT_STARTED", "LEARNING", "COMFORTABLE", "STRONG"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Last used">
            <input
              type="date"
              name="last_used"
              defaultValue={editing?.last_used || ""}
            />
          </Field>
        </div>
        <Field label="Evidence">
          <textarea
            name="evidence"
            defaultValue={editing?.evidence}
            placeholder="What have you built or explained independently?"
          />
        </Field>
        <Feedback {...action} />
        <div className="form-actions">
          <Submit busy={action.busy}>
            {editing ? "Update skill" : "Add skill"}
          </Submit>
          {editing && (
            <button
              type="button"
              className="button"
              onClick={() => setEditing(null)}
            >
              Cancel edit
            </button>
          )}
        </div>
      </Form>
    </section>
  );
}
interface ResumeMetadata {
  id: string;
  name: string;
  file_name: string;
  is_master: boolean;
  version: string;
  notes: string;
  sha256?: string;
}
function Resumes() {
  const [editing, setEditing] = useState<ResumeMetadata | null>(null);
  const client = useQueryClient(),
    action = useAction();
  const { data, error } = useQuery({
    queryKey: ["resumes"],
    queryFn: () => api<ResumeMetadata[]>("/resumes"),
  });
  return (
    <section className="panel spaced">
      <h2>Resume versions</h2>
      <p className="muted">
        Add resume metadata, then upload a PDF (up to 650 KB) for the local
        application runner. Stored in your private CareerOS database.
      </p>
      <ErrorBox error={error} />
      {data?.map((r) => (
        <div className="list-row" key={r.id}>
          <span>
            {r.name} · v{r.version}
            {r.is_master ? " · Master" : ""}
            <small>
              {r.file_name}
              {r.sha256 ? " · PDF uploaded" : " · PDF not uploaded"}
            </small>
            <label>
              Upload PDF
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  action.run(async () => {
                    if (file.size > 650000)
                      throw new Error("Choose a PDF no larger than 650 KB");
                    const encoded = await new Promise<string>(
                      (resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () =>
                          resolve(String(reader.result).split(",")[1]);
                        reader.onerror = () =>
                          reject(new Error("Could not read file"));
                        reader.readAsDataURL(file);
                      },
                    );
                    await send(
                      `/resumes/${r.id}/pdf`,
                      { content_base64: encoded },
                      "PUT",
                    );
                    await client.invalidateQueries();
                  }, "PDF uploaded");
                }}
              />
            </label>
          </span>
          <button className="text-button" onClick={() => setEditing(r)}>
            Edit
          </button>
          <button
            className="text-button danger"
            onClick={() =>
              action.run(async () => {
                await api(`/resumes/${r.id}`, { method: "DELETE" });
                await client.invalidateQueries();
              })
            }
          >
            Remove
          </button>
        </div>
      ))}
      <Form
        key={editing?.id || "new-resume"}
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            await send(
              editing ? `/resumes/${editing.id}` : "/resumes",
              {
                name: f.get("name"),
                file_name: f.get("file_name"),
                version: f.get("version"),
                notes: f.get("notes"),
                is_master: !!f.get("is_master"),
              },
              editing ? "PUT" : "POST",
            );
            setEditing(null);
            await client.invalidateQueries();
          });
        }}
      >
        <div className="two-col">
          <Field label="Resume name">
            <input
              name="name"
              required
              defaultValue={editing?.name}
              placeholder="Master resume"
            />
          </Field>
          <Field label="File name">
            <input
              name="file_name"
              defaultValue={editing?.file_name}
              placeholder="Mohit_Resume.pdf"
            />
          </Field>
          <Field label="Version">
            <input name="version" defaultValue={editing?.version || "1"} />
          </Field>
          <Field label="Notes">
            <input name="notes" defaultValue={editing?.notes} />
          </Field>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            name="is_master"
            defaultChecked={editing?.is_master}
          />
          Set as master resume
        </label>
        <Feedback {...action} />
        <div className="form-actions">
          <Submit busy={action.busy}>
            {editing ? "Update resume metadata" : "Add resume metadata"}
          </Submit>
          {editing && (
            <button
              type="button"
              className="button"
              onClick={() => setEditing(null)}
            >
              Cancel edit
            </button>
          )}
        </div>
      </Form>
    </section>
  );
}

function PasswordForm() {
  const action = useAction();
  return (
    <section className="panel spaced">
      <h2>Account security</h2>
      <p className="muted">
        Changing your password signs out your other sessions.
      </p>
      <Form
        onSubmit={(event) => {
          const form = event.currentTarget;
          const f = new FormData(form);
          action.run(async () => {
            if (f.get("new_password") !== f.get("confirm_password"))
              throw new Error("The new passwords do not match.");
            await send("/auth/password", {
              current_password: f.get("current_password"),
              new_password: f.get("new_password"),
            });
            form.reset();
          }, "Password changed. Other sessions have been signed out.");
        }}
      >
        <Field label="Current password">
          <input
            name="current_password"
            type="password"
            required
            autoComplete="current-password"
            maxLength={128}
          />
        </Field>
        <div className="two-col">
          <Field label="New password" hint="At least 12 characters.">
            <input
              name="new_password"
              type="password"
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Confirm new password">
            <input
              name="confirm_password"
              type="password"
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
            />
          </Field>
        </div>
        <Feedback {...action} />
        <Submit busy={action.busy}>Change password</Submit>
      </Form>
    </section>
  );
}
