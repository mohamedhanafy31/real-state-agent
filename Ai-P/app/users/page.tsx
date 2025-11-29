'use client';

import { useState, useEffect } from 'react';
import { Users, Mail, Phone, Calendar, Download, RefreshCw } from 'lucide-react';

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

        const headers = ['Name,Phone,Email,Timestamp'];
        const rows = users.map(u =>
            `"${u.name}","${u.phone}","${u.email}","${u.timestamp}"`
        );
        const csv = [headers, ...rows].join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `users_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
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
        <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="bg-gradient-to-r from-gray-800/50 to-gray-900/50 backdrop-blur-sm rounded-2xl p-6 mb-6 border border-gray-700/50 shadow-2xl">
                    <div className="flex items-center justify-between flex-wrap gap-4">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-blue-600/20 rounded-xl">
                                <Users className="w-8 h-8 text-blue-400" />
                            </div>
                            <div>
                                <h1 className="text-3xl font-bold text-white">
                                    Users Dashboard
                                </h1>
                                <p className="text-gray-400 mt-1">
                                    Total: {users.length} {users.length === 1 ? 'user' : 'users'}
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={fetchUsers}
                                disabled={loading}
                                className="flex items-center gap-2 px-4 py-2 bg-gray-700/50 hover:bg-gray-600/50 text-white rounded-lg transition disabled:opacity-50"
                            >
                                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                                Refresh
                            </button>
                            <button
                                onClick={exportToCSV}
                                disabled={users.length === 0}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition disabled:opacity-50"
                            >
                                <Download className="w-4 h-4" />
                                Export CSV
                            </button>
                        </div>
                    </div>
                </div>

                {/* Loading State */}
                {loading && (
                    <div className="text-center py-12">
                        <div className="inline-block w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
                        <p className="text-gray-400 mt-4">Loading users...</p>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-6 text-center">
                        <p className="text-red-400">{error}</p>
                    </div>
                )}

                {/* Empty State */}
                {!loading && !error && users.length === 0 && (
                    <div className="bg-gray-800/30 border border-gray-700/50 rounded-xl p-12 text-center">
                        <Users className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                        <p className="text-gray-400 text-lg">No users yet</p>
                        <p className="text-gray-500 text-sm mt-2">
                            Users who submit their information will appear here
                        </p>
                    </div>
                )}

                {/* Users Grid */}
                {!loading && !error && users.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {users.map((user, index) => (
                            <div
                                key={user.email + index}
                                className="bg-gradient-to-br from-gray-800/50 to-gray-900/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700/50 hover:border-blue-500/50 transition shadow-lg hover:shadow-blue-500/10"
                            >
                                {/* User Number Badge */}
                                <div className="flex justify-between items-start mb-4">
                                    <span className="px-3 py-1 bg-blue-600/20 text-blue-400 text-sm font-semibold rounded-full">
                                        #{users.length - index}
                                    </span>
                                </div>

                                {/* Name */}
                                <h3 className="text-xl font-bold text-white mb-4">
                                    {user.name}
                                </h3>

                                {/* Contact Info */}
                                <div className="space-y-3">
                                    <div className="flex items-center gap-3 text-gray-300">
                                        <div className="p-2 bg-gray-700/50 rounded-lg">
                                            <Mail className="w-4 h-4 text-blue-400" />
                                        </div>
                                        <span className="text-sm truncate" title={user.email}>
                                            {user.email}
                                        </span>
                                    </div>

                                    <div className="flex items-center gap-3 text-gray-300">
                                        <div className="p-2 bg-gray-700/50 rounded-lg">
                                            <Phone className="w-4 h-4 text-green-400" />
                                        </div>
                                        <span className="text-sm">{user.phone}</span>
                                    </div>

                                    <div className="flex items-center gap-3 text-gray-400 pt-2 border-t border-gray-700/50">
                                        <div className="p-2 bg-gray-700/50 rounded-lg">
                                            <Calendar className="w-4 h-4 text-purple-400" />
                                        </div>
                                        <span className="text-xs">{formatDate(user.timestamp)}</span>
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
