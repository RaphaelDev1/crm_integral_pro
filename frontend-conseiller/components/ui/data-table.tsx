"use client";

import {
  type ColumnDef,
  type ColumnFiltersState,
  type OnChangeFn,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  // Filtre texte branché sur une colonne précise (accessorKey).
  filterColumn?: string;
  filterPlaceholder?: string;
  // Filtre texte global, toutes colonnes confondues. Omis = pas de champ affiché.
  globalFilterPlaceholder?: string;
  emptyMessage?: string;

  // Sélection multiple : ajoute une colonne de cases à cocher en tête de
  // table. `onSelectionChange` reçoit les lignes sélectionnées à chaque
  // changement.
  selectable?: boolean;
  onSelectionChange?: (rows: TData[]) => void;
  getRowId?: (row: TData) => string;

  // Menu d'actions par ligne (ex. Modifier / Supprimer), ajouté en dernière
  // colonne. Le contenu retourné est placé dans un <DropdownMenuContent>.
  rowActions?: (row: TData) => React.ReactNode;

  // Rend chaque ligne cliquable (ex. navigation vers la fiche détail). Le
  // clic sur la case à cocher ou le menu d'actions ne déclenche pas ce
  // handler (stopPropagation déjà en place sur ces deux éléments).
  onRowClick?: (row: TData) => void;

  // Pagination. En mode client (par défaut), la table pagine elle-même
  // `data` avec `pageSize`. En mode serveur, passer `manualPagination`,
  // `pageCount` et `pagination`/`onPaginationChange` : la table affiche
  // alors la page de `data` telle quelle et délègue le découpage à l'appelant.
  pageSize?: number;
  manualPagination?: boolean;
  pageCount?: number;
  pagination?: PaginationState;
  onPaginationChange?: OnChangeFn<PaginationState>;

  // Tri initial appliqué à l'ouverture (ex. relance la plus proche en
  // premier) — l'utilisateur reste ensuite libre de re-trier au clic.
  defaultSorting?: SortingState;
}

// Composant unique pour toutes les listes (clients, prospects, dossiers,
// factures…) : tri, filtres, pagination, sélection multiple et actions par
// ligne via @tanstack/react-table, rendu avec les primitives shadcn/ui
// (components/ui/table.tsx).
export function DataTable<TData, TValue>({
  columns,
  data,
  filterColumn,
  filterPlaceholder = "Filtrer…",
  globalFilterPlaceholder,
  emptyMessage = "Aucun résultat.",
  selectable = false,
  onSelectionChange,
  getRowId,
  rowActions,
  onRowClick,
  pageSize = 10,
  manualPagination = false,
  pageCount,
  pagination: controlledPagination,
  onPaginationChange,
  defaultSorting,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>(defaultSorting ?? []);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [internalPagination, setInternalPagination] = useState<PaginationState>({ pageIndex: 0, pageSize });

  const pagination = controlledPagination ?? internalPagination;
  const handlePaginationChange = onPaginationChange ?? setInternalPagination;

  const tableColumns = useTableColumns(columns, { selectable, rowActions });

  const table = useReactTable({
    data,
    columns: tableColumns,
    getRowId,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onColumnFiltersChange: setColumnFilters,
    getFilteredRowModel: getFilteredRowModel(),
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: "includesString",
    enableRowSelection: selectable,
    onRowSelectionChange: setRowSelection,
    manualPagination,
    pageCount: manualPagination ? pageCount : undefined,
    onPaginationChange: handlePaginationChange,
    getPaginationRowModel: manualPagination ? undefined : getPaginationRowModel(),
    state: { sorting, columnFilters, globalFilter, rowSelection, pagination },
  });

  useEffect(() => {
    if (!selectable) return;
    onSelectionChange?.(table.getSelectedRowModel().rows.map((row) => row.original));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowSelection, selectable]);

  const sortIndicator: Record<string, string> = { asc: " ↑", desc: " ↓" };
  const pageCountDisplay = manualPagination ? pageCount ?? 0 : table.getPageCount();
  const showPagination = manualPagination ? (pageCount ?? 0) > 1 : table.getPageCount() > 1;

  return (
    <div className="space-y-3">
      {(filterColumn || globalFilterPlaceholder) && (
        <div className="flex gap-2">
          {globalFilterPlaceholder && (
            <Input
              placeholder={globalFilterPlaceholder}
              value={globalFilter}
              onChange={(event) => setGlobalFilter(event.target.value)}
              className="max-w-sm"
            />
          )}
          {filterColumn && (
            <Input
              placeholder={filterPlaceholder}
              value={(table.getColumn(filterColumn)?.getFilterValue() as string) ?? ""}
              onChange={(event) => table.getColumn(filterColumn)?.setFilterValue(event.target.value)}
              className="max-w-sm"
            />
          )}
        </div>
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={header.column.getCanSort() ? "cursor-pointer select-none" : undefined}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    {sortIndicator[header.column.getIsSorted() as string] ?? null}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={onRowClick ? "cursor-pointer" : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={tableColumns.length} className="h-24 text-center text-muted-foreground">
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {showPagination && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {pagination.pageIndex + 1} sur {pageCountDisplay}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
              Précédent
            </Button>
            <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
              Suivant
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// Injecte la colonne de sélection (checkboxes) et/ou la colonne d'actions
// autour des colonnes fournies par l'appelant, sans lui faire dupliquer ce
// câblage à chaque écran.
function useTableColumns<TData, TValue>(
  columns: ColumnDef<TData, TValue>[],
  { selectable, rowActions }: { selectable: boolean; rowActions?: (row: TData) => React.ReactNode }
): ColumnDef<TData, TValue>[] {
  let result = columns;

  if (selectable) {
    const selectionColumn: ColumnDef<TData, TValue> = {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Tout sélectionner"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Sélectionner la ligne"
          onClick={(event) => event.stopPropagation()}
        />
      ),
      enableSorting: false,
      enableHiding: false,
    };
    result = [selectionColumn, ...result];
  }

  if (rowActions) {
    const actionsColumn: ColumnDef<TData, TValue> = {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div onClick={(event) => event.stopPropagation()}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <span className="sr-only">Ouvrir le menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">{rowActions(row.original)}</DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
      enableSorting: false,
      enableHiding: false,
    };
    result = [...result, actionsColumn];
  }

  return result;
}
