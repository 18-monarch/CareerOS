import { test, expect } from "@playwright/test";
const password = "Browser-test-password-123";
test("complete private career workflow on desktop and mobile", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Workflow Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`workflow-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Make your next move, Workflow." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "My profile", exact: true }).click();
  await page.getByLabel("University", { exact: true }).fill("Nirma University");
  await page.getByLabel("Degree", { exact: true }).fill("B.Tech");
  await page.getByLabel("Branch", { exact: true }).fill("CSE");
  await page.getByLabel("Graduation Year", { exact: true }).fill("2028");
  await page.getByLabel("Cgpa", { exact: true }).fill("7.38");
  await page.getByLabel("Semester", { exact: true }).fill("5");
  await page.getByLabel("Work Authorizations").fill("India");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("status").first()).toContainText("Saved");
  await page.getByLabel("Skill name", { exact: true }).fill("Python");
  await page.getByLabel("Proficiency (0–5)").fill("3");
  await page.getByRole("button", { name: "Add skill", exact: true }).click();
  await expect(page.getByText("python", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Opportunities", exact: true }).click();
  await page
    .getByRole("button", { name: "Add opportunity", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Company", { exact: true })
    .fill("Verified Workflow Co");
  await dialog
    .getByLabel("Role title", { exact: true })
    .fill("Software Engineer Intern");
  await dialog.getByLabel("Required skills (comma separated)").fill("Python");
  await dialog.getByLabel("Preferred skills (comma separated)").fill("Docker");
  await dialog.getByLabel("Structured eligibility requirements").fill(
    JSON.stringify({
      minimum_cgpa: 7,
      allowed_graduation_years: [2028],
      minimum_experience: 0,
    }),
  );
  const deadline = new Date(Date.now() + 2 * 86400000)
    .toISOString()
    .slice(0, 16);
  await dialog.getByLabel("Deadline (your local time)").fill(deadline);
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "Save and evaluate eligibility" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Software Engineer Intern", exact: true })
    .click();
  await expect(page.getByText("Eligible", { exact: true })).toBeVisible();
  await expect(page.getByText("How the score adds up")).toBeVisible();
  await expect(page.getByText("docker", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Save opportunity", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Tracked: Saved" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("link", { name: "Notifications", exact: true }).click();
  await page.getByRole("button", { name: "Check alerts" }).click();
  await expect(
    page.getByRole("heading", { name: /Apply within 3 day/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Applications", exact: true }).click();
  for (const status of [
    "APPLIED",
    "OA_RECEIVED",
    "OA_COMPLETED",
    "INTERVIEW",
  ]) {
    await page.getByRole("button", { name: "Update", exact: true }).click();
    await page.getByLabel("Status", { exact: true }).selectOption(status);
    await page.getByRole("button", { name: "Update application" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  await page.getByRole("button", { name: "Update", exact: true }).click();
  await expect(page.locator(".timeline li")).toHaveCount(5);
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(
    page.locator(".pipeline-stats").getByText("1", { exact: true }),
  ).toHaveCount(3);
  await page.getByRole("link", { name: "Learn → Apply", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Docker", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Notifications", exact: true }).click();
  await page.getByRole("button", { name: "Check alerts" }).click();
  await expect(
    page.getByRole("heading", { name: "Your daily career digest" }),
  ).toBeVisible();
  for (const route of [
    "/projects",
    "/dsa",
    "/campus",
    "/sources",
    "/market",
    "/profile",
    "/applications",
    "/opportunities",
  ]) {
    await page.goto(route);
    await expect(page.locator("#main h1")).toBeVisible();
    await expect(page.locator("[data-nextjs-dialog]")).toHaveCount(0);
  }
  await page.goto("/");
  await page.screenshot({
    path: testInfo.outputPath("dashboard-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Opportunities", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Opportunities", exact: true }),
  ).toBeVisible();
  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(widths.content).toBeLessThanOrEqual(widths.viewport);
  await page.screenshot({
    path: testInfo.outputPath("opportunities-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("seed login, imported demo jobs and responsive navigation", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page
    .getByLabel("Email", { exact: true })
    .fill(process.env.DEMO_EMAIL || "mohit@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.DEMO_PASSWORD || "CareerOS-local-demo-2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Make your next move, Mohit." }),
  ).toBeVisible();
  await expect(page.getByText(/synthetic opportunities/)).toBeVisible();
  await expect(page.locator(".job-card")).toHaveCount(4);
  await page.screenshot({
    path: testInfo.outputPath("seed-dashboard-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({
    path: testInfo.outputPath("seed-dashboard-light.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await page.screenshot({
    path: testInfo.outputPath("seed-dashboard-mobile.png"),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
