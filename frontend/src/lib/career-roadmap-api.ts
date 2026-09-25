import {
  RoadmapPlan,
  GenerateRoadmapRequest,
  UpdateMilestoneProgressRequest,
  ListRoadmapsResponse,
  DeleteRoadmapResponse,
  ReconcileRoadmapResponse,
  RefreshRoadmapRequest,
  RefreshRoadmapResponse,
  UpdateRoadmapLifecycleRequest,
} from "@/types/career";

export async function listRoadmaps(
  idToken: string,
  options?: { targetRole?: string; activeOnly?: boolean; lifecycle?: string }
): Promise<ListRoadmapsResponse> {
  const queryParams = new URLSearchParams();
  if (options?.targetRole) queryParams.set("target_role", options.targetRole);
  if (options?.activeOnly !== undefined) queryParams.set("active_only", String(options.activeOnly));
  if (options?.lifecycle) queryParams.set("lifecycle", options.lifecycle);

  const queryString = queryParams.toString();
  const res = await fetch(`/api/career/roadmaps${queryString ? `?${queryString}` : ""}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to load roadmaps.");
  }

  return res.json();
}

export async function getRoadmap(idToken: string, roadmapId: string): Promise<RoadmapPlan> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to load roadmap details.");
  }

  return res.json();
}

export async function generateRoadmap(
  idToken: string,
  req: GenerateRoadmapRequest
): Promise<RoadmapPlan> {
  const res = await fetch("/api/career/roadmaps", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Roadmap generation failed.");
  }

  return res.json();
}

export async function updateMilestoneProgress(
  idToken: string,
  roadmapId: string,
  req: UpdateMilestoneProgressRequest
): Promise<RoadmapPlan> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}/progress`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to update milestone progress.");
  }

  return res.json();
}

export async function promoteMilestoneToEvidenceDraft(
  idToken: string,
  roadmapId: string,
  milestoneId: string
): Promise<any> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}/milestones/${milestoneId}/promote`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    const error: any = new Error(
      errJson.detail || errJson.error || "Failed to promote milestone to evidence draft."
    );
    error.status = res.status;
    error.data = errJson;
    throw error;
  }

  return res.json();
}

export async function reconcileRoadmap(
  idToken: string,
  roadmapId: string
): Promise<ReconcileRoadmapResponse> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}/reconcile`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to reconcile roadmap with Master Workspace.");
  }

  return res.json();
}

export async function refreshRoadmap(
  idToken: string,
  roadmapId: string,
  req: RefreshRoadmapRequest
): Promise<RefreshRoadmapResponse> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to refresh roadmap.");
  }

  return res.json();
}

export async function updateRoadmapLifecycle(
  idToken: string,
  roadmapId: string,
  req: UpdateRoadmapLifecycleRequest
): Promise<RoadmapPlan> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}/lifecycle`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to update roadmap lifecycle.");
  }

  return res.json();
}

export async function deleteRoadmap(
  idToken: string,
  roadmapId: string
): Promise<DeleteRoadmapResponse> {
  const res = await fetch(`/api/career/roadmaps/${roadmapId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || errJson.error || "Failed to delete roadmap.");
  }

  return res.json();
}
