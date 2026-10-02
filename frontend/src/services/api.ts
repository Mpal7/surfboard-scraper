import { PaginatedAds, FilterOptions, Ad } from '../types';

export const AUTH_TOKEN_KEY = 'surfboard_admin_token';
export const AUTH_LOGOUT_EVENT = 'surfboard-auth-logout';
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const request = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');

  const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
      window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
    }
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep the status-based message when the API has no JSON error body.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
};

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export const login = async (username: string, password: string): Promise<LoginResponse> => {
  const response = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  sessionStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
  return response;
};

export const getCurrentAdmin = (): Promise<{ username: string }> => request<{ username: string }>('/auth/me');

export const logout = (): void => {
  sessionStorage.removeItem(AUTH_TOKEN_KEY);
};

export const hasAuthToken = (): boolean => Boolean(sessionStorage.getItem(AUTH_TOKEN_KEY));

export const getAllAds = (): Promise<PaginatedAds> => request<PaginatedAds>('/ads?page_size=10000');

export const getAds = async (page: number = 1, filters: Record<string, unknown> = {}): Promise<PaginatedAds> => {
  const params = new URLSearchParams({ page: page.toString(), page_size: '20' });
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.append(key, String(value));
  });
  return request<PaginatedAds>(`/ads/filter?${params.toString()}`);
};

export const getFilterOptions = async (): Promise<FilterOptions> => {
  const response = await request<PaginatedAds>('/ads?page_size=10000');
  const ads = response.items;

  const counts = {
    brands: {} as Record<string, number>,
    boardTypes: {} as Record<string, number>,
    equipmentTypes: {} as Record<string, number>,
    lengths: {} as Record<string, number>,
    volumes: {} as Record<string, number>,
    locations: {} as Record<string, number>,
  };

  ads.forEach((ad: Ad) => {
    if (ad.brand) counts.brands[ad.brand] = (counts.brands[ad.brand] || 0) + 1;
    if (ad.board_type) counts.boardTypes[ad.board_type] = (counts.boardTypes[ad.board_type] || 0) + 1;
    if (ad.equipment_type) counts.equipmentTypes[ad.equipment_type] = (counts.equipmentTypes[ad.equipment_type] || 0) + 1;
    if (ad.length_ft !== null) {
      const length = `${ad.length_ft}'${ad.length_in || 0}"`;
      counts.lengths[length] = (counts.lengths[length] || 0) + 1;
    }
    if (ad.liters) {
      const volume = String(Math.round(ad.liters));
      counts.volumes[volume] = (counts.volumes[volume] || 0) + 1;
    }
    if (ad.location) counts.locations[ad.location] = (counts.locations[ad.location] || 0) + 1;
  });

  return {
    brands: Object.entries(counts.brands).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name)),
    boardTypes: Object.entries(counts.boardTypes).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name)),
    equipmentTypes: Object.entries(counts.equipmentTypes).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name)),
    lengths: Object.entries(counts.lengths).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name)),
    volumes: Object.entries(counts.volumes).map(([name, count]) => ({ name, count })).sort((a, b) => Number(a.name) - Number(b.name)),
    locations: Object.entries(counts.locations).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name)),
  };
};
