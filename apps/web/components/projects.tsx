"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, FolderGit2 } from "lucide-react";
import { api, send, list, pretty } from "@/lib/api";
import { Project } from "@/lib/types";
import {
  Heading,
  Loading,
  ErrorBox,
  Empty,
  Modal,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
  StateBadge,
} from "./ui";
const levels = ["NOT_STARTED", "LEARNING", "COMFORTABLE", "STRONG"];
export default function Projects() {
  const client = useQueryClient(),
    action = useAction();
  const [edit, setEdit] = useState<Project | "new" | null>(null),
    [mastery, setMastery] = useState<Project | null>(null);
  const { data, error, isPending } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
  });
  return (
    <>
      <Heading
        title="Own what you build"
        eyebrow="PROJECT MASTERY"
        action={
          <button className="button primary" onClick={() => setEdit("new")}>
            <Plus size={17} />
            Add project
          </button>
        }
      >
        Move from “I used it” to “I can explain it.”
      </Heading>
      <Feedback {...action} />
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : (
        <div className="opportunity-grid">
          {data?.map((p) => (
            <article className="panel project-card" key={p.id}>
              <FolderGit2 size={24} />
              <h2>{p.name}</h2>
              <p>{p.description}</p>
              <div className="skill-chips">
                {p.technologies.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
              <p className="footnote">
                Verified skills:{" "}
                {p.verified_skills.join(", ") || "None recorded"}
              </p>
              {p.mastery.map((m) => (
                <div className="mastery-row" key={m.id}>
                  <span>{m.topic}</span>
                  <StateBadge state={m.status} />
                </div>
              ))}
              <div className="form-actions">
                <button className="button small" onClick={() => setMastery(p)}>
                  Track understanding
                </button>
                <button className="text-button" onClick={() => setEdit(p)}>
                  Edit
                </button>
                <button
                  className="text-button danger"
                  onClick={() =>
                    action.run(async () => {
                      if (
                        !window.confirm(
                          `Delete ${p.name} and its mastery notes?`,
                        )
                      )
                        return;
                      await api(`/projects/${p.id}`, { method: "DELETE" });
                      await client.invalidateQueries();
                    }, "Project removed")
                  }
                >
                  Delete
                </button>
              </div>
              {p.repository_url && (
                <a
                  className="text-link"
                  href={p.repository_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Repository
                </a>
              )}
            </article>
          ))}
        </div>
      )}
      {data?.length === 0 && (
        <Empty title="Start with a project you’ve built">
          Track its architecture, algorithms, and failure modes.
        </Empty>
      )}
      {edit && (
        <ProjectEditor
          project={edit === "new" ? null : edit}
          onClose={() => setEdit(null)}
        />
      )}{" "}
      {mastery && (
        <MasteryEditor project={mastery} onClose={() => setMastery(null)} />
      )}
    </>
  );
}
function ProjectEditor({
  project: p,
  onClose,
}: {
  project: Project | null;
  onClose: () => void;
}) {
  const client = useQueryClient(),
    action = useAction();
  return (
    <Modal title={p ? "Edit project" : "Add project"} onClose={onClose}>
      <Form
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            await send(
              p ? `/projects/${p.id}` : "/projects",
              {
                name: f.get("name"),
                description: f.get("description"),
                repository_url: f.get("repository_url") || null,
                live_url: f.get("live_url") || null,
                technologies: list(String(f.get("technologies"))),
                verified_skills: list(String(f.get("verified_skills"))),
                interview_readiness: f.get("interview_readiness"),
              },
              p ? "PUT" : "POST",
            );
            await client.invalidateQueries();
            onClose();
          });
        }}
      >
        {[
          "name",
          "repository_url",
          "live_url",
          "technologies",
          "verified_skills",
        ].map((k) => (
          <Field
            key={k}
            label={pretty(k)}
            hint={
              k === "verified_skills"
                ? "Only skills you can demonstrate and explain. Comma separated."
                : undefined
            }
          >
            <input
              name={k}
              type={k.includes("url") ? "url" : "text"}
              required={k === "name"}
              defaultValue={
                p
                  ? Array.isArray(p[k as keyof Project])
                    ? (p[k as keyof Project] as string[]).join(", ")
                    : String(p[k as keyof Project] ?? "")
                  : ""
              }
            />
          </Field>
        ))}
        <Field label="Description">
          <textarea name="description" defaultValue={p?.description} />
        </Field>
        <Field label="Interview readiness">
          <select
            name="interview_readiness"
            defaultValue={p?.interview_readiness}
          >
            {levels.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Feedback {...action} />
        <Submit busy={action.busy} />
      </Form>
    </Modal>
  );
}
function MasteryEditor({
  project,
  onClose,
}: {
  project: Project;
  onClose: () => void;
}) {
  const client = useQueryClient(),
    action = useAction();
  return (
    <Modal title={`${project.name} · Understanding`} onClose={onClose}>
      <Form
        onSubmit={(e) => {
          const f = new FormData(e.currentTarget);
          action.run(async () => {
            await send(
              `/projects/${project.id}/mastery`,
              {
                topic: f.get("topic"),
                status: f.get("status"),
                confidence: Number(f.get("confidence")),
                notes: f.get("notes"),
                linked_skills: list(String(f.get("linked_skills"))),
              },
              "PUT",
            );
            await client.invalidateQueries();
            onClose();
          });
        }}
      >
        <Field label="Topic">
          <input name="topic" required list="project-topics" />
          <datalist id="project-topics">
            {project.mastery.map((m) => (
              <option key={m.id} value={m.topic} />
            ))}
          </datalist>
        </Field>
        <div className="two-col">
          <Field label="Understanding">
            <select name="status">
              {levels.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Confidence (0–5)">
            <input
              name="confidence"
              type="number"
              min={0}
              max={5}
              defaultValue={1}
            />
          </Field>
        </div>
        <Field label="What can you explain? What needs work?">
          <textarea name="notes" rows={4} />
        </Field>
        <Field label="Linked skills (comma separated)">
          <input name="linked_skills" />
        </Field>
        <Feedback {...action} />
        <Submit busy={action.busy}>Save understanding</Submit>
      </Form>
    </Modal>
  );
}
