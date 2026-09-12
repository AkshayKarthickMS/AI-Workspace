import { HealthStatus } from "@/features/dashboard/health-status";

const plannedCapabilities = [
  "Mission intake and structured planning",
  "Human approval gates",
  "Controlled agent execution and verification",
  "Audit-ready operational history",
];

export default function DashboardPage() {
  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-16 sm:px-10">
      <p className="mb-4 text-sm font-semibold uppercase tracking-[0.24em] text-cyan-300">AegisOS</p>
      <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-6xl">
        Autonomous Enterprise AI Workforce
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
        The platform foundation is online. Agent workflows and mission execution have not been implemented yet.
      </p>
      <section className="mt-12 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/30">
          <h2 className="text-xl font-semibold text-white">Platform connection</h2>
          <p className="mt-2 text-sm text-slate-400">Live status is read from the FastAPI health endpoint.</p>
          <div className="mt-5"><HealthStatus /></div>
        </div>
        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h2 className="text-xl font-semibold text-white">Planned capabilities</h2>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            {plannedCapabilities.map((capability) => <li key={capability}>• {capability}</li>)}
          </ul>
        </div>
      </section>
    </main>
  );
}
