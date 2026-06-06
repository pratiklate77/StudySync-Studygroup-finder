/* eslint-disable */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { Notification } from '../types';
import { notificationsApi } from '../api/notifications';
import { useAuth } from './AuthContext';
import Swal from 'sweetalert2';

interface NotificationContextType {
  notifications: Notification[];
  newCount: number;
  loading: boolean;
  refreshNotifications: () => Promise<void>;
  markAsRead: (id: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  onPanelOpen: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [newCount, setNewCount] = useState(0);
  const [notifLoading, setNotifLoading] = useState(false);
  const { isAuthenticated, isAdmin, loading: authLoading } = useAuth();

  const refreshNotifications = useCallback(async () => {
    if (!isAuthenticated || isAdmin) return;
    try {
      const [data, countRes] = await Promise.all([
        notificationsApi.getAll(),
        notificationsApi.getNewCount(),
      ]);
      setNotifications(data);

      if (countRes.count > newCount && newCount !== 0) {
        const diff = countRes.count - newCount;
        Swal.fire({
          toast: true,
          position: 'bottom-end',
          icon: 'info',
          title: `You have ${diff} new notification${diff > 1 ? 's' : ''}`,
          showConfirmButton: false,
          timer: 3000,
          background: '#12121e',
          color: '#f8fafc',
        });
      }
      setNewCount(countRes.count);
    } catch {
      // Quietly ignore network failures in notifications polling
    }
  }, [isAuthenticated, isAdmin, newCount]);

  useEffect(() => {
    if (isAuthenticated && !isAdmin && !authLoading) {
      setNotifLoading(true);
      refreshNotifications().finally(() => setNotifLoading(false));

      const interval = setInterval(refreshNotifications, 10000);
      return () => clearInterval(interval);
    } else {
      setNotifications([]);
      setNewCount(0);
    }
  }, [isAuthenticated, isAdmin, authLoading]);

  // Called when user opens the notification panel — clears the badge
  const onPanelOpen = useCallback(async () => {
    if (!isAuthenticated || isAdmin) return;
    try {
      await notificationsApi.markAllSeen();
      setNewCount(0);
    } catch {
      // ignore
    }
  }, [isAuthenticated, isAdmin]);

  const markAsRead = useCallback(async (id: string) => {
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch {
      // ignore
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setNewCount(0);
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'success',
        title: 'All notifications marked as read',
        showConfirmButton: false,
        timer: 1500,
        background: '#12121e',
        color: '#f8fafc',
      });
    } catch {
      // ignore
    }
  }, []);

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        newCount,
        loading: notifLoading,
        refreshNotifications,
        markAsRead,
        markAllAsRead,
        onPanelOpen,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};
