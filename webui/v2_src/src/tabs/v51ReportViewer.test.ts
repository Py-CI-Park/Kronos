import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';

const viewerSource = readFileSync(new URL('./V51ReportViewer.svelte', import.meta.url), 'utf8');
const docsSource = readFileSync(new URL('./DocsTab.svelte', import.meta.url), 'utf8');

function assertIncludesAll(source: string, labels: readonly string[]): void {
  for (const label of labels) {
    assert.ok(source.includes(label), `missing exact label: ${label}`);
  }
}

test('V5.1 report viewer is shell-v5 only and uses the GET-only v51 report client', () => {
  assert.ok(docsSource.includes("shell === 'v5'"));
  assert.ok(docsSource.includes('<V51ReportViewer />'));
  assert.ok(viewerSource.includes('v51Api.listReports()'));
  assert.ok(viewerSource.includes('v51Api.readReport(reportId)'));
  assertIncludesAll(viewerSource, [
    'V5.1 Report catalog/list/read viewer',
    'GET-only · read-only',
    'NO writes · NO downloads',
    'Wiki/HTML 리포트 뷰어',
  ]);
});

test('report selection state rejects stale reads and preserves selected report identity', () => {
  assert.ok(viewerSource.includes('let selectedReportId = $state<string | null>(null);'));
  assert.ok(viewerSource.includes('let reportReadToken = 0;'));
  assert.ok(viewerSource.includes('selectedReportId = reportId;'));
  assert.ok(viewerSource.includes('const requestToken = ++reportReadToken;'));
  assert.ok(viewerSource.includes('requestToken !== reportReadToken || selectedReportId !== reportId'));
  assert.ok(viewerSource.includes('data-v51-selected-report={selectedReportId ??'));
  assert.ok(viewerSource.includes('data-active={selectedReportId === report.report_id'));
});

test('XSS-safe rendering contract only injects escaped-pre safe_html and otherwise renders text', () => {
  assert.ok(viewerSource.includes('ESCAPED_PRE_SAFE_HTML'));
  assert.ok(viewerSource.includes('data-kronos-report-html="escaped-pre"'));
  assert.ok(viewerSource.includes('isEscapedPreSafeHtml(content.safe_html)'));
  assert.ok(viewerSource.includes("mode: 'safe_html_escaped_pre'"));
  assert.ok(viewerSource.includes("mode: 'text_fallback'"));
  assert.ok(viewerSource.includes('{@html renderableReportContent.safeHtml}'));
  assert.ok(!viewerSource.includes('{@html selectedReportRead'));
  assert.ok(!viewerSource.includes('{@html selectedSummary'));
  assert.ok(!viewerSource.includes('{@html renderableReportContent.text}'));
  assert.ok(viewerSource.includes('<pre class="v51-report-text">{renderableReportContent.text}</pre>'));
});

test('report metadata and blocked/error labels stay exact for source, date, hash, and UTF-8 Korean', () => {
  assertIncludesAll(viewerSource, [
    'content_hash',
    'catalog_source',
    'updated_at=',
    'generated_at=',
    'safe_html=escaped-pre · raw_text fallback only',
    'charset=utf-8',
    'BLOCKED ·',
    'ERROR ·',
    'NOT_SELECTED',
    'NOT_RUN',
  ]);
});
