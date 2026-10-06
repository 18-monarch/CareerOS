"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, date, pretty } from "@/lib/api";
import {
  Heading,
  Loading,
  ErrorBox,
  Empty,
  Feedback,
  useAction,
  Badge,
} from "./ui";
interface Notice {
  id: string;
  kind: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  emailed_at: string | null;
  delivery_error: string | null;
}
export default function Notifications() {
  const client = useQueryClient(),
    action = useAction();
  const { data, error, isPending } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Notice[]>("/notifications"),
  });
  return (
    <>
      <Heading
        title="A little signal. Less noise."
        eyebrow="NOTIFICATIONS"
        action={
          <button
            className="button"
            disabled={action.busy}
            onClick={() =>
              action.run(async () => {
                const r = await send<{ created: number }>(
                  "/notifications/generate",
                  {},
                );
                await client.invalidateQueries();
                return r;
              }, "Alerts checked. Existing alerts are not duplicated.")
            }
          >
            Check alerts
          </button>
        }
      >
        High matches, upcoming deadlines, and a record of your progress.
      </Heading>
      <Feedback {...action} />
      <ErrorBox error={error} />
      {isPending ? (
        <Loading />
      ) : data?.length ? (
        <div className="notification-list">
          {data.map((n) => (
            <article
              key={n.id}
              className={`panel notification ${n.read ? "read" : ""}`}
            >
              <div className="inline">
                <Badge tone={n.read ? "neutral" : "green"}>
                  {pretty(n.kind)}
                </Badge>
                <small>{date(n.created_at)}</small>
              </div>
              <h3>{n.title}</h3>
              <p className="pre-wrap">{n.body}</p>
              {n.delivery_error && (
                <p className="error-text">{n.delivery_error}</p>
              )}
              <div className="inline">
                <small>
                  {n.emailed_at
                    ? "Email delivered"
                    : "Available in your workspace"}
                </small>
                {!n.read && (
                  <button
                    className="text-button"
                    onClick={() =>
                      action.run(async () => {
                        await api(`/notifications/${n.id}/read`, {
                          method: "PATCH",
                        });
                        await client.invalidateQueries();
                      }, "Marked as read")
                    }
                  >
                    Mark read
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="You’re all caught up">
          Run an alert check or wait for your scheduled digest.
        </Empty>
      )}
    </>
  );
}
