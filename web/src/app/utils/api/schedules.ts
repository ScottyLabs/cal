import { apiGet, apiPost, apiDelete } from "./api";
import { CoursesClubsResponse } from "../types";

// The bearer token (see api.ts) identifies the user; no ids are sent.

export const getSchedule = async (
  scheduleId?: string | number
): Promise<CoursesClubsResponse> => {
  return apiGet<CoursesClubsResponse>("/schedule/", {
    params: scheduleId != null ? { schedule_id: scheduleId } : undefined,
  });
};

export const removeCategoryFromSchedule = async <T = unknown>(
  categoryId: number
): Promise<T> => {
  return apiDelete<T>(`/schedule/category/${categoryId}`);
};