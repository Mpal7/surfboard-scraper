// src/types.ts

export interface Ad {
  id: number;
  model: string;
  brand: string | null;
  price: number | null;
  location: string;
  link: string;
  image_url: string | null;
  scraped_at: string | null;
  length_ft: number | null;
  length_in: number | null;
  width_in: number | null;
  thickness_in: number | null;
  liters: number | null;
}

export interface PaginatedAds {
  total_items: number;
  page: number;
  page_size: number;
  items: Ad[];
}

export interface FilterOptions {
  brands: { name: string; count: number }[];
  lengths: { name: string; count: number }[];
  volumes: { name: string; count: number }[];
  locations: { name: string; count: number }[];
}