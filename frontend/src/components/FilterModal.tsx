import React from 'react';

interface Option {
  name: string;
  count: number;
}

interface FilterModalProps {
  title: string;
  options: Option[];
  selectedOptions: string[];
  onOptionChange: (optionName: string) => void;
  onReset: () => void;
  onClose: () => void;
}

const FilterModal: React.FC<FilterModalProps> = ({ title, options, selectedOptions, onOptionChange, onReset, onClose }) => {
  // Prevent background scroll when modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 z-40 flex justify-center items-center"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-md m-4 relative flex flex-col"
        onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside modal
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h2 className="text-xl font-bold">{title}</h2>
          <button onClick={onClose} className="text-2xl font-light">&times;</button>
        </div>

        {/* Options List */}
        <div className="p-4 overflow-y-auto" style={{ maxHeight: '60vh' }}>
          {options.map(({ name, count }) => (
            <div key={name} className="flex items-center mb-2 p-2 rounded hover:bg-gray-100">
              <input
                type="checkbox"
                id={`filter-${name}`}
                checked={selectedOptions.includes(name)}
                onChange={() => onOptionChange(name)}
                className="h-5 w-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor={`filter-${name}`} className="ml-3 text-gray-800 flex-grow cursor-pointer">
                {name}
              </label>
              <span className="text-gray-500 text-sm">{count}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center p-4 border-t">
            <button
                onClick={onReset}
                className="text-blue-600 hover:underline"
            >
                Reset
            </button>
            <button
                onClick={onClose}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
                Done
            </button>
        </div>
      </div>
    </div>
  );
};

export default FilterModal;