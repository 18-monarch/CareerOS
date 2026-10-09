"use client";
import { MapPin, Clock3, Bookmark } from "lucide-react";
import { Job } from "@/lib/types";
import { careerCategories } from "@/lib/categories";
import { date } from "@/lib/api";
import { Badge, StateBadge } from "./ui";
export default function JobCard({
  job,
  onOpen,
  onSave,
}: {
  job: Job;
  onOpen: (id: string) => void;
  onSave?: (job: Job) => void;
}) {
  return (
    <article className="job-card">
      <div className="job-card-top">
        <span className="company-icon">{job.company_name.slice(0, 1)}</span>
        <div className="job-main">
          <div className="inline">
            <span className="company-name">{job.company_name}</span>
            {job.is_demo && <Badge>Demo</Badge>}
          </div>
          <button className="job-title" onClick={() => onOpen(job.id)}>
            {job.title}
          </button>
          <div className="job-meta">
            <span>
              <MapPin size={13} />
              {job.locations.join(", ") || job.country}
            </span>
            <span>{job.remote_status}</span>
            <span>{job.employment_type}</span>
          </div>
        </div>
        <div className="score">
          <b>
            {job.match.score}
            <small>%</small>
          </b>
          <span>match</span>
        </div>
      </div>
      <div className="skill-chips">
        {job.categories?.map((c) => (
          <span key={c}>{careerCategories[c]}</span>
        ))}
        {job.match.strong_matches.slice(0, 4).map((s) => (
          <span key={s}>{s}</span>
        ))}
        {job.match.missing_required.length > 0 && (
          <span className="missing">
            +{job.match.missing_required.length} skills to build
          </span>
        )}
      </div>
      <div className="job-card-bottom">
        <StateBadge state={job.match.classification} />
        <span className="deadline">
          <Clock3 size={13} />
          {date(job.application_deadline)}
        </span>
        {onSave && (
          <button
            aria-label={`Save ${job.title} at ${job.company_name}`}
            className="icon-button"
            onClick={() => onSave(job)}
            disabled={!!job.application}
          >
            <Bookmark
              size={17}
              fill={job.application ? "currentColor" : "none"}
            />
          </button>
        )}
      </div>
    </article>
  );
}
