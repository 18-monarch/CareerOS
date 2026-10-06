"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, date, pretty } from "@/lib/api";
import {
  Heading,
  Loading,
  ErrorBox,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
} from "./ui";
interface DSAData {
  topics: {
    topic: string;
    problems_solved: number;
    independent: number;
    hint_required: number;
    could_explain: number;
    complexity_understood: number;
    last_reviewed: string | null;
  }[];
  logs: { id: string; topic: string; problem: string; created_at: string }[];
}
export default function DSA() {
  const client = useQueryClient(),
    action = useAction();
  const { data, error, isPending } = useQuery({
    queryKey: ["dsa"],
    queryFn: () => api<DSAData>("/dsa"),
  });
  return (
    <>
      <Heading
        title="Readiness, beyond the problem count"
        eyebrow="DSA PRACTICE"
      >
        Track whether you can solve it, explain it, and reason about its
        complexity.
      </Heading>
      <section className="panel">
        <h2>Log a practice session</h2>
        <Form
          onSubmit={(e) => {
            const f = new FormData(e.currentTarget),
              form = e.currentTarget;
            action.run(async () => {
              await send("/dsa", {
                topic: f.get("topic"),
                problem: f.get("problem"),
                ...Object.fromEntries(
                  [
                    "independent",
                    "hint_required",
                    "could_explain",
                    "complexity_understood",
                  ].map((k) => [k, !!f.get(k)]),
                ),
              });
              form.reset();
              await client.invalidateQueries();
            }, "Practice logged");
          }}
        >
          <div className="two-col">
            <Field label="Topic">
              <select name="topic">
                {data?.topics.map((t) => (
                  <option key={t.topic}>{t.topic}</option>
                ))}
              </select>
            </Field>
            <Field label="Problem name">
              <input name="problem" required />
            </Field>
          </div>
          <div className="checkbox-row">
            {[
              "independent",
              "hint_required",
              "could_explain",
              "complexity_understood",
            ].map((k) => (
              <label className="checkbox" key={k}>
                <input type="checkbox" name={k} />
                {pretty(k)}
              </label>
            ))}
          </div>
          <Feedback {...action} />
          <Submit busy={action.busy}>Log practice</Submit>
        </Form>
      </section>
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="table-wrap spaced">
              <table>
                <thead>
                  <tr>
                    <th>Topic</th>
                    <th>Solved</th>
                    <th>Independent</th>
                    <th>Hints</th>
                    <th>Can explain</th>
                    <th>Complexity</th>
                    <th>Reviewed</th>
                  </tr>
                </thead>
                <tbody>
                  {data.topics.map((t) => (
                    <tr key={t.topic}>
                      <td>
                        <b>{t.topic}</b>
                      </td>
                      <td>{t.problems_solved}</td>
                      <td>{t.independent}</td>
                      <td>{t.hint_required}</td>
                      <td>{t.could_explain}</td>
                      <td>{t.complexity_understood}</td>
                      <td>{date(t.last_reviewed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <section className="panel spaced">
              <h2>Recent practice</h2>
              {data.logs.map((l) => (
                <div className="list-row" key={l.id}>
                  <span>
                    <b>{l.problem}</b>
                    <small>
                      {l.topic} · {date(l.created_at)}
                    </small>
                  </span>
                  <button
                    className="text-button danger"
                    onClick={() =>
                      action.run(async () => {
                        await api(`/dsa/${l.id}`, { method: "DELETE" });
                        await client.invalidateQueries();
                      }, "Entry removed")
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
            </section>
          </>
        )
      )}
    </>
  );
}
