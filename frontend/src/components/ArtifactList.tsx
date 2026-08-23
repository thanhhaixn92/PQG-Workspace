import { FileText } from 'lucide-react';
import type { Artifact } from '../api/artifacts';

export function ArtifactList({ artifacts, sessionId, baseUrl }: { artifacts: Artifact[]; sessionId: string; baseUrl: string }) {
  return <div className="artifact-list">
    {artifacts.map(artifact => <div className="artifact-item" key={artifact.id}>
      <FileText size={15} />
      <div>
        <a href={`${baseUrl}/api/sessions/${sessionId}/artifacts/${artifact.id}/content`} target="_blank" rel="noreferrer">
          <strong>{artifact.relative_path.split('/').at(-1)}</strong>
        </a>
        <div className="runtime-guidance">
          {artifact.kind === 'report_markdown' ? 'Báo cáo Markdown' : artifact.kind === 'report_html' ? 'Báo cáo HTML · mở để in PDF' : artifact.kind === 'imported_file' ? 'Tệp đã nhập' : artifact.kind}
        </div>
      </div>
    </div>)}
  </div>;
}
