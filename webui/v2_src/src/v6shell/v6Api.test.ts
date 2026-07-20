import assert from 'node:assert/strict';
import test from 'node:test';
import { v6ProjectReportHtmlUrl, v6ReportHtmlUrl } from './v6Api';

test('project report URL separates inline viewing from download', () => {
  assert.equal(
    v6ProjectReportHtmlUrl('project id/한글'),
    '/api/v6/project-report-html?project=project%20id%2F%ED%95%9C%EA%B8%80',
  );
  assert.equal(
    v6ProjectReportHtmlUrl('project id/한글', true),
    '/api/v6/project-report-html?project=project%20id%2F%ED%95%9C%EA%B8%80&download=1',
  );
});

test('single-run report URL keeps the same view and download contract', () => {
  assert.equal(
    v6ReportHtmlUrl('dataset 1', 'train/1'),
    '/api/v6/report-html?dataset=dataset%201&train=train%2F1',
  );
  assert.equal(
    v6ReportHtmlUrl('dataset 1', 'train/1', true),
    '/api/v6/report-html?dataset=dataset%201&train=train%2F1&download=1',
  );
});
