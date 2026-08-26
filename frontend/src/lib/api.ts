const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

/**
 * An API failure the UI can react to. `status` is the HTTP status, or 0 when the
 * request never reached the server (offline, DNS, CORS, backend asleep).
 */
export class ApiError extends Error {
    readonly status: number;

    constructor(message: string, status: number) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }

    get isAuthError(): boolean {
        return this.status === 401;
    }

    get isOffline(): boolean {
        return this.status === 0;
    }
}

export function getApiKey(): string {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("api_key") || "";
}

export function setApiKey(key: string) {
    localStorage.setItem("api_key", key);
}

/**
 * Every call goes through here so callers always get an ApiError carrying the
 * status — the UI needs to tell "wrong password" apart from "server unreachable"
 * apart from "no data".
 */
async function apiFetch(
    path: string,
    failureMessage: string,
    init: RequestInit = {},
): Promise<Response> {
    let res: Response;
    try {
        res = await fetch(`${API_BASE}${path}`, {
            ...init,
            headers: {
                "X-API-Key": getApiKey(),
                ...(init.headers as Record<string, string> | undefined),
            },
        });
    } catch {
        // fetch() only rejects on network-level failure, never on a 4xx/5xx.
        throw new ApiError("無法連線到伺服器，請確認網路後再試", 0);
    }

    if (res.status === 401) throw new ApiError("密碼已失效，請重新登入", 401);
    if (!res.ok) throw new ApiError(failureMessage, res.status);
    return res;
}

function jsonBody(data: unknown): RequestInit {
    return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
}

export interface Spot {
    id: number;
    title: string;
    description: string;
    address: string;
    latitude: number | null;
    longitude: number | null;
    google_maps_url: string;
    business_hours: string;
    notes: string;
    region: "taiwan" | "japan" | "international";
    continent: string | null;
    country: string;
    city: string;
    source_type: string;
    source_id: number | null;
    images: string;
    tags: string[];
    created_at: string | null;
    updated_at: string | null;
}

export interface Source {
    id: number;
    url: string;
    platform: string;
    status: string;
    raw_content: string;
    error_message: string;
    created_at: string | null;
}

export interface ScrapeResult {
    source: Source;
    spots: Record<string, string>[];
    message: string;
}

// --- Spots ---

export async function fetchSpots(params?: {
    region?: string;
    country?: string;
    search?: string;
    tag?: string;
}): Promise<Spot[]> {
    const query = new URLSearchParams();
    if (params?.region) query.set("region", params.region);
    if (params?.country) query.set("country", params.country);
    if (params?.search) query.set("search", params.search);
    if (params?.tag) query.set("tag", params.tag);

    const res = await apiFetch(`/spots?${query}`, "載入景點失敗，請稍後再試");
    return res.json();
}

export async function fetchSpot(id: number): Promise<Spot> {
    const res = await apiFetch(`/spots/${id}`, "找不到這個景點");
    return res.json();
}

export async function createSpot(data: Partial<Spot> & { tags?: string[] }): Promise<Spot> {
    const res = await apiFetch(`/spots`, "新增景點失敗，請稍後再試", {
        method: "POST",
        ...jsonBody(data),
    });
    return res.json();
}

export async function deleteSpot(id: number): Promise<void> {
    await apiFetch(`/spots/${id}`, "刪除景點失敗，請稍後再試", { method: "DELETE" });
}

export async function updateSpot(id: number, data: Partial<Spot>): Promise<Spot> {
    const res = await apiFetch(`/spots/${id}`, "更新景點失敗，請稍後再試", {
        method: "PUT",
        ...jsonBody(data),
    });
    return res.json();
}

// --- Sources ---

export async function scrapeUrl(url: string): Promise<ScrapeResult> {
    const res = await apiFetch(`/sources/scrape`, "抓取失敗，請稍後再試", {
        method: "POST",
        ...jsonBody({ url }),
    });
    return res.json();
}

export async function manualExtract(data: {
    url?: string;
    platform?: string;
    raw_content: string;
}): Promise<ScrapeResult> {
    const res = await apiFetch(`/sources/manual`, "解析失敗，請稍後再試", {
        method: "POST",
        ...jsonBody(data),
    });
    return res.json();
}
