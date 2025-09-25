import React from 'react';
import { Ad } from '../types';
import { toFraction, formatLength } from '../utils/formatters';

interface AdCardProps {
  ad: Ad;
}

// A small sub-component for displaying each stat to keep the main return clean
const Stat: React.FC<{ label: string; value: string | number | null }> = ({ label, value }) => (
    <div className="text-center">
        <p className="text-xs text-gray-600 uppercase tracking-wider">{label}</p>
        <p className="text-sm font-bold text-gray-800">{value ?? 'N/A'}</p>
    </div>
);


const AdCard: React.FC<AdCardProps> = ({ ad }) => {
  return (
    <a
      href={ad.link}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col border rounded-lg overflow-hidden shadow-lg hover:shadow-2xl transition-shadow duration-300 bg-white"
    >
      {/* Image Container */}
      <div className="w-full h-64 bg-gray-200 overflow-hidden">
        <img
          src={ad.image_url || 'https://via.placeholder.com/400x300.png?text=No+Image'}
          alt={ad.model}
          className="w-full h-full object-cover transition-transform duration-300 hover:scale-110"
        />
      </div>

      {/* Content Container */}
      <div className="p-4 flex flex-col flex-grow">
        {/* Title and Price */}
        <h3 className="text-lg font-bold text-gray-900 truncate" title={ad.model}>{ad.model}</h3>
        <p className="text-2xl font-extrabold text-blue-600 mt-1 mb-4">{ad.price ? `€${ad.price}` : 'Contact for Price'}</p>
        
        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-y-3 gap-x-2 mt-auto pt-4 border-t">
            <Stat label="Brand" value={ad.brand} />
            <Stat label="Length" value={formatLength(ad.length_ft, ad.length_in)} />
            <Stat label="Volume" value={ad.liters ? `${ad.liters}L` : null} />
            <Stat label="Width" value={ad.width_in ? `${toFraction(ad.width_in)}"` : null} />
            <Stat label="Thickness" value={ad.thickness_in ? `${toFraction(ad.thickness_in)}"` : null} />
            {/* You can add more stats here if needed, like location */}
            <Stat label="Location" value={ad.location} />
        </div>
      </div>
    </a>
  );
};

export default AdCard;