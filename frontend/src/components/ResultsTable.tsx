interface ResultsTableProps {
  columns: string[];
  rows: (string | number | boolean | null)[][];
  rowCount: number;
  truncated?: boolean;
}

export function ResultsTable({
  columns,
  rows,
  rowCount,
  truncated = false,
}: ResultsTableProps) {
  if (columns.length === 0 || rows.length === 0) {
    return null;
  }

  // Detect whether each column is predominantly numeric for right-alignment
  const isNumericColumn = columns.map((_, colIndex) => {
    return rows.some(
      (row) =>
        row[colIndex] !== null &&
        typeof row[colIndex] === 'number'
    );
  });

  return (
    <div className="table-card" aria-label="Query results data table">
      <div className="table-header-meta">
        <div className="table-title">
          <span>Results Data</span>
          <span className="row-count-badge">
            {rowCount} {rowCount === 1 ? 'row' : 'rows'}
          </span>
        </div>
        {truncated && (
          <div className="truncated-badge" role="status">
            <span>Result truncated to safety limit ({rowCount} rows).</span>
          </div>
        )}
      </div>

      <div className="table-scroll-container" tabIndex={0} role="region" aria-label="Tabular data">
        <table className="data-table">
          <thead>
            <tr>
              <th className="row-num-header">#</th>
              {columns.map((col, idx) => (
                <th
                  key={col}
                  className={isNumericColumn[idx] ? 'numeric-cell' : 'text-cell'}
                  scope="col"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                <td className="row-num-cell">{rowIdx + 1}</td>
                {row.map((cell, cellIdx) => (
                  <td
                    key={cellIdx}
                    className={isNumericColumn[cellIdx] ? 'numeric-cell' : 'text-cell'}
                  >
                    {cell === null ? (
                      <span className="null-indicator">null</span>
                    ) : typeof cell === 'number' ? (
                      Number.isInteger(cell)
                        ? cell.toLocaleString()
                        : cell.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 4,
                          })
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
