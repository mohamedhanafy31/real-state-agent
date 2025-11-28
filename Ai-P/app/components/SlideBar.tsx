'use client';

import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import styles from './SlideBar.module.css';

// Real estate project images
const PLACEHOLDER_IMAGES = [
    { id: 1, url: '/lux-finishing.png', label: 'HawaBay', isAvailable: true },
    { id: 2, url: '/property1.jpg', label: 'Palm Heights', isAvailable: false },
    { id: 3, url: '/property2.webp', label: 'Marina Residences', isAvailable: false },
    { id: 4, url: '/property3.jpg', label: 'Sunset Villas', isAvailable: false },
    { id: 5, url: '/property4.webp', label: 'Ocean View Towers', isAvailable: false },
    { id: 6, url: '/property5.webp', label: 'Garden Estates', isAvailable: false },
    { id: 7, url: '/property6.jpg', label: 'Royal Palms', isAvailable: false },
    { id: 8, url: '/property7.jpg', label: 'Crystal Bay', isAvailable: false },
];

export default function SlideBar() {
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [isScrolling, setIsScrolling] = useState(false);
    const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const currentIndexRef = useRef(0);
    const autoScrollIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const isScrollingRef = useRef(false);
    const isAutoScrollingRef = useRef(false);
    const initializationAttemptsRef = useRef(0);
    const maxInitAttempts = 20; // Maximum attempts to initialize (4 seconds total)
    const imagesLoadedRef = useRef(0);
    const totalImagesRef = useRef(PLACEHOLDER_IMAGES.length * 2); // Original + duplicates
    const scrollCheckCallbackRef = useRef<(() => void) | null>(null);

    // Auto-scroll functionality - slide one item every 3 seconds
    useEffect(() => {
        const container = scrollContainerRef.current;
        
        if (!container) {
            console.error('[SlideBar] ❌ Container ref is null!');
            return;
        }

        let scrollCheckInterval: NodeJS.Timeout | undefined;
        const itemWidth = 200 + 16; // image width + gap (16px)
        const totalItems = PLACEHOLDER_IMAGES.length;

        // Function to check if container can scroll
        const checkScrollability = () => {
            if (!container) {
                return false;
            }
            
            // Check if images are loaded
            const imagesLoaded = imagesLoadedRef.current;
            const totalImages = totalImagesRef.current;
            const allImagesLoaded = imagesLoaded >= totalImages;
            
            const canScroll = container.scrollWidth > container.clientWidth;
            // Only return true if images are loaded AND container is scrollable
            return canScroll && allImagesLoaded;
        };

        // Wait for container to be scrollable (images loading)
        const waitForScrollability = () => {
            initializationAttemptsRef.current++;
            
            if (initializationAttemptsRef.current > maxInitAttempts) {
                return;
            }

            if (checkScrollability()) {
                startAutoScroll();
            } else {
                scrollCheckInterval = setTimeout(waitForScrollability, 200);
            }
        };

        // Store callback so it can be called when images load
        scrollCheckCallbackRef.current = waitForScrollability;

        const startAutoScroll = () => {
                if (!container) {
                    return;
                }

                // Final check: is container actually scrollable?
                if (container.scrollWidth <= container.clientWidth) {
                    return;
                }

                const autoScroll = () => {
                    if (!container) {
                        return;
                    }

                    // Skip auto-scroll if user is manually scrolling
                    if (isScrollingRef.current) {
                        return;
                    }

                    isAutoScrollingRef.current = true;
                    
                    // Calculate max scroll position (end of original items)
                    const maxScroll = itemWidth * totalItems;
                    const actualMaxScroll = container.scrollWidth - container.clientWidth;
                    const usableMaxScroll = Math.min(maxScroll, actualMaxScroll);
                    
                    // For right-to-left scrolling, we start at maxScroll and decrease
                    // Calculate scroll position from right to left
                    const scrollPosition = usableMaxScroll - (currentIndexRef.current * itemWidth);
                    
                    // Ensure scroll position is valid (not negative)
                    const validScrollPosition = Math.max(0, Math.min(scrollPosition, actualMaxScroll));

                    // Reset if we've scrolled through all original items (reached the left)
                    if (validScrollPosition <= 0 || currentIndexRef.current >= totalItems) {
                        container.scrollLeft = usableMaxScroll; // Use direct assignment for instant reset
                        currentIndexRef.current = 0;
                        // Reset flag after scroll completes
                        setTimeout(() => {
                            isAutoScrollingRef.current = false;
                        }, 100);
                    } else {
                        // Increment index for next scroll BEFORE scrolling
                        currentIndexRef.current++;
                        
                        // Ensure smooth scrolling is enabled
                        container.style.scrollBehavior = 'smooth';
                        
                        // Use direct assignment immediately for more reliable scrolling
                        // The negative scrollLeft suggests a CSS issue, so we'll force it
                        const currentScroll = container.scrollLeft;
                        
                        // If scrollLeft is negative, we need to fix it first
                        if (currentScroll < 0) {
                            container.scrollLeft = 0;
                            // Wait a bit for the reset
                            setTimeout(() => {
                                container.scrollLeft = validScrollPosition;
                            }, 50);
                        } else {
                            // Use requestAnimationFrame for smoother animation
                            requestAnimationFrame(() => {
                                container.scrollTo({ 
                                    left: validScrollPosition, 
                                    behavior: 'smooth' 
                                });
                                
                                // Verify scroll happened after a short delay
                                setTimeout(() => {
                                    const actualScroll = container.scrollLeft;
                                    if (Math.abs(actualScroll - validScrollPosition) > 10) {
                                        container.scrollLeft = validScrollPosition;
                                    }
                                }, 100);
                            });
                        }
                        
                        // Reset flag after scroll completes (smooth scroll takes ~800ms)
                        setTimeout(() => {
                            isAutoScrollingRef.current = false;
                        }, 800);
                    }
                };

            // Clear any existing interval
            if (autoScrollIntervalRef.current) {
                clearInterval(autoScrollIntervalRef.current);
            }

            // Initialize: Start at the right side (end of original items)
            const maxScroll = itemWidth * totalItems;
            const actualMaxScroll = container.scrollWidth - container.clientWidth;
            // Use the actual max scroll position
            const startPosition = Math.min(maxScroll, actualMaxScroll);
            
            // Fix negative scrollLeft first if it exists, then set to start position
            const initScroll = () => {
                if (container.scrollLeft < 0) {
                    container.scrollLeft = 0;
                }
                container.scrollLeft = startPosition;
            };
            
            // Try multiple times to ensure it works
            setTimeout(initScroll, 100);
            setTimeout(initScroll, 300);
            setTimeout(initScroll, 500);
            
            currentIndexRef.current = 0;
            
            // Start auto-scroll every 3 seconds
            autoScrollIntervalRef.current = setInterval(autoScroll, 3000);
            
            // Trigger first scroll after a short delay
            setTimeout(() => {
                autoScroll();
            }, 1000);
        };

        // Wait a bit for images to load and DOM to settle
        const initTimeout = setTimeout(() => {
            waitForScrollability();
        }, 500);

        return () => {
            if (initTimeout) clearTimeout(initTimeout);
            if (scrollCheckInterval) clearTimeout(scrollCheckInterval);
            if (autoScrollIntervalRef.current) {
                clearInterval(autoScrollIntervalRef.current);
            }
        };
    }, []); // Empty dependency array - only run once on mount

    // Update ref when isScrolling changes
    useEffect(() => {
        isScrollingRef.current = isScrolling;
    }, [isScrolling]);

    const handleScroll = () => {
        const container = scrollContainerRef.current;
        if (!container) {
            return;
        }

        // Ignore scroll events during auto-scroll
        if (isAutoScrollingRef.current) {
            const itemWidth = 200 + 16;
            const newIndex = Math.round(container.scrollLeft / itemWidth);
            currentIndexRef.current = newIndex;
            return;
        }

        // User is manually scrolling
        setIsScrolling(true);
        const itemWidth = 200 + 16;
        const newIndex = Math.round(container.scrollLeft / itemWidth);
        currentIndexRef.current = newIndex;
        
        if (scrollTimeoutRef.current) {
            clearTimeout(scrollTimeoutRef.current);
        }
        
        scrollTimeoutRef.current = setTimeout(() => {
            setIsScrolling(false);
        }, 1000); // Wait 1s after user stops scrolling
    };

    useEffect(() => {
        const container = scrollContainerRef.current;
        if (container) {
            container.addEventListener('scroll', handleScroll);
            return () => {
                container.removeEventListener('scroll', handleScroll);
                if (scrollTimeoutRef.current) {
                    clearTimeout(scrollTimeoutRef.current);
                }
            };
        }
    }, []);

    return (
        <div className={styles.slideBarContainer}>
            {/* Branding */}
            <div className={styles.branding}>
                <span className={styles.brandingText}>AI-P</span>
            </div>
            
            <div className={styles.slideBar}>
                {/* Left edge fade */}
                <div className={styles.edgeFadeLeft}></div>
            
            <div className={styles.imageCarousel} ref={scrollContainerRef}>
        {PLACEHOLDER_IMAGES.map((item) => (
                    <div 
                        key={item.id} 
                        className={styles.imageItem}
                    >
                        <Image
                            src={item.url}
                            alt={item.label}
                            width={200}
                            height={88}
                            className={styles.image}
                            unoptimized
                            onLoad={() => {
                                imagesLoadedRef.current++;
                                // Re-check scrollability when image loads
                                if (scrollCheckCallbackRef.current && imagesLoadedRef.current >= totalImagesRef.current) {
                                    setTimeout(() => {
                                        scrollCheckCallbackRef.current?.();
                                    }, 100);
                                }
                            }}
                            onError={() => {
                                // Still increment to avoid blocking initialization
                                imagesLoadedRef.current++;
                            }}
                        />
                        {!item.isAvailable && (
                            <div className={styles.soonBadge}>
                                <span className={styles.soonText}>SOON</span>
                            </div>
                        )}
                        <div className={styles.imageOverlay}>
                            <span className={styles.imageLabel}>{item.label}</span>
                        </div>
                    </div>
                ))}
                {/* Duplicate images for seamless loop */}
                {PLACEHOLDER_IMAGES.map((item) => (
                    <div 
                        key={`duplicate-${item.id}`} 
                        className={styles.imageItem}
                    >
                        <Image
                            src={item.url}
                            alt={item.label}
                            width={200}
                            height={88}
                            className={styles.image}
                            unoptimized
                            onLoad={() => {
                                imagesLoadedRef.current++;
                                // Re-check scrollability when image loads
                                if (scrollCheckCallbackRef.current && imagesLoadedRef.current >= totalImagesRef.current) {
                                    setTimeout(() => {
                                        scrollCheckCallbackRef.current?.();
                                    }, 100);
                                }
                            }}
                            onError={() => {
                                // Still increment to avoid blocking initialization
                                imagesLoadedRef.current++;
                            }}
                        />
                        {!item.isAvailable && (
                            <div className={styles.soonBadge}>
                                <span className={styles.soonText}>SOON</span>
                            </div>
                        )}
                        <div className={styles.imageOverlay}>
                            <span className={styles.imageLabel}>{item.label}</span>
                        </div>
                    </div>
                ))}
            </div>
            
            {/* Right edge fade */}
            <div className={styles.edgeFadeRight}></div>
            
            {!isScrolling && (
                <div className={styles.scrollIndicator}>
                    <div className={styles.scrollArrow}>→</div>
                </div>
            )}
            </div>
        </div>
    );
}
