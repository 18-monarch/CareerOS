"use client";
import { useDeferredValue, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, SlidersHorizontal } from "lucide-react";
import { api, send, pretty, statuses } from "@/lib/api";
import { Job } from "@/lib/types";
import {
  Heading,
  Loading,
  ErrorBox,
  Empty,
  Field,
  Feedback,
  useAction,
} from "./ui";
import { careerCategories } from "@/lib/categories";
import JobCard from "./job-card";
import JobDetail from "./job-detail";
import JobForm from "./job-form";
export default function Opportunities() {
  const client = useQueryClient(),
    action = useAction();
  const [selected, setSelected] = useState<string | null>(null),
    [adding, setAdding] = useState(false),
    [filters, setFilters] = useState<Record<string, string>>({}),
    [advanced, setAdvanced] = useState(false),
    [page, setPage] = useState(1);
  const deferred = useDeferredValue(filters);
  const params = new URLSearchParams({
    ...deferred,
    page: String(page),
    page_size: "12",
  }).toString();
  const { data, error, isPending } = useQuery({
    queryKey: ["jobs", params],
    queryFn: () => api<{ items: Job[]; total: number }>(`/jobs?${params}`),
  });
  function set(k: string, v: string) {
    setFilters({ ...filters, [k]: v });
    setPage(1);
  }
  return (
    <>
      <Heading
        title="Opportunities"
        eyebrow="FIND YOUR FIT"
        action={
          <button className="button primary" onClick={() => setAdding(true)}>
            <Plus size={17} />
            Add opportunity
          </button>
        }
      >
        Eligibility first. Fit second. Every score explained.
      </Heading>
      <div className="filter-bar">
        <select
          aria-label="Career category filter"
          value={filters.category || ""}
          onChange={(e) => set("category", e.target.value)}
        >
          <option value="">All career categories</option>
          {Object.entries(careerCategories).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <label className="search">
          <Search size={18} />
          <input
            aria-label="Search opportunities"
            placeholder="Search roles, companies or skills…"
            value={filters.q || ""}
            onChange={(e) => set("q", e.target.value)}
          />
        </label>
        <select
          aria-label="Eligibility filter"
          value={filters.eligibility || ""}
          onChange={(e) => set("eligibility", e.target.value)}
        >
          <option value="">All eligibility</option>
          {[
            "ELIGIBLE",
            "LIKELY_ELIGIBLE",
            "REVIEW_REQUIRED",
            "NOT_ELIGIBLE",
            "CLOSED",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Sort opportunities"
          onChange={(e) => set("sort", e.target.value)}
        >
          <option value="match">Best match</option>
          <option value="deadline">Soonest deadline</option>
          <option value="newest">Newest</option>
        </select>
        <button
          className="button"
          onClick={() => setAdvanced(!advanced)}
          aria-expanded={advanced}
        >
          <SlidersHorizontal size={17} />
          Filters
        </button>
      </div>
      {advanced && (
        <div className="panel filter-grid">
          {[
            "role",
            "company",
            "country",
            "city",
            "skill",
            "source",
            "min_score",
            "graduation_year",
            "max_cgpa",
            "deadline_before",
          ].map((k) => (
            <Field key={k} label={pretty(k)}>
              <input
                type={
                  ["min_score", "graduation_year", "max_cgpa"].includes(k)
                    ? "number"
                    : k === "deadline_before"
                      ? "datetime-local"
                      : "text"
                }
                value={filters[k] || ""}
                onChange={(e) => set(k, e.target.value)}
                step="any"
              />
            </Field>
          ))}
          <Field label="Work arrangement">
            <select onChange={(e) => set("remote", e.target.value)}>
              <option value="">Any</option>
              {["remote", "hybrid", "onsite"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Employment">
            <select onChange={(e) => set("employment_type", e.target.value)}>
              <option value="">Any</option>
              {["internship", "full-time", "part-time", "contract"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Application state">
            <select onChange={(e) => set("state", e.target.value)}>
              <option value="">Any</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {pretty(s)}
                </option>
              ))}
            </select>
          </Field>
          <button
            className="button"
            onClick={() => {
              setFilters({});
              setPage(1);
            }}
          >
            Clear filters
          </button>
        </div>
      )}
      <Feedback {...action} />
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="list-caption">
              {data.total} opportunities · based on your current profile
            </div>
            <div className="opportunity-grid">
              {data.items.map((j) => (
                <JobCard
                  key={j.id}
                  job={j}
                  onOpen={setSelected}
                  onSave={(j) =>
                    action.run(async () => {
                      await send("/applications", {
                        job_id: j.id,
                        status: "SAVED",
                      });
                      await client.invalidateQueries();
                    }, "Saved to applications")
                  }
                />
              ))}
            </div>
            {!data.items.length && (
              <Empty title="No opportunities here yet">
                Try different filters, add a posting, or connect a source.
              </Empty>
            )}
            <div className="pagination">
              <button
                className="button"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span>Page {page}</span>
              <button
                className="button"
                disabled={page * 12 >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </>
        )
      )}
      {selected && (
        <JobDetail id={selected} onClose={() => setSelected(null)} />
      )}{" "}
      {adding && (
        <JobForm
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            client.invalidateQueries();
          }}
        />
      )}
    </>
  );
}
