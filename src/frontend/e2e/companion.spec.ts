import { expect, test } from "@playwright/test";

const apiOrigin = (process.env.PLAYWRIGHT_API_BASE_URL || "").replace(/\/$/, "");

test("deployed event guide renders a real grounded answer and source", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "Requires the real deployed Foundry agent.");
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.getByLabel("Your event question").fill("When does the live demonstration start?");
  const response = page.waitForResponse(
    response => response.url().endsWith("/api/assistant")
      && response.request().method() === "POST",
    { timeout: 75_000 },
  );
  await page.getByRole("button", { name: "Ask the guide", exact: true }).click();
  const result = await response;
  expect(result.ok()).toBe(true);
  expect(await result.json()).toMatchObject({
    refused: false,
    citations: [{ source_id: "session:meeting-to-pull-request" }],
  });
  await expect(page.locator(".assistant-answer")).toContainText("13:27");
  const source = page.locator(".assistant-answer .sources").getByRole("button", {
    name: "Ubiquitous Innovation with GitHub, Copilot & Foundry",
  });
  await expect(source).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../../.local/companion-assistant-mobile.png", fullPage: true });
  await source.click();
  await expect(page.getByRole("heading", { name: "Explore the sessions." })).toBeVisible();
});

test("mobile attendee can ask, vote, and privately suggest a feature", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Cloud & AI Day");
  await page.getByRole("button", { name: "Live questions", exact: true }).click();
  const question = `How do governed skills work? ${Date.now()}`;
  await page.getByLabel("Ask a question about this session").fill(question);
  const saved = page.waitForResponse(response =>
    response.url().endsWith("/api/sessions/meeting-to-pull-request/questions")
    && response.request().method() === "POST");
  await page.getByRole("button", { name: "Post question", exact: true }).click();
  expect((await saved).ok()).toBe(true);
  await expect(page.locator(".question-card").filter({ hasText: question })).toBeVisible();
  const vote = page.getByRole("button", { name: `Upvote: ${question}`, exact: true });
  await vote.click();
  await expect(vote).toHaveAttribute("aria-pressed", "true");
  await expect(vote).toContainText("1");
  await page.reload();
  await page.getByRole("button", { name: "Live questions", exact: true }).click();
  await expect(page.getByText(question, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Suggest a feature", exact: true }).click();
  await page.getByLabel("Your idea in a few words").fill("A venue map");
  await page.getByLabel("Tell us a little more").fill("Help attendees find each session room.");
  await page.getByRole("button", { name: "Send your idea", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Your idea is saved.");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../../.local/companion-mobile.png", fullPage: true });
});

test("desktop agenda and warm API remain responsive at ten concurrent readers", async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 1000 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Explore the sessions." })).toBeVisible();
  const warm = await page.request.get(`${apiOrigin}/api/sessions/meeting-to-pull-request/questions`);
  expect(warm.ok()).toBe(true);
  const durations = await Promise.all(Array.from({ length: 10 }, async () => {
    const start = performance.now();
    const response = await page.request.get(`${apiOrigin}/api/sessions/meeting-to-pull-request/questions`);
    expect(response.ok()).toBe(true);
    return performance.now() - start;
  }));
  durations.sort((a, b) => a - b);
  expect(durations[Math.ceil(durations.length * 0.95) - 1]).toBeLessThan(1000);
  await page.screenshot({ path: "../../.local/companion-desktop.png", fullPage: true });
});
