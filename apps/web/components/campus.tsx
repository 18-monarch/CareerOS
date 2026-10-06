"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send } from "@/lib/api";
import { Job } from "@/lib/types";
import {
  Heading,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
  Empty,
  ErrorBox,
} from "./ui";
import JobForm from "./job-form";
import JobCard from "./job-card";
import JobDetail from "./job-detail";
export default function Campus() {
  const client = useQueryClient(),
    action = useAction();
  const [parsed, setParsed] = useState<Record<string, unknown> | null>(null),
    [selected, setSelected] = useState<string | null>(null),
    [warnings, setWarnings] = useState<string[]>([]);
  const jobs = useQuery({
    queryKey: ["campus"],
    queryFn: () => api<Job[]>("/campus/jobs"),
  });
  return (
    <>
      <Heading title="Nirma campus" eyebrow="FROM NOTICE TO NEXT STEP">
        Paste a placement notice. Review the facts. Check your eligibility.
      </Heading>
      <section className="panel">
        <Form
          onSubmit={(e) => {
            const f = new FormData(e.currentTarget);
            action.run(async () => {
              const result = await send<{
                job: Record<string, unknown>;
                warnings: string[];
              }>("/campus/parse", { text: f.get("notice") });
              setParsed(result.job);
              setWarnings(result.warnings);
            }, "Notice parsed. Review every extracted requirement before saving.");
          }}
        >
          <Field
            label="Placement notice"
            hint="The parser recognizes labeled fields such as Company, Role, CGPA, Batch, Location and Deadline (YYYY-MM-DD)."
          >
            <textarea
              name="notice"
              rows={9}
              required
              minLength={10}
              placeholder={
                "Company: Example Company\nRole: Software Engineer Intern\nCGPA: 7.0\nBatch: 2028\nBranches: CSE\nLocation: Ahmedabad\nDeadline: 2027-01-20\nRequired: Python, SQL\nPreferred: Docker"
              }
            />
          </Field>
          <Feedback {...action} />
          <Submit busy={action.busy}>Extract and review</Submit>
        </Form>
      </section>
      {warnings.map((w) => (
        <p className="footnote" key={w}>
          {w}
        </p>
      ))}
      <div className="section-heading">
        <h2>Campus opportunities</h2>
      </div>
      <ErrorBox error={jobs.error} />
      <div className="opportunity-grid">
        {jobs.data?.map((j) => (
          <JobCard key={j.id} job={j} onOpen={setSelected} />
        ))}
      </div>
      {jobs.data?.length === 0 && (
        <Empty title="Your campus board is empty">
          Add the first verified notice above.
        </Empty>
      )}
      {parsed && (
        <JobForm
          initial={parsed}
          onClose={() => setParsed(null)}
          onSaved={() => {
            setParsed(null);
            client.invalidateQueries();
          }}
        />
      )}
      {selected && (
        <JobDetail id={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
