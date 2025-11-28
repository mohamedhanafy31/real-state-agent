import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-P - Voice Assistant",
  description: "Real-time voice-to-voice AI assistant with immersive blob visualization",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
