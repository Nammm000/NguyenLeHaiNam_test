import { Tag as TagIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Pencil, Trash2 } from "lucide-react";
import type { Todo } from "../api/todos";
import { useAttachTag, useDetachTag, useTags } from "../api/tags";

interface TodoItemProps {
  todo: Todo;
  selected: boolean;
  onSelect: (id: string, selected: boolean) => void;
  onToggle: (todo: Todo) => void;
  onEdit: (todo: Todo) => void;
  onDelete: (id: string) => void;
}

export function TodoItem({
  todo,
  selected,
  onSelect,
  onToggle,
  onEdit,
  onDelete,
}: TodoItemProps) {
  const { data: tagsData } = useTags();
  const attachTag = useAttachTag();
  const detachTag = useDetachTag();
  const allTags = tagsData?.items ?? [];
  const attachedTagIds = new Set(todo.tags.map((tag) => tag.id));

  const handleTagClick = (tagId: string) => {
    if (attachedTagIds.has(tagId)) {
      detachTag.mutate({ todoId: todo.id, tagId });
    } else {
      attachTag.mutate({ todoId: todo.id, tagId });
    }
  };

  return (
    <div
      className="flex items-center gap-2 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors group"
      data-testid="todo-item"
    >
      <Checkbox
        aria-label={`Select ${todo.title}`}
        data-testid={`todo-select-${todo.id}`}
        checked={selected}
        onCheckedChange={(checked) => onSelect(todo.id, checked === true)}
        className="data-[state=checked]:border-primary"
      />

      <Checkbox
        id={`todo-${todo.id}`}
        data-testid="todo-toggle"
        checked={todo.completed}
        onCheckedChange={() => onToggle(todo)}
      />

      <div className="flex-1 min-w-0">
        <label
          htmlFor={`todo-${todo.id}`}
          data-testid="todo-title"
          className={`text-sm font-medium cursor-pointer ${
            todo.completed ? "line-through text-muted-foreground" : ""
          }`}
        >
          {todo.title}
        </label>
        {todo.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {todo.description}
          </p>
        )}
        {todo.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1" data-testid="todo-tags">
            {todo.tags.map((tag) => (
              <Badge
                key={tag.id}
                variant="secondary"
                className="text-[10px] px-1.5"
                style={tag.color ? { backgroundColor: tag.color } : undefined}
              >
                {tag.name}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              data-testid={`tag-menu-${todo.id}`}
              aria-label={`Tags for ${todo.title}`}
            >
              <TagIcon className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {allTags.length === 0 && (
              <p className="px-2 py-1.5 text-xs text-muted-foreground">
                No tags — create some in Manage Tags
              </p>
            )}
            {allTags.map((tag) => (
              <DropdownMenuCheckboxItem
                key={tag.id}
                checked={attachedTagIds.has(tag.id)}
                onCheckedChange={() => handleTagClick(tag.id)}
                onSelect={(event) => event.preventDefault()}
              >
                {tag.name}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => onEdit(todo)}
            aria-label={`Edit ${todo.title}`}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={() => onDelete(todo.id)}
            data-testid="todo-delete"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
