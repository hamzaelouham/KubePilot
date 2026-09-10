"use client"

import { useState } from "react"

import {
  type ColumnDef,
  type PaginationState,
  type RowData,
  type SortingState,
  columnFilteringFeature,
  createFilteredRowModel,
  createPaginatedRowModel,
  createSortedRowModel,
  filterFns,
  globalFilteringFeature,
  rowPaginationFeature,
  rowSortingFeature,
  sortFns,
  tableFeatures,
  useTable,
} from "@tanstack/react-table"
import { ArrowDown, ArrowUp, Search, X } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const features = tableFeatures({
  columnFilteringFeature,
  globalFilteringFeature,
  rowSortingFeature,
  rowPaginationFeature,
  filteredRowModel: createFilteredRowModel(),
  sortedRowModel: createSortedRowModel(),
  paginatedRowModel: createPaginatedRowModel(),
  filterFns,
  sortFns,
})

export type DataTableColumn<TData extends RowData, TValue = unknown> = ColumnDef<
  typeof features,
  TData,
  TValue
>

interface DataTableProps<TData extends RowData, TValue> {
  columns: DataTableColumn<TData, TValue>[]
  data: TData[]
  title?: React.ReactNode
  placeholder?: React.ReactNode
  searchPlaceholder?: string
  searchable?: boolean
  pageSize?: number
  serverPagination?: {
    page: number
    totalPages: number
    onPageChange: (page: number) => void
  }
  className?: string
}

export function DataTable<TData extends RowData, TValue>({
  columns,
  data,
  title,
  placeholder = "No data to display.",
  searchPlaceholder = "Filter rows…",
  searchable = true,
  pageSize = 10,
  serverPagination,
  className,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState("")
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize,
  })

  interface SelectedState {
  sorting: SortingState
  globalFilter: string
  pagination: PaginationState
}

const table = useTable<typeof features, TData, SelectedState>(
    {
      features,
      data,
      columns: columns as unknown as ColumnDef<typeof features, TData, unknown>[],
      state: { sorting, globalFilter, pagination },
      onSortingChange: setSorting,
      onGlobalFilterChange: setGlobalFilter,
      onPaginationChange: setPagination,
      enableSorting: true,
      enableGlobalFilter: true,
    },
    (state) => ({
      sorting: state.sorting,
      globalFilter: state.globalFilter,
      pagination: state.pagination,
    })
  )

  const filteredCount = table.getFilteredRowModel().rows.length
  const rows = table.getRowModel().rows

  return (
    <div
      className={cn("rounded-xl border border-border bg-card", className)}
    >
      {title ? (
        <div className="border-b border-border px-4 py-3">{title}</div>
      ) : null}

      {searchable ? (
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="relative w-full max-w-sm">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={globalFilter}
              onChange={(event) => setGlobalFilter(event.target.value)}
              placeholder={searchPlaceholder}
              aria-label="Filter rows"
              className="bg-card ps-8 pr-8"
            />
            {globalFilter ? (
              <button
                type="button"
                onClick={() => setGlobalFilter("")}
                aria-label="Clear filter"
                className="absolute top-1/2 right-2 flex size-4 -translate-y-1/2 items-center justify-center text-muted-foreground transition hover:text-foreground"
              >
                <X className="size-3.5" />
              </button>
            ) : null}
          </div>
          <p className="text-sm whitespace-nowrap text-muted-foreground">
            Showing {filteredCount} of {data.length}
          </p>
        </div>
      ) : null}

      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow
              key={headerGroup.id}
              className="border-b border-border bg-muted hover:bg-muted"
            >
              {headerGroup.headers.map((header) => {
                const canSort = header.column.getCanSort() && !header.isPlaceholder
                const sorted = header.column.getIsSorted()
                return (
                  <TableHead
                    key={header.id}
                    className="px-4 py-3 text-base font-medium text-muted-foreground"
                  >
                    {canSort ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        aria-label={
                          sorted
                            ? `Sort by ${String(header.column.id)} descending`
                            : `Sort by ${String(header.column.id)}`
                        }
                        className="inline-flex items-center gap-1.5 transition hover:text-foreground"
                      >
                        <table.FlexRender header={header} />
                        {sorted === "asc" ? (
                          <ArrowUp className="size-3.5" />
                        ) : sorted === "desc" ? (
                          <ArrowDown className="size-3.5" />
                        ) : null}
                      </button>
                    ) : (
                      <table.FlexRender header={header} />
                    )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {rows.length ? (
            rows.map((row) => (
              <TableRow
                key={row.id}
                className="border-t border-border text-foreground hover:bg-muted/50"
              >
                {row.getAllCells().map((cell) => (
                  <TableCell key={cell.id} className="px-4 py-3 text-base">
                    <table.FlexRender cell={cell} />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={table.getAllLeafColumns().length}
                className="px-4 py-8 text-center text-base text-muted-foreground"
              >
                {placeholder}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
        <p className="text-sm text-muted-foreground" data-testid="pagination-page">
          Page {serverPagination ? serverPagination.page + 1 : table.state.pagination.pageIndex + 1} of{" "}
          {serverPagination ? Math.max(1, serverPagination.totalPages) : Math.max(1, table.getPageCount())}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={serverPagination ? serverPagination.page === 0 : !table.getCanPreviousPage()}
            onClick={() =>
              serverPagination
                ? serverPagination.onPageChange(serverPagination.page - 1)
                : setPagination((previous) => ({
                    ...previous,
                    pageIndex: previous.pageIndex - 1,
                  }))
            }
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={serverPagination ? serverPagination.page >= serverPagination.totalPages - 1 : !table.getCanNextPage()}
            onClick={() =>
              serverPagination
                ? serverPagination.onPageChange(serverPagination.page + 1)
                : setPagination((previous) => ({
                    ...previous,
                    pageIndex: previous.pageIndex + 1,
                  }))
            }
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
