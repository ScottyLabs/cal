import { apiGet, apiPost, apiDelete } from "./api";
import { AuthStatus, CalendarFields, GCalEvent } from "../types";

export const checkGoogleAuthStatus = () =>
  apiGet<AuthStatus>("/google/calendar/status");

export interface EnsureCalendarResponse {
  calendar_id: string;
  created: boolean; // true if newly created, false if already existed
}

export type EnsureCalendarRequest = null;
export const ensureCalendarExists = () =>
  apiPost<EnsureCalendarResponse, EnsureCalendarRequest>(
    "/google/calendars/init",
    null,
  );

export const listGoogleCalendars = () => apiGet<CalendarFields[]>("/google/calendar/list");

export const unauthorizeGoogle = () => apiDelete("/google/unauthorize");

export const fetchBulkEventsFromCalendars = async (
  calendarIds: string[],
): Promise<GCalEvent[]> => {
  try {
    return await apiPost<GCalEvent[], { calendarIds: string[] }>(
      "/google/calendar/events/bulk",
      { calendarIds: calendarIds },
    );
  } catch (error) {
    console.error("Failed to fetch events from calendars:", error);
    throw error;
  }
};
