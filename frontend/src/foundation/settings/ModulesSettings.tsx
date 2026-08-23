import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '../../api/client';
import {
  attachModule,
  detachModule,
  renameModule,
  reorderModules,
  type ModuleInstance,
} from '../../api/modules';
import { getModuleDefinitionById } from '../modules/registry';
import { useModuleProjectionStore } from '../modules/store';

function sortInstances(items: ModuleInstance[]) {
  return [...items].sort((left, right) => left.sort_order - right.sort_order || left.module_id.localeCompare(right.module_id));
}

export function ModulesSettings() {
  const instances = useModuleProjectionStore(state => state.instances);
  const status = useModuleProjectionStore(state => state.status);
  const projectionError = useModuleProjectionStore(state => state.error);
  const refresh = useModuleProjectionStore(state => state.refresh);
  const replaceInstance = useModuleProjectionStore(state => state.replaceInstance);
  const setInstances = useModuleProjectionStore(state => state.setInstances);
  const [draftNames, setDraftNames] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'idle') void refresh();
  }, [refresh, status]);

  useEffect(() => {
    setDraftNames(Object.fromEntries(instances.map(item => [item.module_id, item.display_name])));
  }, [instances]);

  const ordered = useMemo(() => sortInstances(instances), [instances]);
  const attached = useMemo(() => ordered.filter(item => item.attached), [ordered]);
  const adminBusy = Boolean(busy);

  const run = async (key: string, action: () => Promise<void>, success: string) => {
    setBusy(key);
    setMessage(null);
    try {
      await action();
      setMessage(success);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setMessage('Trạng thái Module đã thay đổi. Hãy làm mới trước khi thử lại.');
      } else {
        setMessage('Không thể cập nhật Module. Không có thay đổi nào được xác nhận.');
      }
    } finally {
      setBusy(null);
    }
  };

  const changeAttachment = async (item: ModuleInstance) => {
    const key = `${item.attached ? 'detach' : 'attach'}-${item.module_id}`;
    await run(
      key,
      async () => {
        const updated = item.attached
          ? await detachModule(item.module_id, item.revision)
          : await attachModule(item.module_id, item.revision);
        replaceInstance(updated);
      },
      item.attached
        ? 'Đã tháo Module khỏi điều hướng. Dữ liệu của Module được giữ nguyên.'
        : 'Đã gắn Module vào điều hướng.',
    );
  };

  const saveName = async (item: ModuleInstance) => {
    const value = (draftNames[item.module_id] ?? item.display_name).trim();
    if (!value || value === item.display_name) return;
    await run(
      `rename-${item.module_id}`,
      async () => {
        const updated = await renameModule(item.module_id, value, item.revision);
        replaceInstance(updated);
      },
      'Đã đổi tên hiển thị. ID, route và dữ liệu Module không thay đổi.',
    );
  };

  const moveAttached = async (item: ModuleInstance, direction: -1 | 1) => {
    const currentIndex = attached.findIndex(candidate => candidate.module_id === item.module_id);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= attached.length) return;
    const next = [...attached];
    [next[currentIndex], next[targetIndex]] = [next[targetIndex], next[currentIndex]];
    const expectedRevisions = Object.fromEntries(attached.map(candidate => [candidate.module_id, candidate.revision]));
    await run(
      `move-${item.module_id}`,
      async () => {
        const updated = await reorderModules(next.map(candidate => candidate.module_id), expectedRevisions);
        setInstances(updated);
      },
      'Đã cập nhật thứ tự Module.',
    );
  };

  return (
    <section className="model-settings-panel" aria-labelledby="module-settings-title">
      <header>
        <h2 id="module-settings-title">Modules</h2>
        <p>Chỉ bạn quản trị việc gắn, tháo, đổi tên hiển thị và sắp xếp Module. Trợ lý GYO không có các quyền quản trị này.</p>
      </header>

      {message && (
        <div className="inline-note" role="status">
          {message}
          <button className="btn-secondary compact-button" type="button" onClick={() => void refresh()}>Làm mới</button>
        </div>
      )}
      {status === 'error' && (
        <div className="runtime-guidance" role="status">
          {projectionError ?? 'Chưa tải được trạng thái Modules.'}
          <button className="btn-secondary compact-button" type="button" onClick={() => void refresh()}>Thử lại</button>
        </div>
      )}
      {status === 'loading' && instances.length === 0 && <p className="muted-copy" role="status">Đang tải Modules…</p>}

      <div className="gyo-profile-list" aria-label="Quản lý Modules">
        {ordered.map(item => {
          const definition = getModuleDefinitionById(item.module_id);
          if (!definition) return null;
          const attachedIndex = attached.findIndex(candidate => candidate.module_id === item.module_id);
          return (
            <article key={item.module_id}>
              <header>
                <div>
                  <strong>{item.display_name}</strong>
                  <small>ID {item.module_id} · route {definition.path} · {item.source_kind === 'builtin' ? 'tích hợp sẵn' : 'Marketplace'}</small>
                </div>
                <span className={`status-badge ${item.attached ? 'ready' : ''}`}>{item.attached ? 'Đã gắn' : 'Đã tháo'}</span>
              </header>

              <div className="gyo-profile-actions">
                <input
                  aria-label={`Tên hiển thị cho ${item.module_id}`}
                  value={draftNames[item.module_id] ?? item.display_name}
                  maxLength={80}
                  onChange={event => setDraftNames(current => ({ ...current, [item.module_id]: event.target.value }))}
                />
                <button
                  className="btn-secondary compact-button"
                  type="button"
                  disabled={adminBusy || !(draftNames[item.module_id] ?? '').trim() || (draftNames[item.module_id] ?? '').trim() === item.display_name}
                  onClick={() => void saveName(item)}
                >
                  Lưu tên
                </button>
                <button
                  className="btn-secondary compact-button"
                  type="button"
                  disabled={adminBusy}
                  onClick={() => void changeAttachment(item)}
                >
                  {item.attached ? 'Tháo khỏi điều hướng' : 'Gắn vào điều hướng'}
                </button>
                {item.attached && (
                  <>
                    <button className="btn-secondary compact-button" type="button" disabled={adminBusy || attachedIndex <= 0} onClick={() => void moveAttached(item, -1)}>Lên</button>
                    <button className="btn-secondary compact-button" type="button" disabled={adminBusy || attachedIndex < 0 || attachedIndex >= attached.length - 1} onClick={() => void moveAttached(item, 1)}>Xuống</button>
                  </>
                )}
              </div>
              <p className="muted-copy">Tháo Module chỉ ẩn khỏi điều hướng; dữ liệu vẫn được giữ nguyên. Khu vực này không cung cấp thao tác xóa dữ liệu Module.</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
