import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { tagSchema, type TagFormData } from "../schemas/tag";

interface TagFormProps {
  onSubmit: (data: TagFormData) => void;
  submitting?: boolean;
  defaultValues?: Partial<TagFormData>;
  submitLabel?: string;
  testIdPrefix?: string;
}

export function TagForm({
  onSubmit,
  submitting = false,
  defaultValues,
  submitLabel = "Save",
  testIdPrefix = "tag-form",
}: TagFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<TagFormData>({
    resolver: zodResolver(tagSchema),
    defaultValues: {
      name: defaultValues?.name ?? "",
      color: defaultValues?.color ?? "",
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor={`${testIdPrefix}-name`}>Name</Label>
        <Input
          id={`${testIdPrefix}-name`}
          placeholder="e.g. Work"
          data-testid={`${testIdPrefix}-name`}
          {...register("name")}
        />
        {errors.name && (
          <p className="text-sm text-destructive" data-testid={`${testIdPrefix}-name-error`}>
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor={`${testIdPrefix}-color`}>Color (optional)</Label>
        <Input
          id={`${testIdPrefix}-color`}
          placeholder="#3b82f6"
          data-testid={`${testIdPrefix}-color`}
          {...register("color")}
        />
        {errors.color && (
          <p className="text-sm text-destructive">{errors.color.message}</p>
        )}
      </div>

      <Button type="submit" data-testid={`${testIdPrefix}-submit`} disabled={submitting}>
        {submitting ? "Saving..." : submitLabel}
      </Button>
    </form>
  );
}
