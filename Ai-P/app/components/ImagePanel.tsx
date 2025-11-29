'use client';

import { useAppStore } from '@/store/useAppStore';
import type { GalleryUnit } from '@/types';
import { useMemo, useState } from 'react';
import styles from './ImagePanel.module.css';

const FALLBACK_IMAGE = '/property1.jpg';
const DESCRIPTION_PREVIEW_LIMIT = 220;

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

    // Handle relative paths from RAG API (e.g., "generated_images/filename.png")
    // Convert to full RAG API URL
    const orchestratorUrl = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 'https://orchestrator-dbgj63mjca-uc.a.run.app';
    const ragApiUrl = orchestratorUrl.replace('orchestrator', 'rag-api');
    const fullImageUrl = `${ragApiUrl}/images/${trimmed.replace(/^generated_images\//, '')}`;

    return `/api/image-proxy?url=${encodeURIComponent(fullImageUrl)}`;
};

export default function ImagePanel() {
    const { content, ui, toggleUnitSelection } = useAppStore();
    const gallery = content.gallery;
    const hasGallery = ui.showImages && gallery.length > 0;
    const selectedUnitIds = content.selectedUnitIds;
    const selectionLocked = content.selectionLocked;
    const [expandedDescriptions, setExpandedDescriptions] = useState<Record<string, boolean>>({});

    const displayUnits = useMemo(() => {
        if (!hasGallery) {
            return [];
        }
        return gallery.map((unit) => ({
            ...unit,
            image: resolveImageUrl(unit.imageUrl),
            highlights: unit.highlights ?? [],
            tags: unit.tags ?? [],
        }));
    }, [gallery, hasGallery]);

    if (!hasGallery || displayUnits.length === 0) {
        return null;
    }

    const renderHighlights = (unit: GalleryUnit) => {
        if (!unit.highlights || unit.highlights.length === 0) {
            return null;
        }

        return (
            <div className={styles.unitStats}>
                {unit.highlights.slice(0, 3).map((item) => (
                    <div key={`${unit.id}-${item.label}`} className={styles.unitStat}>
                        <span className={styles.unitStatLabel}>{item.label}</span>
                        <span className={styles.unitStatValue}>{item.value}</span>
                    </div>
                ))}
            </div>
        );
    };

    return (
        <aside className={`${styles.panel} ${styles.panelVisible}`}>
            <header className={styles.header}>
                <div>
                    <p className={styles.panelTitle}>الوحدات المطابقة</p>
                    <p className={styles.panelMeta}>
                        {gallery.length === 1 ? 'وحدة واحدة' : `${gallery.length} وحدات`}
                    </p>
                </div>
            </header>

            <section className={styles.unitList}>
                {displayUnits.map((unit) => {
                    const isSelected = selectedUnitIds.includes(unit.id);
                    const toggleSelection = () => {
                        if (selectionLocked) return;
                        toggleUnitSelection(unit.id);
                    };
                    return (
                        <article
                            key={unit.id}
                            className={`${styles.unitCard} ${isSelected ? styles.unitCardSelected : ''}`}
                            aria-pressed={isSelected}
                            role="button"
                            tabIndex={0}
                            onClick={toggleSelection}
                            onKeyDown={(event) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                    event.preventDefault();
                                    toggleSelection();
                                }
                            }}
                        >
                            <div className={styles.unitMedia}>
                                <img src={unit.image} alt={unit.title} className={styles.unitImage} />
                                {unit.tags && unit.tags.length > 0 && (
                                    <div className={styles.mediaTagRow}>
                                        {unit.tags.slice(0, 3).map((tag) => (
                                            <span key={`${unit.id}-${tag}`} className={styles.mediaTag}>
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                <span className={styles.selectionToggle} aria-hidden="true">
                                    {isSelected ? '✓' : ''}
                                </span>
                            </div>
                            <div className={styles.unitInfo}>
                                {unit.subtitle && <p className={styles.unitSubtitle}>{unit.subtitle}</p>}
                                <h3 className={styles.unitTitle}>{unit.title}</h3>
                                {renderHighlights(unit)}
                                {unit.description && (
                                    <div className={styles.unitDescriptionWrapper}>
                                        <p className={styles.unitDescription}>
                                            {expandedDescriptions[unit.id] || unit.description.length <= DESCRIPTION_PREVIEW_LIMIT
                                                ? unit.description
                                                : `${unit.description.slice(0, DESCRIPTION_PREVIEW_LIMIT)}…`}
                                        </p>
                                        {unit.description.length > DESCRIPTION_PREVIEW_LIMIT && (
                                            <span
                                                role="button"
                                                tabIndex={0}
                                                className={styles.moreToggle}
                                                onClick={() =>
                                                    setExpandedDescriptions((prev) => ({
                                                        ...prev,
                                                        [unit.id]: !prev[unit.id],
                                                    }))
                                                }
                                                onKeyDown={(event) => {
                                                    if (event.key === 'Enter' || event.key === ' ') {
                                                        event.preventDefault();
                                                        setExpandedDescriptions((prev) => ({
                                                            ...prev,
                                                            [unit.id]: !prev[unit.id],
                                                        }));
                                                    }
                                                }}
                                            >
                                                {expandedDescriptions[unit.id] ? 'عرض أقل' : 'المزيد'}
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </article>
                    );
                })}
            </section>
        </aside>
    );
}
