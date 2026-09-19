import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import type { Tag } from "./tags";

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
  tags: Tag[];
}

interface TodoListResponse {
  items: Todo[];
  total: number;
  page: number;
  size: number;
}

interface CreateTodoRequest {
  title: string;
  description?: string;
}

interface UpdateTodoRequest {
  title?: string;
  description?: string;
  completed?: boolean;
}

export interface TodoFiltersState {
  status: string;
  tag_id: string;
  keyword: string;
  date_from: string;
  date_to: string;
}

export const EMPTY_FILTERS: TodoFiltersState = {
  status: "",
  tag_id: "",
  keyword: "",
  date_from: "",
  date_to: "",
};

export const TODO_PAGE_SIZE = 10;

export function buildTodosQueryKey(
  page: number,
  pageSize: number,
  filters: TodoFiltersState
) {
  return [
    "todos",
    {
      page,
      page_size: pageSize,
      status: filters.status,
      tag_id: filters.tag_id,
      keyword: filters.keyword,
      date_from: filters.date_from,
      date_to: filters.date_to,
    },
  ] as const;
}

export function useTodos(
  page: number = 1,
  pageSize: number = TODO_PAGE_SIZE,
  filters: TodoFiltersState = EMPTY_FILTERS
) {
  return useQuery({
    queryKey: buildTodosQueryKey(page, pageSize, filters),
    queryFn: async (): Promise<TodoListResponse> => {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      };
      if (filters.status) params.status = filters.status;
      if (filters.tag_id) params.tag_id = filters.tag_id;
      if (filters.keyword) params.keyword = filters.keyword;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      const response = await api.get("/todos", { params });
      return response.data;
    },
  });
}

export function useCreateTodo() {
  return useMutation({
    mutationFn: async (data: CreateTodoRequest): Promise<Todo> => {
      const response = await api.post("/todos", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Todo created successfully!");
    },
    onError: () => {
      toast.error("Failed to create todo");
    },
  });
}

export function useUpdateTodo() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateTodoRequest;
    }): Promise<Todo> => {
      const response = await api.put(`/todos/${id}`, data);
      return response.data;
    },
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: ["todos"] });

      const previousTodos = queryClient.getQueriesData<TodoListResponse>({
        queryKey: ["todos"],
      });

      queryClient.setQueriesData<TodoListResponse>({ queryKey: ["todos"] }, (old) =>
        old
          ? {
              ...old,
              items: old.items.map((todo) =>
                todo.id === id ? { ...todo, ...data } : todo
              ),
            }
          : old
      );

      return { previousTodos };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousTodos) {
        for (const [queryKey, previousData] of context.previousTodos) {
          queryClient.setQueryData(queryKey, previousData);
        }
      }
      toast.error("Failed to update todo");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
    },
  });
}

export function useDeleteTodo() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/todos/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Todo deleted successfully!");
    },
    onError: () => {
      toast.error("Failed to delete todo");
    },
  });
}

export function useToggleTodo() {
  const updateTodo = useUpdateTodo();

  return {
    ...updateTodo,
    mutate: (todo: Todo) => {
      updateTodo.mutate({
        id: todo.id,
        data: { completed: !todo.completed },
      });
    },
  };
}
