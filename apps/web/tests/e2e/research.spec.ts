import { test, expect } from "@playwright/test";

test("research → category filter → PDF → application review persists", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const email = `research-${Date.now()}@example.com`;
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Research Tester");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Research-password-12345");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Make your next move, Research." }),
  ).toBeVisible();
  const created = await page.evaluate(async () => {
    const csrf = document.cookie
      .split("; ")
      .find((x) => x.startsWith("career_csrf="))!
      .split("=")[1];
    const write = async (path: string, body: unknown, method = "POST") => {
      const r = await fetch("/api" + path, {
        method,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    };
    const job = await write("/jobs", {
      company_name: "Fixture design studio",
      title: "Product Design Intern",
      country: "India",
      description:
        "Figma, user research and prototyping. Fixture for browser tests.",
      required_skills: ["Figma"],
      application_url:
        "https://jobs.lever.co/fixture/12345678-1234-1234-1234-123456789012/apply",
    });
    const profile = await (await fetch("/api/profile")).json();
    delete profile.email;
    await write(
      "/profile",
      {
        ...profile,
        external_profiles: {
          portfolio: "https://example.com/fixture-portfolio",
        },
        work_authorizations: ["India"],
      },
      "PUT",
    );
    const resume = await write("/resumes", {
      name: "Design portfolio resume",
      file_name: "design.pdf",
    });
    await write(
      `/resumes/${resume.id}/pdf`,
      { content_base64: btoa("%PDF-1.4\nFixture browser test\n%%EOF") },
      "PUT",
    );
    await write(
      "/application-settings",
      { design_resume_id: resume.id },
      "PUT",
    );
    return { job: job.id, resume: resume.id };
  });
  expect(created.job).toBeTruthy();
  await page
    .getByRole("link", { name: "Internship brief", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your internship brief" }),
  ).toBeVisible();
  await expect(
    page.getByText("Company feeds active · broad web search not connected"),
  ).toBeVisible();
  await page
    .getByLabel("Career category", { exact: true })
    .selectOption("design");
  await expect(
    page.getByRole("button", { name: "Product Design Intern", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Prepare application", exact: true })
    .click();
  await expect(
    page.getByText("Draft prepared. Open Application desk to review it."),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Application desk", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Application desk", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Design portfolio resume", { exact: false }).last(),
  ).toBeVisible();
  const approve = page.getByRole("button", {
    name: "Approve this application",
  });
  await expect(approve).toBeDisabled();
  await page
    .getByLabel("I reviewed this exact packet", { exact: false })
    .check();
  await approve.click();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("application-desk-desktop.png"),
    fullPage: true,
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: test.info().outputPath("application-desk-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
