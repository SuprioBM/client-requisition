import { expect, test } from "@playwright/test";
import { installMockBackend, makeState } from "./mock-backend";

test("full operator flow: discover -> job -> prospect intelligence -> outreach approve/send", async ({
  page,
}) => {
  const state = makeState();
  await installMockBackend(page, state);

  // 1. dashboard
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: /New discovery/i })).toBeVisible();

  // 2. discovery form
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
  await page.getByRole("button", { name: "Preview plan" }).click();
  await expect(page.getByText("dental clinic")).toBeVisible();
  await page.getByRole("button", { name: "Start Discovery" }).click();

  // 3. job monitor (form navigates here on success)
  await expect(page).toHaveURL(/\/jobs\/job-1/, { timeout: 10000 });
  await expect(page.getByText("Pipeline")).toBeVisible();
  await expect(page.getByText(/prospects created/i)).toBeVisible();

  // 4. prospect intelligence
  await page.goto("/prospects/p1");
  await expect(page.getByRole("heading", { name: "ABC Dental" })).toBeVisible();
  await expect(
    page.getByText("No online booking mechanism was identified on the researched pages.").first(),
  ).toBeVisible(); // evidence
  await expect(page.getByText("No online booking flow").first()).toBeVisible(); // pain point
  await expect(page.getByText("Booking Systems")).toBeVisible(); // solution
  await expect(page.getByText("78", { exact: true })).toBeVisible(); // score ring total
  await expect(page.getByText("Problem Severity")).toBeVisible();

  // 5. outreach review + approve (with confirmation) + send
  await page.goto("/outreach/m1");
  await expect(page.getByText("A quick note about online booking")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approve this message?")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("button", { name: /Send message/i })).toBeVisible();
  await page.getByRole("button", { name: /Send message/i }).click();
  await expect(page.getByText(/no sending provider is configured/i)).toBeVisible();
});

test("backend unavailable shows a retry-able error, not a blank screen", async ({ page }) => {
  await page.route("**/api/backend/**", (route) =>
    route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        data: null,
        error: { code: "BACKEND_UNREACHABLE", message: "down" },
      }),
    }),
  );
  await page.goto("/prospects");
  await expect(page.getByText(/Unable to load data|Backend unavailable/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
