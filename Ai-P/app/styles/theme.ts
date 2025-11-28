export const theme = {
    colors: {
        background: {
            primary: '#0F172A',
            secondary: '#1E293B',
            panel: 'rgba(30, 41, 59, 0.6)',
        },
        text: {
            primary: '#E2E8F0',
            secondary: '#94A3B8',
            muted: '#64748B',
        },
        accent: {
            primary: '#9333EA',
            secondary: '#D4AF37',
            hover: '#B68C43',
            success: '#10B981',
            warning: '#F59E0B',
            error: '#EF4444',
        },
        gradients: {
            primary: 'linear-gradient(135deg, #9333EA 0%, #D4AF37 100%)',
            background: 'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
            blob: 'linear-gradient(180deg, #9333EA 0%, #D4AF37 100%)',
        },
    },

    breakpoints: {
        mobile: '768px',
        tablet: '1024px',
        desktop: '1440px',
    },

    typography: {
        fontFamily: {
            primary: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`,
            monospace: `'Fira Code', 'Courier New', monospace`,
        },
        fontSize: {
            h1: { desktop: '32px', mobile: '24px' },
            h2: { desktop: '24px', mobile: '20px' },
            body: '16px',
            small: '14px',
            tiny: '12px',
        },
    },

    spacing: {
        xs: '4px',
        sm: '8px',
        md: '16px',
        lg: '24px',
        xl: '32px',
        xxl: '48px',
    },

    borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
        full: '9999px',
    },

    shadows: {
        sm: '0 4px 15px rgba(212, 175, 55, 0.3)',
        md: '0 6px 20px rgba(212, 175, 55, 0.5)',
        lg: '0 4px 20px rgba(0, 0, 0, 0.3)',
        glow: '0 0 20px rgba(16, 185, 129, 0.6)',
        blobGlow: '0 0 30px rgba(147, 51, 234, 0.4)',
    },

    transitions: {
        fast: '200ms ease-out',
        medium: '400ms cubic-bezier(0.4, 0.0, 0.2, 1)',
        slow: '500ms cubic-bezier(0.4, 0.0, 0.2, 1)',
        elastic: '600ms cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    },

    blob: {
        sizes: {
            desktop: {
                idle: 450,
                reduced: 450,
            },
            tablet: {
                idle: 350,
                reduced: 170,
            },
            mobile: {
                idle: 280,
                reduced: 110,
            },
        },
    },

    slideBar: {
        height: {
            desktop: 60,
            tablet: 48,
            mobile: 40,
        },
    },

    micButton: {
        size: {
            desktop: 80,
            tablet: 70,
            mobile: 80,
        },
        iconSize: {
            desktop: 32,
            tablet: 28,
            mobile: 32,
        },
    },
} as const;

export type Theme = typeof theme;
