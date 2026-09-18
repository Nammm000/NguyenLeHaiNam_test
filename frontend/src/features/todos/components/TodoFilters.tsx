import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTags } from "../api/tags";
import { EMPTY_FILTERS, type TodoFiltersState } from "../api/todos";

interface TodoFiltersProps {
  filters: TodoFiltersState;
  onChange: (filters: TodoFiltersState) => void;
}

const DEBOUNCE_MS = 300;

export function TodoFilters({ filters, onChange }: TodoFiltersProps) {
  const { data: tagsData } = useTags();
  const [keywordInput, setKeywordInput] = useState(filters.keyword);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (keywordInput !== filters.keyword) {
        onChange({ ...filters, keyword: keywordInput });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keywordInput]);

  const hasActiveFilters =
    filters.status !== "" ||
    filters.tag_id !== "" ||
    filters.keyword !== "" ||
    filters.date_from !== "" ||
    filters.date_to !== "";

  return (
    <div
      className="flex flex-wrap items-end gap-2 mb-4"
      data-testid="todo-filters"
    >
      <div className="space-y-1 flex-1 min-w-40">
        <Label htmlFor="filter-keyword">Keyword</Label>
        <Input
          id="filter-keyword"
          placeholder="Search title or description"
          data-testid="filter-keyword"
          value={keywordInput}
          onChange={(e) => setKeywordInput(e.target.value)}
        />
      </div>

      <div className="space-y-1 w-36">
        <Label htmlFor="filter-status">Status</Label>
        <Select
          value={filters.status || "all"}
          onValueChange={(value) =>
            onChange({ ...filters, status: value === "all" ? "" : value })
          }
        >
          <SelectTrigger id="filter-status" data-testid="filter-status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1 w-36">
        <Label htmlFor="filter-tag">Tag</Label>
        <Select
          value={filters.tag_id || "all"}
          onValueChange={(value) =>
            onChange({ ...filters, tag_id: value === "all" ? "" : value })
          }
        >
          <SelectTrigger id="filter-tag" data-testid="filter-tag">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tags</SelectItem>
            {(tagsData?.items ?? []).map((tag) => (
              <SelectItem key={tag.id} value={tag.id}>
                {tag.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="filter-date-from">From</Label>
        <Input
          id="filter-date-from"
          type="date"
          data-testid="filter-date-from"
          value={filters.date_from}
          onChange={(e) => onChange({ ...filters, date_from: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="filter-date-to">To</Label>
        <Input
          id="filter-date-to"
          type="date"
          data-testid="filter-date-to"
          value={filters.date_to}
          onChange={(e) => onChange({ ...filters, date_to: e.target.value })}
        />
      </div>

      <Button
        variant="outline"
        size="sm"
        data-testid="filter-clear"
        disabled={!hasActiveFilters}
        onClick={() => {
          setKeywordInput("");
          onChange({ ...EMPTY_FILTERS });
        }}
      >
        <ChevronDown className="h-4 w-4 mr-1 rotate-45" />
        Clear
      </Button>
    </div>
  );
}
