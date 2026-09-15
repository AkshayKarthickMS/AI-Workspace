export function DemoBanner() {
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-center text-xs text-amber-900 sm:px-10">
      <strong className="font-semibold">Public demo</strong> — this deployment uses local-dev
      identity mode: anyone can type any identity and see or change any workspace&apos;s data.
      Don&apos;t enter real names, secrets, or sensitive information.
    </div>
  );
}
