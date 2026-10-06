import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StateBadge, Empty, ErrorBox, Field } from "@/components/ui";
import JobCard from "@/components/job-card";
import { Job } from "@/lib/types";
const job = {
  id: "1",
  normalized_role: "Backend Engineer",
  description: "Test vacancy",
  source: "manual",
  application_url: null,
  is_active: true,
  required_skills: ["python"],
  preferred_skills: [],
  requirements: {},
  provenance: {},
  stipend: null,
  company_name: "Demo Co",
  title: "Backend Intern",
  locations: ["Ahmedabad"],
  country: "India",
  remote_status: "hybrid",
  employment_type: "internship",
  is_demo: true,
  application_deadline: "2027-01-20T00:00:00",
  match: {
    score: 80,
    eligibility: { state: "ELIGIBLE", reasons: [], checks: [] },
    missing_preferred: [],
    project_evidence: [],
    preparation: [],
    breakdown: {},
    score_suppressed: false,
    classification: "APPLY_NOW",
    strong_matches: ["python"],
    missing_required: [],
  },
} as Job;
describe("decision components", () => {
  it("renders disqualification as text rather than color alone", () => {
    render(<StateBadge state="NOT_ELIGIBLE" />);
    expect(screen.getByText("Not Eligible")).toBeVisible();
  });
  it("labels demo postings and exposes real save/detail actions", () => {
    const open = vi.fn(),
      save = vi.fn();
    render(<JobCard job={job} onOpen={open} onSave={save} />);
    expect(screen.getByText("Demo")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Backend Intern" }));
    expect(open).toHaveBeenCalledWith("1");
    fireEvent.click(
      screen.getByRole("button", { name: "Save Backend Intern at Demo Co" }),
    );
    expect(save).toHaveBeenCalledWith(job);
  });
  it("prevents saving an already tracked job", () => {
    render(
      <JobCard
        job={{ ...job, application: { id: "a", status: "SAVED" } }}
        onOpen={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Save Backend Intern at Demo Co" }),
    ).toBeDisabled();
  });
  it("shows useful error and empty states", () => {
    render(
      <>
        <ErrorBox error={new Error("Backend unavailable")} />
        <Empty title="No results">Try another filter</Empty>
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Backend unavailable");
    expect(screen.getByText("Try another filter")).toBeVisible();
  });
});

describe("accessible form labels", () => {
  it("keeps option and help text out of the field name", () => {
    render(
      <Field label="Status" hint="Choose the current stage">
        <select>
          <option>Saved</option>
          <option>Applied</option>
        </select>
      </Field>,
    );
    expect(
      screen.getByLabelText("Status", { exact: true }),
    ).toHaveAccessibleDescription("Choose the current stage");
  });
});
