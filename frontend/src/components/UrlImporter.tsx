"use client";

import { useState } from "react";
import { scrapeUrl, manualExtract, ScrapeResult } from "@/lib/api";

export default function UrlImporter({
    onComplete,
}: {
    onComplete: (result: ScrapeResult) => void;
}) {
    const [url, setUrl] = useState("");
    const [manualText, setManualText] = useState("");
    const [mode, setMode] = useState<"url" | "manual">("url");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleScrape = async () => {
        setLoading(true);
        setError("");
        try {
            const result = await scrapeUrl(url);
            onComplete(result);
            if (result.source.status === "failed") {
                setMode("manual");
                setError(result.message);
            } else {
                setUrl("");
            }
        } catch {
            setError("抓取失敗，請嘗試手動貼上內容");
            setMode("manual");
        } finally {
            setLoading(false);
        }
    };

    const handleManual = async () => {
        setLoading(true);
        setError("");
        try {
            const result = await manualExtract({ url, raw_content: manualText });
            onComplete(result);
            setManualText("");
        } catch {
            setError("解析失敗，請稍後再試");
        } finally {
            setLoading(false);
        }
    };

    const canSubmit = mode === "url" ? !!url : !!manualText;

    return (
        <div>
            <div className="flex items-center gap-2 mb-3">
                <div className="w-1.5 h-1.5 bg-mag-gold rotate-45"></div>
                <h2 className="text-[10px] font-black text-mag-gray uppercase tracking-[0.2em]">Import / 匯入景點</h2>
            </div>

            {/* Main input bar */}
            <div className="flex items-stretch border border-card-border bg-card-bg shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
                {/* Dropdown */}
                <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as "url" | "manual")}
                    className="shrink-0 bg-input-bg border-r border-card-border px-3 py-3 text-xs font-black text-mag-black appearance-none cursor-pointer focus:outline-none"
                    style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238E8E8E' stroke-width='2.5'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")", backgroundRepeat: "no-repeat", backgroundPosition: "right 8px center", paddingRight: "28px" }}
                >
                    <option value="url">網址</option>
                    <option value="manual">手動</option>
                </select>

                {/* Input */}
                {mode === "url" ? (
                    <input
                        type="url"
                        placeholder="貼上 IG / FB / Threads 網址..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter" && canSubmit && !loading) handleScrape(); }}
                        className="flex-1 min-w-0 px-4 py-3 text-sm font-bold text-mag-black placeholder-mag-gray/50 bg-transparent focus:outline-none"
                    />
                ) : (
                    <textarea
                        placeholder="貼上貼文內容或影片逐字稿..."
                        value={manualText}
                        onChange={(e) => setManualText(e.target.value)}
                        rows={3}
                        className="flex-1 min-w-0 px-4 py-3 text-sm font-bold text-mag-black placeholder-mag-gray/50 bg-transparent focus:outline-none resize-none"
                    />
                )}

                {/* Submit button */}
                <button
                    onClick={mode === "url" ? handleScrape : handleManual}
                    disabled={loading || !canSubmit}
                    className="shrink-0 px-5 bg-mag-black text-mag-paper text-xs font-black tracking-wider uppercase active:scale-[0.97] transition-all disabled:opacity-40"
                >
                    {loading ? (
                        <span className="inline-block w-4 h-4 border-2 border-mag-paper/30 border-t-mag-paper rounded-full animate-spin" />
                    ) : "萃取"}
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="mt-3 border-l-4 border-mag-red bg-mag-gold-light p-3 text-sm font-bold text-mag-red flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={() => setError("")} className="ml-2 p-1 text-mag-gray hover:text-mag-red">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>
            )}
        </div>
    );
}
