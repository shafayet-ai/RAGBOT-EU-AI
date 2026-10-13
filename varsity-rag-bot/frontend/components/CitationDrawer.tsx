"use client";

import { useEffect } from "react";
import { ArrowUpRight, BookOpen, FileText, X } from "lucide-react";
import type { Citation, Language } from "@/lib/api";

interface CitationDrawerProps {
  citation: Citation | null;
  language: Language;
  onClose: () => void;
}

export default function CitationDrawer({
  citation,
  language,
  onClose,
}: CitationDrawerProps) {
  const copy =
    language === "bn"
      ? {
          official: "অফিসিয়াল সূত্র",
          close: "সূত্রের বিবরণ বন্ধ করুন",
          passage: "প্রাসঙ্গিক অংশ",
          page: "পৃষ্ঠা",
          open: "মূল সূত্র খুলুন",
          note: "উত্তরগুলো পাওয়া বিশ্ববিদ্যালয়-নথির ভিত্তিতে তৈরি। সময়-সংবেদনশীল তথ্য অফিসিয়াল সূত্রে যাচাই করুন।",
        }
      : {
          official: "Official source",
          close: "Close source details",
          passage: "Retrieved passage",
          page: "Page",
          open: "Open original source",
          note: "Answers are generated from retrieved university documents. Confirm time-sensitive details with the official source.",
        };
  useEffect(() => {
    if (!citation) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [citation, onClose]);

  if (!citation) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/35 backdrop-blur-[2px]"
      onClick={onClose}
      role="presentation"
    >
      <section
        aria-labelledby="citation-title"
        aria-modal="true"
        className="flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
          <div className="flex items-start gap-3">
            <span className="rounded-xl bg-emerald-50 p-2.5 text-brand">
              <BookOpen size={19} aria-hidden="true" />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                {copy.official}
              </p>
              <h2
                className="mt-1 max-w-[270px] text-base font-semibold leading-6 text-ink"
                id="citation-title"
              >
                {citation.title}
              </h2>
            </div>
          </div>
          <button
            aria-label={copy.close}
            className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-ink"
            onClick={onClose}
            type="button"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="scrollbar-subtle flex-1 space-y-6 overflow-y-auto px-6 py-6">
          <div className="flex flex-wrap gap-2">
            {citation.section && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {citation.section}
              </span>
            )}
            {citation.page !== null && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {copy.page} {citation.page}
              </span>
            )}
          </div>

          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
              <FileText size={16} className="text-brand" aria-hidden="true" />
              {copy.passage}
            </h3>
            <blockquote className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-7 text-slate-700">
              {citation.snippet}
            </blockquote>
          </div>

          {citation.url && (
            <a
              className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-900 focus:outline-none focus:ring-4 focus:ring-emerald-100"
              href={citation.url}
              rel="noreferrer"
              target="_blank"
            >
              {copy.open}
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          )}
        </div>

        <footer className="border-t border-slate-100 px-6 py-4 text-xs leading-5 text-muted">
          {copy.note}
        </footer>
      </section>
    </div>
  );
}
