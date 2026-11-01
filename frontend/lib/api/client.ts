import axios, { isAxiosError } from "axios";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Must match the JWT template name in the Clerk dashboard; it adds the email claim the backend needs.
export const JWT_TEMPLATE = "fastapi-backend";

type TokenGetter = () => Promise<string | null>;

let resolveTokenGetter: (getter: TokenGetter) => void = () => {};
let tokenGetter = new Promise<TokenGetter>((resolve) => {
  resolveTokenGetter = resolve;
});

export function setTokenGetter(getter: TokenGetter) {
  resolveTokenGetter(getter);
  tokenGetter = Promise.resolve(getter);
}

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use(async (config) => {
  const getToken = await tokenGetter;
  const token = await getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function errorMessage(error: unknown) {
  if (isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Can't reach the server";
  }
  return "Something went wrong";
}
