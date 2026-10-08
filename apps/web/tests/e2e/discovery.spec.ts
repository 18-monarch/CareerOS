import { test, expect } from "@playwright/test";

test("automatically discovers internships without adding sources or running commands", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_AUTODISCOVERY !== "true",
    "Requires background discovery fixture mode",
  );
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Automatic Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`automatic-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Automatic-test-password-123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Make your next move, Automatic." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Manage discovery" }).click();
  const discovery = page.getByRole("region", { name: "Automatic discovery" });
  await expect(
    discovery.getByRole("heading", { name: "Automatic discovery is on" }),
  ).toBeVisible({ timeout: 45000 });
  await expect(discovery).toContainText(
    "4 postings checked · 2 outside the starter-feed focus",
  );
  const source = page.getByRole("row", { name: /Fixture Company careers/ });
  await expect(source).toContainText("4 fetched · 1 added");
  await page.getByRole("link", { name: "Opportunities", exact: true }).click();
  await expect(page.locator(".job-card")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Software Engineer Intern", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Sources", exact: true }).click();
  await discovery.getByRole("button", { name: "Pause discovery" }).click();
  await expect(
    discovery.getByRole("heading", { name: "Paused", exact: true }),
  ).toBeVisible();
  await expect(
    discovery.getByRole("button", { name: "Check now" }),
  ).toBeDisabled();
  await page.reload();
  await expect(
    discovery.getByRole("heading", { name: "Paused", exact: true }),
  ).toBeVisible();
  await discovery.getByRole("button", { name: "Resume discovery" }).click();
  await expect(source).toContainText("4 fetched · 0 added", { timeout: 30000 });
  await page.screenshot({
    path: test.info().outputPath("automatic-discovery-desktop.png"),
    fullPage: true,
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(discovery).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: test.info().outputPath("automatic-discovery-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
