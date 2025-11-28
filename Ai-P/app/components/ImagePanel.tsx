'use client';

import { useAppStore } from '@/store/useAppStore';
import type { GalleryUnit } from '@/types';
import { useEffect, useMemo, useRef, useState } from 'react';
import styles from './ImagePanel.module.css';

const FALLBACK_IMAGE = '/property1.jpg';

const resolveImageUrl = (rawUrl?: string) => {
    if (!rawUrl || typeof rawUrl !== 'string') {
        return FALLBACK_IMAGE;
    }

    const trimmed = rawUrl.trim();
    if (!trimmed) {
        return FALLBACK_IMAGE;
    }

    if (trimmed.startsWith('data:')) {
        return trimmed;
    }

    if (trimmed.startsWith('/api/image-proxy')) {
        return trimmed;
    }

    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
        return `/api/image-proxy?url=${encodeURIComponent(trimmed)}`;
    }

    if (trimmed.startsWith('/')) {
        return trimmed;
    }

    return `/api/image-proxy?url=${encodeURIComponent(trimmed)}`;
};

const truncate = (value?: string, max = 220) => {
    if (!value) return '';
    return value.length > max ? `${value.slice(0, max)}…` : value;
};

export default function ImagePanel() {
    const { content, ui } = useAppStore();
    const gallery = content.gallery;
    const heroContainerRef = useRef<HTMLDivElement>(null);
    const [activeId, setActiveId] = useState<string | null>(null);
    const [heroLoaded, setHeroLoaded] = useState(false);
    const [heroFailed, setHeroFailed] = useState(false);

    const hasGallery = ui.showImages && gallery.length > 0;

    useEffect(() => {
        if (!hasGallery) {
            setActiveId(null);
            return;
        }
        if (!activeId || !gallery.some((unit) => unit.id === activeId)) {
            setActiveId(gallery[0].id);
            setHeroLoaded(false);
            setHeroFailed(false);
        }
    }, [gallery, hasGallery, activeId]);

    useEffect(() => {
        if (!heroContainerRef.current || !hasGallery) {
            return;
        }
        heroContainerRef.current.scrollTop = 0;
    }, [hasGallery, activeId]);

    if (!hasGallery) {
        return null;
    }

    const heroUnit = useMemo(() => {
        if (gallery.length === 0) {
            return null;
        }
        return gallery.find((unit) => unit.id === activeId) ?? gallery[0];
    }, [gallery, activeId]);

    const secondaryUnits = useMemo(() => {
        if (!heroUnit) {
            return [];
        }
        return gallery.filter((unit) => unit.id !== heroUnit.id);
    }, [gallery, heroUnit]);

    if (!hasGallery || !heroUnit) {
        return null;
    }

    const heroImage = resolveImageUrl(heroUnit.imageUrl);

    const renderHighlights = (unit: GalleryUnit) => {
        if (!unit.highlights || unit.highlights.length === 0) {
            return null;
        }

        return (
            <div className={styles.metrics}>
                {unit.highlights.slice(0, 4).map((item) => (
                    <div key={`${unit.id}-${item.label}`} className={styles.metric}>
                        <span className={styles.metricLabel}>{item.label}</span>
                        <span className={styles.metricValue}>{item.value}</span>
                    </div>
                ))}
            </div>
        );
    };

    return (
        <aside className={styles.panel}>
            <header className={styles.header}>
                <div>
                    <p className={styles.panelTitle}>الوحدات المطابقة</p>
                    <p className={styles.panelMeta}>
                        {gallery.length === 1 ? 'وحدة واحدة' : `${gallery.length} وحدات`}
                    </p>
                </div>
                <span className={styles.badge}>مباشر من قاعدة البيانات</span>
            </header>

            <section className={styles.heroCard} ref={heroContainerRef}>
                <div className={styles.heroMedia}>
                    <img
                        src={heroImage}
                        alt={heroUnit.title}
                        className={styles.heroImage}
                        onLoad={() => setHeroLoaded(true)}
                        onError={() => {
                            setHeroFailed(true);
                            setHeroLoaded(true);
                        }}
                    />
                    {!heroLoaded && (
                        <div className={styles.heroSkeleton}>
                            <span className={styles.loader} />
                            <p>جاري تحميل المعاينة…</p>
                        </div>
                    )}
                    {heroFailed && (
                        <div className={styles.heroFallback}>
                            <p>تعذر تحميل الصورة</p>
                        </div>
                    )}
                    {heroUnit.tags && heroUnit.tags.length > 0 && (
                        <div className={styles.tagRow}>
                            {heroUnit.tags.slice(0, 3).map((tag) => (
                                <span key={`${heroUnit.id}-${tag}`} className={styles.tag}>
                                    {tag}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
                <div className={styles.heroDetails}>
                    {heroUnit.subtitle && <p className={styles.heroSubtitle}>{heroUnit.subtitle}</p>}
                    <h3 className={styles.heroTitle}>{heroUnit.title}</h3>
                    {renderHighlights(heroUnit)}
                    {heroUnit.description && (
                        <p className={styles.heroDescription}>{truncate(heroUnit.description)}</p>
                    )}
                </div>
            </section>

            {secondaryUnits.length > 0 && (
                <section className={styles.unitList}>
                    {secondaryUnits.map((unit) => {
                        const unitImage = resolveImageUrl(unit.imageUrl);
                        const isActive = unit.id === activeId;
                        return (
                            <button
                                key={unit.id}
                                type="button"
                                className={`${styles.unitCard} ${isActive ? styles.unitCardActive : ''}`}
                                onClick={() => {
                                    setActiveId(unit.id);
                                    setHeroLoaded(false);
                                    setHeroFailed(false);
                                }}
                                onMouseEnter={() => {
                                    setActiveId(unit.id);
                                    setHeroLoaded(false);
                                    setHeroFailed(false);
                                }}
                            >
                                <div className={styles.unitImageWrapper}>
                                    <img src={unitImage} alt={unit.title} className={styles.unitImage} />
                                </div>
                                <div className={styles.unitBody}>
                                    <p className={styles.unitTitle}>{unit.title}</p>
                                    {unit.subtitle && (
                                        <p className={styles.unitSubtitle}>{unit.subtitle}</p>
                                    )}
                                    <div className={styles.unitHighlights}>
                                        {unit.highlights.slice(0, 2).map((item) => (
                                            <span
                                                key={`${unit.id}-${item.label}`}
                                                className={styles.unitHighlight}
                                            >
                                                {item.value}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </section>
            )}
        </aside>
    );
}
