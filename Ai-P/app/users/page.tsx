'use client';

import { useState, useEffect } from 'react';
import { Users, Mail, Phone, Calendar, Download, RefreshCw, Home } from 'lucide-react';
import Link from 'next/link';
import styles from './page.module.css';

interface UserInfo {
    name: string;
    phone: string;
    email: string;
    timestamp: string;
}

export default function UsersPage() {
    const [users, setUsers] = useState<UserInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const fetchUsers = async () => {
        setLoading(true);
        setError('');
        try {
            const response = await fetch('/api/users/save');
            if (!response.ok) throw new Error('Failed to fetch users');
            const data = await response.json();
            setUsers(data.users || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'حدث خطأ');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const exportToCSV = () => {
        if (users.length === 0) return;

        try {
            // Proper CSV formatting with separate header columns
            const headers = ['Name', 'Phone', 'Email', 'Timestamp'];
            const rows = users.map(u =>
                `"${u.name.replace(/"/g, '""')}","${u.phone.replace(/"/g, '""')}","${u.email.replace(/"/g, '""')}","${u.timestamp.replace(/"/g, '""')}"`
            );
            const csv = [headers.join(','), ...rows].join('\n');

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `users_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Error exporting CSV:', err);
            setError('Failed to export CSV. Please try again.');
        }
    };

    const formatDate = (timestamp: string) => {
        const date = new Date(timestamp);
        return new Intl.DateTimeFormat('ar-EG', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    };

    return (
        <div className={styles.page}>
            <div className={styles.container}>
                {/* Header */}
                <div className={styles.header}>
                    <div className={styles.headerContent}>
                        <div className={styles.headerLeft}>
                            <div className={styles.iconContainer}>
                                <Users className={styles.icon} />
                            </div>
                            <div className={styles.headerText}>
                                <h1 className={styles.title}>
                                    Users Dashboard
                                </h1>
                                <p className={styles.subtitle}>
                                    Total: {users.length} {users.length === 1 ? 'user' : 'users'}
                                </p>
                            </div>
                        </div>

                        <div className={styles.headerActions}>
                            <Link
                                href="/"
                                className={styles.button}
                            >
                                <Home className={styles.buttonIcon} />
                                Home
                            </Link>
                            <button
                                onClick={fetchUsers}
                                disabled={loading}
                                className={styles.button}
                            >
                                <RefreshCw className={`${styles.buttonIcon} ${loading ? styles.spinning : ''}`} />
                                Refresh
                            </button>
                            <button
                                onClick={exportToCSV}
                                disabled={users.length === 0}
                                className={`${styles.button} ${styles.buttonPrimary}`}
                            >
                                <Download className={styles.buttonIcon} />
                                Export CSV
                            </button>
                        </div>
                    </div>
                </div>

                {/* Loading State */}
                {loading && (
                    <div className={styles.loadingContainer}>
                        <div className={styles.spinner}></div>
                        <p className={styles.loadingText}>Loading users...</p>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className={styles.errorContainer}>
                        <p className={styles.errorText}>{error}</p>
                    </div>
                )}

                {/* Empty State */}
                {!loading && !error && users.length === 0 && (
                    <div className={styles.emptyContainer}>
                        <Users className={styles.emptyIcon} />
                        <p className={styles.emptyTitle}>No users yet</p>
                        <p className={styles.emptySubtitle}>
                            Users who submit their information will appear here
                        </p>
                    </div>
                )}

                {/* Users Grid */}
                {!loading && !error && users.length > 0 && (
                    <div className={styles.usersGrid}>
                        {users.map((user, index) => (
                            <div
                                key={user.email + index}
                                className={styles.userCard}
                            >
                                {/* User Number Badge */}
                                <div className={styles.userBadge}>
                                    <span className={styles.badge}>
                                        #{users.length - index}
                                    </span>
                                </div>

                                {/* Name */}
                                <h3 className={styles.userName}>
                                    {user.name}
                                </h3>

                                {/* Contact Info */}
                                <div className={styles.contactInfo}>
                                    <div className={styles.contactItem}>
                                        <div className={`${styles.contactIcon} ${styles.contactIconMail}`}>
                                            <Mail className={styles.buttonIcon} />
                                        </div>
                                        <span className={`${styles.contactText} ${styles.contactTextTruncate}`} title={user.email}>
                                            {user.email}
                                        </span>
                                    </div>

                                    <div className={styles.contactItem}>
                                        <div className={`${styles.contactIcon} ${styles.contactIconPhone}`}>
                                            <Phone className={styles.buttonIcon} />
                                        </div>
                                        <span className={styles.contactText}>{user.phone}</span>
                                    </div>

                                    <div className={`${styles.contactItem} ${styles.divider}`}>
                                        <div className={`${styles.contactIcon} ${styles.contactIconCalendar}`}>
                                            <Calendar className={styles.buttonIcon} />
                                        </div>
                                        <span className={styles.contactTextSmall}>{formatDate(user.timestamp)}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
