import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ChartHint } from '../types/api';

interface ChartViewProps {
  chartHint: ChartHint | null;
  columns: string[];
  rows: (string | number | boolean | null)[][];
}

export function ChartView({ chartHint, columns, rows }: ChartViewProps) {
  if (
    !chartHint ||
    chartHint.type === 'none' ||
    !chartHint.x_key ||
    !chartHint.y_key ||
    columns.length === 0 ||
    rows.length === 0
  ) {
    return null;
  }

  const { type, x_key, y_key, title } = chartHint;

  // Verify that required keys actually exist in the returned columns
  const xIndex = columns.indexOf(x_key);
  const yIndex = columns.indexOf(y_key);

  if (xIndex === -1 || yIndex === -1) {
    return null;
  }

  // Format data into Recharts record array, ensuring valid numeric values for y_key
  const chartData = rows.map((row) => {
    const xVal = row[xIndex];
    const yVal = row[yIndex];

    // Format X label nicely
    const formattedX =
      xVal === null
        ? 'null'
        : typeof xVal === 'string' && xVal.length > 25
        ? `${xVal.slice(0, 22)}...`
        : String(xVal);

    const numericY =
      typeof yVal === 'number'
        ? yVal
        : typeof yVal === 'string' && !isNaN(Number(yVal))
        ? Number(yVal)
        : 0;

    return {
      [x_key]: formattedX,
      [y_key]: numericY,
    };
  });

  const displayTitle =
    title ||
    `${y_key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} by ${x_key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())}`;

  return (
    <div className="chart-card" aria-label={`Chart: ${displayTitle}`}>
      <div className="chart-header">
        <h3 className="chart-title">{displayTitle}</h3>
        <span className="chart-type-tag">
          {type === 'bar' ? 'Bar Chart' : 'Line Trend'}
        </span>
      </div>

      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={320}>
          {type === 'bar' ? (
            <BarChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis
                dataKey={x_key}
                tick={{ fontSize: 12, fill: '#64748b' }}
                interval={0}
                angle={chartData.length > 6 ? -30 : 0}
                textAnchor={chartData.length > 6 ? 'end' : 'middle'}
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#64748b' }}
                tickFormatter={(val) =>
                  val >= 1000 ? `${(val / 1000).toFixed(1)}k` : String(val)
                }
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
              />
              <Legend />
              <Bar
                dataKey={y_key}
                name={y_key.replace(/_/g, ' ')}
                fill="#3b82f6"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          ) : (
            <LineChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis
                dataKey={x_key}
                tick={{ fontSize: 12, fill: '#64748b' }}
                angle={chartData.length > 6 ? -30 : 0}
                textAnchor={chartData.length > 6 ? 'end' : 'middle'}
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#64748b' }}
                tickFormatter={(val) =>
                  val >= 1000 ? `${(val / 1000).toFixed(1)}k` : String(val)
                }
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey={y_key}
                name={y_key.replace(/_/g, ' ')}
                stroke="#2563eb"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#2563eb' }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
