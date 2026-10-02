// src/types.ts

export interface Ad {
  id: number;
  model: string;
  brand: string | null;
  board_type: string | null;
  equipment_type: string | null;
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
  foil_area_cm2: number | null;
  mast_length_cm: number | null;
  foil_wingspan_cm: number | null;
  wing_area_m2: number | null;
  board_length_cm: number | null;
  board_width_cm: number | null;
}

export interface PaginatedAds {
  total_items: number;
  page: number;
  page_size: number;
  items: Ad[];
}

export interface FilterOptions {
  brands: { name: string; count: number }[];
  boardTypes: { name: string; count: number }[];
  equipmentTypes: { name: string; count: number }[];
  lengths: { name: string; count: number }[];
  volumes: { name: string; count: number }[];
  locations: { name: string; count: number }[];
}

export type MeasurementKey =
  | 'foil_area_cm2'
  | 'mast_length_cm'
  | 'foil_wingspan_cm'
  | 'wing_area_m2'
  | 'board_length_cm'
  | 'board_width_cm';

export interface NumericRange {
  min?: number;
  max?: number;
}

export type MeasurementFilters = Record<MeasurementKey, NumericRange>;
