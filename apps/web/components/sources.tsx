"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, date, pretty } from "@/lib/api";
import { Source } from "@/lib/types";
import {
  Modal,
  Heading,
  Loading,
  ErrorBox,
  Field,
  Form,
  Submit,
  Feedback,
  useAction,
  StateBadge,
  Empty,
} from "./ui";
import DiscoveryPanel from "./discovery";
export default function Sources() {
  const [editing, setEditing] = useState<Source | null>(null);
  const client = useQueryClient(),
    action = useAction();
  const { data, error, isPending } = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/sources"),
  });
  return (
    <>
      <Heading title="Sources you can trust" eyebrow="INGESTION & HEALTH">
        Connect public company boards. A failed source won’t stop the rest.
      </Heading>
      <DiscoveryPanel />
      {editing && (
        <Modal title="Edit source" onClose={() => setEditing(null)}>
          <SourceForm source={editing} onSaved={() => setEditing(null)} />
        </Modal>
      )}
      <Feedback {...action} />
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Health</th>
                <th>Latest run</th>
                <th>Last success</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id}>
                  <td>
                    <b>{s.name}</b>
                    <span className="cell-sub">
                      {s.kind} ·{" "}
                      {s.config.board || s.config.feed_url || "Manual entry"}
                    </span>
                  </td>
                  <td>
                    <StateBadge state={s.status} />
                    {s.latest?.error && (
                      <p className="error-text">{s.latest.error}</p>
                    )}
                  </td>
                  <td>
                    {s.latest ? (
                      <>
                        <span>
                          {s.latest.fetched} fetched · {s.latest.added} added
                        </span>
                        <small>
                          {s.latest.updated} updated · {s.latest.skipped || 0}{" "}
                          filtered · {s.latest.closed || 0} closed ·{" "}
                          {s.latest.parse_errors} errors · avg{" "}
                          {s.average_runtime_ms}ms
                        </small>
                      </>
                    ) : (
                      "Not run"
                    )}
                  </td>
                  <td>
                    {date(s.last_success)}
                    {s.last_failure && (
                      <small>Failed {date(s.last_failure)}</small>
                    )}
                  </td>
                  <td>
                    <div className="form-actions">
                      {!["manual", "campus"].includes(s.kind) && (
                        <button
                          className="text-button"
                          onClick={() => setEditing(s)}
                        >
                          Edit
                        </button>
                      )}
                      {!["manual", "campus"].includes(s.kind) && (
                        <button
                          className="button small"
                          disabled={action.busy || !s.enabled}
                          onClick={() =>
                            action.run(async () => {
                              const result = await send<{
                                status: string;
                                error?: string;
                              }>(`/sources/${s.id}/ingest`, {});
                              await client.invalidateQueries();
                              if (result.status === "RUNNING")
                                throw new Error(
                                  "This source is already being processed. Refresh health shortly.",
                                );
                              if (result.status === "DEGRADED")
                                throw new Error(
                                  "Some records could not be parsed. Valid records were saved; review source health.",
                                );
                              if (result.status === "FAILED")
                                throw new Error(
                                  result.error ||
                                    "Source failed. Review configuration.",
                                );
                            }, "Ingestion finished; see source health for counts")
                          }
                        >
                          Run now
                        </button>
                      )}
                      <button
                        className="text-button"
                        disabled={action.busy}
                        onClick={() =>
                          action.run(async () => {
                            await api(`/sources/${s.id}/toggle`, {
                              method: "PATCH",
                            });
                            await client.invalidateQueries();
                          })
                        }
                      >
                        {s.enabled ? "Disable" : "Enable"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title="Connect your first source">
          Use the board token from a company’s official careers link.
        </Empty>
      )}
      <section className="panel spaced">
        <h2>Add a public source</h2>
        <SourceForm />
        <p className="footnote">
          Public sources only. Use Application desk for supported, authorized
          submissions. Unsupported sources can be entered manually.
        </p>
      </section>
    </>
  );
}

function SourceForm({
  source,
  onSaved,
}: {
  source?: Source;
  onSaved?: () => void;
}) {
  const client = useQueryClient(),
    action = useAction();
  return (
    <Form
      onSubmit={(e) => {
        const f = new FormData(e.currentTarget);
        action.run(
          async () => {
            await send(
              source ? `/sources/${source.id}` : "/sources",
              {
                name: f.get("name"),
                close_missing_after: Number(f.get("close_missing_after")),
                kind: f.get("kind"),
                board: f.get("board"),
                company_name: f.get("company_name"),
                country: f.get("country"),
                feed_url: f.get("feed_url") || null,
                enabled: source?.enabled ?? true,
              },
              source ? "PUT" : "POST",
            );
            await client.invalidateQueries();
            onSaved?.();
          },
          source ? "Source updated" : "Source connected",
        );
      }}
    >
      <div className="two-col">
        <Field label="Source name">
          <input
            name="name"
            defaultValue={source?.name}
            required
            placeholder="Company careers"
          />
        </Field>
        <Field label="Adapter">
          <select name="kind" defaultValue={source?.kind || "greenhouse"}>
            {["greenhouse", "lever", "ashby", "official"].map((s) => (
              <option key={s} value={s}>
                {pretty(s)}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Board token"
          hint="Company identifier in the board URL, e.g. the segment after jobs.lever.co/"
        >
          <input
            name="board"
            defaultValue={source?.config.board}
            pattern="[a-zA-Z0-9_-]*"
          />
        </Field>
        <Field label="Company">
          <input
            name="company_name"
            defaultValue={source?.config.company_name}
            required
          />
        </Field>
        <Field
          label="Country"
          hint="Use Unknown for boards spanning multiple countries."
        >
          <input
            name="country"
            defaultValue={source?.config.country || "Unknown"}
            required
          />
        </Field>
        <Field
          label="Official JSON feed URL"
          hint="Only for the Official adapter. Host must be allowlisted by the operator."
        >
          <input
            type="url"
            name="feed_url"
            defaultValue={source?.config.feed_url || ""}
          />
        </Field>
      </div>
      <Field
        label="Close missing jobs"
        hint="After complete, nonempty, error-free snapshots. A job stays open while any source still lists it."
      >
        <select
          name="close_missing_after"
          defaultValue={source?.config.close_missing_after || 0}
        >
          <option value={0}>Keep open until reviewed manually</option>
          <option value={2}>After 2 missing snapshots</option>
          <option value={3}>After 3 missing snapshots</option>
        </select>
      </Field>
      {source && (
        <p className="footnote">
          After a successful import, add a new source to change the adapter,
          board or feed URL. Existing source history is preserved.
        </p>
      )}
      <Feedback {...action} />
      <Submit busy={action.busy}>
        {source ? "Save source" : "Connect source"}
      </Submit>
    </Form>
  );
}
