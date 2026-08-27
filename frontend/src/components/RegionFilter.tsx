"use client";

import { useState, useEffect } from "react";
import { fetchSpots, Spot } from "@/lib/api";

const REGIONS = [
    { value: "", label: "全部" },
    { value: "taiwan", label: "台灣" },
    { value: "japan", label: "日本" },
    { value: "international", label: "國外" },
];

/** Overseas spots are grouped by country; Taiwan and Japan by prefecture/county,
 *  where the country would be a single useless value. */
const SUB_FILTER_LABEL: Record<string, string> = {
    taiwan: "縣市",
    japan: "都道府縣",
    international: "國家",
};

export default function RegionFilter({
    value,
    onChange,
    country,
    onCountryChange,
    city,
    onCityChange,
}: {
    value: string;
    onChange: (v: string) => void;
    country?: string;
    onCountryChange?: (v: string) => void;
    city?: string;
    onCityChange?: (v: string) => void;
}) {
    // Tagged with the region it was fetched for: without that, switching regions
    // shows the previous region's options under the new label until the next
    // fetch lands, and clearing them in the effect is a synchronous setState.
    const [options, setOptions] = useState<{ region: string; values: string[] }>({
        region: "",
        values: [],
    });

    const groupsByCountry = value === "international";
    const selected = groupsByCountry ? country : city;
    const onSelect = groupsByCountry ? onCountryChange : onCityChange;

    useEffect(() => {
        if (!value) return;
        let cancelled = false;
        fetchSpots({ region: value })
            .then((spots: Spot[]) => {
                if (cancelled) return;
                const field = value === "international" ? "country" : "city";
                const unique = [
                    ...new Set(spots.map((s) => s[field as "country" | "city"]).filter(Boolean)),
                ].sort();
                setOptions({ region: value, values: unique });
            })
            .catch(() => {
                // A failed lookup only costs the sub-filter; the region tabs still work.
                if (!cancelled) setOptions({ region: value, values: [] });
            });
        return () => {
            cancelled = true;
        };
    }, [value]);

    const subFilterOptions = options.region === value ? options.values : [];

    const clearSubFilters = () => {
        onCountryChange?.("");
        onCityChange?.("");
    };

    return (
        <div className="flex flex-col gap-2">
            <div className="flex gap-0">
                {REGIONS.map((r) => (
                    <button
                        key={r.value}
                        onClick={() => {
                            onChange(r.value);
                            clearSubFilters();
                        }}
                        aria-current={value === r.value ? "true" : undefined}
                        className={`flex-1 min-w-0 px-2 py-2 text-xs font-black tracking-wide transition-all border-b-[3px] ${value === r.value
                            ? "border-mag-gold text-mag-black"
                            : "border-transparent text-mag-gray hover:text-mag-black"
                            }`}
                    >
                        {r.label}
                    </button>
                ))}
            </div>

            {value && subFilterOptions.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] font-black uppercase tracking-wider text-mag-gray/60 mr-1">
                        {SUB_FILTER_LABEL[value]}
                    </span>
                    <button
                        onClick={() => onSelect?.("")}
                        className={`px-3 py-1 text-[11px] font-bold transition-all ${!selected
                            ? "bg-mag-gold text-white"
                            : "bg-input-bg text-mag-gray hover:text-mag-black"
                            }`}
                    >
                        全部
                    </button>
                    {subFilterOptions.map((option) => (
                        <button
                            key={option}
                            onClick={() => onSelect?.(option)}
                            className={`px-3 py-1 text-[11px] font-bold transition-all ${selected === option
                                ? "bg-mag-gold text-white"
                                : "bg-input-bg text-mag-gray hover:text-mag-black"
                                }`}
                        >
                            {option}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
