// src/components/AdCard.tsx

import React from 'react';
import { Ad } from '../types';
import { toFraction, formatLength } from '../utils/formatters';

interface AdCardProps {
  ad: Ad;
}

const AdCard: React.FC<AdCardProps> = ({ ad }) => {
  return (
    <a
      href={ad.link}
      target="_blank"
      rel="noopener noreferrer"
      className="block border rounded-lg overflow-hidden shadow-lg hover:shadow-2xl transition-shadow duration-300"
    >
      <div className="w-full h-64 bg-gray-200">
        <img
          src={ad.image_url || 'https://via.placeholder.com/400x300'}
          alt={ad.model}
          className="w-full h-full object-cover"
        />
      </div>
      <div className="p-4">
        <h3 className="text-lg font-bold text-gray-800 truncate">{ad.brand} - {ad.model}</h3>
        <p className="text-gray-600">{formatLength(ad.length_ft, ad.length_in)}</p>
        <p className="text-xl font-semibold text-blue-600 mt-2">{ad.price ? `€${ad.price}` : 'Price not listed'}</p>
        <div className="text-sm text-gray-500 mt-4">
          <span>Width: {ad.width_in ? toFraction(ad.width_in) : 'N/A'}</span>
          <span className="mx-2">|</span>
          <span>Thickness: {ad.thickness_in ? toFraction(ad.thickness_in) : 'N/A'}</span>
        </div>
      </div>
    </a>
  );
};

export default AdCard;