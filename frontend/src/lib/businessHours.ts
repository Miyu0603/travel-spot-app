/**
 * Google Places returns opening hours one line per weekday, which fills a card
 * with seven near-identical rows. This collapses runs of days that share the
 * same hours; anything it cannot parse is returned untouched, because the field
 * also holds free text written by the model or by hand.
 */

const DAY_ORDER = [
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
] as const;

const SEPARATOR = "；";

interface DayHours {
    day: string;
    hours: string;
}

function parseDays(raw: string): DayHours[] | null {
    const parts = raw
        .split(SEPARATOR)
        .map((part) => part.trim())
        .filter(Boolean);

    if (parts.length !== DAY_ORDER.length) return null;

    const parsed: DayHours[] = [];
    for (const part of parts) {
        // Split on the first colon only — the hours contain colons too.
        const colon = part.indexOf(":");
        if (colon === -1) return null;
        const day = part.slice(0, colon).trim();
        const hours = part.slice(colon + 1).trim();
        if (!day || !hours) return null;
        parsed.push({ day, hours });
    }

    // Only collapse a genuine Monday-to-Sunday list; anything else is free text
    // that happens to have the right number of segments.
    const inOrder = parsed.every((entry, index) => entry.day === DAY_ORDER[index]);
    return inOrder ? parsed : null;
}

export function formatBusinessHours(raw: string): string {
    if (!raw?.trim()) return "";

    const days = parseDays(raw);
    if (!days) return raw;

    if (days.every((entry) => entry.hours === days[0].hours)) {
        return `每天 ${days[0].hours}`;
    }

    const groups: string[] = [];
    let start = 0;
    for (let index = 1; index <= days.length; index++) {
        const sameAsRun = index < days.length && days[index].hours === days[start].hours;
        if (sameAsRun) continue;

        const end = index - 1;
        const label =
            end === start
                ? days[start].day
                : end === start + 1
                    ? `${days[start].day}、${days[end].day}`
                    : `${days[start].day}–${days[end].day}`;
        groups.push(`${label} ${days[start].hours}`);
        start = index;
    }

    return groups.join(SEPARATOR);
}
