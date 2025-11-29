'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface UserInfoModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: UserInfo) => void;
}

export interface UserInfo {
    name: string;
    phone: string;
    email: string;
    timestamp: string;
}

export default function UserInfoModal({ isOpen, onClose, onSubmit }: UserInfoModalProps) {
    const [name, setName] = useState('');
    const [phone, setPhone] = useState('');
    const [email, setEmail] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    // Reset form when modal opens
    useEffect(() => {
        if (isOpen) {
            setName('');
            setPhone('');
            setEmail('');
            setError('');
        }
    }, [isOpen]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        // Basic validation
        if (!name.trim()) {
            setError('الاسم مطلوب');
            return;
        }
        if (!phone.trim()) {
            setError('رقم الهاتف مطلوب');
            return;
        }
        if (!email.trim() || !email.includes('@')) {
            setError('البريد الإلكتروني غير صحيح');
            return;
        }

        setIsSubmitting(true);

        const userData: UserInfo = {
            name: name.trim(),
            phone: phone.trim(),
            email: email.trim().toLowerCase(),
            timestamp: new Date().toISOString(),
        };

        try {
            // Save to API
            const response = await fetch('/api/users/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userData),
            });

            if (!response.ok) {
                throw new Error('فشل في حفظ البيانات');
            }

            // Save flag to localStorage to not show again
            localStorage.setItem('userInfoSubmitted', 'true');
            localStorage.setItem('userName', userData.name);

            // Call parent callback
            onSubmit(userData);
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'حدث خطأ أثناء الحفظ');
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="relative w-full max-w-md mx-4 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl shadow-2xl border border-gray-700/50">
                {/* Header */}
                <div className="relative px-6 py-5 border-b border-gray-700/50">
                    <h2 className="text-2xl font-bold text-white text-center">
                        مرحباً بك! 👋
                    </h2>
                    <p className="text-gray-400 text-center mt-2 text-sm">
                        نود التعرف عليك بشكل أفضل لتقديم أفضل خدمة
                    </p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-6 space-y-5">
                    {/* Name Field */}
                    <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
                            الاسم الكامل <span className="text-red-400">*</span>
                        </label>
                        <input
                            type="text"
                            id="name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                            placeholder="أدخل اسمك الكامل"
                            disabled={isSubmitting}
                            autoFocus
                        />
                    </div>

                    {/* Phone Field */}
                    <div>
                        <label htmlFor="phone" className="block text-sm font-medium text-gray-300 mb-2">
                            رقم الهاتف <span className="text-red-400">*</span>
                        </label>
                        <input
                            type="tel"
                            id="phone"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                            placeholder="+20 1XX XXX XXXX"
                            disabled={isSubmitting}
                        />
                    </div>

                    {/* Email Field */}
                    <div>
                        <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                            البريد الإلكتروني <span className="text-red-400">*</span>
                        </label>
                        <input
                            type="email"
                            id="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                            placeholder="example@email.com"
                            disabled={isSubmitting}
                        />
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="p-3 bg-red-500/10 border border-red-500/50 rounded-lg">
                            <p className="text-red-400 text-sm text-center">{error}</p>
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full py-3 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/30"
                    >
                        {isSubmitting ? 'جاري الحفظ...' : 'متابعة'}
                    </button>

                    {/* Privacy Note */}
                    <p className="text-xs text-gray-500 text-center">
                        🔒 بياناتك آمنة ولن يتم مشاركتها مع أي طرف ثالث
                    </p>
                </form>
            </div>
        </div>
    );
}
