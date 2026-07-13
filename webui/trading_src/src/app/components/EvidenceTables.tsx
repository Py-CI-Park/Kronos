'use client';

import { useMemo, useState } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { AuditPayload, AuditTimelineRow, EvidenceArtifact, EvidencePayload, RunComparisonRow, StatusPayload } from '../tradingTypes';
import { FALLBACK_EVIDENCE } from '../tradingApi';
import { CARD_COPY, compactCardValue, statusLabel } from '../tradingFormat';

function normalizedArtifacts(artifacts: EvidenceArtifact[]): EvidenceArtifact[] {
  return (artifacts.length ? artifacts : FALLBACK_EVIDENCE.artifacts).map((artifact) => ({
    ...artifact,
    artifact_id: artifact.artifact_id ?? `${artifact.kind}-${artifact.source_stage ?? 'unknown'}`,
    hash: artifact.hash ?? null,
    path: artifact.path ?? null,
    timestamp: artifact.timestamp ?? null,
    freshness: artifact.freshness ?? artifact.status ?? 'UNKNOWN',
    schema_status: artifact.schema_status ?? 'UNKNOWN',
    blocker_reason: artifact.blocker_reason ?? '백엔드 schema field가 없어 fail-closed로 표시합니다.',
    source_stage: artifact.source_stage ?? 'UNKNOWN',
    source_run_id: artifact.source_run_id ?? 'research_ts_imb_rule_baseline_23bp',
    symbols: Array.isArray(artifact.symbols) ? artifact.symbols : FALLBACK_EVIDENCE.symbols,
  }));
}

export function ArtifactManifestTable({ artifacts }: { artifacts: EvidenceArtifact[] }) {
  const [filter, setFilter] = useState('');
  const data = normalizedArtifacts(artifacts);
  const filteredData = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return data;
    return data.filter((artifact) => JSON.stringify(artifact).toLowerCase().includes(needle));
  }, [data, filter]);
  const columnHelper = createColumnHelper<EvidenceArtifact>();
  const columns = useMemo(
    () => [
      columnHelper.accessor('artifact_id', { header: '산출물 ID' }),
      columnHelper.accessor('source_stage', { header: '단계' }),
      columnHelper.accessor('source_run_id', { header: '출처 run' }),
      columnHelper.accessor('status', { header: '상태', cell: (info) => statusLabel(info.getValue()) }),
      columnHelper.accessor('hash', { header: '해시', cell: (info) => info.getValue() ?? '없음' }),
      columnHelper.accessor('path', { header: '경로', cell: (info) => info.getValue() ?? '없음' }),
      columnHelper.accessor('timestamp', { header: '시간', cell: (info) => info.getValue() ?? '없음' }),
      columnHelper.accessor('freshness', { header: '신선도' }),
      columnHelper.accessor('schema_status', { header: '스키마' }),
      columnHelper.accessor('row_count', { header: '행 수', cell: (info) => info.getValue() ?? '—' }),
      columnHelper.accessor('blocker_reason', { header: '차단 사유' }),
      columnHelper.accessor('symbols', { header: '종목 코드', cell: (info) => info.getValue().join(', ') }),
    ],
    [columnHelper],
  );
  const table = useReactTable({ data: filteredData, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="manifest-table-wrap" data-tanstack-evidence-table="true">
      <label className="table-filter">
        <span>manifest 필터</span>
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="stage, blocker, symbol, hash 검색" aria-label="증거 manifest 필터" />
      </label>
      <table className="manifest-table">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RunComparisonTable({ status, evidence }: { status: StatusPayload; evidence: EvidencePayload }) {
  const [filter, setFilter] = useState('');
  const rows = useMemo<RunComparisonRow[]>(() => {
    const artifactStages = evidence.artifacts.map((artifact) => `${artifact.source_stage}:${artifact.status}`).join(', ');
    return status.first_viewport.cards.map((card) => ({
      metric: CARD_COPY[card.id]?.title ?? card.title,
      value: compactCardValue(card),
      status: statusLabel(card.status),
      evidence: card.id === 'd0_d9_gate_status' ? artifactStages : card.label,
      source: `backend:first_viewport.${card.id}`,
    }));
  }, [evidence.artifacts, status.first_viewport.cards]);
  const data = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(needle));
  }, [filter, rows]);
  const columnHelper = createColumnHelper<RunComparisonRow>();
  const columns = useMemo(
    () => [
      columnHelper.accessor('metric', { header: '지표' }),
      columnHelper.accessor('value', { header: '값' }),
      columnHelper.accessor('status', { header: '상태' }),
      columnHelper.accessor('evidence', { header: '증거 / 차단 사유' }),
      columnHelper.accessor('source', { header: '출처' }),
    ],
    [columnHelper],
  );
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="manifest-table-wrap" data-run-comparison-table="true">
      <label className="table-filter">
        <span>비교 테이블 필터</span>
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="NO-GO, 23bp, drawdown 검색" aria-label="선택 산출물 비교 테이블 필터" />
      </label>
      <table className="manifest-table">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>)}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AuditTimelineTable({ audit }: { audit: AuditPayload }) {
  const [filter, setFilter] = useState('');
  const rows = useMemo<AuditTimelineRow[]>(() => audit.events.map((event, index) => ({
    index: String(index + 1).padStart(2, '0'),
    event: String(event.event ?? 'unknown'),
    status: String(event.status ?? 'UNKNOWN'),
    details: String(event.details ?? event.workflow ?? event.job_id ?? '감사 세부 없음'),
  })), [audit.events]);
  const data = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(needle));
  }, [filter, rows]);
  const columnHelper = createColumnHelper<AuditTimelineRow>();
  const columns = useMemo(
    () => [
      columnHelper.accessor('index', { header: '#' }),
      columnHelper.accessor('event', { header: '이벤트' }),
      columnHelper.accessor('status', { header: '상태' }),
      columnHelper.accessor('details', { header: '세부 / 출처' }),
    ],
    [columnHelper],
  );
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="manifest-table-wrap" data-audit-timeline-table="true">
      <label className="table-filter">
        <span>감사 로그 필터</span>
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="guardrails, research_intent 검색" aria-label="감사 로그 필터" />
      </label>
      <table className="manifest-table">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>)}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
