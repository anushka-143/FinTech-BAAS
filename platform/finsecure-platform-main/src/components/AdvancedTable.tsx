import { ReactNode, useState, useMemo, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Search, Filter, Download, ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
  Bookmark, X, Columns3, MoreHorizontal,
} from "lucide-react";
import { useIsMobile } from "@/hooks/use-mobile";

// --- Types ---
export interface ColumnDef<T> {
  key: string;
  label: string;
  sortable?: boolean;
  defaultVisible?: boolean;
  align?: "left" | "center" | "right";
  width?: string;
  render: (row: T) => ReactNode;
  /** Raw value accessor for filtering and sorting */
  getValue?: (row: T) => string | number;
  priority?: boolean;
}

export interface FilterDef {
  key: string;
  label: string;
  options: { value: string; label: string }[];
}

export interface SavedView {
  id: string;
  name: string;
  filters: Record<string, string>;
}

interface AdvancedTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  filters?: FilterDef[];
  savedViews?: SavedView[];
  searchPlaceholder?: string;
  getRowId: (row: T) => string;
  onRowClick?: (row: T) => void;
  pageSize?: number;
  bulkActions?: { label: string; action: (ids: string[]) => void }[];
  exportFileName?: string;
}

function getRowValues<T>(row: T, columns: ColumnDef<T>[]): string {
  return columns.map(col => {
    if (col.getValue) return String(col.getValue(row));
    // Fallback: extract from row data directly
    const val = (row as any)[col.key];
    return val != null ? String(val) : "";
  }).join(" ").toLowerCase();
}

export default function AdvancedTable<T>({
  data, columns, filters = [], savedViews = [], searchPlaceholder = "Search…",
  getRowId, onRowClick, pageSize = 10, bulkActions = [], exportFileName = "export",
}: AdvancedTableProps<T>) {
  const [search, setSearch] = useState("");
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [visibleCols, setVisibleCols] = useState<Set<string>>(
    new Set(columns.filter(c => c.defaultVisible !== false).map(c => c.key))
  );
  const [activeView, setActiveView] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const isMobile = useIsMobile();

  const filtered = useMemo(() => {
    let result = data;
    // Apply filters by matching raw data values
    Object.entries(activeFilters).forEach(([filterKey, filterValue]) => {
      if (filterValue && filterValue !== "__all__") {
        result = result.filter(row => {
          // Try to match against the raw row data
          const rawVal = (row as any)[filterKey];
          if (rawVal != null) {
            return String(rawVal).toUpperCase().includes(filterValue.toUpperCase());
          }
          // Fallback: check column getValue
          const col = columns.find(c => c.key === filterKey);
          if (col?.getValue) {
            return String(col.getValue(row)).toUpperCase().includes(filterValue.toUpperCase());
          }
          return true;
        });
      }
    });
    // Full-text search across all columns
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(row => getRowValues(row, columns).includes(q));
    }
    return result;
  }, [data, activeFilters, search, columns]);

  // Sorting
  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const col = columns.find(c => c.key === sortKey);
    if (!col) return filtered;
    return [...filtered].sort((a, b) => {
      let aVal: string | number = "";
      let bVal: string | number = "";
      if (col.getValue) {
        aVal = col.getValue(a);
        bVal = col.getValue(b);
      } else {
        aVal = String((a as any)[sortKey] ?? "");
        bVal = String((b as any)[sortKey] ?? "");
      }
      const cmp = typeof aVal === "number" && typeof bVal === "number"
        ? aVal - bVal
        : String(aVal).localeCompare(String(bVal));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir, columns]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paged = sorted.slice(page * pageSize, (page + 1) * pageSize);

  const handleSort = useCallback((key: string) => {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }, [sortKey]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (selectedIds.size === paged.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(paged.map(getRowId)));
    }
  }, [paged, selectedIds.size, getRowId]);

  const applyView = useCallback((view: SavedView) => {
    setActiveFilters(view.filters);
    setActiveView(view.id);
    setPage(0);
  }, []);

  const clearFilters = useCallback(() => {
    setActiveFilters({});
    setSearch("");
    setActiveView(null);
    setPage(0);
  }, []);

  const exportCSV = useCallback(() => {
    const visibleColumns = columns.filter(c => visibleCols.has(c.key));
    const header = visibleColumns.map(c => c.label).join(",");
    const rows = filtered.map(row =>
      visibleColumns.map(c => {
        if (c.getValue) return `"${c.getValue(row)}"`;
        const val = (row as any)[c.key];
        return val != null ? `"${val}"` : '""';
      }).join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${exportFileName}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [columns, filtered, visibleCols, exportFileName]);

  const activeFilterCount = Object.values(activeFilters).filter(v => v && v !== "__all__").length;
  const visCols = columns.filter(c => visibleCols.has(c.key));

  return (
    <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between px-3 md:px-4 py-3 border-b border-border gap-2 md:gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className="relative flex-1 md:max-w-[280px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0); }}
              placeholder={searchPlaceholder}
              className="h-8 pl-9 text-[13px] bg-accent/30 border-border"
            />
          </div>

          {isMobile && filters.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-[12px] px-2.5 text-muted-foreground gap-1"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-3.5 h-3.5" />
              {activeFilterCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-primary text-primary-foreground text-[10px] flex items-center justify-center">{activeFilterCount}</span>
              )}
            </Button>
          )}

          {!isMobile && filters.map(f => (
            <Select key={f.key} value={activeFilters[f.key] || "__all__"} onValueChange={v => {
              setActiveFilters(prev => ({ ...prev, [f.key]: v }));
              setPage(0);
            }}>
              <SelectTrigger className="h-8 text-[12px] border-border bg-accent/30 w-auto min-w-[100px] gap-1.5">
                <SelectValue placeholder={f.label} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__" className="text-[12px]">All {f.label}</SelectItem>
                {f.options.map(o => (
                  <SelectItem key={o.value} value={o.value} className="text-[12px]">{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}

          {activeFilterCount > 0 && (
            <Button variant="ghost" size="sm" className="h-8 text-[11px] px-2 text-muted-foreground" onClick={clearFilters}>
              <X className="w-3 h-3 mr-1" />Clear
            </Button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {savedViews.length > 0 && (
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-8 text-[12px] px-2.5 md:px-3 text-muted-foreground gap-1.5">
                  <Bookmark className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">{activeView ? savedViews.find(v => v.id === activeView)?.name : "Views"}</span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[200px] p-1.5" align="end">
                {savedViews.map(v => (
                  <button
                    key={v.id}
                    onClick={() => applyView(v)}
                    className={`w-full text-left px-3 py-2 rounded-md text-[12px] transition-colors ${activeView === v.id ? "bg-accent text-foreground font-medium" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"}`}
                  >
                    {v.name}
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          )}

          {!isMobile && (
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-8 text-[12px] px-2.5 text-muted-foreground">
                  <Columns3 className="w-3.5 h-3.5" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[200px] p-2" align="end">
                <p className="text-[11px] font-medium text-muted-foreground px-2 mb-2">Toggle columns</p>
                {columns.map(c => (
                  <label key={c.key} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-accent/50 cursor-pointer">
                    <Checkbox
                      checked={visibleCols.has(c.key)}
                      onCheckedChange={checked => {
                        setVisibleCols(prev => {
                          const next = new Set(prev);
                          checked ? next.add(c.key) : next.delete(c.key);
                          return next;
                        });
                      }}
                    />
                    <span className="text-[12px] text-foreground">{c.label}</span>
                  </label>
                ))}
              </PopoverContent>
            </Popover>
          )}

          <Button variant="outline" size="sm" className="h-8 text-[12px] px-2.5 md:px-3 text-muted-foreground gap-1.5" onClick={exportCSV}>
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </Button>
        </div>
      </div>

      {/* Mobile filters row */}
      {isMobile && showFilters && filters.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3 py-2.5 border-b border-border bg-accent/20">
          {filters.map(f => (
            <Select key={f.key} value={activeFilters[f.key] || "__all__"} onValueChange={v => {
              setActiveFilters(prev => ({ ...prev, [f.key]: v }));
              setPage(0);
            }}>
              <SelectTrigger className="h-8 text-[12px] border-border bg-card w-auto min-w-[100px] gap-1.5">
                <SelectValue placeholder={f.label} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__" className="text-[12px]">All {f.label}</SelectItem>
                {f.options.map(o => (
                  <SelectItem key={o.value} value={o.value} className="text-[12px]">{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
        </div>
      )}

      {/* Bulk actions bar */}
      {selectedIds.size > 0 && bulkActions.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-primary/5 border-b border-primary/10">
          <span className="text-[12px] font-medium text-foreground">{selectedIds.size} selected</span>
          {bulkActions.map(ba => (
            <Button key={ba.label} variant="outline" size="sm" className="h-7 text-[11px] px-2.5" onClick={() => ba.action(Array.from(selectedIds))}>
              {ba.label}
            </Button>
          ))}
          <Button variant="ghost" size="sm" className="h-7 text-[11px] px-2 text-muted-foreground ml-auto" onClick={() => setSelectedIds(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {/* Mobile card view */}
      {isMobile ? (
        <div className="divide-y divide-border/50">
          {paged.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <Search className="w-8 h-8 mx-auto mb-3 opacity-30 text-muted-foreground" />
              <p className="text-[14px] font-medium text-muted-foreground mb-1">No results found</p>
              <p className="text-[12px] text-muted-foreground">Try adjusting your search or filter criteria.</p>
            </div>
          ) : (
            paged.map(row => {
              const id = getRowId(row);
              return (
                <div
                  key={id}
                  className={`px-4 py-3.5 hover:bg-accent/30 transition-colors ${onRowClick ? "cursor-pointer active:bg-accent/50" : ""}`}
                  onClick={() => onRowClick?.(row)}
                >
                  <div className="space-y-1.5">
                    {visCols.slice(0, 4).map(col => (
                      <div key={col.key} className="flex items-center justify-between gap-2">
                        <span className="text-[11px] text-muted-foreground uppercase tracking-wide shrink-0">{col.label}</span>
                        <div className="text-right">{col.render(row)}</div>
                      </div>
                    ))}
                    {visCols.length > 4 && (
                      <details className="group">
                        <summary className="text-[11px] text-primary cursor-pointer list-none flex items-center gap-1 mt-1">
                          <MoreHorizontal className="w-3 h-3" />
                          <span>{visCols.length - 4} more fields</span>
                        </summary>
                        <div className="mt-1.5 space-y-1.5">
                          {visCols.slice(4).map(col => (
                            <div key={col.key} className="flex items-center justify-between gap-2">
                              <span className="text-[11px] text-muted-foreground uppercase tracking-wide shrink-0">{col.label}</span>
                              <div className="text-right">{col.render(row)}</div>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        /* Desktop table */
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-table-head text-muted-foreground uppercase border-b border-border bg-accent/30">
                {bulkActions.length > 0 && (
                  <th className="w-10 px-3 py-3">
                    <Checkbox
                      checked={selectedIds.size === paged.length && paged.length > 0}
                      onCheckedChange={selectAll}
                    />
                  </th>
                )}
                {visCols.map(col => (
                  <th
                    key={col.key}
                    className={`px-5 py-3 font-medium ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"} ${col.sortable ? "cursor-pointer select-none hover:text-foreground transition-colors" : ""}`}
                    style={col.width ? { width: col.width } : undefined}
                    onClick={() => col.sortable && handleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {col.sortable && sortKey === col.key && (
                        sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.length === 0 ? (
                <tr>
                  <td colSpan={visCols.length + (bulkActions.length > 0 ? 1 : 0)} className="px-5 py-16 text-center">
                    <div className="text-muted-foreground">
                      <Search className="w-8 h-8 mx-auto mb-3 opacity-30" />
                      <p className="text-[14px] font-medium mb-1">No results found</p>
                      <p className="text-[12px]">Try adjusting your search or filter criteria.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                paged.map(row => {
                  const id = getRowId(row);
                  return (
                    <tr
                      key={id}
                      className={`border-b border-border/50 hover:bg-accent/30 transition-colors ${onRowClick ? "cursor-pointer" : ""} ${selectedIds.has(id) ? "bg-primary/5" : ""}`}
                      onClick={() => onRowClick?.(row)}
                    >
                      {bulkActions.length > 0 && (
                        <td className="w-10 px-3 py-3.5" onClick={e => e.stopPropagation()}>
                          <Checkbox
                            checked={selectedIds.has(id)}
                            onCheckedChange={() => toggleSelect(id)}
                          />
                        </td>
                      )}
                      {visCols.map(col => (
                        <td
                          key={col.key}
                          className={`px-5 py-3.5 ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"}`}
                        >
                          {col.render(row)}
                        </td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 md:px-5 py-3 border-t border-border">
        <span className="text-[12px] text-muted-foreground">
          {sorted.length} result{sorted.length !== 1 ? "s" : ""}
          {totalPages > 1 && ` · Page ${page + 1} of ${totalPages}`}
        </span>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" className="h-7 w-7 p-0" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="w-3.5 h-3.5" />
            </Button>
            <Button variant="outline" size="sm" className="h-7 w-7 p-0" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
