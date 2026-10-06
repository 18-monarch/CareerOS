"use client";
import { useState } from "react";
import { list, send, localDateTime } from "@/lib/api";
import {
  Field,
  Form,
  Modal,
  Submit,
  JSONEditor,
  Feedback,
  useAction,
} from "./ui";
export default function JobForm({
  onClose,
  onSaved,
  initial,
  editId,
}: {
  onClose: () => void;
  onSaved: () => void;
  initial?: Record<string, unknown>;
  editId?: string;
}) {
  const action = useAction();
  const [requirements, setRequirements] = useState(
    JSON.stringify(
      initial?.requirements || {
        minimum_cgpa: null,
        allowed_graduation_years: [],
        minimum_experience: null,
        degree_requirements: [],
        branch_requirements: [],
        work_authorization: null,
        visa_sponsorship: null,
      },
      null,
      2,
    ),
  );
  const [advanced, setAdvanced] = useState(
    JSON.stringify(
      {
        salary_min: initial?.salary_min || null,
        salary_max: initial?.salary_max || null,
        salary_currency: initial?.salary_currency || null,
        salary_period: initial?.salary_period || null,
        stipend: initial?.stipend || null,
        selection_stages: initial?.selection_stages || [],
      },
      null,
      2,
    ),
  );
  const str = (k: string, fallback = "") => String(initial?.[k] ?? fallback);
  return (
    <Modal
      title={
        editId
          ? "Review and edit opportunity"
          : initial
            ? "Review campus opportunity"
            : "Add an opportunity"
      }
      onClose={onClose}
    >
      <Form
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            const provenance = {
              ...((initial?.provenance as Record<string, unknown>) || {}),
            };
            if (f.get("confirmed"))
              for (const k of [
                ...Object.keys(JSON.parse(requirements)),
                "application_deadline",
              ])
                provenance[k] = {
                  ...((provenance[k] as object) || {}),
                  method: "manual",
                  confirmed: true,
                };
            const deadline = String(f.get("application_deadline") || "");
            await send(
              editId ? `/jobs/${editId}` : initial ? "/campus/jobs" : "/jobs",
              {
                company_name: f.get("company_name"),
                title: f.get("title"),
                normalized_role: f.get("normalized_role"),
                description: f.get("description"),
                source: initial ? "campus" : "manual",
                application_url: f.get("application_url") || null,
                source_url: f.get("application_url") || null,
                country: f.get("country"),
                locations: list(String(f.get("locations"))),
                remote_status: f.get("remote_status"),
                employment_type: f.get("employment_type"),
                required_skills: list(String(f.get("required_skills"))),
                preferred_skills: list(String(f.get("preferred_skills"))),
                application_deadline: deadline
                  ? new Date(deadline).toISOString()
                  : null,
                requirements: JSON.parse(requirements),
                provenance,
                ...JSON.parse(advanced),
              },
              editId ? "PUT" : "POST",
            );
            onSaved();
          });
        }}
      >
        <div className="two-col">
          {[
            ["company_name", "Company"],
            ["title", "Role title"],
            ["country", "Country"],
            ["locations", "Cities / locations"],
          ].map(([key, label]) => (
            <Field label={label} key={key}>
              <input
                name={key}
                required={key !== "locations"}
                defaultValue={
                  Array.isArray(initial?.[key])
                    ? (initial![key] as string[]).join(", ")
                    : str(key, key === "country" ? "India" : "")
                }
              />
            </Field>
          ))}
          <Field label="Role family">
            <select
              name="normalized_role"
              defaultValue={str("normalized_role", "Software Engineer")}
            >
              {[
                "Software Engineer",
                "Backend Engineer",
                "Full-Stack Engineer",
                "Product Engineer",
                "Platform Engineer",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Employment type">
            <select
              name="employment_type"
              defaultValue={str("employment_type", "internship")}
            >
              {["internship", "full-time", "part-time", "contract"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Work arrangement">
            <select
              name="remote_status"
              defaultValue={str("remote_status", "unknown")}
            >
              {["unknown", "onsite", "hybrid", "remote"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Deadline (your local time)">
            <input
              type="datetime-local"
              name="application_deadline"
              defaultValue={localDateTime(str("application_deadline"))}
            />
          </Field>
        </div>
        <Field label="Official application URL">
          <input
            type="url"
            name="application_url"
            defaultValue={str("application_url")}
          />
        </Field>
        <Field label="Job description">
          <textarea
            name="description"
            rows={5}
            defaultValue={str("description")}
          />
        </Field>
        <div className="two-col">
          <Field label="Required skills (comma separated)">
            <input
              name="required_skills"
              defaultValue={((initial?.required_skills as string[]) || []).join(
                ", ",
              )}
            />
          </Field>
          <Field label="Preferred skills (comma separated)">
            <input
              name="preferred_skills"
              defaultValue={(
                (initial?.preferred_skills as string[]) || []
              ).join(", ")}
            />
          </Field>
        </div>
        <JSONEditor
          label="Structured eligibility requirements"
          value={requirements}
          onChange={setRequirements}
        />
        <details>
          <summary>Compensation and selection stages</summary>
          <JSONEditor
            label="Additional details"
            value={advanced}
            onChange={setAdvanced}
          />
        </details>
        <label className="checkbox">
          <input name="confirmed" type="checkbox" required />I reviewed these
          requirements against the posting. Unknown values remain null.
        </label>
        <Feedback {...action} />
        <Submit busy={action.busy}>Save and evaluate eligibility</Submit>
      </Form>
    </Modal>
  );
}
