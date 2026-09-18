import { expect, test } from "@playwright/test";
import { createTodo, registerAndLogin, uniqueEmail } from "./helpers";

test("cross-user data isolation", async ({ browser }) => {
  const secretTitle = `SECRET-${Date.now()}`;

  const contextA = await browser.newContext();
  const pageA = await contextA.newPage();
  await registerAndLogin(pageA, uniqueEmail("alice"));
  await createTodo(pageA, secretTitle);
  await expect(
    pageA.locator("[data-testid='todo-item']", { hasText: secretTitle })
  ).toBeVisible();
  await contextA.close();

  const contextB = await browser.newContext();
  const pageB = await contextB.newPage();
  await registerAndLogin(pageB, uniqueEmail("bob"));

  await expect(pageB.getByText("No todos yet")).toBeVisible();
  await expect(pageB.locator("[data-testid='todo-item']")).toHaveCount(0);
  await expect(pageB.getByText(secretTitle)).toHaveCount(0);
  await contextB.close();
});
