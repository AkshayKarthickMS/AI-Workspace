import { StatusBadge } from "@/components/ui/badge";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";

interface PlanTask {
  task_id?: string;
  agent?: string;
  description?: string;
  status?: string;
  dependencies?: string[];
}

function asTaskList(plan: Record<string, unknown> | null | undefined): PlanTask[] {
  const tasks = plan?.tasks;
  if (!Array.isArray(tasks)) return [];
  return tasks as PlanTask[];
}

interface PlanViewProps {
  plan: Record<string, unknown> | null | undefined;
  /** Live per-task state keyed by task_id (RunDetailResponse.tasks) -- the
   * plan itself is a frozen snapshot from when it was drafted, so a task's
   * status there never advances past "pending" as the run executes. */
  tasks?: Record<string, { status?: string }> | null;
}

export function PlanView({ plan, tasks: liveTasks }: PlanViewProps) {
  const tasks = asTaskList(plan).map((task) => {
    const live = task.task_id ? liveTasks?.[task.task_id] : undefined;
    return live?.status ? { ...task, status: live.status } : task;
  });
  const rationale = typeof plan?.rationale === "string" ? plan.rationale : null;

  return (
    <Card>
      <CardHeading>Plan</CardHeading>
      {rationale ? <CardSubtext>{rationale}</CardSubtext> : null}
      <div className="mt-5">
        {tasks.length === 0 ? (
          <EmptyState>No plan has been drafted for this run yet.</EmptyState>
        ) : (
          <ol className="space-y-3">
            {tasks.map((task, index) => (
              <li
                key={task.task_id ?? index}
                className="rounded-md border border-line bg-paper p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      {index + 1}. {task.agent ?? "agent"}
                    </p>
                    <p className="mt-1 text-sm text-ink">{task.description ?? ""}</p>
                  </div>
                  {task.status ? <StatusBadge status={task.status} /> : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </Card>
  );
}
