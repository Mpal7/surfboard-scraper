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

const Measurement: React.FC<{ label: string; value: string | number | null }> = ({ label, value }) => (
  value === null ? null : <Stat label={label} value={value} />
);

const AdCard: React.FC<AdCardProps> = ({ ad }) => {
  const measurements = ad.board_type === 'surf' ? (
    <>
      <Measurement label="Length" value={ad.length_ft === null ? null : formatLength(ad.length_ft, ad.length_in)} />
      <Measurement label="Volume" value={ad.liters === null ? null : `${ad.liters}L`} />
      <Measurement label="Width" value={ad.width_in === null ? null : `${toFraction(ad.width_in)}"`} />
      <Measurement label="Thickness" value={ad.thickness_in === null ? null : `${toFraction(ad.thickness_in)}"`} />
    </>
  ) : ad.board_type === 'foil' ? (
    <>
      <Measurement label="Foil area" value={ad.foil_area_cm2 === null ? null : `${ad.foil_area_cm2} cm2`} />
      <Measurement label="Mast" value={ad.mast_length_cm === null ? null : `${ad.mast_length_cm} cm`} />
      <Measurement label="Wingspan" value={ad.foil_wingspan_cm === null ? null : `${ad.foil_wingspan_cm} cm`} />
      <Measurement label="Wing area" value={ad.wing_area_m2 === null ? null : `${ad.wing_area_m2} m2`} />
      <Measurement label="Volume" value={ad.liters === null ? null : `${ad.liters}L`} />
      <Measurement label="Board length" value={ad.board_length_cm === null ? null : `${ad.board_length_cm} cm`} />
      <Measurement label="Board width" value={ad.board_width_cm === null ? null : `${ad.board_width_cm} cm`} />
    </>
  ) : ad.board_type === 'kite' ? (
    <>
      <Measurement label="Wing area" value={ad.wing_area_m2 === null ? null : `${ad.wing_area_m2} m2`} />
      <Measurement label="Board length" value={ad.board_length_cm === null ? null : `${ad.board_length_cm} cm`} />
      <Measurement label="Board width" value={ad.board_width_cm === null ? null : `${ad.board_width_cm} cm`} />
    </>
  ) : null;

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
        {ad.board_type && (
          <span className="inline-block mt-1 mb-1 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide bg-blue-100 text-blue-700 rounded-full self-start">{ad.board_type}</span>
        )}
        <p className="text-2xl font-extrabold text-blue-600 mt-1 mb-4">{ad.price ? `€${ad.price}` : 'Contact for Price'}</p>
        
        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-y-3 gap-x-2 mt-auto pt-4 border-t">
            <Stat label="Brand" value={ad.brand} />
            {measurements}
            {/* You can add more stats here if needed, like location */}
            <Stat label="Location" value={ad.location} />
        </div>
      </div>
    </a>
  );
};

export default AdCard;
