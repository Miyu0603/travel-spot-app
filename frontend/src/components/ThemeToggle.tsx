"use client";

import { useEffect, useSyncExternalStore } from "react";

const STORAGE_KEY = "theme";

/**
 * The chosen theme lives in localStorage, not in React — so it's read through
 * useSyncExternalStore rather than copied into state by an effect. That keeps the
 * prerendered (static export) markup consistent with hydration, which a lazy
 * useState initialiser would break.
 */
const listeners = new Set<() => void>();

function notify() {
    listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
    listeners.add(listener);
    // Another tab changing the theme, or the OS switching appearance while no
    // explicit choice is stored.
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    window.addEventListener("storage", listener);
    media.addEventListener("change", listener);
    return () => {
        listeners.delete(listener);
        window.removeEventListener("storage", listener);
        media.removeEventListener("change", listener);
    };
}

function isDark(): boolean {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "dark") return true;
    if (saved === "light") return false;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// The static export is built light; hydration corrects it from the real store.
function isDarkOnServer(): boolean {
    return false;
}

function setDark(dark: boolean) {
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
    notify();
}

export default function ThemeToggle() {
    const dark = useSyncExternalStore(subscribe, isDark, isDarkOnServer);

    // Mirrors the store onto the document — an external system, no state involved.
    useEffect(() => {
        document.documentElement.classList.toggle("dark", dark);
    }, [dark]);

    return (
        <button
            onClick={() => setDark(!dark)}
            className="p-2 text-mag-gray hover:text-mag-gold transition-colors"
            aria-label={dark ? "切換淺色模式" : "切換深色模式"}
        >
            {dark ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="5" />
                    <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                    <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
            ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
            )}
        </button>
    );
}
