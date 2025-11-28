import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'picsum.photos',
      },
      {
        protocol: 'https',
        hostname: '*.ngrok-free.app',
      },
      {
        protocol: 'https',
        hostname: '*.ngrok.io',
      },
    ],
  },
  // Allow ngrok origins for development
  allowedDevOrigins: [
    'ngrok-free.app',
    'ngrok.io',
    '127.0.0.1',
    'localhost',
    '*.ngrok-free.app',
    '*.ngrok.io',
  ],
};

export default nextConfig;
