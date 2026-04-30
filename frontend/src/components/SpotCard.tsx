"use client";

import { useState, useRef, useEffect } from "react";
import { Spot, updateSpot, deleteSpot } from "@/lib/api";

export default function SpotCard({
    spot,
    onUpdate,
    onDelete,
}: {
    spot: Spot;
    onUpdate?: () => void;
    onDelete?: () => void;
}) {
    const [editing, setEditing] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [saving, setSaving] = useState(false);
    const cardRef = useRef<HTMLDivElement>(null);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const el = cardRef.current;
        if (!el) return;
        const observer = new IntersectionObserver(
            ([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect(); } },
            { threshold: 0.1 }
        );
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    const [form, setForm] = useState({
        title: spot.title,
        description: spot.description,
        address: spot.address,
        business_hours: spot.business_hours,
        notes: spot.notes,
    });

    const handleSave = async () => {
        setSaving(true);
        try {
            await updateSpot(spot.id, form);
            setEditing(false);
            onUpdate?.();
        } catch {
            alert("儲存失敗");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm("確定要刪除這個景點嗎？")) return;
        setDeleting(true);
        try {
            await deleteSpot(spot.id);
            onDelete?.();
        } catch {
            alert("刪除失敗");
            setDeleting(false);
        }
    };

    if (editing) {
        return (
            <div ref={cardRef} className="bg-card-bg border-2 border-mag-gold p-5 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
                <div className="text-[9px] font-black text-mag-gold uppercase tracking-[0.2em] mb-4">Edit Spot / 編輯景點</div>
                <div className="space-y-3">
                    <div>
                        <label className="block text-[10px] font-black text-mag-gold uppercase tracking-wider mb-1">景點名稱</label>
                        <input
                            value={form.title}
                            onChange={(e) => setForm({ ...form, title: e.target.value })}
                            className="w-full border border-input-border bg-input-bg px-3 py-2.5 text-sm font-black text-mag-black focus:border-mag-gold focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-mag-gold uppercase tracking-wider mb-1">描述</label>
                        <textarea
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            rows={2}
                            className="w-full border border-input-border bg-input-bg px-3 py-2.5 text-sm font-bold text-mag-black focus:border-mag-gold focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-mag-gold uppercase tracking-wider mb-1">地址</label>
                        <input
                            value={form.address}
                            onChange={(e) => setForm({ ...form, address: e.target.value })}
                            className="w-full border border-input-border bg-input-bg px-3 py-2.5 text-sm font-bold text-mag-black focus:border-mag-gold focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-mag-gold uppercase tracking-wider mb-1">營業時間</label>
                        <input
                            value={form.business_hours}
                            onChange={(e) => setForm({ ...form, business_hours: e.target.value })}
                            className="w-full border border-input-border bg-input-bg px-3 py-2.5 text-sm font-bold text-mag-black focus:border-mag-gold focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-mag-gold uppercase tracking-wider mb-1">備註</label>
                        <input
                            value={form.notes}
                            onChange={(e) => setForm({ ...form, notes: e.target.value })}
                            className="w-full border border-input-border bg-input-bg px-3 py-2.5 text-sm font-bold text-mag-black focus:border-mag-gold focus:outline-none"
                        />
                    </div>
                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="flex-1 py-3 bg-mag-black text-mag-paper text-sm font-bold active:scale-[0.98] transition-all disabled:opacity-40"
                        >
                            {saving ? "儲存中..." : "儲存修改"}
                        </button>
                        <button
                            onClick={() => setEditing(false)}
                            className="flex-1 py-3 border border-card-border text-sm font-bold text-mag-gray hover:bg-input-bg"
                        >
                            取消
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div
            ref={cardRef}
            className={`bg-card-bg border border-card-border p-5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] transition-all duration-500 hover:shadow-[0_10px_30px_rgba(0,0,0,0.08)] ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}
        >
            <div className="mb-3 flex items-start justify-between gap-2">
                <h3 className="font-noto text-base font-bold text-mag-black leading-snug">{spot.title}</h3>
                <div className="flex items-center gap-1.5 shrink-0">
                    <button
                        onClick={() => setEditing(true)}
                        className="p-1.5 text-mag-gray hover:text-mag-gold transition-colors"
                        aria-label="編輯"
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                    </button>
                    <button
                        onClick={handleDelete}
                        disabled={deleting}
                        className="p-1.5 text-mag-gray hover:text-mag-red transition-colors disabled:opacity-50"
                        aria-label="刪除"
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                    </button>
                </div>
            </div>

            <span className="inline-block bg-mag-gold-light text-mag-gold text-[10px] font-black px-2 py-0.5 tracking-wider mb-3">
                {spot.country || spot.region}{spot.city ? ` · ${spot.city}` : ""}
            </span>

            {spot.description && (
                <p className="mb-4 text-sm leading-relaxed font-medium text-mag-gray">
                    {spot.description}
                </p>
            )}

            <div className="w-8 h-[2px] bg-mag-gold mb-4"></div>

            <div className="space-y-2 text-[13px]">
                {spot.address && (
                    <div className="flex items-start gap-2">
                        <span className="text-mag-gold font-black text-[10px] uppercase tracking-wider w-10 shrink-0 pt-0.5">地址</span>
                        <span className="font-bold text-mag-black">{spot.address}</span>
                    </div>
                )}
                {spot.business_hours && (
                    <div className="flex items-start gap-2">
                        <span className="text-mag-gold font-black text-[10px] uppercase tracking-wider w-10 shrink-0 pt-0.5">時間</span>
                        <span className="font-bold text-mag-black">{spot.business_hours}</span>
                    </div>
                )}
                {spot.notes && (
                    <div className="flex items-start gap-2">
                        <span className="text-mag-gold font-black text-[10px] uppercase tracking-wider w-10 shrink-0 pt-0.5">備註</span>
                        <span className="font-bold text-mag-gray">{spot.notes}</span>
                    </div>
                )}
            </div>

            {spot.tags.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                    {spot.tags.map((tag) => (
                        <span
                            key={tag}
                            className="bg-input-bg border border-card-border px-2.5 py-0.5 text-[11px] font-bold text-mag-gray"
                        >
                            {tag}
                        </span>
                    ))}
                </div>
            )}

            {spot.google_maps_url && (
                <div className="mt-4 border-t border-divider pt-4">
                    <a
                        href={spot.google_maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] font-black text-mag-black uppercase tracking-[0.15em] hover:text-mag-gold transition-colors"
                    >
                        Google Maps ↗
                    </a>
                </div>
            )}
        </div>
    );
}
