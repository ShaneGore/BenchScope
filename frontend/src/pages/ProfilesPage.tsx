import { useState } from 'react';
import { Pencil, Plus, Trash2, UserCog } from 'lucide-react';
import type { ApiError, ModelProfile } from '@/types';
import { getBenchmarkService } from '@/services/benchmark-service';
import { APP_MODE, canDelete, canEditProfiles, showEndpointFields } from '@/lib/mode';
import { useAsync } from '@/lib/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Field, TextInput } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { EmptyState, ErrorState, SkeletonText } from '@/components/ui/State';

interface ProfileFormState {
  name: string;
  model_name: string;
  quantization: string;
  context_length: string;
  inference_engine: string;
  endpoint_url: string;
}

const emptyForm: ProfileFormState = {
  name: '',
  model_name: '',
  quantization: '',
  context_length: '',
  inference_engine: '',
  endpoint_url: '',
};

function fromProfile(p: ModelProfile): ProfileFormState {
  return {
    name: p.name,
    model_name: p.model_name,
    quantization: p.quantization ?? '',
    context_length: p.context_length != null ? String(p.context_length) : '',
    inference_engine: p.inference_engine ?? '',
    endpoint_url: p.endpoint_url ?? '',
  };
}

function toPayload(f: ProfileFormState): Omit<ModelProfile, 'id' | 'owner_id' | 'created_at' | 'updated_at'> {
  return {
    name: f.name.trim(),
    model_name: f.model_name.trim(),
    quantization: f.quantization.trim() || null,
    context_length: f.context_length.trim() ? Number(f.context_length) : null,
    inference_engine: f.inference_engine.trim() || null,
    endpoint_url: showEndpointFields ? f.endpoint_url.trim() || null : null,
  };
}

export function ProfilesPage() {
  const store = getBenchmarkService(APP_MODE);
  const { data, loading, error, refetch } = useAsync(() => store.listProfiles(), []);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ModelProfile | null>(null);
  const [form, setForm] = useState<ProfileFormState>(emptyForm);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const profiles = data ?? [];

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  };

  const openEdit = (p: ModelProfile) => {
    setEditing(p);
    setForm(fromProfile(p));
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  };
  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});
    try {
      const payload = toPayload(form);
      if (editing) {
        await store.updateProfile(editing.id, payload);
      } else {
        await store.createProfile(payload);
      }
      setFormOpen(false);
      refetch();
    } catch (e) {
      const err = e as ApiError;
      if (err.detail && typeof err.detail === 'object') {
        const mapped: Record<string, string> = {};
        Object.entries(err.detail).forEach(([k, v]) => {
          mapped[k] = String(v);
        });
        setFieldErrors(mapped);
      } else {
        setSubmitError(String(err.detail ?? 'Request failed'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleteBusy(true);
    try {
      await store.deleteProfile(deleteId);
      setDeleteId(null);
      refetch();
    } catch (e) {
      setSubmitError((e as ApiError).detail?.toString?.() ?? 'Delete failed');
    } finally {
      setDeleteBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Profiles</h1>
        <Card>
          <SkeletonText lines={6} />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Profiles</h1>
        <ErrorState onRetry={refetch} description="Could not load profiles." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primary tracking-tight">Model profiles</h1>
          <p className="text-sm text-text-secondary mt-1">
            Manage named model and configuration profiles.
          </p>
        </div>
        {canEditProfiles && (
          <Button size="sm" variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreate}>
            New profile
          </Button>
        )}
      </div>

      {submitError && (
        <div className="rounded-md border border-status-failed-border bg-status-failed-bg px-4 py-2 text-sm text-status-failed-fg">
          {submitError}
        </div>
      )}

      {profiles.length === 0 ? (
        <EmptyState
          icon={<UserCog className="h-9 w-9" strokeWidth={1.5} />}
          title="No profiles yet"
          description={
            canEditProfiles
              ? 'Create a profile to launch benchmarks and organise results.'
              : 'No profiles available in this mode.'
          }
          action={
            canEditProfiles ? (
              <Button size="md" variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreate}>
                Create profile
              </Button>
            ) : null
          }
        />
      ) : (
        <Card className="!p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface/40">
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                    Model
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide hidden sm:table-cell">
                    Quantization
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide hidden md:table-cell">
                    Engine
                  </th>
                  {showEndpointFields && (
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide hidden lg:table-cell">
                      Endpoint
                    </th>
                  )}
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">

                {profiles.map((p) => (
                  <tr key={p.id} className="hover:bg-surface-raised/30">
                    <td className="px-4 py-3 font-medium text-text-primary">{p.name}</td>
                    <td className="px-4 py-3 text-text-secondary font-mono text-xs">{p.model_name}</td>
                    <td className="px-4 py-3 text-text-secondary hidden sm:table-cell">
                      {p.quantization ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-text-secondary hidden md:table-cell">
                      {p.inference_engine ?? '—'}
                    </td>
                    {showEndpointFields && (
                      <td className="px-4 py-3 text-text-secondary font-mono text-xs hidden lg:table-cell">
                        {p.endpoint_url ?? '—'}
                      </td>
                    )}
                    <td className="px-4 py-3 text-right">
                      {canEditProfiles && (
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => openEdit(p)}
                            className="p-1.5 text-text-muted hover:text-text-primary transition-colors"
                            aria-label={`Edit ${p.name}`}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          {canDelete && (
                            <button
                              onClick={() => setDeleteId(p.id)}
                              className="p-1.5 text-text-muted hover:text-status-failed-fg transition-colors"
                              aria-label={`Delete ${p.name}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit profile' : 'New profile'}
        maxWidth="lg"
        footer={
          <>
            <Button size="sm" variant="ghost" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" variant="primary" loading={submitting} onClick={handleSubmit}>
              {editing ? 'Save' : 'Create'}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Field label="Name" required error={fieldErrors.name}>
            <TextInput
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              invalid={!!fieldErrors.name}
            />
          </Field>
          <Field label="Model name" required error={fieldErrors.model_name}>
            <TextInput
              value={form.model_name}
              onChange={(e) => setForm({ ...form, model_name: e.target.value })}
              invalid={!!fieldErrors.model_name}
            />
          </Field>
          <Field label="Quantization">
            <TextInput
              value={form.quantization}
              onChange={(e) => setForm({ ...form, quantization: e.target.value })}
            />
          </Field>
          <Field label="Context length">
            <TextInput
              type="number"
              value={form.context_length}
              onChange={(e) => setForm({ ...form, context_length: e.target.value })}
            />
          </Field>
          <Field label="Inference engine">
            <TextInput
              value={form.inference_engine}
              onChange={(e) => setForm({ ...form, inference_engine: e.target.value })}
            />
          </Field>
          {showEndpointFields && (
            <>
              <Field label="Endpoint URL">
                <TextInput
                  value={form.endpoint_url}
                  onChange={(e) => setForm({ ...form, endpoint_url: e.target.value })}
                />
              </Field>
            </>
          )}
        </div>
      </Modal>

      <Modal
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Delete profile"
        footer={
          <>
            <Button size="sm" variant="ghost" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button size="sm" variant="danger" loading={deleteBusy} onClick={handleDelete}>
              Delete
            </Button>
          </>
        }
      >
        <p>
          This will permanently remove profile <span className="font-mono text-text-primary">{deleteId}</span>.
          Runs retain their profile snapshot.
        </p>
      </Modal>
    </div>
  );
}
