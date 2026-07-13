'use client';

import { useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { DrilldownPayload, DrilldownTab, JsonValue } from '../tradingTypes';

function preview(value: JsonValue, maxChars = 1400): string {
  return JSON.stringify(value, null, 2).slice(0, maxChars);
}

function rowValue(row: JsonValue, key: string): string {
  if (!row || typeof row !== 'object' || Array.isArray(row)) return '—';
  const value = (row as Record<string, JsonValue>)[key];
  if (Array.isArray(value)) return value.join(', ');
  if (value && typeof value === 'object') return JSON.stringify(value);
  return value === null || value === undefined ? '—' : String(value);
}

function tabColumns(tab: DrilldownTab): string[] {
  const keys = new Set<string>();
  for (const row of tab.rows) {
    if (row && typeof row === 'object' && !Array.isArray(row)) {
      for (const key of Object.keys(row)) {
        if (keys.size < 8) keys.add(key);
      }
    }
  }
  return Array.from(keys);
}

export function RawJsonExcerpt({ title, payload }: { title: string; payload: unknown }) {
  return (
    <article className="raw-json-card" title={`${title} 원본 JSON 일부를 보여주는 읽기 전용 드릴다운입니다.`}>
      <h3>{title}</h3>
      <pre>{JSON.stringify(payload, null, 2).slice(0, 1400)}</pre>
    </article>
  );
}

export function ArtifactDrilldowns({ drilldown }: { drilldown: DrilldownPayload }) {
  const tabs = drilldown.tabs.length ? drilldown.tabs : [];
  const [activeTabId, setActiveTabId] = useState(tabs[0]?.id ?? 'raw_json');
  const activeTab = useMemo(() => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0], [activeTabId, tabs]);
  const columns = useMemo(() => (activeTab ? tabColumns(activeTab) : []), [activeTab]);


  function selectTabByIndex(index: number): void {
    if (!tabs.length) return;
    const next = tabs[(index + tabs.length) % tabs.length];
    setActiveTabId(next.id);
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number): void {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      selectTabByIndex(index + 1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      selectTabByIndex(index - 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectTabByIndex(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      selectTabByIndex(tabs.length - 1);
    }
  }

  if (!activeTab) {
    return (
      <div className="drilldown-empty" data-drilldown-tabs="true">
        해시가 부여된 드릴다운 payload가 없어 원본 JSON을 닫힘 우선으로 숨겼습니다.
      </div>
    );
  }

  return (
    <div className="artifact-drilldown" data-drilldown-tabs="true" data-path-safe={String(drilldown.safe_preview_policy.path_safe)}>
      <div className="drilldown-tabs" role="tablist" aria-label="증거 원본 드릴다운 탭">
        {tabs.map((tab, index) => (
          <button
            type="button"
            key={tab.id}
            role="tab"
            aria-selected={tab.id === activeTab.id}
            data-active={tab.id === activeTab.id}
            id={`drilldown-tab-${tab.id}`}
            aria-controls={`drilldown-panel-${tab.id}`}
            tabIndex={tab.id === activeTab.id ? 0 : -1}
            onClick={() => setActiveTabId(tab.id)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
          >
            {tab.title}
          </button>
        ))}
      </div>
      <div className="drilldown-meta" aria-label="드릴다운 안전 정책">
        <span>run {drilldown.run_id}</span>
        <span>active {drilldown.safe_preview_policy.active_job_count}</span>
        <span>path_safe {String(activeTab.path_safe)}</span>
        <span>hash_backed {String(activeTab.hash_backed)}</span>
        <span>hash {activeTab.preview_hash}</span>
        <span>source {activeTab.source}</span>
      </div>
      <article
        className="drilldown-panel"
        role="tabpanel"
        id={`drilldown-panel-${activeTab.id}`}
        aria-labelledby={`drilldown-tab-${activeTab.id}`}
        tabIndex={0}
      >
        <div className="panel-heading">
          <p className="eyebrow">Drilldown · hash-backed raw JSON</p>
          <h3>{activeTab.title}</h3>
        </div>
        <p>{activeTab.description}</p>
        {columns.length > 0 && (
          <div className="manifest-table-wrap compact-drilldown-table">
            <table className="manifest-table">
              <thead>
                <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {activeTab.rows.slice(0, 6).map((row, index) => (
                  <tr key={`${activeTab.id}-${index}`}>
                    {columns.map((column) => <td key={column}>{rowValue(row, column)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <pre className="drilldown-json">{preview(activeTab.raw_json, drilldown.safe_preview_policy.max_preview_chars)}</pre>
      </article>
    </div>
  );
}
