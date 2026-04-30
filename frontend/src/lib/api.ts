const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export function getApiKey(): string {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("api_key") || "";
}

export function setApiKey(key: string) {
    localStorage.setItem("api_key", key);
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
    return { "X-API-Key": getApiKey(), ...extra };
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

    const res = await fetch(`${API_BASE}/spots?${query}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Failed to fetch spots");
    return res.json();
}

export async function fetchSpot(id: number): Promise<Spot> {
    const res = await fetch(`${API_BASE}/spots/${id}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Spot not found");
    return res.json();
}

export async function createSpot(data: Partial<Spot> & { tags?: string[] }): Promise<Spot> {
    const res = await fetch(`${API_BASE}/spots`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to create spot");
    return res.json();
}

export async function deleteSpot(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/spots/${id}`, { method: "DELETE", headers: authHeaders() });
    if (!res.ok) throw new Error("Failed to delete spot");
}

export async function updateSpot(id: number, data: Partial<Spot>): Promise<Spot> {
    const res = await fetch(`${API_BASE}/spots/${id}`, {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to update spot");
    return res.json();
}

// --- Sources ---

export async function scrapeUrl(url: string): Promise<ScrapeResult> {
    const res = await fetch(`${API_BASE}/sources/scrape`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error("Failed to scrape URL");
    return res.json();
}

export async function manualExtract(data: {
    url?: string;
    platform?: string;
    raw_content: string;
}): Promise<ScrapeResult> {
    const res = await fetch(`${API_BASE}/sources/manual`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to extract");
    return res.json();
}
