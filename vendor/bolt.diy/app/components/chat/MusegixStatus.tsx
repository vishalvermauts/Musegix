/**
 * Live Musegix status cards, shown above each assistant reply.
 * The gateway sends a fenced ```musegix-status block with a JSON object; this renders three cards side by side.
 */
import { memo, useEffect } from 'react';
import { musegixStatus } from '~/lib/stores/musegixStatus';

export type MusegixImpact = { symbol: string; files: string[] };

export type MusegixStatusData = {
  tier: string;
  model: string;
  triageMs: number | null;
  selectedTokens: number | null;
  rawTokens: number | null;
  prunedPct: number | null;
  staleMemories: number | null;
  toolRaw?: number | null;
  toolKept?: number | null;
  toolPrunedPct?: number | null;
  impact?: MusegixImpact[];
};

function parseStatus(raw: string): MusegixStatusData | null {
  try {
    const data = JSON.parse(raw);
    return typeof data === 'object' && data && typeof data.tier === 'string' ? (data as MusegixStatusData) : null;
  } catch {
    return null;
  }
}

const card = 'flex flex-col rounded-lg border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 px-3 py-2 min-w-0';
const label = 'text-[10px] font-semibold uppercase tracking-[0.12em] text-[#4d8fe0]';
const value = 'mt-1 text-sm font-semibold text-bolt-elements-textPrimary truncate';
const sub = 'mt-0.5 text-[11px] leading-snug text-bolt-elements-textTertiary truncate';

export const MusegixStatus = memo(({ raw, sticky = false }: { raw: string; sticky?: boolean }) => {
  const s = parseStatus(raw);

  // Keep the sticky bar on the latest status.
  useEffect(() => {
    musegixStatus.set(raw);
  }, [raw]);

  // Only the sticky bar shows the cards; replies keep the store in sync without repeating them.
  if (!s || !sticky) {
    return null;
  }

  const stale = s.staleMemories ?? 0;
  const hasFiles = s.selectedTokens !== null && s.selectedTokens !== undefined && s.rawTokens !== null && s.rawTokens !== undefined;
  const hasTool = s.toolRaw !== null && s.toolRaw !== undefined && s.toolKept !== null && s.toolKept !== undefined;
  const impact = s.impact ?? [];

  return (
    <div className="grid grid-cols-3 gap-2 my-1" aria-label="Musegix status">
      <div className={card}>
        <span className={label}>Ysolveth</span>
        <span className={value}>{s.tier}</span>
        <span className={sub}>{s.model}</span>
        {s.triageMs !== null && s.triageMs !== undefined && (
          <span className="mt-1 text-sm font-bold text-bolt-elements-textPrimary">{s.triageMs} ms on CPU</span>
        )}
      </div>
      <div className={card}>
        <span className={label}>PolyFabric</span>
        <span className={value}>
          {hasTool && s.toolPrunedPct !== null && s.toolPrunedPct !== undefined ? `${s.toolPrunedPct}% trimmed` : 'Nothing trimmed'}
        </span>
        <span className={sub}>
          {hasTool ? `Old tool output ${s.toolRaw} → ${s.toolKept} tokens` : 'No old tool output yet'}
        </span>
        <span className={sub}>
          {hasFiles
            ? `Project files: ${s.selectedTokens} of ${s.rawTokens} tokens sent`
            : 'No project files in this request'}
        </span>
      </div>
      <div className={card}>
        <span className={label}>Veylqora</span>
        <span className={value}>{stale > 0 ? `${stale} stale` : 'All current'}</span>
        <span className={sub}>
          {impact.length > 0
            ? impact
                .slice(0, 2)
                .map((i) => `${i.symbol} used by ${i.files.map((f) => f.split('/').pop()).join(', ')}`)
                .join(' · ')
            : 'No dependent files flagged'}
        </span>
      </div>
    </div>
  );
});
