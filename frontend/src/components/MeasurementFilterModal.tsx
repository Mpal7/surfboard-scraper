import React from 'react';
import { MeasurementFilters, MeasurementKey } from '../types';

interface MeasurementFilterModalProps {
  values: MeasurementFilters;
  boardTypes: string[];
  onChange: (key: MeasurementKey, bound: 'min' | 'max', value: string) => void;
  onReset: () => void;
  onClose: () => void;
}

const FIELDS: Array<{
  key: MeasurementKey;
  label: string;
  unit: string;
  types: string[];
  step: number;
}> = [
  { key: 'foil_area_cm2', label: 'Foil area', unit: 'cm2', types: ['foil'], step: 1 },
  { key: 'mast_length_cm', label: 'Mast length', unit: 'cm', types: ['foil'], step: 1 },
  { key: 'foil_wingspan_cm', label: 'Foil wingspan', unit: 'cm', types: ['foil'], step: 1 },
  { key: 'wing_area_m2', label: 'Wing area', unit: 'm2', types: ['foil', 'kite'], step: 0.1 },
  { key: 'board_length_cm', label: 'Board length', unit: 'cm', types: ['foil', 'kite'], step: 1 },
  { key: 'board_width_cm', label: 'Board width', unit: 'cm', types: ['foil', 'kite'], step: 1 },
];

const MeasurementFilterModal: React.FC<MeasurementFilterModalProps> = ({
  values,
  boardTypes,
  onChange,
  onReset,
  onClose,
}) => {
  const activeTypes = boardTypes.length > 0 ? boardTypes : ['foil', 'kite'];
  const fields = FIELDS.filter(field => field.types.some(type => activeTypes.includes(type)));

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-40 flex justify-center items-center" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-md m-4 relative flex flex-col"
        onClick={event => event.stopPropagation()}
      >
        <div className="flex justify-between items-center p-4 border-b">
          <h2 className="text-xl font-bold">Measurements</h2>
          <button onClick={onClose} className="text-2xl font-light" aria-label="Close measurements">
            &times;
          </button>
        </div>

        <div className="p-4 overflow-y-auto" style={{ maxHeight: '60vh' }}>
          {fields.length === 0 ? (
            <p className="text-sm text-gray-600">Select a foil or kite type to filter its measurements.</p>
          ) : (
            <div className="space-y-4">
              {fields.map(field => (
                <div key={field.key}>
                  <label className="block text-sm font-semibold text-gray-800">
                    {field.label} ({field.unit})
                  </label>
                  <div className="grid grid-cols-2 gap-3 mt-1">
                    {(['min', 'max'] as const).map(bound => (
                      <input
                        key={bound}
                        type="number"
                        min="0"
                        step={field.step}
                        placeholder={bound === 'min' ? 'Minimum' : 'Maximum'}
                        value={values[field.key][bound] ?? ''}
                        onChange={event => onChange(field.key, bound, event.target.value)}
                        className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                        aria-label={`${field.label} ${bound}`}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-between items-center p-4 border-t">
          <button onClick={onReset} className="text-blue-600 hover:underline">Reset</button>
          <button onClick={onClose} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

export default MeasurementFilterModal;
