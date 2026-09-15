import Link from "next/link";

interface Plan {
  name: string;
  price: string;
  cadence?: string;
  description: string;
  features: string[];
  cta: { label: string; href: string };
  highlighted?: boolean;
}

const PLANS: Plan[] = [
  {
    name: "Starter",
    price: "$0",
    description: "Evaluate AegisOS on a single workspace.",
    features: [
      "1 workspace",
      "10 missions per month",
      "Bring your own CSV/Excel data",
      "Human approval on every run",
      "Community support",
    ],
    cta: { label: "Start free", href: "/app" },
  },
  {
    name: "Team",
    price: "$199",
    cadence: "/ month",
    description: "For teams running AegisOS in day-to-day operations.",
    features: [
      "Unlimited missions",
      "10 seats included",
      "Full audit log export",
      "Compliance & PII screening",
      "Priority support",
    ],
    cta: { label: "Start free trial", href: "/app" },
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For organizations with dedicated security and compliance needs.",
    features: [
      "SSO / SCIM provisioning",
      "Dedicated deployment",
      "Custom data retention policy",
      "Uptime SLA",
      "Dedicated support contact",
    ],
    cta: { label: "Contact sales", href: "mailto:sales@aegisos.app" },
  },
];

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Simple pricing, no surprises.
        </h1>
        <p className="mt-4 text-base text-ink-muted">
          Every plan runs the same approval-gated, audited workflow. No credit card required to
          start.
        </p>
      </div>

      <div className="mt-12 grid gap-6 lg:grid-cols-3">
        {PLANS.map((plan) => (
          <div
            key={plan.name}
            className={
              plan.highlighted
                ? "flex flex-col rounded-lg border-2 border-accent bg-white p-8"
                : "flex flex-col rounded-lg border border-line bg-white p-8"
            }
          >
            {plan.highlighted ? (
              <p className="mb-4 inline-flex w-fit rounded-md border border-accent bg-paper px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-accent">
                Most popular
              </p>
            ) : null}
            <h2 className="text-lg font-semibold text-ink">{plan.name}</h2>
            <p className="mt-1 text-sm text-ink-muted">{plan.description}</p>
            <p className="mt-6 flex items-baseline gap-1">
              <span className="text-3xl font-semibold tracking-tight text-ink">{plan.price}</span>
              {plan.cadence ? (
                <span className="text-sm text-ink-muted">{plan.cadence}</span>
              ) : null}
            </p>
            <ul className="mt-6 flex-1 list-none space-y-3 pl-0 text-sm text-ink-muted">
              {plan.features.map((feature) => (
                <li key={feature} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-faint" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <Link
              href={plan.cta.href}
              className={
                plan.highlighted
                  ? "mt-8 inline-flex items-center justify-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
                  : "mt-8 inline-flex items-center justify-center rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:border-ink-faint"
              }
            >
              {plan.cta.label}
            </Link>
          </div>
        ))}
      </div>

      <div className="mt-16 border-t border-line pt-10">
        <h2 className="text-lg font-semibold text-ink">Frequently asked</h2>
        <dl className="mt-6 grid gap-8 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-semibold text-ink">Can I use my own data?</dt>
            <dd className="mt-1.5 text-sm text-ink-muted">
              Yes — upload a CSV or Excel file directly from the mission creation screen, or point
              at a dataset already staged on your deployment.
            </dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink">What does the approval gate do?</dt>
            <dd className="mt-1.5 text-sm text-ink-muted">
              AegisOS drafts a plan and pauses before any task executes. A person on your team
              reviews and approves it — nothing runs unattended.
            </dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink">Is there a free trial?</dt>
            <dd className="mt-1.5 text-sm text-ink-muted">
              The Starter plan is free and doesn&apos;t require a card. Team includes a free trial
              period before billing begins.
            </dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink">How is compliance handled?</dt>
            <dd className="mt-1.5 text-sm text-ink-muted">
              Every finding is screened by a deterministic policy and PII check before it can
              reach a report, with a full audit trail of the decision.
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
