import { z } from "zod";

export const tagSchema = z.object({
  name: z.string().min(1, "Name is required").max(50, "Max 50 characters"),
  color: z
    .string()
    .max(20, "Max 20 characters")
    .optional()
    .or(z.literal("")),
});

export type TagFormData = z.infer<typeof tagSchema>;
