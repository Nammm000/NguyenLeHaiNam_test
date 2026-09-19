import { expect, test } from "@playwright/test";
import { createTodo, registerAndLogin, uniqueEmail } from "./helpers";

test("full user journey: register, create, toggle, verify, logout", async ({
  page,
}) => {
  await registerAndLogin(page, uniqueEmail("journey"));

  await createTodo(page, "Journey todo item");
  const item = page.locator("[data-testid='todo-item']", {
    hasText: "Journey todo item",
  });
  await expect(item).toBeVisible();

  await item.getByTestId("todo-toggle").click();
  await expect(item.getByTestId("todo-title")).toHaveClass(/line-through/);

  await page.reload();
  const reloaded = page.locator("[data-testid='todo-item']", {
    hasText: "Journey todo item",
  });
  await expect(reloaded).toBeVisible();
  await expect(reloaded.getByTestId("todo-title")).toHaveClass(/line-through/);

  await page.getByTestId("logout-button").click();
  await page.waitForURL("/login");
  await expect(page.getByTestId("email-input")).toBeVisible();

  await page.goto("/");
  await page.waitForURL("/login");
});
