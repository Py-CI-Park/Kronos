export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(url, init);
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function requireJsonPayload<T>(label: string, request: Promise<T | null>): Promise<T> {
  const payload = await request;
  if (payload === null) {
    throw new Error(`${label} payload unavailable`);
  }
  return payload;
}
