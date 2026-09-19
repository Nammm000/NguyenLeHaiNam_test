import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface Tag {
  id: string;
  name: string;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface TagListResponse {
  items: Tag[];
}

export interface TagInput {
  name: string;
  color?: string | null;
}

export function useTags() {
  return useQuery({
    queryKey: ["tags"],
    queryFn: async (): Promise<TagListResponse> => {
      const response = await api.get("/tags");
      return response.data;
    },
  });
}

export function useCreateTag() {
  return useMutation({
    mutationFn: async (data: TagInput): Promise<Tag> => {
      const response = await api.post("/tags", data);
      return response.data;
    },
    onSuccess: (tag) => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast.success(`Tag "${tag.name}" created`);
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      toast.error(detail || "Failed to create tag");
    },
  });
}

export function useUpdateTag() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: TagInput;
    }): Promise<Tag> => {
      const response = await api.patch(`/tags/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      // Cached todo lists embed tag chips.
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Tag updated");
    },
    onError: () => {
      toast.error("Failed to update tag");
    },
  });
}

export function useDeleteTag() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/tags/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      // Cached todo lists embed tag chips.
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Tag deleted");
    },
    onError: () => {
      toast.error("Failed to delete tag");
    },
  });
}

export function useAttachTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      todoId,
      tagId,
    }: {
      todoId: string;
      tagId: string;
    }): Promise<void> => {
      await api.post(`/todos/${todoId}/tags`, { tag_id: tagId });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["todos"] });
    },
    onError: () => {
      toast.error("Failed to attach tag");
    },
  });
}

export function useDetachTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      todoId,
      tagId,
    }: {
      todoId: string;
      tagId: string;
    }): Promise<void> => {
      await api.delete(`/todos/${todoId}/tags/${tagId}`);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["todos"] });
    },
    onError: () => {
      toast.error("Failed to detach tag");
    },
  });
}

interface BulkStatusContext {
  previous: Array<[readonly unknown[], unknown]>;
}

export function useBulkStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      todoIds,
      completed,
    }: {
      todoIds: string[];
      completed: boolean;
    }): Promise<{ updated: number; requested: number }> => {
      const response = await api.patch("/todos/bulk-status", {
        todo_ids: todoIds,
        completed,
      });
      return response.data;
    },
    onMutate: async ({ todoIds, completed }) => {
      await qc.cancelQueries({ queryKey: ["todos"] });
      const previous = qc.getQueriesData({ queryKey: ["todos"] });
      qc.setQueriesData({ queryKey: ["todos"] }, (old: unknown) => {
        if (!old || typeof old !== "object") return old;
        const list = old as {
          items: Array<{ id: string; completed: boolean }>;
        };
        return {
          ...list,
          items: list.items.map((todo) =>
            todoIds.includes(todo.id) ? { ...todo, completed } : todo
          ),
        };
      });
      return { previous } as BulkStatusContext;
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        for (const [queryKey, previousData] of context.previous) {
          qc.setQueryData(queryKey, previousData);
        }
      }
      toast.error("Failed to update todos");
    },
    onSuccess: (result) => {
      toast.success(`Updated ${result.updated} of ${result.requested} todos`);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["todos"] });
    },
  });
}
