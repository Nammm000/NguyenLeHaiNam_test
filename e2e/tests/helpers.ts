import type { Page } from "@playwright/test";

export function uniqueEmail(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@test.com`;
}

export async function registerAndLogin(
  page: Page,
  email: string,
  password = "Test@1234"
): Promise<void> {
  await page.goto("/register");
  await page.getByTestId("email-input").fill(email);
  await page.getByTestId("password-input").fill(password);
  await page.getByTestId("confirm-password-input").fill(password);
  await page.getByTestId("auth-submit").click();
  await page.waitForURL("/");
}

export async function createTodo(page: Page, title: string): Promise<void> {
  await page.getByTestId("add-todo-button").click();
  await page.getByTestId("todo-title-input").fill(title);
  await page.getByTestId("todo-submit").click();
}
