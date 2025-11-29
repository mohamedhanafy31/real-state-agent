import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Users Dashboard - AI-P',
  description: 'View and manage user information',
};

export default function UsersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

