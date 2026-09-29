// src/lib/api.ts
import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

import { clearAccessToken, getAccessToken } from "./token";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

// Reusable axios instance
export const api = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,                  
    headers: { "Content-Type": "application/json" },
});

// --- Keycloak bearer token ------------------------------------------------------
// Every request to the CMUCal API carries `Authorization: Bearer <access token>`;
// the API derives the user from it and nothing else. Requests to any other
// origin never get the token.

type RetryableConfig = InternalAxiosRequestConfig & { _authRetried?: boolean };

function isApiUrl(url: string): boolean {
  if (!API_BASE_URL) return false;
  const base = API_BASE_URL.replace(/\/+$/u, "");
  return url === base || url.startsWith(`${base}/`) || url.startsWith(`${base}?`);
}

function isApiRequest(config: InternalAxiosRequestConfig): boolean {
  const url = config.url ?? "";
  if (/^[a-z][a-z0-9+.-]*:/iu.test(url) || url.startsWith("//")) return isApiUrl(url);
  return isApiUrl(config.baseURL ?? "");
}

function withBearer(instance: AxiosInstance): void {
  instance.interceptors.request.use(async (config) => {
    if (isApiRequest(config) && !config.headers.has("Authorization")) {
      const token = await getAccessToken();
      if (token) config.headers.set("Authorization", `Bearer ${token}`);
    }
    return config;
  });

  instance.interceptors.response.use(undefined, async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined;
    const challenge = String(error.response?.headers?.["www-authenticate"] ?? "");
    if (
      error.response?.status === 401 &&
      config &&
      isApiRequest(config) &&
      !config._authRetried &&
      /^bearer/iu.test(challenge)
    ) {
      // The token expired or was revoked between fetch and use: get a fresh
      // one and retry once.
      config._authRetried = true;
      clearAccessToken();
      const token = await getAccessToken({ force: true });
      if (token) {
        config.headers.set("Authorization", `Bearer ${token}`);
        return instance.request(config);
      }
    }
    throw error;
  });
}

// Components also call the global axios with absolute API URLs.
withBearer(api);
withBearer(axios);

/** GET helper that returns typed data T (res.data) */
export async function apiGet<T>(
    path: string,
    config?: AxiosRequestConfig
): Promise<T> {
    try {
        // console.log(path);
        const res = await api.get<T>(path, config);
        return res.data;
    } catch (err) {
        const e = err as AxiosError;
        const status = e.response?.status ?? "";
        const statusText = e.response?.statusText ?? e.message;
        throw new Error(`${status} ${statusText}`.trim());
    }
}

export async function apiPost<T, B = unknown>(
  path: string,
  body: B,
  config?: AxiosRequestConfig
): Promise<T> {
  try {
    const res = await api.post<T>(path, body, config);
    return res.data;
  } catch (err) {
    const e = err as AxiosError;
    const status = e.response?.status ?? "";
    const statusText = e.response?.statusText ?? e.message;
    throw new Error(`${status} ${statusText}`.trim());
  }
}

// new helper when you need HTTP status too
export async function apiPostWithStatus<T, B = unknown>(
  path: string,
  body: B,
  config?: AxiosRequestConfig
): Promise<{ data: T; status: number }> {
  const res = await api.post<T>(path, body, config);
  return { data: res.data, status: res.status };
}

export async function apiPatch<T, B = unknown>(
  path: string,
  body: B,
  config?: AxiosRequestConfig
): Promise<T> {
  try {
    const res = await api.patch<T>(path, body, config);
    return res.data;
  } catch (err) {
    const e = err as AxiosError;
    const status = e.response?.status ?? "";
    const statusText = e.response?.statusText ?? e.message;
    throw new Error(`${status} ${statusText}`.trim());
  }
}


export async function apiDelete<T = unknown>(
  path: string,
  config?: AxiosRequestConfig
): Promise<T> {
  try {
    const res = await api.delete<T>(path, config);
    return res.data;
  } catch (err) {
    const e = err as AxiosError<any>;
    const status = e.response?.status;
    const statusText = e.response?.statusText;
    const serverMsg =
      (e.response?.data && (e.response.data.message || e.response.data.error)) ??
      undefined;

    const parts = [
      status ? String(status) : undefined,
      statusText,
      serverMsg ?? e.message,
    ].filter(Boolean);

    throw new Error(parts.join(" - "));
  }
}