// src/components/Sidebar.tsx

import React from 'react';
import { FilterOptions } from '../types';

interface SidebarProps {
  filters: FilterOptions;
  selectedBrands: string[];
  selectedLengths: string[];
  onBrandChange: (brand: string) => void;
  onLengthChange: (length: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ filters, selectedBrands, selectedLengths, onBrandChange, onLengthChange }) => {
  return (
    <aside className="w-1/4 p-4">
      <h2 className="text-2xl font-bold mb-4">Filters</h2>
      <div>
        <h3 className="text-lg font-semibold mb-2">Brand</h3>
        {filters.brands.map(({ name, count }) => (
          <div key={name} className="flex items-center mb-1">
            <input
              type="checkbox"
              id={`brand-${name}`}
              checked={selectedBrands.includes(name)}
              onChange={() => onBrandChange(name)}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor={`brand-${name}`} className="ml-2 text-gray-700">
              {name} ({count})
            </label>
          </div>
        ))}
      </div>
      <div className="mt-6">
        <h3 className="text-lg font-semibold mb-2">Length</h3>
        {filters.lengths.map(({ name, count }) => (
          <div key={name} className="flex items-center mb-1">
            <input
              type="checkbox"
              id={`length-${name}`}
              checked={selectedLengths.includes(name)}
              onChange={() => onLengthChange(name)}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor={`length-${name}`} className="ml-2 text-gray-700">
              {name} ({count})
            </label>
          </div>
        ))}
      </div>
    </aside>
  );
};

export default Sidebar;