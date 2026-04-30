"use client";

import { useState, useEffect } from "react";
import { fetchSpots, Spot } from "@/lib/api";

const REGIONS = [
    { value: "", label: "全部" },
    { value: "taiwan", label: "台灣" },
    { value: "japan", label: "日本" },
    { value: "international", label: "國外" },
];

export default function RegionFilter({
    value,
    onChange,
    country,
    onCountryChange,
}: {
    value: string;
    onChange: (v: string) => void;
    country?: string;
    onCountryChange?: (v: string) => void;
}) {
    const [countries, setCountries] = useState<string[]>([]);

    useEffect(() => {
        if (value === "international") {
            fetchSpots({ region: "international" }).then((spots: Spot[]) => {
                const unique = [...new Set(spots.map((s) => s.country).filter(Boolean))].sort();
                setCountries(unique);
            });
        }
    }, [value]);

    return (
        <div className="flex flex-col gap-2">
            <div className="flex gap-0">
                {REGIONS.map((r) => (
                    <button
                        key={r.value}
                        onClick={() => {
                            onChange(r.value);
                            onCountryChange?.("");
                        }}
                        className={`flex-1 min-w-0 px-2 py-2 text-xs font-black tracking-wide transition-all border-b-[3px] ${value === r.value
                            ? "border-mag-gold text-mag-black"
                            : "border-transparent text-mag-gray hover:text-mag-black"
                            }`}
                    >
                        {r.label}
                    </button>
                ))}
            </div>
            {value === "international" && countries.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    <button
                        onClick={() => onCountryChange?.("")}
                        className={`px-3 py-1 text-[11px] font-bold transition-all ${!country
                            ? "bg-mag-gold text-white"
                            : "bg-input-bg text-mag-gray hover:text-mag-black"
                            }`}
                    >
                        全部
                    </button>
                    {countries.map((c) => (
                        <button
                            key={c}
                            onClick={() => onCountryChange?.(c)}
                            className={`px-3 py-1 text-[11px] font-bold transition-all ${country === c
                                ? "bg-mag-gold text-white"
                                : "bg-input-bg text-mag-gray hover:text-mag-black"
                                }`}
                        >
                            {c}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
