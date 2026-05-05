"use client";

import { useState, useEffect, useCallback } from "react";
import UrlImporter from "@/components/UrlImporter";
import SpotCard from "@/components/SpotCard";
import RegionFilter from "@/components/RegionFilter";
import ThemeToggle from "@/components/ThemeToggle";
import { fetchSpots, Spot, ScrapeResult, getApiKey, setApiKey } from "@/lib/api";

export default function Home() {
  const [spots, setSpots] = useState<Spot[]>([]);
  const [region, setRegion] = useState("");
  const [country, setCountry] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [authed, setAuthed] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    if (getApiKey()) setAuthed(true);
  }, []);

  const handleLogin = async () => {
    setApiKey(keyInput);
    try {
      await fetchSpots();
      setAuthed(true);
      setAuthError("");
    } catch {
      setApiKey("");
      setAuthError("密碼錯誤");
    }
  };
  const [lastResult, setLastResult] = useState<ScrapeResult | null>(null);

  const loadSpots = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchSpots({
        region: region || undefined,
        country: country || undefined,
        search: search || undefined,
      });
      setSpots(data);
    } catch {
      console.error("Failed to load spots");
    } finally {
      setLoading(false);
    }
  }, [region, country, search, authed]);

  useEffect(() => {
    if (authed) loadSpots();
  }, [loadSpots]);

  const handleImportComplete = (result: ScrapeResult) => {
    setLastResult(result);
    loadSpots();
  };

  if (!authed) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-1.5 mb-3">
              <span className="bg-mag-black text-mag-paper text-[10px] px-1.5 py-0.5 font-black">APP</span>
              <span className="text-[10px] font-bold tracking-[0.15em] uppercase text-mag-gold">Travel Spot</span>
            </div>
            <h1 className="font-noto text-[22px] font-bold text-mag-black">旅遊景點蒐集</h1>
          </div>
          <div className="border border-card-border bg-card-bg p-6 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
            <label className="block text-[10px] font-black text-mag-gray uppercase tracking-[0.2em] mb-2">Password</label>
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && keyInput) handleLogin(); }}
              placeholder="請輸入密碼..."
              className="w-full border border-input-border bg-input-bg px-4 py-3 text-sm font-bold text-mag-black placeholder-mag-gray/50 focus:border-mag-gold focus:outline-none mb-3"
            />
            {authError && <p className="text-xs font-bold text-mag-red mb-3">{authError}</p>}
            <button
              onClick={handleLogin}
              disabled={!keyInput}
              className="w-full py-3 bg-mag-black text-mag-paper text-xs font-black tracking-wider uppercase active:scale-[0.97] transition-all disabled:opacity-40"
            >
              進入
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="mb-10 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="bg-mag-black text-mag-paper text-[10px] px-1.5 py-0.5 font-black tracking-normal leading-none">APP</span>
            <span className="text-[10px] font-bold tracking-[0.15em] uppercase text-mag-gold">Travel Spot</span>
          </div>
          <h1 className="font-noto text-[22px] font-bold leading-none text-mag-black">旅遊景點蒐集</h1>
          <p className="mt-2 text-xs font-bold text-mag-gray">
            從社群貼文自動萃取旅遊景點資訊
          </p>
        </div>
        <ThemeToggle />
      </div>

      {/* Importer */}
      <div className="mb-10">
        <UrlImporter onComplete={handleImportComplete} />
      </div>

      {/* Last result message */}
      {lastResult && (
        <div
          className={`mb-8 p-4 text-sm font-bold border-l-4 flex items-center justify-between ${lastResult.source.status === "completed"
            ? "border-mag-gold bg-mag-gold-light text-mag-black"
            : "border-mag-red bg-mag-gold-light text-mag-red"
            }`}
        >
          <span>{lastResult.message}</span>
          <button
            onClick={() => setLastResult(null)}
            className="ml-4 p-1 text-mag-gray hover:text-mag-black transition-colors shrink-0"
            aria-label="關閉"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1.5 h-1.5 bg-mag-gold"></div>
          <h2 className="text-[10px] font-black text-mag-gray uppercase tracking-[0.2em]">Saved Spots / 已收藏景點</h2>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1 min-w-0">
            <RegionFilter value={region} onChange={setRegion} country={country} onCountryChange={setCountry} />
          </div>
          <input
            type="text"
            placeholder="搜尋景點..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full sm:w-auto sm:min-w-[200px] shrink-0 border border-input-border bg-input-bg px-4 py-2.5 text-sm font-bold text-mag-black placeholder-mag-gray/50 focus:border-mag-gold focus:outline-none"
          />
        </div>
      </div>

      {/* Spots list */}
      {!loading && spots.length === 0 ? (
        <div className="text-center py-16 bg-card-bg border border-dashed border-card-border">
          <div className="text-4xl mb-3">🗺️</div>
          <p className="text-sm font-black text-mag-gray">目前沒有景點</p>
          <p className="text-xs text-mag-gray/60 mt-1">試試貼上一個網址或手動新增</p>
        </div>
      ) : loading && spots.length === 0 ? (
        <div className="py-16 text-center text-sm font-black text-mag-gray">載入中...</div>
      ) : (
        <div className={`grid grid-cols-1 sm:grid-cols-2 gap-4 transition-opacity duration-200 ${loading ? "opacity-50" : "opacity-100"}`}>
          {spots.map((spot) => (
            <SpotCard key={spot.id} spot={spot} onUpdate={loadSpots} onDelete={() => {
              setSpots((prev) => prev.filter((s) => s.id !== spot.id));
            }} />
          ))}
        </div>
      )}
    </main>
  );
}
