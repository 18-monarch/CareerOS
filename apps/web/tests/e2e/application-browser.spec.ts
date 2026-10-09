import { test, expect } from "@playwright/test";
import {
  fillLever,
  submitLever,
} from "../../../../scripts/application-browser.mjs";

const packet = {
  name: "Fixture Candidate",
  email: "fixture@example.com",
  phone: "",
  cover_letter: "Fixture cover letter",
  links: { GitHub: "https://example.com/fixture" },
  answers: {},
};
const resume = Buffer.from("%PDF-1.4\nFixture\n%%EOF").toString("base64");
const form = (extra = "") =>
  `<form><label>Full name<input name="name" required></label><label>Email<input name="email" type="email" required></label><input type="file" name="resume" required><textarea name="comments"></textarea>${extra}<button type="submit">Submit application</button></form><script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();const r=await fetch('/fixture-submit',{method:'POST'});if(r.ok)document.body.innerHTML='<h1>Thank you for applying</h1>';}</script>`;

test("local application adapter fills a form and requires confirmation after submission", async ({
  page,
}) => {
  let posts = 0;
  await page.route("https://jobs.lever.co/**", async (route) => {
    if (route.request().method() === "POST") {
      posts++;
      return route.fulfill({ status: 200, body: "ok" });
    }
    return route.fulfill({ contentType: "text/html", body: form() });
  });
  await page.goto(
    "https://jobs.lever.co/fixture/12345678-1234-1234-1234-123456789012/apply",
  );
  const filled = await fillLever(page, packet, resume);
  expect(filled.status).toBe("READY");
  expect(posts).toBe(0);
  expect(await page.locator("input[name=email]").inputValue()).toBe(
    packet.email,
  );
  const result = await submitLever(page);
  expect(result.status).toBe("SUBMITTED");
  expect(posts).toBe(1);
  expect((await submitLever(page)).status).toBe("HANDOFF");
  expect(posts).toBe(1);
});

test("local adapter hands off missing questions and CAPTCHA without submitting", async ({
  page,
}) => {
  await page.setContent(
    form(
      '<label>Available for six months? *<input name="availability"></label>',
    ),
  );
  expect((await fillLever(page, packet, resume)).status).toBe("HANDOFF");
  await page.setContent(form('<div class="g-recaptcha"></div>'));
  expect((await fillLever(page, packet, resume)).status).toBe("HANDOFF");
});
