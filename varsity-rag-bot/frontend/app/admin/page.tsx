"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ChevronLeft, ChevronRight, Database, FileUp, LoaderCircle, RefreshCw, Trash2, UsersRound } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import {
  ApiError,
  deleteAdminDocument,
  getAdminDocuments,
  getAdminOverview,
  getAdminUsers,
  reindexAdminDocuments,
  uploadAdminDocument,
  type AdminDocument,
  type AdminOverview,
  type UserProfile,
} from "@/lib/api";

const USERS_PER_PAGE = 25;

const formatSize = (size: number) =>
  size < 1024 * 1024
    ? `${(size / 1024).toFixed(1)} KB`
    : `${(size / (1024 * 1024)).toFixed(1)} MB`;

export default function AdminPage() {
  const router = useRouter();
  const { accessToken, user } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [userOffset, setUserOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setError("");
    try {
      const [nextOverview, nextDocuments, nextUsers] = await Promise.all([
        getAdminOverview(accessToken),
        getAdminDocuments(accessToken),
        getAdminUsers(accessToken, userOffset, USERS_PER_PAGE),
      ]);
      setOverview(nextOverview);
      setDocuments(nextDocuments);
      setUsers(nextUsers.users);
      setUserTotal(nextUsers.total);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace("/login");
        return;
      }
      setError(caught instanceof Error ? caught.message : "Unable to load admin data.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, router, userOffset]);

  useEffect(() => {
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    if (user?.role !== "admin") {
      router.replace("/");
      return;
    }
    void refresh();
  }, [accessToken, refresh, router, user]);

  const runReindex = async () => {
    if (!accessToken) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await reindexAdminDocuments(accessToken);
      setNotice(`${result.message} ${result.indexed_chunk_count} chunks from ${result.source_document_count} documents.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Re-indexing failed.");
    } finally {
      setBusy(false);
    }
  };

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!accessToken || !file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await uploadAdminDocument(accessToken, file);
      setNotice(`${file.name} uploaded and indexed.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed.");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  };

  const remove = async (filename: string) => {
    if (!accessToken || !window.confirm(`Delete ${filename}?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await deleteAdminDocument(accessToken, filename.split(/[\\/]/).pop() ?? filename);
      setNotice(`${filename} deleted and the index was refreshed.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Document deletion failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!user || user.role !== "admin") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas text-sm text-muted">
        Checking administrator access…
      </main>
    );
  }

  const stats = overview
    ? [
        ["Users", overview.user_count],
        ["Chat responses", overview.chat_count],
        ["Source documents", overview.source_document_count],
        ["Indexed chunks", overview.indexed_chunk_count],
      ]
    : [];

  return (
    <main className="min-h-screen bg-canvas px-4 py-8 text-ink sm:px-8">
      <div className="mx-auto max-w-6xl">
        <button
          className="mb-7 inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink"
          onClick={() => router.push("/")}
          type="button"
        >
          <ArrowLeft size={16} aria-hidden="true" /> Back to assistant
        </button>

        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-brand">
              EU-AI · Administration
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">Knowledge & system overview</h1>
            <p className="mt-2 text-sm text-muted">{overview?.application}</p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold shadow-sm hover:bg-slate-50 disabled:opacity-50"
            disabled={busy || loading}
            onClick={() => void refresh()}
            type="button"
          >
            <RefreshCw size={16} aria-hidden="true" /> Refresh
          </button>
        </header>

        {error && <p className="mb-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-800" role="alert">{error}</p>}
        {notice && <p className="mb-5 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900" role="status">{notice}</p>}

        <section aria-label="System metrics" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map(([label, value]) => (
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" key={label}>
              <p className="text-sm text-muted">{label}</p>
              <p className="mt-2 text-3xl font-semibold">{loading ? "—" : value}</p>
            </article>
          ))}
        </section>

        <section className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
            <div>
              <h2 className="flex items-center gap-2 font-semibold">
                <UsersRound size={18} className="text-brand" aria-hidden="true" />
                Registered users
              </h2>
              <p className="mt-1 text-sm text-muted">
                Account profile information only; passwords and credential data are never shown.
              </p>
            </div>
            <p className="text-sm font-medium text-muted">
              {userTotal} {userTotal === 1 ? "account" : "accounts"}
            </p>
          </div>
          {loading ? (
            <p className="p-6 text-sm text-muted">Loading user accounts…</p>
          ) : users.length === 0 ? (
            <p className="p-6 text-sm text-muted">No registered users found.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Name</th>
                      <th className="px-5 py-3 font-semibold">Student ID</th>
                      <th className="px-5 py-3 font-semibold">Email</th>
                      <th className="px-5 py-3 font-semibold">Role</th>
                      <th className="px-5 py-3 font-semibold">Registered</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {users.map((account) => (
                      <tr key={account.id}>
                        <td className="px-5 py-3.5 font-medium">{account.full_name}</td>
                        <td className="px-5 py-3.5">{account.student_id ?? "—"}</td>
                        <td className="px-5 py-3.5">{account.email}</td>
                        <td className="px-5 py-3.5">
                          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold capitalize text-emerald-800">
                            {account.role}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-muted">
                          {new Date(account.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
                <p className="text-xs text-muted">
                  Showing {userOffset + 1}–{Math.min(userOffset + users.length, userTotal)} of {userTotal}
                </p>
                <div className="flex gap-2">
                  <button
                    aria-label="Previous users"
                    className="rounded-lg border border-slate-200 p-2 hover:bg-slate-50 disabled:opacity-40"
                    disabled={userOffset === 0 || loading}
                    onClick={() => setUserOffset((current) => Math.max(0, current - USERS_PER_PAGE))}
                    type="button"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    aria-label="Next users"
                    className="rounded-lg border border-slate-200 p-2 hover:bg-slate-50 disabled:opacity-40"
                    disabled={userOffset + users.length >= userTotal || loading}
                    onClick={() => setUserOffset((current) => current + USERS_PER_PAGE)}
                    type="button"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </>
          )}
        </section>

        {overview && (
          <section className="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 font-semibold">
              <Database size={18} className="text-brand" aria-hidden="true" /> Software information
            </h2>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div><dt className="text-muted">Version</dt><dd className="mt-0.5">{overview.application_version}</dd></div>
              <div><dt className="text-muted">Python runtime</dt><dd className="mt-0.5">{overview.python_version}</dd></div>
              <div><dt className="text-muted">Database</dt><dd className="mt-0.5">{overview.database_engine} · {overview.database_status}</dd></div>
              <div><dt className="text-muted">RAG provider / chat model</dt><dd className="mt-0.5">{overview.rag_provider} · {overview.chat_model}</dd></div>
              <div><dt className="text-muted">Embedding model</dt><dd className="mt-0.5">{overview.embedding_model}</dd></div>
              <div><dt className="text-muted">Vector store</dt><dd className="mt-0.5">{overview.vector_store}</dd></div>
            </dl>
          </section>
        )}

        <section className="mt-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-5">
            <div>
              <h2 className="font-semibold">Knowledge documents</h2>
              <p className="mt-1 text-sm text-muted">Add PDF, Markdown, or text files (up to 20 MiB).</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-900">
                <FileUp size={16} aria-hidden="true" /> Upload document
                <input accept=".pdf,.md,.txt" className="sr-only" disabled={busy} onChange={upload} type="file" />
              </label>
              <button
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50"
                disabled={busy}
                onClick={() => void runReindex()}
                type="button"
              >
                {busy ? <LoaderCircle className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                Re-index all
              </button>
            </div>
          </div>
          {loading ? (
            <p className="p-6 text-sm text-muted">Loading documents…</p>
          ) : documents.length === 0 ? (
            <p className="p-6 text-sm text-muted">No supported source documents found.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {documents.map((document) => (
                <li className="flex flex-wrap items-center justify-between gap-3 px-5 py-4" key={document.filename}>
                  <div className="min-w-0">
                    <p className="break-all text-sm font-medium">{document.filename}</p>
                    <p className="mt-1 text-xs text-muted">{formatSize(document.size_bytes)} · Updated {new Date(document.modified_at).toLocaleString()}</p>
                  </div>
                  {document.managed && (
                    <button
                      aria-label={`Delete ${document.filename}`}
                      className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                      disabled={busy}
                      onClick={() => void remove(document.filename)}
                      type="button"
                    >
                      <Trash2 size={15} aria-hidden="true" /> Delete
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
