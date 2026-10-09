import { test, expect } from "@playwright/test";

test("hosted discovery queues without an API background thread", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_EXTERNAL_DISCOVERY !== "true",
    "Run the external-worker configuration separately",
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Hosted Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`hosted-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Hosted-password-12345");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.getByRole("link", { name: "Sources", exact: true }).click();
  const queue = page.getByRole("button", {
    name: "Queue a check",
    exact: true,
  });
  await expect(queue).toBeEnabled();
  await queue.click();
  await expect(
    page.getByText(/Check queued for the next hosted worker run/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Pause discovery", exact: true })
    .click();
  await page.reload();
  await expect(queue).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Resume discovery", exact: true }),
  ).toBeVisible();
});
