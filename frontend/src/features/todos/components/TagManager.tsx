import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useCreateTag, useDeleteTag, useTags, useUpdateTag } from "../api/tags";
import { TagForm } from "./TagForm";

interface TagManagerProps {
  open: boolean;
  onClose: () => void;
}

export function TagManager({ open, onClose }: TagManagerProps) {
  const { data, isLoading } = useTags();
  const createTag = useCreateTag();
  const updateTag = useUpdateTag();
  const deleteTag = useDeleteTag();
  const [editingId, setEditingId] = useState<string | null>(null);

  const tags = data?.items ?? [];

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle data-testid="tag-manager-title">Manage Tags</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <TagForm
            testIdPrefix="tag-create"
            submitLabel="Create tag"
            submitting={createTag.isPending}
            onSubmit={(values) =>
              createTag.mutate({
                name: values.name,
                color: values.color || null,
              })
            }
          />

          <Separator />

          <div className="space-y-2 max-h-72 overflow-y-auto" data-testid="tag-manager-list">
            {isLoading && (
              <p className="text-sm text-muted-foreground">Loading tags...</p>
            )}
            {!isLoading && tags.length === 0 && (
              <p className="text-sm text-muted-foreground">No tags yet</p>
            )}
            {tags.map((tag) => (
              <div
                key={tag.id}
                className="flex items-center justify-between gap-2 rounded-md border p-2"
                data-testid={`tag-row-${tag.id}`}
              >
                {editingId === tag.id ? (
                  <div className="flex-1">
                    <TagForm
                      testIdPrefix="tag-edit"
                      submitLabel="Save"
                      defaultValues={{ name: tag.name, color: tag.color ?? "" }}
                      submitting={updateTag.isPending}
                      onSubmit={(values) => {
                        updateTag.mutate(
                          {
                            id: tag.id,
                            data: { name: values.name, color: values.color || null },
                          },
                          { onSuccess: () => setEditingId(null) }
                        );
                      }}
                    />
                  </div>
                ) : (
                  <>
                    <Badge
                      variant="secondary"
                      style={
                        tag.color ? { backgroundColor: tag.color } : undefined
                      }
                    >
                      {tag.name}
                    </Badge>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        data-testid={`tag-edit-button-${tag.id}`}
                        onClick={() => setEditingId(tag.id)}
                        aria-label={`Rename tag ${tag.name}`}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:text-destructive"
                        data-testid={`tag-delete-button-${tag.id}`}
                        onClick={() => deleteTag.mutate(tag.id)}
                        aria-label={`Delete tag ${tag.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
