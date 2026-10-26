import type { components } from "@/types/api.generated";

type RunMetrics = components["schemas"]["RunMetrics"];
type RunStatus = components["schemas"]["RunStatus"];

// @ts-expect-error metrics cannot be strings
const invalidMetric: RunMetrics = { quality_score: "high" };

// @ts-expect-error unknown run status
const invalidStatus: RunStatus = "done";

export { invalidMetric, invalidStatus };
