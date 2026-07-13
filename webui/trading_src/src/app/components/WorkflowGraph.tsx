'use client';

import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react';
import type { WorkflowStep } from '../tradingTypes';
import { statusLabel, statusTone, STAGE_COPY } from '../tradingFormat';

export function WorkflowGraph({ steps }: { steps: WorkflowStep[] }) {
  const nodes: Node[] = steps.map((stage, index) => ({
    id: stage.step,
    position: { x: (index % 5) * 190, y: Math.floor(index / 5) * 122 },
    data: { label: `${stage.step} · ${STAGE_COPY[stage.step] ?? stage.name}\n${statusLabel(stage.status)}\n${stage.artifact_refs?.[0] ?? stage.source_run_id ?? 'artifact 없음'}` },
    className: `flow-node-${statusTone(stage.status)}`,
  }));
  const edges: Edge[] = steps.slice(0, -1).map((stage, index) => ({
    id: `${stage.step}-${steps[index + 1].step}`,
    source: stage.step,
    target: steps[index + 1].step,
    animated: steps[index + 1].step === 'D9',
    label: statusLabel(steps[index + 1].status),
    labelStyle: { fill: '#cfe9ff', fontSize: 10, fontWeight: 800 },
    markerEnd: { type: MarkerType.ArrowClosed, color: statusTone(steps[index + 1].status) === 'danger' ? '#fb7185' : '#38bdf8' },
    style: { stroke: statusTone(steps[index + 1].status) === 'danger' ? '#fb7185' : '#38bdf8', strokeDasharray: steps[index + 1].status === 'MISSING' ? '4 4' : undefined },
  }));

  return (
    <div className="flow-shell" data-react-flow-evidence="true" aria-label="D0-D9 연구 증거 흐름 그래프" role="group" title="각 노드는 백엔드 증거 상태와 artifact 출처를 보여주며 실행 가능 신호가 아닙니다.">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} zoomOnScroll={false} panOnDrag={false} proOptions={{ hideAttribution: true }}>
        <Background color="rgba(145,168,186,0.16)" gap={18} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
