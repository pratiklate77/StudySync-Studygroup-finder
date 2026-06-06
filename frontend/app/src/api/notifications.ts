import { apiFetch } from './client';
import type { Notification } from '../types';

export const notificationsApi = {
  getAll: () =>
    apiFetch<Notification[]>('/api/v1/notifications/', {
      method: 'GET',
    }),

  getNewCount: () =>
    apiFetch<{ count: number }>('/api/v1/notifications/new-count', {
      method: 'GET',
    }),

  markAllSeen: () =>
    apiFetch<void>('/api/v1/notifications/seen-all', {
      method: 'POST',
    }),

  markAsRead: (notificationId: string) =>
    apiFetch<void>(`/api/v1/notifications/${notificationId}/read`, {
      method: 'POST',
    }),

  markAllAsRead: () =>
    apiFetch<{ updated_count: number }>('/api/v1/notifications/read-all', {
      method: 'POST',
    }),
};
