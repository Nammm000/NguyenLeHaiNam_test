import { useState } from "react";
import { CheckCircle2, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { TodoItem } from "./TodoItem";
import { TodoForm } from "./TodoForm";
import type { Todo } from "../api/todos";
import { useDeleteTodo, useToggleTodo } from "../api/todos";
import { useBulkStatus } from "../api/tags";

interface TodoListProps {
  todos: Todo[];
  selectedIds: Set<string>;
  onSelect: (id: string, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
}

export function TodoList({
  todos,
  selectedIds,
  onSelect,
  onSelectAll,
}: TodoListProps) {
  const [editingTodo, setEditingTodo] = useState<Todo | null>(null);
  const deleteTodo = useDeleteTodo();
  const toggleTodo = useToggleTodo();
  const bulkStatus = useBulkStatus();

  const allSelected = todos.length > 0 && todos.every((t) => selectedIds.has(t.id));
  const hasSelection = selectedIds.size > 0;

  const handleBulk = (completed: boolean) => {
    bulkStatus.mutate({ todoIds: Array.from(selectedIds), completed });
    onSelectAll(false);
  };

  if (todos.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground" data-testid="todo-empty">
        <p className="text-lg">No todos found</p>
        <p className="text-sm mt-1">
          Create your first todo or adjust the filters
        </p>
      </div>
    );
  }

  return (
    <>
      <div
        className="flex items-center justify-between gap-2 mb-2 px-3 py-2 rounded-md bg-muted/40"
        data-testid="bulk-bar"
      >
        <div className="flex items-center gap-2">
          <Checkbox
            aria-label="Select all todos on this page"
            data-testid="bulk-select-all"
            checked={allSelected}
            onCheckedChange={(checked) => onSelectAll(checked === true)}
          />
          <span className="text-xs text-muted-foreground">
            {hasSelection
              ? `${selectedIds.size} selected`
              : "Select all on page"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            data-testid="bulk-complete"
            disabled={!hasSelection || bulkStatus.isPending}
            onClick={() => handleBulk(true)}
          >
            <CheckCircle2 className="h-4 w-4 mr-1" />
            Mark completed
          </Button>
          <Button
            variant="outline"
            size="sm"
            data-testid="bulk-active"
            disabled={!hasSelection || bulkStatus.isPending}
            onClick={() => handleBulk(false)}
          >
            <Circle className="h-4 w-4 mr-1" />
            Mark active
          </Button>
        </div>
      </div>

      <div className="space-y-2" data-testid="todo-list">
        {todos.map((todo) => (
          <TodoItem
            key={todo.id}
            todo={todo}
            selected={selectedIds.has(todo.id)}
            onSelect={onSelect}
            onToggle={(t) => toggleTodo.mutate(t)}
            onEdit={(t) => setEditingTodo(t)}
            onDelete={(id) => deleteTodo.mutate(id)}
          />
        ))}
      </div>

      {editingTodo && (
        <TodoForm
          mode="edit"
          todo={editingTodo}
          open={!!editingTodo}
          onClose={() => setEditingTodo(null)}
        />
      )}
    </>
  );
}
