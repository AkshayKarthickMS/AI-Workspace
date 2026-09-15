import Link from "next/link";

const CAPABILITIES = [
  "Human approval on every run",
  "Full audit trail",
  "Automated PII & compliance scanning",
  "Bring your own data",
];

const STEPS = [
  {
    step: "01",
    title: "Describe the mission",
    body: "State the objective in plain language — \"identify our top revenue drivers\" — and, optionally, attach your own CSV or Excel file.",
  },
  {
    step: "02",
    title: "Review the plan",
    body: "AegisOS drafts a task plan before touching any data. Nothing executes until a person on your team approves it.",
  },
  {
    step: "03",
    title: "Analysis runs, checked twice",
    body: "The analysis is verified for evidence and groundedness, then screened by a deterministic compliance pass for PII and policy issues.",
  },
  {
    step: "04",
    title: "Get a report you can act on",
    body: "A written executive summary and specific recommendations, grounded only in verified findings — plus the full audit trail behind them.",
  },
];

const FEATURES = [
  {
    title: "Analysis that finds the driver, not just the number",
    body: "Segment and concentration breakdowns, correlation-based drivers, real period-over-period growth, and margin analysis — computed directly from your data, not templated boilerplate.",
  },
  {
    title: "Governance built into the workflow",
    body: "Every run pauses for approval before execution. Every finding is evidence-checked. Every decision — approvals, rejections, escalations — is written to an audit log you can search and export.",
  },
];

export default function MarketingHomePage() {
  return (
    <div>
      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10 sm:py-28">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink-muted">
            Autonomous business analysis
          </p>
          <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
            Turn your business data into decisions your team can trust.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-ink-muted">
            AegisOS plans an analysis, stops for a human to approve it, then runs, verifies, and
            reports — with a full audit trail behind every finding.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/app"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Open the app
            </Link>
            <Link
              href="/pricing"
              className="rounded-md border border-line px-5 py-2.5 text-sm font-medium text-ink hover:border-ink-faint"
            >
              See pricing
            </Link>
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-white">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-8 sm:px-10 md:grid-cols-4">
          {CAPABILITIES.map((capability) => (
            <div key={capability} className="text-sm font-medium text-ink-muted">
              {capability}
            </div>
          ))}
        </div>
      </section>

      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10">
          <h2 className="text-2xl font-semibold tracking-tight text-ink">How it works</h2>
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((item) => (
              <div key={item.step}>
                <p className="font-mono text-sm text-ink-faint">{item.step}</p>
                <h3 className="mt-3 text-base font-semibold text-ink">{item.title}</h3>
                <p className="mt-2 text-sm text-ink-muted">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-white">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10">
          <div className="grid gap-10 md:grid-cols-2">
            {FEATURES.map((feature) => (
              <div key={feature.title} className="rounded-lg border border-line p-8">
                <h3 className="text-lg font-semibold text-ink">{feature.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-muted">{feature.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="mx-auto max-w-6xl px-6 py-20 text-center sm:px-10">
          <h2 className="text-2xl font-semibold tracking-tight text-ink">
            Start analyzing your data
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-ink-muted">
            No credit card required. Bring your own dataset or try it on the sample workspace.
          </p>
          <div className="mt-8">
            <Link
              href="/app"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Open the app
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
