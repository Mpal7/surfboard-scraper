// src/services/api.ts

import axios from 'axios';
import { PaginatedAds, FilterOptions, Ad } from '../types';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000', // Your backend URL
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getAds = async (page: number = 1, filters: any = {}): Promise<PaginatedAds> => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: '20',
    });
  
    // Clean up filters before appending
    Object.entries(filters).forEach(([key, value]) => {
      if (value) { // Only add if value is not null, undefined, or empty string
        params.append(key, String(value));
      }
    });
  
    const response = await apiClient.get(`/ads/filter?${params.toString()}`);
    return response.data;
};

export const getFilterOptions = async (): Promise<FilterOptions> => {
    const response = await apiClient.get<PaginatedAds>('/ads?page_size=10000');
    const ads = response.data.items;

    const brandCounts: { [key: string]: number } = {};
    const lengthCounts: { [key: string]: number } = {};
    const volumeCounts: { [key: string]: number } = {}; // Use string key for rounded volume

    ads.forEach((ad: Ad) => {
        if (ad.brand) {
            brandCounts[ad.brand] = (brandCounts[ad.brand] || 0) + 1;
        }
        const length = ad.length_ft !== null ? `${ad.length_ft}'${ad.length_in || 0}"` : null;
        if (length) {
            lengthCounts[length] = (lengthCounts[length] || 0) + 1;
        }
        if (ad.liters) {
            // --- THIS IS THE NEW ROUNDING LOGIC ---
            const roundedLiters = Math.round(ad.liters);
            volumeCounts[roundedLiters] = (volumeCounts[roundedLiters] || 0) + 1;
        }
    });

    return {
        brands: Object.entries(brandCounts).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name)),
        lengths: Object.entries(lengthCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name)),
        volumes: Object.entries(volumeCounts).map(([name, count]) => ({ name, count })).sort((a, b) => Number(a.name) - Number(b.name))
    };
};