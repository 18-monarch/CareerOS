"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, pretty } from "@/lib/api";
import { Gap } from "@/lib/types";
import {
  Heading,
  Loading,
  ErrorBox,
  Empty,
  Field,
  Form,
  Submit,
  StateBadge,
  Feedback,
  useAction,
} from "./ui";
export default function Learning() {
  const client = useQueryClient(),
    action = useAction();
  const { data, error, isPending } = useQuery({
    queryKey: ["learning"],
    queryFn: () => api<Gap[]>("/learning/recommendations"),
  });
  const progress = useQuery({
    queryKey: ["learning-progress"],
    queryFn: () =>
      api<{ id: string; topic: string; status: string; notes: string }[]>(
        "/learning/progress",
      ),
  });
  return (
    <>
      <Heading title="Learn something that opens doors" eyebrow="LEARN → APPLY">
        Priorities from your relevant opportunities, weighted by demand and
        effort.
      </Heading>
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : data?.length ? (
        <div className="learning-grid">
          {data.map((g, i) => (
            <article className="panel learning-card" key={g.skill}>
              <div className="inline">
                <span className="rank">{String(i + 1).padStart(2, "0")}</span>
                <span className="muted">Priority {g.priority}</span>
              </div>
              <h2>{pretty(g.skill)}</h2>
              <p>
                {g.jobs} relevant roles · {g.required_count} require it
              </p>
              <div className="skill-demand">
                <span>Estimated effort</span>
                <b>{g.estimated_hours} hours</b>
              </div>
              <p className="footnote">{g.explanation}</p>
              <button
                className="button"
                disabled={action.busy}
                onClick={() =>
                  action.run(async () => {
                    await send(
                      "/learning/progress",
                      { topic: g.skill, status: "LEARNING", notes: "" },
                      "PUT",
                    );
                    await client.invalidateQueries();
                  }, `Added ${g.skill} to your learning plan`)
                }
              >
                Start learning
              </button>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="No skill gaps to prioritize yet">
          Add relevant opportunities and an honest skills profile first.
        </Empty>
      )}
      <Feedback {...action} />
      <section className="panel spaced">
        <h2>Your learning plan</h2>
        {progress.data?.map((p) => (
          <div className="list-row" key={p.id}>
            <div>
              <b>{pretty(p.topic)}</b>
              <p>{p.notes}</p>
            </div>
            <StateBadge state={p.status} />
          </div>
        ))}
        <Form
          onSubmit={(e) => {
            const f = new FormData(e.currentTarget);
            action.run(async () => {
              await send(
                "/learning/progress",
                {
                  topic: f.get("topic"),
                  status: f.get("status"),
                  notes: f.get("notes"),
                },
                "PUT",
              );
              await client.invalidateQueries();
            });
          }}
        >
          <div className="two-col">
            <Field label="Topic">
              <input name="topic" required />
            </Field>
            <Field label="Progress">
              <select name="status">
                {["LEARNING", "NOT_STARTED", "COMFORTABLE", "STRONG"].map(
                  (s) => (
                    <option key={s}>{s}</option>
                  ),
                )}
              </select>
            </Field>
          </div>
          <Field label="Practice plan / evidence">
            <textarea
              name="notes"
              placeholder="Build a Docker image for one project, then explain image layers."
            />
          </Field>
          <Submit busy={action.busy}>Update learning topic</Submit>
        </Form>
        <p className="footnote">
          Completing a topic does not automatically certify a skill. Update your
          profile when you can demonstrate it.
        </p>
      </section>
    </>
  );
}
