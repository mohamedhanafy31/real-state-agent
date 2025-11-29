'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import styles from './UserInfoModal.module.css';

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
        <div className={styles.modalOverlay} onClick={onClose}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className={styles.modalHeader}>
                    <button
                        type="button"
                        onClick={onClose}
                        className={styles.closeButton}
                        aria-label="Close modal"
                    >
                        <X className="w-5 h-5" />
                    </button>
                    <h2 className={styles.modalTitle}>
                        مرحباً بك! 👋
                    </h2>
                    <p className={styles.modalSubtitle}>
                        نود التعرف عليك بشكل أفضل لتقديم أفضل خدمة
                    </p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className={styles.modalForm}>
                    {/* Name Field */}
                    <div className={styles.formField}>
                        <label htmlFor="name" className={styles.formLabel}>
                            الاسم الكامل <span className={styles.required}>*</span>
                        </label>
                        <input
                            type="text"
                            id="name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className={styles.formInput}
                            placeholder="أدخل اسمك الكامل"
                            disabled={isSubmitting}
                            autoFocus
                        />
                    </div>

                    {/* Phone Field */}
                    <div className={styles.formField}>
                        <label htmlFor="phone" className={styles.formLabel}>
                            رقم الهاتف <span className={styles.required}>*</span>
                        </label>
                        <input
                            type="tel"
                            id="phone"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            className={styles.formInput}
                            placeholder="+20 1XX XXX XXXX"
                            disabled={isSubmitting}
                        />
                    </div>

                    {/* Email Field */}
                    <div className={styles.formField}>
                        <label htmlFor="email" className={styles.formLabel}>
                            البريد الإلكتروني <span className={styles.required}>*</span>
                        </label>
                        <input
                            type="email"
                            id="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className={styles.formInput}
                            placeholder="example@email.com"
                            disabled={isSubmitting}
                        />
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className={styles.errorMessage}>
                            <p className={styles.errorText}>{error}</p>
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className={styles.submitButton}
                    >
                        {isSubmitting ? 'جاري الحفظ...' : 'متابعة'}
                    </button>

                    {/* Privacy Note */}
                    <p className={styles.privacyNote}>
                        🔒 بياناتك آمنة ولن يتم مشاركتها مع أي طرف ثالث
                    </p>
                </form>
            </div>
        </div>
    );
}
