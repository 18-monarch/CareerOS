import { test, expect } from "@playwright/test";

test("source ingestion, review, archive persistence and account maintenance", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_FIXTURE_FEED !== "1",
    "Requires isolated external-feed fixtures",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const email = `source-${Date.now()}@example.com`,
    password = "Source-workflow-password-123";
  const button = (name: string) =>
    page.getByRole("button", { name, exact: true });
  const field = (name: string) => page.getByLabel(name, { exact: true });
  const navigate = (name: string) =>
    page.getByRole("link", { name, exact: true }).click();
  await page.goto("/");
  await button("New here? Create an account").click();
  await field("Name").fill("Source Tester");
  await field("Email").fill(email);
  await field("Password").fill(password);
  await button("Create account").click();
  await expect(
    page.getByRole("heading", { name: "Make your next move, Source." }),
  ).toBeVisible();
  await navigate("My profile");
  await field("Graduation Year").fill("2028");
  await field("Cgpa").fill("7.38");
  await field("Work Authorizations").fill("India");
  await button("Save changes").click();
  await expect(page.getByRole("status").first()).toHaveText("Saved");
  await field("Skill name").fill("Python");
  await button("Add skill").click();
  await expect(page.getByText("python", { exact: true })).toBeVisible();
  await navigate("Sources");
  await field("Source name").fill("Fixture Careers");
  await field("Board token").fill("careeros-missing");
  await field("Company").fill("Fixture Company");
  await field("Country").fill("India");
  await button("Connect source").click();
  const row = page.getByRole("row", { name: /Fixture Careers/ });
  const run = () => row.getByRole("button", { name: "Run now" }).click();
  await run();
  await expect(row.getByText("Failed", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: "Edit", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Board token", { exact: true })
    .fill("careeros-fixture");
  await dialog
    .getByLabel("Close missing jobs", { exact: true })
    .selectOption("2");
  await dialog.getByRole("button", { name: "Save source" }).click();
  await expect(dialog).toHaveCount(0);
  await run();
  await expect(row.getByText("Healthy", { exact: true })).toBeVisible();
  await expect(row).toContainText("2 fetched · 1 added");
  await run();
  await expect(row).toContainText("2 fetched · 0 added");
  await navigate("Opportunities");
  await expect(page.locator(".job-card")).toHaveCount(1);
  await button("Software Engineer Intern").click();
  await expect(
    page.getByText("Review Required", { exact: true }),
  ).toBeVisible();
  await button("Review / edit facts").click();
  await dialog.getByRole("checkbox").check();
  await button("Save and evaluate eligibility").click();
  await expect(page.getByText("Eligible", { exact: true })).toBeVisible();
  await expect(page.getByText("docker", { exact: true })).toBeVisible();
  await button("Archive").click();
  await expect(button("Restore")).toBeVisible();
  await button("Close dialog").click();
  await navigate("Sources");
  await run();
  await expect(page.getByRole("status")).toContainText("Ingestion finished");
  await navigate("Opportunities");
  await button("Software Engineer Intern").click();
  await expect(page.getByText("Closed", { exact: true })).toBeVisible();
  await button("Restore").click();
  await expect(page.getByText("Eligible", { exact: true })).toBeVisible();
  await button("Save opportunity").click();
  await expect(button("Tracked: Saved")).toBeDisabled();
  await button("Close dialog").click();
  await navigate("Applications");
  await button("Update").click();
  await field("Status").selectOption("APPLIED");
  await button("Update application").click();
  await expect(dialog).toHaveCount(0);
  await navigate("My profile");
  await field("Resume name").fill("Master resume");
  await button("Add resume metadata").click();
  const resume = page.locator(".list-row").filter({ hasText: "Master resume" });
  await resume.getByRole("button", { name: "Edit", exact: true }).click();
  await field("Version").fill("2");
  await button("Update resume metadata").click();
  await expect(resume).toContainText("v2");
  await field("Current password").fill(password);
  await field("New password").fill(password + "-new");
  await field("Confirm new password").fill(password + "-new");
  await button("Change password").click();
  await expect(
    page.getByText("Password changed. Other sessions have been signed out."),
  ).toBeVisible();
  await button("Sign out").click();
  await field("Email").fill(email);
  await field("Password").fill(password + "-new");
  await button("Sign in").click();
  await expect(
    page.getByRole("heading", { name: "Make your next move, Source." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
