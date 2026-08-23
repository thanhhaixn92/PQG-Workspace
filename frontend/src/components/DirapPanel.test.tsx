import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getWorkItemDetail,
  listKnowledgeRecords,
  listWorkItems,
  searchKnowledgeRecords,
  type DirapKnowledgeSearchResponse,
  type DirapKnowledgeSearchResult,
} from '../api/dirap';
import { useHermesStore } from '../store/store';
import { DirapPanel } from './DirapPanel';

// Mock toàn bộ API DIRAP; chỉ searchKnowledgeRecords là "controllable"
// (deferred) để tái hiện chính xác cuộc đua bất đồng bộ.
vi.mock('../api/dirap', () => ({
  listWorkItems: vi.fn(),
  createWorkItem: vi.fn(),
  getWorkItemDetail: vi.fn(),
  attachSourceFile: vi.fn(),
  extractSourceFile: vi.fn(),
  createKnowledgeRecord: vi.fn(),
  listKnowledgeRecords: vi.fn(),
  getKnowledgeRecordDetail: vi.fn(),
  submitKnowledgeRecord: vi.fn(),
  approveKnowledgeRecord: vi.fn(),
  rejectKnowledgeRecord: vi.fn(),
  getKnowledgeUsability: vi.fn(),
  searchKnowledgeRecords: vi.fn(),
  DIRAP_AUTHORITY_OPTIONS: [
    { value: 'regulatory', label: 'Quy phạm' },
    { value: 'organizational', label: 'Tổ chức' },
    { value: 'expert', label: 'Chuyên gia' },
    { value: 'derived', label: 'Dẫn xuất' },
  ],
  DIRAP_USABILITY_QUERY_TYPES: [
    'official_search',
    'exploratory_search',
    'analysis_input',
    'legal_review',
    'context_packaging',
    'memory_query',
  ],
}));

const mkResult = (id: string, excerpt: string): DirapKnowledgeSearchResult => ({
  record_id: id,
  content_excerpt: excerpt,
  provenance: 'line 1',
  lifecycle_state: 'active',
  source_verification_state: 'verified',
  calculation_verification_state: 'verified',
  owner_acceptance_state: 'accepted',
  authority_status: 'regulatory',
  matched_field: 'content',
  usability_state: 'usable',
});

const mkResp = (
  results: DirapKnowledgeSearchResult[],
  total: number,
  queryType: string,
  limit = 20,
  offset = 0,
): DirapKnowledgeSearchResponse => ({
  query_type: queryType as DirapKnowledgeSearchResponse['query_type'],
  total,
  limit,
  offset,
  results,
});

type PendingCall = {
  params: { q: string; queryType: string; limit?: number; offset?: number };
  resolve: (v: DirapKnowledgeSearchResponse) => void;
};

describe('DirapPanel — tìm kiếm tri thức có kiểm soát (hành vi giao diện)', () => {
  let pending: PendingCall[] = [];

  beforeEach(() => {
    pending = [];
    vi.clearAllMocks();

    useHermesStore.setState({ activeSessionId: 's1' });

    const wi = {
      task_id: 't1',
      session_id: 's1',
      title: 'WI Test',
      goal: null,
      status: 'in_progress',
      task_type: 'dirap',
      session_title: 'S1',
      workspace_path: 'C:\\tmp',
      source_files: [],
      created_at: 0,
      updated_at: 0,
      duplicate: false,
    };
    vi.mocked(listWorkItems).mockResolvedValue([wi]);
    vi.mocked(getWorkItemDetail).mockResolvedValue({
      work_item: wi,
      audit_events: [],
    });
    vi.mocked(listKnowledgeRecords).mockResolvedValue([]);

    vi.mocked(searchKnowledgeRecords).mockImplementation(
      (_taskId, params) =>
        new Promise<DirapKnowledgeSearchResponse>(resolve => {
          pending.push({ params, resolve });
        }),
    );
  });

  async function openDetailView() {
    render(<DirapPanel />);
    fireEvent.click(await screen.findByText('WI Test'));
    await screen.findByText('Tìm kiếm tri thức (chỉ đọc)');
  }

  function resolveNext(value: DirapKnowledgeSearchResponse, index = 0) {
    expect(pending[index]).toBeDefined();
    const [call] = pending.splice(index, 1);
    call!.resolve(value);
  }

  it('không hiển thị danh sách work item trả về muộn của phiên cũ', async () => {
    const resolvers: Array<(value: any[]) => void> = [];
    vi.mocked(listWorkItems).mockImplementation(() => new Promise(resolve => resolvers.push(resolve)));
    render(<DirapPanel />);
    expect(resolvers).toHaveLength(1);

    act(() => useHermesStore.getState().setActiveSession('s2'));
    await waitFor(() => expect(resolvers).toHaveLength(2));
    resolvers[1]!([{
      task_id: 't2', session_id: 's2', title: 'Work B', goal: null,
      status: 'in_progress', task_type: 'dirap', session_title: 'S2',
      workspace_path: 'C:\\tmp-b', source_files: [], created_at: 0, updated_at: 0, duplicate: false,
    }]);
    expect(await screen.findByText('Work B')).toBeDefined();

    resolvers[0]!([{
      task_id: 't1', session_id: 's1', title: 'Work A stale', goal: null,
      status: 'in_progress', task_type: 'dirap', session_title: 'S1',
      workspace_path: 'C:\\tmp-a', source_files: [], created_at: 0, updated_at: 0, duplicate: false,
    }]);
    await Promise.resolve();
    expect(screen.queryByText('Work A stale')).toBeNull();
    expect(screen.getByText('Work B')).toBeDefined();
  });

  it('đổi cụm từ xóa ngay kết quả cũ (không còn Tải thêm của truy vấn cũ)', async () => {
    await openDetailView();

    const input = screen.getByPlaceholderText('Cụm từ (tìm trong nội dung và nguồn)');

    // Tìm 'cầu' -> 1 kết quả cũ
    fireEvent.change(input, { target: { value: 'cầu' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    resolveNext(mkResp([mkResult('r-cau', 'Kết quả CẦU cũ')], 1, 'official_search'));
    await screen.findByText(/Kết quả CẦU cũ/);
    expect(screen.getByText(/1 kết quả đủ điều kiện/)).toBeDefined();

    // Đổi cụm từ -> kết quả cũ phải biến mất ngay, Tải thêm không còn
    fireEvent.change(input, { target: { value: 'cảng' } });
    await waitFor(() => {
      expect(screen.queryByText(/Kết quả CẦU cũ/)).toBeNull();
      expect(screen.queryByText(/kết quả đủ điều kiện/)).toBeNull();
      expect(screen.queryByRole('button', { name: /Tải thêm/ })).toBeNull();
    });

    // Tìm mới -> chỉ hiển thị kết quả mới, không ghép với kết quả cũ
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    resolveNext(mkResp([mkResult('r-cang', 'Kết quả CẢNG mới')], 1, 'official_search'));
    await screen.findByText(/Kết quả CẢNG mới/);
    expect(screen.queryByText(/Kết quả CẦU cũ/)).toBeNull();
  });

  it('đổi mục đích vô hiệu hóa kết quả cũ; Tải thêm sau đó dùng offset 0 của truy vấn mới', async () => {
    await openDetailView();

    const input = screen.getByPlaceholderText('Cụm từ (tìm trong nội dung và nguồn)');
    const select = screen.getByRole('combobox');

    // Tìm 'cầu' với 3 kết quả, trang 1 chỉ 1 -> có nút Tải thêm
    fireEvent.change(input, { target: { value: 'cầu' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    resolveNext(mkResp([mkResult('r1', 'CẦU trang 1')], 3, 'official_search', 1, 0));
    await screen.findByText(/CẦU trang 1/);
    fireEvent.click(screen.getByRole('button', { name: /Tải thêm/ }));
    resolveNext(mkResp([mkResult('r2', 'CẦU trang 2')], 3, 'official_search', 1, 1));
    await screen.findByText(/CẦU trang 2/);

    // Đổi mục đích -> kết quả cũ (2 trang) biến mất ngay, Tải thêm biến mất
    fireEvent.change(select, { target: { value: 'exploratory_search' } });
    await waitFor(() => {
      expect(screen.queryByText(/CẦU trang 1/)).toBeNull();
      expect(screen.queryByText(/CẦU trang 2/)).toBeNull();
      expect(screen.queryByRole('button', { name: /Tải thêm/ })).toBeNull();
    });

    // Tìm lại với mục đích mới -> offset phải reset về 0
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    resolveNext(mkResp([mkResult('r3', 'KẾT QUẢ MỚI exploratory')], 1, 'exploratory_search', 20, 0));
    await screen.findByText(/KẾT QUẢ MỚI exploratory/);

    const calls = vi.mocked(searchKnowledgeRecords).mock.calls;
    const lastCall = calls[calls.length - 1];
    expect(lastCall[1].q).toBe('cầu');
    expect(lastCall[1].queryType).toBe('exploratory_search');
    expect(lastCall[1].offset).toBe(0);
  });

  it('phản hồi bất đồng bộ cũ không ghi đè truy vấn mới (đổi cụm từ giữa chừng)', async () => {
    await openDetailView();

    const input = screen.getByPlaceholderText('Cụm từ (tìm trong nội dung và nguồn)');

    // Bắt đầu tìm 'cầu' nhưng chưa trả về
    fireEvent.change(input, { target: { value: 'cầu' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    expect(pending).toHaveLength(1);

    // Đổi cụm từ trong lúc truy vấn A đang chạy: phản hồi A bị vô hiệu ngay,
    // kết quả cũ xóa, VÀ nút "Tìm" được giải phóng (không còn khoá vô thời hạn).
    fireEvent.change(input, { target: { value: 'cảng' } });
    const searchBtn = screen.getByRole('button', { name: 'Tìm' }) as HTMLButtonElement;
    expect(searchBtn.disabled).toBe(false);
    fireEvent.click(searchBtn);
    expect(pending).toHaveLength(2);

    // Truy vấn MỚI ('cảng', index 1) trả về trước -> hiển thị kết quả mới
    resolveNext(mkResp([mkResult('r-moi', 'Kết quả CẢNG mới')], 1, 'official_search'), 1);
    await screen.findByText(/Kết quả CẢNG mới/);

    // Phản hồi cũ của 'cầu' (index 0) về sau -> phải bị bỏ, không ghi đè/ghép
    resolveNext(mkResp([mkResult('r-cu', 'Kết quả CẦU cũ')], 1, 'official_search'), 0);
    await waitFor(() => {
      expect(screen.queryByText(/Kết quả CẦU cũ/)).toBeNull();
    });
    expect(screen.getByText(/Kết quả CẢNG mới/)).toBeDefined();
    expect(screen.getByText(/1 kết quả đủ điều kiện/)).toBeDefined();
  });

  it('đổi mục đích giữa chừng giải phóng nút Tìm; phản hồi cũ không ghi đè truy vấn mới', async () => {
    await openDetailView();

    const input = screen.getByPlaceholderText('Cụm từ (tìm trong nội dung và nguồn)');
    const select = screen.getByRole('combobox');

    // Bước 1: chạy truy vấn A ('official_search') chưa trả về -> nút khoá khi busy
    fireEvent.change(input, { target: { value: 'cầu' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    expect(pending).toHaveLength(1);
    const busyBtn = screen.getByRole('button', { name: 'Đang tìm...' }) as HTMLButtonElement;
    expect(busyBtn.disabled).toBe(true);

    // Bước 2: đổi mục đích giữa chừng -> bước 3: nút "Tìm" được bật lại ngay
    fireEvent.change(select, { target: { value: 'exploratory_search' } });
    const searchBtn = screen.getByRole('button', { name: 'Tìm' }) as HTMLButtonElement;
    expect(searchBtn.disabled).toBe(false);

    // Bước 4: bấm nút "Tìm" (không dùng Enter) để chạy truy vấn B
    fireEvent.click(searchBtn);
    expect(pending).toHaveLength(2);
    expect(pending[1].params.queryType).toBe('exploratory_search');

    // Bước 5: B trả về trước -> hiển thị kết quả B
    resolveNext(mkResp([mkResult('rb', 'Kết quả B (exploratory)')], 1, 'exploratory_search'), 1);
    await screen.findByText(/Kết quả B \(exploratory\)/);

    // Bước 6: A trả về sau -> không ghi đè/ghép kết quả B
    resolveNext(mkResp([mkResult('ra', 'Kết quả A (official)')], 1, 'official_search'), 0);
    await waitFor(() => {
      expect(screen.queryByText(/Kết quả A \(official\)/)).toBeNull();
    });
    expect(screen.getByText(/Kết quả B \(exploratory\)/)).toBeDefined();
    // Notice phản ánh đúng truy vấn mới (mục đích exploratory), not A
    expect(screen.getByText(/cho .*exploratory_search/)).toBeDefined();
    // Sau toàn bộ quá trình, nút Tìm không bị khoá lại
    expect((screen.getByRole('button', { name: 'Tìm' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('does not dispatch a duplicate request when Enter is pressed while search is busy', async () => {
    await openDetailView();

    const input = screen.getByPlaceholderText('Cụm từ (tìm trong nội dung và nguồn)');
    fireEvent.change(input, { target: { value: 'cầu' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));
    expect(pending).toHaveLength(1);

    fireEvent.keyDown(input, { key: 'Enter' });
    expect(pending).toHaveLength(1);

    resolveNext(mkResp([mkResult('r1', 'Kết quả cầu')], 1, 'official_search'));
    await screen.findByText(/Kết quả cầu/);
  });
});
