"use client";

import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  FileText,
  Globe2,
  GraduationCap,
  Languages,
  LoaderCircle,
  Menu,
  MessageCircle,
  Moon,
  Plus,
  ShieldCheck,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import CitationDrawer from "@/components/CitationDrawer";
import {
  getHealth,
  sendChat,
  type Citation,
  type ChatRole,
  type Language,
} from "@/lib/api";

interface Message {
  id: string;
  role: ChatRole;
  content: string;
  sources?: Citation[];
  grounded?: boolean;
}

const COPY = {
  en: {
    brand: "Eastern University",
    assistant: "EU-AI assistant",
    newChat: "New conversation",
    language: "Language",
    appearance: "Appearance",
    lightMode: "Light",
    darkMode: "Dark",
    topics: "Explore",
    admission: "Admissions",
    curriculum: "CSE curriculum",
    faculty: "Faculty & officials",
    notices: "Department notices",
    library: "Knowledge library",
    files: "indexed files",
    sourceList: "View source files",
    privacy: "Grounded in university documents",
    connected: "Knowledge base online",
    offline: "Assistant offline",
    eyebrow: "Your campus, clearly answered",
    welcome: "A smarter way to find your way around EU.",
    description:
      "Ask about Eastern University admissions, programs, and campus information. Answers are grounded in the documents available to this assistant.",
    ask: "Ask your university assistant",
    askHint: "Choose a popular question or write your own.",
    suggestions: [
      "What are the CSE admission requirements?",
      "Which documents are needed for admission?",
      "Who are the CSE faculty and officials?",
      "Which programs does Eastern University offer?",
    ],
    placeholder: "Ask anything about Eastern University...",
    send: "Send question",
    thinking: "Searching university documents",
    sources: "Sources",
    grounded: "Source-backed",
    ungrounded: "Check with the university",
    citation: "View source",
    empty: "Start with a question about admissions, programs, or CSE.",
    connection:
      "Could not reach the assistant API. Please try again later.",
    confidence: "Evidence confidence",
    footer: "EU-AI can make mistakes. Check official sources for important decisions.",
    menu: "Open navigation",
    closeMenu: "Close navigation",
  },
  bn: {
    brand: "ইস্টার্ন ইউনিভার্সিটি",
    assistant: "EU-AI সহকারী",
    newChat: "নতুন কথোপকথন",
    language: "ভাষা",
    appearance: "রঙের ধরন",
    lightMode: "লাইট",
    darkMode: "ডার্ক",
    topics: "জানতে পারবেন",
    admission: "ভর্তি",
    curriculum: "CSE কারিকুলাম",
    faculty: "শিক্ষক ও কর্মকর্তা",
    notices: "বিভাগীয় নোটিশ",
    library: "নথির সংগ্রহ",
    files: "টি ইনডেক্স করা নথি",
    sourceList: "নথির তালিকা দেখুন",
    privacy: "বিশ্ববিদ্যালয়ের নথিভিত্তিক উত্তর",
    connected: "নথির সংগ্রহ সচল",
    offline: "সহকারী সংযোগ বিচ্ছিন্ন",
    eyebrow: "ক্যাম্পাসের তথ্য, সহজ উত্তরে",
    welcome: "ইস্টার্ন ইউনিভার্সিটির তথ্য জানুন সহজে।",
    description:
      "ভর্তি, প্রোগ্রাম, CSE বিভাগ ও ক্যাম্পাস সম্পর্কে প্রশ্ন করুন। এই সহকারী ইনডেক্স করা নথি থেকে উত্তর খোঁজে।",
    ask: "আপনার সহকারীকে প্রশ্ন করুন",
    askHint: "জনপ্রিয় প্রশ্ন থেকে বেছে নিন অথবা নিজের প্রশ্ন লিখুন।",
    suggestions: [
      "CSE ভর্তির যোগ্যতা কী?",
      "ভর্তির জন্য কী কী কাগজ লাগবে?",
      "CSE বিভাগের কর্মকর্তারা কারা?",
      "ইস্টার্ন ইউনিভার্সিটিতে কোন প্রোগ্রাম আছে?",
    ],
    placeholder: "ইস্টার্ন ইউনিভার্সিটি সম্পর্কে প্রশ্ন করুন...",
    send: "প্রশ্ন পাঠান",
    thinking: "বিশ্ববিদ্যালয়ের নথিতে খোঁজা হচ্ছে",
    sources: "সূত্র",
    grounded: "সূত্র-সমর্থিত",
    ungrounded: "বিশ্ববিদ্যালয়ে যাচাই করুন",
    citation: "নথি দেখুন",
    empty: "ভর্তি, প্রোগ্রাম বা CSE সম্পর্কে প্রশ্ন দিয়ে শুরু করুন।",
    connection:
      "সহকারী API-তে সংযোগ করা যায়নি। অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
    confidence: "তথ্যের নির্ভরযোগ্যতা",
    footer: "EU-AI ভুল করতে পারে। গুরুত্বপূর্ণ বিষয়ে অফিসিয়াল সূত্র যাচাই করুন।",
    menu: "নেভিগেশন খুলুন",
    closeMenu: "নেভিগেশন বন্ধ করুন",
  },
} satisfies Record<string, Record<string, string | string[]>>;

function makeConversationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

export default function ChatInterface() {
  const router = useRouter();
  const { accessToken, user, clearSession } = useAuth();
  const [language, setLanguage] = useState<Language>("en");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [conversationId, setConversationId] = useState(makeConversationId);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const t = COPY[language];
  const exploreActions = [
    {
      Icon: BookOpen,
      label: t.admission,
      question:
        language === "bn"
          ? "ভর্তির যোগ্যতা, আবেদন প্রক্রিয়া এবং প্রয়োজনীয় কাগজপত্র কী কী?"
          : "What are the admission requirements, application process, and required documents?",
    },
    {
      Icon: GraduationCap,
      label: t.curriculum,
      question:
        language === "bn"
          ? "CSE কারিকুলামে কী কী কোর্স আছে এবং ক্রেডিটের প্রয়োজনীয়তা কী?"
          : "Show me the CSE curriculum, including its courses and credit requirements.",
    },
    {
      Icon: MessageCircle,
      label: t.faculty,
      question:
        language === "bn"
          ? "CSE বিভাগের শিক্ষক ও কর্মকর্তারা কারা?"
          : "Who are the CSE faculty members and department officials?",
    },
    {
      Icon: FileText,
      label: t.notices,
      question:
        language === "bn"
          ? "CSE বিভাগের নোটিশগুলো কী কী?"
          : "What notices are available from the CSE department?",
    },
  ];

  useEffect(() => {
    if (!accessToken) router.replace("/login");
  }, [accessToken, router]);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("eu-ai-theme");
    if (savedTheme === "dark" || savedTheme === "light") {
      setTheme(savedTheme);
      document.documentElement.dataset.theme = savedTheme;
    }
  }, []);

  const changeTheme = (nextTheme: "light" | "dark") => {
    setTheme(nextTheme);
    window.localStorage.setItem("eu-ai-theme", nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  };

  useEffect(() => {
    const controller = new AbortController();
    void getHealth(controller.signal)
      .then((health) => {
        setApiOnline(health.status === "ok");
        setDocumentCount(health.document_count);
      })
      .catch(() => setApiOnline(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (messages.length > 0 || isLoading) {
      messagesEndRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }
  }, [messages, isLoading]);

  const startNewChat = () => {
    setMessages([]);
    setDraft("");
    setError("");
    setConversationId(makeConversationId());
    setMobileNavOpen(false);
    textareaRef.current?.focus();
  };

  const ask = useCallback(
    async (rawQuestion: string) => {
      const question = rawQuestion.trim();
      if (!question || isLoading || !accessToken) return;
      const userMessage: Message = {
        id: makeConversationId(),
        role: "user",
        content: question,
      };
      const answerId = makeConversationId();
      setMessages((current) => [...current, userMessage]);
      setDraft("");
      setError("");
      setIsLoading(true);

      try {
        const response = await sendChat(
          question,
          language,
          conversationId,
          accessToken,
        );
        setConversationId(response.conversation_id);
        setMessages((current) => [
          ...current,
          {
            id: answerId,
            role: "assistant",
            content: response.answer,
            sources: response.sources,
            grounded: response.grounded,
          },
        ]);
      } catch (requestError) {
        if (requestError instanceof ApiError && requestError.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : t.connection,
        );
      } finally {
        setIsLoading(false);
      }
    },
    [
      accessToken,
      clearSession,
      conversationId,
      isLoading,
      language,
      router,
      t.connection,
    ],
  );

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void ask(draft);
  };

  const onComposerKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(draft);
    }
  };

  const sidebar = (
    <aside className="flex h-screen max-h-screen flex-col overflow-y-auto bg-[#102a23] px-5 py-6 text-white scrollbar-subtle">
      <div className="flex items-center gap-3 px-1">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#d7f3e7] text-brand">
          <GraduationCap size={23} aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-wide">EU-AI</p>
          <p className="text-xs text-emerald-100/65">{t.assistant}</p>
        </div>
        <button
          aria-label={t.closeMenu}
          className="ml-auto rounded-lg p-2 text-emerald-100/75 hover:bg-white/10 lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          type="button"
        >
          <X size={18} />
        </button>
      </div>

      <button
        className="mt-8 flex w-full items-center justify-center gap-2 rounded-xl bg-[#d9f3e8] px-4 py-3 text-sm font-semibold text-[#123a2f] shadow-sm transition hover:bg-white"
        onClick={startNewChat}
        type="button"
      >
        <Plus size={17} aria-hidden="true" />
        {t.newChat}
      </button>

      <div className="mt-8">
        <label
          className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.13em] text-emerald-100/60"
          htmlFor="appearance"
        >
          {theme === "dark" ? (
            <Moon size={14} aria-hidden="true" />
          ) : (
            <Sun size={14} aria-hidden="true" />
          )}
          {t.appearance}
        </label>
        <div className="relative">
          <select
            className="w-full appearance-none rounded-xl border border-white/10 bg-white/[0.07] px-3 py-2.5 pr-9 text-sm text-white outline-none transition focus:border-emerald-200/60 focus:ring-2 focus:ring-emerald-300/20"
            id="appearance"
            onChange={(event) =>
              changeTheme(event.target.value as "light" | "dark")
            }
            value={theme}
          >
            <option className="text-slate-900" value="light">
              {t.lightMode}
            </option>
            <option className="text-slate-900" value="dark">
              {t.darkMode}
            </option>
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-emerald-100/65"
            size={15}
            aria-hidden="true"
          />
        </div>
      </div>

      <div className="mt-5">
        <label
          className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.13em] text-emerald-100/60"
          htmlFor="language"
        >
          <Languages size={14} aria-hidden="true" />
          {t.language}
        </label>
        <div className="relative">
          <select
            className="w-full appearance-none rounded-xl border border-white/10 bg-white/[0.07] px-3 py-2.5 pr-9 text-sm text-white outline-none transition focus:border-emerald-200/60 focus:ring-2 focus:ring-emerald-300/20"
            id="language"
            onChange={(event) => setLanguage(event.target.value as Language)}
            value={language}
          >
            <option className="text-slate-900" value="en">
              English
            </option>
            <option className="text-slate-900" value="bn">
              বাংলা
            </option>
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-emerald-100/65"
            size={15}
            aria-hidden="true"
          />
        </div>
      </div>

      <div className="mt-9">
        <p className="mb-3 px-1 text-xs font-semibold uppercase tracking-[0.13em] text-emerald-100/60">
          {t.topics}
        </p>
        <nav aria-label={t.topics} className="space-y-1">
          {exploreActions.map(({ Icon, label, question }) => (
            <button
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-emerald-50/85 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-200 disabled:cursor-wait disabled:opacity-50"
              disabled={isLoading}
              key={label}
              onClick={() => {
                setMobileNavOpen(false);
                void ask(question);
              }}
              type="button"
            >
              <Icon
                className="shrink-0 text-emerald-200/75"
                size={17}
                aria-hidden="true"
              />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.06] p-4">
        {user?.role === "admin" && (
          <button
            className="mb-4 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-100 px-3 py-2.5 text-sm font-semibold text-emerald-950 transition hover:bg-white"
            onClick={() => router.push("/admin")}
            type="button"
          >
            <ShieldCheck size={17} aria-hidden="true" />
            {language === "bn" ? "অ্যাডমিন ড্যাশবোর্ড" : "Admin dashboard"}
          </button>
        )}
        <div className="flex items-center gap-2 text-sm font-medium text-white">
          <FileText size={16} className="text-emerald-200" aria-hidden="true" />
          {t.library}
        </div>
        <p className="mt-2 text-xs leading-5 text-emerald-50/60">
          {documentCount === null ? "—" : documentCount} {t.files}
        </p>
        <div
          className={`mt-3 flex items-center gap-1.5 text-[11px] ${
            apiOnline ? "text-emerald-200/80" : "text-amber-200/80"
          }`}
          role="status"
        >
          <ShieldCheck size={13} aria-hidden="true" />
          {apiOnline ? t.connected : t.offline}
        </div>
        {user && (
          <div className="mt-4 border-t border-white/10 pt-3">
            <p className="truncate text-xs font-medium text-white">
              {user.full_name}
            </p>
            <p className="mt-0.5 text-[11px] capitalize text-emerald-50/60">
              {user.role}
            </p>
            <button
              className="mt-3 w-full rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-emerald-50 transition hover:bg-white/10"
              onClick={() => {
                clearSession();
                router.replace("/login");
              }}
              type="button"
            >
              {language === "bn" ? "সাইন আউট" : "Sign out"}
            </button>
          </div>
        )}
      </div>
    </aside>
  );

  return (
    <main className="min-h-screen bg-canvas lg:flex" data-theme={theme}>
      <div className="hidden w-[276px] shrink-0 lg:fixed lg:inset-y-0 lg:block">
        {sidebar}
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label={t.closeMenu}
            className="absolute inset-0 bg-slate-950/40"
            onClick={() => setMobileNavOpen(false)}
            type="button"
          />
          <div className="relative h-full w-[min(86vw,300px)] shadow-2xl">
            {sidebar}
          </div>
        </div>
      )}

      <section className="flex min-h-screen min-w-0 flex-1 flex-col lg:ml-[276px]">
        <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-xl sm:px-8">
          <div className="flex items-center gap-3">
            <button
              aria-label={t.menu}
              className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
              onClick={() => setMobileNavOpen(true)}
              type="button"
            >
              <Menu size={19} />
            </button>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-brand lg:hidden">
              <GraduationCap size={19} />
            </div>
            <div>
              <p className="text-sm font-semibold text-ink">{t.brand}</p>
              <p className="hidden text-xs text-muted sm:block">{t.assistant}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-brand">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <Globe2 size={13} aria-hidden="true" />
            <span>Eastern University</span>
          </div>
        </header>

        <div className="soft-grid pointer-events-none absolute left-[276px] right-0 top-[70px] h-[280px] opacity-[0.22] [mask-image:linear-gradient(to_bottom,black,transparent)] max-lg:hidden" />

        <div className="relative mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 pb-5 pt-8 sm:px-8 sm:pt-12">
          {messages.length === 0 ? (
            <div className="my-auto pb-10">
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-white/80 px-3 py-1.5 text-xs font-semibold text-brand shadow-sm">
                <Sparkles size={14} aria-hidden="true" />
                {t.eyebrow}
              </div>
              <h1 className="max-w-3xl text-3xl font-semibold leading-tight tracking-[-0.04em] text-ink sm:text-5xl sm:leading-[1.12]">
                {t.welcome}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-muted sm:text-base sm:leading-8">
                {t.description}
              </p>

              <section className="mt-10 rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-panel sm:p-7">
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-base font-semibold text-ink">{t.ask}</h2>
                    <p className="mt-1 text-sm text-muted">{t.askHint}</p>
                  </div>
                  <span className="hidden rounded-xl bg-slate-50 p-2.5 text-slate-500 sm:inline-flex">
                    <CircleHelp size={19} aria-hidden="true" />
                  </span>
                </div>
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {t.suggestions.map((suggestion) => (
                    <button
                      className="group flex min-h-[54px] items-center justify-between gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-left text-sm font-medium leading-6 text-slate-700 transition hover:border-emerald-200 hover:bg-emerald-50/70 hover:text-brand focus:outline-none focus:ring-4 focus:ring-emerald-100"
                      key={suggestion}
                      onClick={() => void ask(suggestion)}
                      type="button"
                    >
                      <span>{suggestion}</span>
                      <ArrowDown
                        className="-rotate-45 shrink-0 text-slate-400 transition group-hover:text-brand"
                        size={15}
                        aria-hidden="true"
                      />
                    </button>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <div className="flex-1 space-y-7 pb-6">
              <div className="mb-7 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted">
                    {t.assistant}
                  </p>
                  <h1 className="mt-1 text-xl font-semibold tracking-tight text-ink">
                    {t.ask}
                  </h1>
                </div>
                <button
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-emerald-200 hover:text-brand"
                  onClick={startNewChat}
                  type="button"
                >
                  {t.newChat}
                </button>
              </div>

              {messages.map((message) => (
                <article
                  className={`flex gap-3 sm:gap-4 ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                  key={message.id}
                >
                  {message.role === "assistant" && (
                    <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand text-white shadow-sm">
                      <GraduationCap size={18} aria-hidden="true" />
                    </div>
                  )}
                  <div
                    className={`max-w-[min(88%,680px)] ${
                      message.role === "user"
                        ? "rounded-[22px] rounded-br-md bg-[#e4f2eb] px-4 py-3 text-ink sm:px-5"
                        : "min-w-0 flex-1 pt-1"
                    }`}
                  >
                    {message.role === "assistant" && (
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-ink">
                          {t.assistant}
                        </span>
                        {message.grounded && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
                            <Check size={11} aria-hidden="true" />
                            {t.grounded}
                          </span>
                        )}
                        {message.grounded === false && (
                          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                            {t.ungrounded}
                          </span>
                        )}
                      </div>
                    )}
                    <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                      {message.content}
                    </p>
                    {message.role === "assistant" &&
                      message.sources &&
                      message.sources.length > 0 && (
                        <div className="mt-4">
                          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                            {t.sources}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {message.sources.map((citation, index) => (
                              <button
                                className="inline-flex max-w-full items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-brand"
                                key={`${citation.title}-${index}`}
                                onClick={() => setSelectedCitation(citation)}
                                type="button"
                              >
                                <FileText
                                  className="shrink-0 text-brand"
                                  size={13}
                                  aria-hidden="true"
                                />
                                <span className="max-w-[250px] truncate">
                                  {citation.title}
                                </span>
                                <span className="sr-only">{t.citation}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                  </div>
                </article>
              ))}

              {isLoading && (
                <div className="flex gap-3 sm:gap-4" role="status">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand text-white">
                    <GraduationCap size={18} aria-hidden="true" />
                  </div>
                  <div className="flex items-center gap-2 pt-1 text-sm text-muted">
                    <LoaderCircle
                      className="animate-spin text-brand"
                      size={16}
                      aria-hidden="true"
                    />
                    {t.thinking}
                    <span className="sr-only">{t.thinking}</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}

          {error && (
            <div
              className="mb-3 flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-800"
              role="alert"
            >
              <CircleHelp className="mt-0.5 shrink-0" size={16} aria-hidden="true" />
              <span>{error || t.connection}</span>
            </div>
          )}

          {messages.length === 0 && (
            <p className="mb-3 text-center text-xs text-muted">{t.empty}</p>
          )}

          <form
            className="sticky bottom-3 z-10 rounded-[24px] border border-slate-200 bg-white p-2 shadow-[0_12px_38px_rgba(15,23,42,0.10)]"
            onSubmit={onSubmit}
          >
            <div className="flex items-end gap-2">
              <label className="sr-only" htmlFor="chat-message">
                {t.placeholder}
              </label>
              <textarea
                className="scrollbar-subtle max-h-40 min-h-[48px] flex-1 resize-none bg-transparent px-3 py-3 text-sm leading-6 text-ink outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
                disabled={isLoading}
                id="chat-message"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={onComposerKeyDown}
                placeholder={t.placeholder}
                ref={textareaRef}
                rows={1}
                value={draft}
              />
              <button
                aria-label={t.send}
                className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-[15px] bg-brand text-white transition hover:bg-emerald-900 focus:outline-none focus:ring-4 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={!draft.trim() || isLoading}
                type="submit"
              >
                {isLoading ? (
                  <LoaderCircle className="animate-spin" size={18} />
                ) : (
                  <ArrowUp size={19} aria-hidden="true" />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between px-3 pb-1 pt-0.5">
              <span className="text-[10px] text-slate-400">
                {t.footer}
              </span>
              <span className="hidden items-center gap-1 text-[10px] text-slate-400 sm:inline-flex">
                <span className="rounded border border-slate-200 px-1 py-0.5 font-mono">
                  Enter
                </span>
                <span>to send</span>
              </span>
            </div>
          </form>
        </div>
      </section>

      <CitationDrawer
        citation={selectedCitation}
        language={language}
        onClose={() => setSelectedCitation(null)}
      />
    </main>
  );
}
