import { useState } from "react";
import { ChevronLeft, ChevronRight, LogOut, Plus, Tags } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  EMPTY_FILTERS,
  TODO_PAGE_SIZE,
  useTodos,
  type TodoFiltersState,
} from "../api/todos";
import { TodoList } from "./TodoList";
import { TodoForm } from "./TodoForm";
import { TodoFilters } from "./TodoFilters";
import { TagManager } from "./TagManager";
import { useAuth } from "@/features/auth/hooks/useAuth";

export function TodoPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showTagManager, setShowTagManager] = useState(false);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<TodoFiltersState>(EMPTY_FILTERS);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const { data, isLoading, error } = useTodos(page, TODO_PAGE_SIZE, filters);
  const { user, logout } = useAuth();

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  const handleFiltersChange = (next: TodoFiltersState) => {
    setFilters(next);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleSelect = (id: string, selected: boolean) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (selected) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  };

  const handleSelectAll = (selected: boolean) => {
    if (!selected || !data) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(data.items.map((todo) => todo.id)));
  };

  return (
    <div className="min-h-screen bg-muted/40">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Todo App</h1>
            {user && (
              <p className="text-sm text-muted-foreground">{user.email}</p>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowTagManager(true)}
              data-testid="manage-tags-button"
            >
              <Tags className="h-4 w-4 mr-2" />
              Manage Tags
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              data-testid="logout-button"
            >
              <LogOut className="h-4 w-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">My Todos</CardTitle>
            <Button
              size="sm"
              onClick={() => setShowCreateForm(true)}
              data-testid="add-todo-button"
            >
              <Plus className="h-4 w-4 mr-1" />
              Add Todo
            </Button>
          </CardHeader>
          <Separator />
          <CardContent className="pt-4">
            <TodoFilters filters={filters} onChange={handleFiltersChange} />

            {isLoading && (
              <div className="text-center py-12 text-muted-foreground">
                Loading todos...
              </div>
            )}

            {error && (
              <div className="text-center py-12 text-destructive">
                Failed to load todos. Please try again.
              </div>
            )}

            {data && (
              <TodoList
                todos={data.items}
                selectedIds={selectedIds}
                onSelect={handleSelect}
                onSelectAll={handleSelectAll}
              />
            )}

            {data && data.total > 0 && (
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {data.items.length} of {data.total} todos
                </p>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid="pagination-prev"
                    disabled={page <= 1}
                    onClick={() => {
                      setPage((p) => Math.max(1, p - 1));
                      setSelectedIds(new Set());
                    }}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Prev
                  </Button>
                  <span className="text-sm text-muted-foreground px-1">
                    {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid="pagination-next"
                    disabled={page >= totalPages}
                    onClick={() => {
                      setPage((p) => p + 1);
                      setSelectedIds(new Set());
                    }}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Create Todo Dialog */}
      <TodoForm
        mode="create"
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
      />

      {/* Tag Manager Dialog */}
      <TagManager
        open={showTagManager}
        onClose={() => setShowTagManager(false)}
      />
    </div>
  );
}
