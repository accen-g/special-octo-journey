import { useState, useMemo } from 'react';

type SortDir = 'asc' | 'desc';

/**
 * Client-side sort hook.
 *
 * Usage:
 *   const { sorted, sortKey, sortDir, toggleSort } = useTableSort(filteredItems);
 *
 *   // In column header:
 *   <TableSortLabel active={sortKey === 'kri_code'} direction={...} onClick={() => toggleSort('kri_code')}>
 *     KRI Code
 *   </TableSortLabel>
 *
 *   // In table body — iterate over `sorted` instead of the raw array.
 */
export function useTableSort<T extends Record<string, any>>(
  items: T[],
  defaultKey: keyof T | null = null,
  defaultDir: SortDir = 'asc',
) {
  const [sortKey, setSortKey] = useState<keyof T | null>(defaultKey);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);

  const toggleSort = (key: keyof T) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return items;
    return [...items].sort((a, b) => {
      const av = a[sortKey as string];
      const bv = b[sortKey as string];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = String(av).localeCompare(String(bv), undefined, {
        numeric: true,
        sensitivity: 'base',
      });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [items, sortKey, sortDir]);

  return { sorted, sortKey: sortKey as string | null, sortDir, toggleSort: toggleSort as (key: string) => void };
}
