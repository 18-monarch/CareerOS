// Local, bounded Lever adapter. No employer API keys or CAPTCHA bypasses.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import { pathToFileURL } from "node:url";

export async function fillLever(page, packet, resume) {
  const fields = {
    name: packet.name,
    email: packet.email,
    phone: packet.phone,
    comments: packet.cover_letter,
  };
  for (const [name, value] of Object.entries(fields)) {
    const field = page.locator(
      `input[name="${name}"],textarea[name="${name}"]`,
    );
    if (value && (await field.count()) === 1 && (await field.isVisible()))
      await field.fill(value);
  }
  for (const [label, value] of Object.entries(packet.links || {})) {
    const inputs = page.locator("input");
    for (const input of await inputs.all()) {
      const name = ((await input.getAttribute("name")) || "").toLowerCase();
      if (name === `urls[${label.toLowerCase()}]` && (await input.isVisible()))
        await input.fill(value);
    }
  }
  const upload = page.locator('input[type="file"][name="resume"]');
  if ((await upload.count()) === 1)
    await upload.setInputFiles({
      name: "resume.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from(resume, "base64"),
    });
  else
    return {
      status: "HANDOFF",
      reason:
        "This form does not expose the supported resume field. Open it manually.",
    };
  for (const input of await page
    .locator('input:not([type="hidden"]):not([type="file"]),textarea,select')
    .all()) {
    if (!(await input.isVisible())) continue;
    const label = await input.evaluate(
      (e) =>
        e.labels?.[0]?.innerText?.trim() ||
        e.getAttribute("aria-label") ||
        e.name ||
        "",
    );
    const answer = packet.answers?.[label];
    const type = await input.getAttribute("type");
    // Agreements, demographics, assessments and radio/checkbox choices stay with the candidate.
    if (
      answer !== undefined &&
      !["checkbox", "radio", "submit", "button"].includes(type)
    ) {
      const tag = await input.evaluate((e) => e.tagName);
      if (tag === "SELECT") await input.selectOption({ label: answer });
      else await input.fill(answer);
    }
  }
  if (
    await page
      .locator(
        'iframe[src*="recaptcha"],iframe[src*="hcaptcha"],iframe[src*="challenges.cloudflare"],.g-recaptcha,.h-captcha',
      )
      .count()
  )
    return {
      status: "HANDOFF",
      reason:
        "A CAPTCHA or verification challenge requires you to continue on the employer site.",
    };
  const incomplete = await page
    .locator("input,textarea,select")
    .evaluateAll((elements) =>
      elements
        .filter((e) => {
          if (!e.getClientRects().length) return false;
          const required =
            e.required ||
            e.getAttribute("aria-required") === "true" ||
            e.closest(".application-question")?.querySelector(".required") ||
            /\*/.test(e.labels?.[0]?.innerText || "");
          if (!required) return false;
          if (e.type === "checkbox") return !e.checked;
          if (e.type === "radio")
            return !elements.some(
              (other) => other.name === e.name && other.checked,
            );
          if (e.type === "file") return !e.files?.length;
          return !e.value?.trim() || !e.checkValidity();
        })
        .map(
          (e) =>
            e.labels?.[0]?.innerText?.trim() || e.name || "Required question",
        ),
    );
  if (incomplete.length)
    return {
      status: "HANDOFF",
      reason:
        "Answer required questions on the employer form: " +
        incomplete.join("; "),
    };
  const unanswered = await page
    .locator('[aria-required="true"],.application-question.required')
    .evaluateAll(
      (els) =>
        els.filter(
          (e) =>
            e.getClientRects().length &&
            !e.querySelector("input,textarea,select") &&
            !["INPUT", "TEXTAREA", "SELECT"].includes(e.tagName),
        ).length,
    );
  if (unanswered)
    return {
      status: "HANDOFF",
      reason:
        "Unsupported required question widget; complete the application manually.",
    };
  const filledEmail = page.locator('input[name="email"]');
  if (
    (await filledEmail.count()) !== 1 ||
    (await filledEmail.inputValue()) !== packet.email
  )
    return {
      status: "HANDOFF",
      reason: "Could not verify candidate email in form.",
    };
  return {
    status: "READY",
    reason: "Known fields filled; browser validity checks passed.",
  };
}

export async function submitLever(page) {
  const confirmation =
    /thank you for applying|application (?:has been )?(?:received|submitted)|we have received your application/i;
  if (confirmation.test(await page.locator("body").innerText()))
    return {
      status: "HANDOFF",
      reason:
        "Page already contains confirmation text; check the existing application.",
    };
  const button = page.getByRole("button", { name: /^submit application$/i });
  if ((await button.count()) !== 1)
    return { status: "HANDOFF", reason: "Supported submit button not found." };
  try {
    await button.click({ timeout: 10000 });
    await page.waitForFunction(
      () =>
        /thank you for applying|application (?:has been )?(?:received|submitted)|we have received your application/i.test(
          document.body.innerText,
        ),
      {},
      { timeout: 20000 },
    );
    return {
      status: "SUBMITTED",
      reason: "Employer page displayed an application confirmation.",
      confirmation: (await page.locator("body").innerText()).match(
        confirmation,
      )?.[0],
      url: page.url(),
    };
  } catch {
    return {
      status: "UNCERTAIN",
      reason:
        "Submit was attempted, but no reliable confirmation was observed. Check email/employer site before any retry.",
    };
  }
}

async function main() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  const task = JSON.parse(input);
  const url = new URL(task.url);
  if (
    url.protocol !== "https:" ||
    url.hostname !== "jobs.lever.co" ||
    url.username ||
    url.password ||
    !/^\/[A-Za-z0-9_.-]+\/[a-f0-9-]{36}(\/apply)?\/?$/i.test(url.pathname)
  )
    throw new Error("Unsupported application URL");
  if (!url.pathname.endsWith("/apply"))
    url.pathname = url.pathname.replace(/\/$/, "") + "/apply";
  const browser = await chromium.launch({
    headless: task.headless !== false,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH
      ? {
          executablePath: process.env.CHROMIUM_EXECUTABLE_PATH,
          args: ["--no-sandbox", "--disable-dev-shm-usage"],
        }
      : {}),
  });
  try {
    const page = await browser.newPage();
    await page.route("**/*", async (route) => {
      const request = route.request();
      if (
        request.isNavigationRequest() &&
        request.frame() === page.mainFrame() &&
        new URL(request.url()).hostname !== "jobs.lever.co"
      )
        return route.abort();
      return route.continue();
    });
    await page.goto(url.href, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
    let result = await fillLever(page, task.packet, task.resume);
    if (result.status === "READY" && task.submit)
      result = await submitLever(page);
    else if (result.status === "READY")
      result = {
        status: "PREVIEWED",
        reason: "Fields filled and validated. No submission attempted.",
      };
    process.stdout.write(JSON.stringify(result) + "\n");
  } finally {
    await browser.close();
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  main().catch(() => {
    process.stdout.write(
      JSON.stringify({
        status: "UNCERTAIN",
        reason:
          "Browser runner stopped unexpectedly. Check employer site before retrying.",
      }) + "\n",
    );
    process.exitCode = 1;
  });
