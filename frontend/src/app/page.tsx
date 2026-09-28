import Link from "next/link";
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
  OrganizationSwitcher,
} from "@clerk/nextjs";
import { ArrowRight, BarChart3, Sparkles, UploadCloud, Wand2 } from "lucide-react";

const STEPS = [
  {
    icon: UploadCloud,
    title: "Upload",
    description: "Bring in client master data, orders, and reference tables from CSV, TXT, or Excel.",
  },
  {
    icon: Wand2,
    title: "Cleanse",
    description: "Run rule-based and AI-assisted checks — addresses, tax IDs, register numbers, duplicates.",
  },
  {
    icon: Sparkles,
    title: "Transform",
    description: "Map cleansed data onto SAP target templates with field-level validation.",
  },
  {
    icon: BarChart3,
    title: "Report",
    description: "Track data quality, review findings, and export a migration-ready dataset.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-ink-50">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
            <Sparkles className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="text-sm font-semibold text-ink-900">MDM Migrate</span>
        </div>

        <SignedOut>
          <div className="flex items-center gap-3">
            <SignInButton mode="modal">
              <button className="rounded-lg px-4 py-2 text-sm font-medium text-ink-700 hover:bg-ink-100">
                Sign in
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-brand-600/20 hover:bg-brand-700">
                Sign up
              </button>
            </SignUpButton>
          </div>
        </SignedOut>

        <SignedIn>
          <div className="flex items-center gap-3">
            {/* Creating/selecting an org here is what makes it the active tenant
                for subsequent API calls - see app/api/deps.py::get_current_tenant. */}
            <OrganizationSwitcher hidePersonal createOrganizationMode="modal" />
            <UserButton />
          </div>
        </SignedIn>
      </header>

      <section className="mx-auto max-w-3xl px-6 pb-16 pt-12 text-center sm:pt-20">
        <span className="inline-flex items-center rounded-full bg-brand-100 px-3 py-1 text-xs font-medium text-brand-700">
          Multi-tenant data migration platform
        </span>
        <h1 className="mt-5 text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
          Clean client data, ready for SAP — without the spreadsheet chaos.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-base text-ink-500">
          Upload your master data, run rule-based and AI-assisted cleansing, and generate
          migration-ready SAP templates — all in one guided pipeline, per client workspace.
        </p>

        <div className="mt-8 flex items-center justify-center gap-3">
          <SignedOut>
            <SignUpButton mode="modal">
              <button className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm shadow-brand-600/20 hover:bg-brand-700">
                Get started
                <ArrowRight className="h-4 w-4" />
              </button>
            </SignUpButton>
            <SignInButton mode="modal">
              <button className="rounded-lg border border-ink-300 bg-white px-5 py-2.5 text-sm font-medium text-ink-800 hover:bg-ink-50">
                Sign in
              </button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm shadow-brand-600/20 hover:bg-brand-700"
            >
              Go to dashboard
              <ArrowRight className="h-4 w-4" />
            </Link>
          </SignedIn>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <div
                key={step.title}
                className="rounded-xl border border-ink-200 bg-white p-5 shadow-sm shadow-ink-900/[0.03]"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-xs font-medium text-ink-300">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                <p className="mt-4 text-sm font-semibold text-ink-900">{step.title}</p>
                <p className="mt-1 text-sm text-ink-500">{step.description}</p>
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}
