"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Clock3, BookOpen, Plus } from "lucide-react";
import { api, date, pretty, send } from "@/lib/api";
import { Dashboard as DashboardData, Job } from "@/lib/types";
import { Heading, Loading, ErrorBox, Empty, useAction, Feedback } from "./ui";
import JobCard from "./job-card";
import JobDetail from "./job-detail";
export default function Dashboard({ name }: { name: string }) {
  const client = useQueryClient(),
    action = useAction();
  const [selected, setSelected] = useState<string | null>(null);
  const { data, error, isPending } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardData>("/dashboard"),
  });
  const save = (j: Job) =>
    action.run(async () => {
      await send("/applications", { job_id: j.id, status: "SAVED" });
      await client.invalidateQueries();
    }, "Opportunity saved");
  return (
    <>
      <Heading
        eyebrow="YOUR NEXT STEP, CLEARER"
        title={`Make your next move, ${name.split(" ")[0]}.`}
        action={
          <Link href="/opportunities" className="button primary">
            <Plus size={17} />
            Add opportunity
          </Link>
        }
      >
        A little focus today. More options tomorrow.
      </Heading>
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : (
        data && (
          <>
            {data.demo_jobs > 0 && (
              <div className="demo-banner">
                You’re exploring {data.demo_jobs} synthetic opportunities. Add
                live roles from official sources when you’re ready.
              </div>
            )}
            <div className="stats-grid">
              <div className="stat">
                <span>New today</span>
                <b>{data.new_today.toString().padStart(2, "0")}</b>
                <small>discovered opportunities</small>
              </div>
              <div className="stat featured">
                <span>
                  <Sparkles size={15} />
                  Ready to apply
                </span>
                <b>
                  {(data.classifications.APPLY_NOW || 0)
                    .toString()
                    .padStart(2, "0")}
                </b>
                <small>matched to your profile</small>
              </div>
              <div className="stat">
                <span>Prep, then apply</span>
                <b>
                  {(data.classifications.PREP_THEN_APPLY || 0)
                    .toString()
                    .padStart(2, "0")}
                </b>
                <small>a few skills to strengthen</small>
              </div>
              <div className="stat">
                <span>Needs a closer look</span>
                <b>
                  {(data.classifications.WATCH || 0)
                    .toString()
                    .padStart(2, "0")}
                </b>
                <small>{data.not_eligible} outside eligibility</small>
              </div>
            </div>
            <div className="dashboard-grid">
              <section>
                <div className="section-heading">
                  <div>
                    <h2>Worth your attention</h2>
                    <p>The strongest matches, with the reasons attached.</p>
                  </div>
                  <Link href="/opportunities">View all</Link>
                </div>
                <Feedback {...action} />
                <div className="job-list">
                  {data.top_jobs.length ? (
                    data.top_jobs.map((j) => (
                      <JobCard
                        key={j.id}
                        job={j}
                        onOpen={setSelected}
                        onSave={save}
                      />
                    ))
                  ) : (
                    <Empty title="Your next opportunity starts here">
                      Add a job or connect a public company board.
                    </Empty>
                  )}
                </div>
              </section>
              <aside className="insight-stack">
                <section className="panel deadline-panel">
                  <div className="eyebrow">
                    <Clock3 size={15} />
                    NEXT DEADLINE
                  </div>
                  {data.next_deadline ? (
                    <>
                      <h3>{data.next_deadline.company_name}</h3>
                      <p>{data.next_deadline.title}</p>
                      <b className="deadline-date">
                        {date(data.next_deadline.application_deadline)}
                      </b>
                      <button
                        className="button full"
                        onClick={() => setSelected(data.next_deadline!.id)}
                      >
                        Review opportunity
                      </button>
                    </>
                  ) : (
                    <p>No upcoming eligible deadlines.</p>
                  )}
                </section>
                <section className="panel">
                  <div className="eyebrow">
                    <BookOpen size={15} />
                    LEARN SOMETHING THAT COUNTS
                  </div>
                  {data.learning[0] ? (
                    <>
                      <h3 className="learning-title">
                        {pretty(data.learning[0].skill)}
                      </h3>
                      <p>
                        Requested in{" "}
                        <strong>{data.learning[0].jobs} relevant roles</strong>.
                        An estimated {data.learning[0].estimated_hours} hours to
                        build a foundation.
                      </p>
                      <div className="skill-demand">
                        <span>Required</span>
                        <b>{data.learning[0].required_count} roles</b>
                      </div>
                      <Link href="/learning" className="text-link">
                        See learning priorities
                      </Link>
                    </>
                  ) : (
                    <p>Learning priorities appear as you add relevant roles.</p>
                  )}
                </section>
                <section className="panel">
                  <div className="eyebrow">THIS WEEK</div>
                  <h3>{data.planned} applications planned</h3>
                  <p className="pre-wrap">
                    {data.weekly_plan ||
                      "Set a realistic weekly plan in your profile."}
                  </p>
                  <Link href="/profile" className="text-link">
                    Edit your plan
                  </Link>
                </section>
              </aside>
            </div>
            <section className="panel pipeline-panel">
              <div className="section-heading">
                <div>
                  <h2>From application to offer</h2>
                  <p>Progress based on your recorded application history.</p>
                </div>
                <Link href="/applications">Open tracker</Link>
              </div>
              <div className="pipeline-stats">
                {["APPLIED", "OA_RECEIVED", "INTERVIEW", "OFFER"].map(
                  (s, i) => (
                    <div key={s}>
                      <span className="step-number">0{i + 1}</span>
                      <b>{data.pipeline.counts[s]}</b>
                      <span>{pretty(s)}</span>
                    </div>
                  ),
                )}
              </div>
              <p className="footnote">{data.pipeline.recommendation}</p>
            </section>
          </>
        )
      )}
      {selected && (
        <JobDetail id={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
