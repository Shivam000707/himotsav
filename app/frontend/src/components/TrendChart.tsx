import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { MedicineEvent, Observation, PlanItem, TrendStats } from '../api';
import { Info } from './icons';
import { fmtDate, obsDisplay, rawDisplay } from '../format';

const INK = '#17211e';
const BOARD = '#0b5b4b';
const AMBER = '#85530a';
const DAY = 86_400_000;

interface Point {
  t: number;
  date: string;
  value: number;
  obs: Observation;
}

function toTime(iso: string): number {
  return Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function tickLabel(t: number): string {
  const d = new Date(t);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** A round step for the value axis, so ticks read 6, 7, 8 and not 6.4, 7.3. */
function niceStep(range: number): number {
  const raw = Math.max(range, 0.0001) / 4;
  const pow = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 5, 10]) if (m * pow >= raw) return m * pow;
  return 10 * pow;
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{obsDisplay(p.obs)}</strong>
      <div>{fmtDate(p.date)}</div>
      <div className="muted">{p.obs.source_org ?? 'unknown lab'}</div>
      {p.obs.converted && <div className="muted">converted from {rawDisplay(p.obs)}</div>}
      <div className="chart-tip-hint">Click the point to open the paper</div>
    </div>
  );
}

function rateText(stats: TrendStats | undefined, unit: string): string | null {
  if (!stats || stats.n < 2) return null;
  const parts: string[] = [];
  if (stats.change_since_previous !== null) {
    const c = stats.change_since_previous;
    parts.push(`Last result ${c > 0 ? 'up' : c < 0 ? 'down' : 'unchanged'}${c !== 0 ? ` ${Math.abs(c)} ${unit}` : ''} from the one before.`);
  }
  if (stats.slope_per_year !== null) {
    const s = stats.slope_per_year;
    const years = (stats.span_days / 365.25).toFixed(1);
    parts.push(`Straight-line rate: ${s > 0 ? '+' : ''}${s} ${unit} a year (${stats.n} results over ${years} years).`);
  }
  return parts.length ? parts.join(' ') : null;
}

interface Props {
  title: string;
  observations: Observation[];
  plan?: PlanItem;
  events: MedicineEvent[];
  stats?: TrendStats;
  onOpen: (o: Observation) => void;
}

/** One test over time on a true date axis. Points open their paper; the doctor's target is a shaded band;
 *  dashed amber lines are medicine events from dated prescriptions (order of events only). */
export function TrendChart({ title, observations, plan, events, stats, onOpen }: Props) {
  const points: Point[] = observations
    .filter((o) => o.obs_date && (o.value_std ?? o.value_num) != null)
    .map((o) => ({ t: toTime(o.obs_date as string), date: o.obs_date as string, value: (o.value_std ?? o.value_num) as number, obs: o }))
    .sort((a, b) => a.t - b.t);
  if (points.length === 0) return null;

  const unit = points[points.length - 1].obs.unit_std ?? points[points.length - 1].obs.unit_raw ?? '';
  const tMin0 = points[0].t;
  const tMax0 = points[points.length - 1].t;
  const pad = tMax0 === tMin0 ? 120 * DAY : Math.max(20 * DAY, (tMax0 - tMin0) * 0.07);
  const tMin = tMin0 - pad;
  const tMax = tMax0 + pad;
  const ticks = [0, 1, 2, 3].map((i) => Math.round(tMin + ((tMax - tMin) * i) / 3));

  const shownEvents = events.filter((e) => {
    const t = toTime(e.date);
    return t >= tMin && t <= tMax;
  });

  const low = plan?.target_low ?? null;
  const high = plan?.target_high ?? null;
  const values = [...points.map((p) => p.value), ...(low !== null ? [low] : []), ...(high !== null ? [high] : [])];
  const vMin = Math.min(...values);
  const vMax = Math.max(...values);
  const step = niceStep(vMax - vMin || Math.abs(vMax) * 0.4 || 1);
  const clean = (n: number) => Math.round(n * 10000) / 10000; // no 0.30000000000000004 on the axis
  const yMin = clean(Math.floor((vMin - step * 0.4) / step) * step);
  const yMax = clean(Math.ceil((vMax + step * 0.4) / step) * step);
  const yTicks: number[] = [];
  for (let v = yMin; v <= yMax + step / 2 && yTicks.length < 12; v = clean(v + step)) yTicks.push(v);

  const gaps: string[] = [];
  for (let i = 1; i < points.length; i++) {
    if (points[i].t - points[i - 1].t > 365 * DAY) {
      gaps.push(`No ${title} in the papers from ${tickLabel(points[i - 1].t)} to ${tickLabel(points[i].t)}.`);
    }
  }
  const converted = points.some((p) => p.obs.converted);
  const rate = rateText(stats, unit);

  return (
    <div className="trend">
      <h3>
        {title} <span className="trend-unit">{unit}</span>
      </h3>
      {points.length === 1 && <p className="trend-meta">Only one result so far.</p>}
      {gaps.map((g) => (
        <p key={g} className="trend-note">
          <Info size={16} />
          {g}
        </p>
      ))}
      {converted && (
        <p className="trend-meta">Hollow point: the paper used another unit and it was converted. Both values are kept.</p>
      )}
      {low !== null && high !== null && (
        <p className="trend-meta">
          Shaded band: the doctor&rsquo;s target, {low} to {high} {unit}.
        </p>
      )}
      {(low === null) !== (high === null) && (
        <p className="trend-meta">
          Green line: the doctor&rsquo;s {low !== null ? 'lower' : 'upper'} target, {low ?? high} {unit}.
        </p>
      )}
      <div className="trend-chart">
        <ResponsiveContainer>
          <LineChart data={points} margin={{ top: 32, right: 24, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} stroke="#d4d9d0" strokeDasharray="2 5" />
            <XAxis
              type="number"
              dataKey="t"
              domain={[tMin, tMax]}
              ticks={ticks}
              tickFormatter={tickLabel}
              tick={{ fontSize: 12, fill: '#44524d' }}
              tickLine={false}
              axisLine={{ stroke: '#aeb6ac' }}
              allowDataOverflow
            />
            <YAxis
              width={44}
              domain={[yMin, yMax]}
              ticks={yTicks}
              tickFormatter={(v: number) => String(clean(v))}
              tick={{ fontSize: 12, fill: '#62706a' }}
              tickLine={false}
              axisLine={false}
            />
            {low !== null && high !== null && <ReferenceArea y1={low} y2={high} fill="#dff1e8" fillOpacity={0.9} strokeOpacity={0} ifOverflow="extendDomain" />}
            {low !== null && high === null && <ReferenceLine y={low} stroke="#17734f" strokeDasharray="6 3" ifOverflow="extendDomain" />}
            {high !== null && low === null && <ReferenceLine y={high} stroke="#17734f" strokeDasharray="6 3" ifOverflow="extendDomain" />}
            {shownEvents.map((e, i) => (
              <ReferenceLine key={`${e.medicine}-${e.date}-${i}`} x={toTime(e.date)} stroke={AMBER} strokeDasharray="4 4" strokeWidth={1.5} />
            ))}
            <Tooltip content={<Tip />} cursor={false} />
            <Line
              type="linear"
              dataKey="value"
              stroke={BOARD}
              strokeWidth={3}
              isAnimationActive={false}
              activeDot={false}
              dot={(props: { cx?: number; cy?: number; index?: number; payload?: Point; value?: number }) => {
                const { cx = 0, cy = 0, index = 0, payload, value } = props;
                if (!payload) return <g key={index} />;
                const label = `${obsDisplay(payload.obs)}, ${fmtDate(payload.date)}. Open the source paper.`;
                return (
                  <g
                    key={index}
                    className="pt"
                    role="button"
                    tabIndex={0}
                    aria-label={label}
                    onClick={() => onOpen(payload.obs)}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onOpen(payload.obs)}
                  >
                    <circle cx={cx} cy={cy} r={18} fill="transparent" />
                    <circle
                      cx={cx}
                      cy={cy}
                      r={payload.obs.converted ? 6.5 : 6}
                      fill={payload.obs.converted ? '#ffffff' : BOARD}
                      stroke={BOARD}
                      strokeWidth={3}
                    />
                    <text
                      x={cx}
                      y={cy - 15}
                      textAnchor="middle"
                      fontSize={15}
                      fontWeight={800}
                      fill={INK}
                      stroke="#ffffff"
                      strokeWidth={4}
                      paintOrder="stroke"
                    >
                      {value}
                    </text>
                  </g>
                );
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {shownEvents.length > 0 && (
        <p className="trend-meta trend-events">
          Dashed lines: {shownEvents.map((e) => `${e.medicine} ${tickLabel(toTime(e.date))}`).join('; ')}. See the medicine events list below.
        </p>
      )}
      {rate && <p className="trend-meta">{rate}</p>}
    </div>
  );
}
