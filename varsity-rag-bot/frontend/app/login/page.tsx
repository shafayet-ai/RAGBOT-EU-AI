"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { GraduationCap, LoaderCircle } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { getCurrentUser, login, register } from "@/lib/api";

type LoginRole = "student" | "admin";

export default function LoginPage() {
  const router = useRouter();
  const { establishSession } = useAuth();
  const [isRegistering, setIsRegistering] = useState(false);
  const [loginRole, setLoginRole] = useState<LoginRole>("student");
  const [fullName, setFullName] = useState("");
  const [studentId, setStudentId] = useState("");
  const [email, setEmail] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      if (isRegistering) await register(studentId, fullName, email, password);
      const username = isRegistering
        ? studentId
        : loginRole === "student"
          ? identifier
          : email;
      const token = await login(
        username,
        password,
        isRegistering ? "student" : loginRole,
      );
      const user = await getCurrentUser(token.access_token);
      establishSession(token.access_token, user);
      router.replace(user.role === "admin" ? "/admin" : "/");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not authenticate. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <section className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-7 shadow-panel sm:p-9">
        <div className="mb-7 flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-brand">
            <GraduationCap size={25} aria-hidden="true" />
          </span>
          <div>
            <p className="font-semibold text-ink">EU-AI</p>
            <p className="text-sm text-muted">Eastern University assistant</p>
          </div>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          {isRegistering
            ? "Create your student account"
            : loginRole === "student"
              ? "Student sign in"
              : "Administrator sign in"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          {isRegistering
            ? "Register with your student ID and university email."
            : loginRole === "student"
              ? "Sign in with your student ID and password."
              : "Sign in with your administrator email and password."}
        </p>

        {!isRegistering && (
          <div
            aria-label="Account type"
            className="mt-6 grid grid-cols-2 rounded-xl bg-slate-100 p-1"
            role="group"
          >
            {(["student", "admin"] as const).map((role) => (
              <button
                aria-pressed={loginRole === role}
                className={`rounded-lg px-3 py-2.5 text-sm font-semibold transition ${
                  loginRole === role
                    ? "bg-white text-brand shadow-sm"
                    : "text-muted hover:text-ink"
                }`}
                key={role}
                onClick={() => {
                  setLoginRole(role);
                  setIdentifier("");
                  setEmail("");
                  setError("");
                }}
                type="button"
              >
                {role === "student" ? "Student login" : "Admin login"}
              </button>
            ))}
          </div>
        )}

        <form className="mt-7 space-y-4" onSubmit={submit}>
          {isRegistering && (
            <>
              <label className="block text-sm font-medium text-slate-700">
                Full name
                <input
                  autoComplete="name"
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-ink outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-100"
                  maxLength={160}
                  onChange={(event) => setFullName(event.target.value)}
                  required
                  value={fullName}
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Student ID
                <input
                  autoComplete="username"
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-ink outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-100"
                  maxLength={32}
                  minLength={3}
                  onChange={(event) => setStudentId(event.target.value)}
                  pattern="[A-Za-z0-9][A-Za-z0-9-]*"
                  required
                  value={studentId}
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Email address
                <input
                  autoComplete="email"
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-ink outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-100"
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  type="email"
                  value={email}
                />
              </label>
            </>
          )}
          {!isRegistering && (
            <label className="block text-sm font-medium text-slate-700">
              {loginRole === "student" ? "Student ID" : "Administrator email"}
              <input
                autoComplete={loginRole === "student" ? "username" : "email"}
                className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-ink outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-100"
                onChange={(event) =>
                  loginRole === "student"
                    ? setIdentifier(event.target.value)
                    : setEmail(event.target.value)
                }
                required
                type={loginRole === "admin" ? "email" : "text"}
                value={loginRole === "student" ? identifier : email}
              />
            </label>
          )}
          <label className="block text-sm font-medium text-slate-700">
            Password
            <input
              autoComplete={isRegistering ? "new-password" : "current-password"}
              className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-ink outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-100"
              minLength={isRegistering ? 12 : undefined}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
            {isRegistering && (
              <span className="mt-1 block text-xs font-normal text-muted">
                Use at least 12 characters.
              </span>
            )}
          </label>

          {error && (
            <p
              className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-800"
              role="alert"
            >
              {error}
            </p>
          )}

          <button
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 font-semibold text-white transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting && <LoaderCircle className="animate-spin" size={17} />}
            {isRegistering ? "Create student account" : "Sign in"}
          </button>
        </form>

        {loginRole === "student" ? (
          <p className="mt-6 text-center text-sm text-muted">
            {isRegistering ? "Already registered?" : "New to EU-AI?"}{" "}
            <button
              className="font-semibold text-brand hover:underline"
              onClick={() => {
                setIsRegistering((current) => !current);
                setLoginRole("student");
                setPassword("");
                setError("");
              }}
              type="button"
            >
              {isRegistering ? "Student sign in" : "Create a student account"}
            </button>
          </p>
        ) : (
          <p className="mt-6 text-center text-xs text-muted">
            Administrator accounts are provisioned by the system administrator.
          </p>
        )}
      </section>
    </main>
  );
}
