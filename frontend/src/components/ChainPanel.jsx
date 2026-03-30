import React from 'react';
import './ChainPanel.css';
import {
  ASSET_DESCRIPTIONS,
  buildPlainQuestion,
  buildConditionDetail,
  buildConditionTooltip
} from './NodeBox';

export default function ChainPanel({ panelData, onClose }) {
  if (!panelData) return null;
  const { chain, highlightNodeId, tabName, computedAt } = panelData;
  const timestamp = new Date(computedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const handleCopy = () => {
    const lines = [
      `NUTS Visualizer — ${tabName} · ${timestamp}`,
      '',
      ...chain.conditionNodes.map(n => {
        const flag = n.close_call ? '⚠️ ' : '';
        const icon = n.result ? '✅' : '❌';
        const desc = ASSET_DESCRIPTIONS[n.ticker] ? `\n(${ASSET_DESCRIPTIONS[n.ticker]})` : '';
        return `${icon} ${flag}${buildConditionTooltip(n)}${desc}`;
      }),
      '',
      `→ ${chain.outcome} — ${ASSET_DESCRIPTIONS[chain.outcome] ?? chain.outcome}`,
    ];
    navigator.clipboard.writeText(lines.join('\n'));
  };

  return (
    <div className="chain-panel-overlay" onClick={onClose}>
      <div className="chain-panel" onClick={e => e.stopPropagation()}>

        <div className="chain-panel-header">
          <span className="chain-panel-title">{tabName} · {timestamp}</span>
          <button className="chain-panel-copy" onClick={handleCopy}>copy</button>
          <button className="chain-panel-close" onClick={onClose}>✕</button>
        </div>

        <div className="chain-panel-entries">
          {chain.conditionNodes.map((node, i) => (
            <div
              key={node.id}
              className={[
                'chain-entry',
                node.close_call ? 'close-call-entry' : '',
                node.id === highlightNodeId ? 'highlighted-entry' : '',
                !node.isActiveInGlobalPath ? 'dimmed-entry' : ''
              ].join(' ').trim()}
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <div className="chain-entry-question">
                {buildPlainQuestion(node)}{node.close_call ? ' ⚠️' : (node.result ? ' ✅' : ' ❌')}
              </div>
              <div className="chain-entry-detail">{buildConditionDetail(node)}</div>
              {ASSET_DESCRIPTIONS[node.ticker] && (
                <div className="chain-entry-description">({ASSET_DESCRIPTIONS[node.ticker]})</div>
              )}
            </div>
          ))}

          {chain.outcome && (
            <>
              <hr className="chain-divider" />
              <div
                className={[
                  'chain-outcome',
                  chain.outcomeNodeId === highlightNodeId ? 'highlighted-entry' : '',
                  // If the last condition was inactive, the outcome is probably inactive too
                  (chain.conditionNodes.length > 0 && !chain.conditionNodes[chain.conditionNodes.length - 1].isActiveInGlobalPath) ? 'dimmed-entry' : ''
                ].join(' ').trim()}
                style={{ animationDelay: `${chain.conditionNodes.length * 40}ms` }}
              >
                <strong>→ {chain.outcome}</strong>
                <p>{ASSET_DESCRIPTIONS[chain.outcome] ?? chain.outcome}</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
