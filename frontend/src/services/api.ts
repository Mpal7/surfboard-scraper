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
    ...filters,
  });

  const response = await apiClient.get(`/ads/filter?${params.toString()}`);
  return response.data;
};

// This is a helper function to fetch all ads to generate filter options.
// In a real-world scenario with a large dataset, this should be a dedicated backend endpoint.
export const getFilterOptions = async (): Promise<FilterOptions> => {
    const response = await apiClient.get<PaginatedAds>('/ads?page_size=1000');
    const ads = response.data.items;

    const brandCounts: { [key: string]: number } = {};
    const lengthCounts: { [key: string]: number } = {};

    ads.forEach((ad: Ad) => {
        if (ad.brand) {
            brandCounts[ad.brand] = (brandCounts[ad.brand] || 0) + 1;
        }
        const length = ad.length_ft !== null ? `${ad.length_ft}'${ad.length_in || 0}"` : null;
        if (length) {
            lengthCounts[length] = (lengthCounts[length] || 0) + 1;
        }
    });

    return {
        brands: Object.entries(brandCounts).map(([name, count]) => ({ name, count })),
        lengths: Object.entries(lengthCounts).map(([name, count]) => ({ name, count })),
    };
};