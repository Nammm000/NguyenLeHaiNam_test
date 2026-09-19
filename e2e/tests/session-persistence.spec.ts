import { expect, test } from "@playwright/test";
import { registerAndLogin, uniqueEmail } from "./helpers";

test("session survives page reload via silent cookie refresh", async ({
  page,
}) => {
  await registerAndLogin(page, uniqueEmail("session"));

  // Memory access token is gone on reload; the HttpOnly refresh cookie
  // must silently restore the session without bouncing to /login.
  await page.reload();
  await page.waitForURL("/");
  await expect(page.getByTestId("logout-button")).toBeVisible();

  // Logout clears the cookie server-side: next reload is unauthenticated.
  await page.getByTestId("logout-button").click();
  await page.waitForURL("/login");
  await page.reload();
  await page.waitForURL("/login");
  await expect(page.getByTestId("email-input")).toBeVisible();
});
