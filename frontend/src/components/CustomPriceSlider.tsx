// src/components/CustomPriceSlider.tsx

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Ad } from '../types';

interface PriceFilterProps {
  allAds: Ad[];
  onPriceChange: (min: number, max: number) => void;
}

const CustomPriceSlider: React.FC<PriceFilterProps> = ({ allAds, onPriceChange }) => {
  const { MIN, MAX } = useMemo(() => {
    if (allAds.length === 0) return { MIN: 0, MAX: 1000 };
    const prices = allAds.map(ad => ad.price).filter((p): p is number => p !== null && p > 0);
    if (prices.length === 0) return { MIN: 0, MAX: 1000 };
    const minPrice = Math.floor(Math.min(...prices));
    const maxPrice = Math.ceil(Math.max(...prices));
    return { MIN: minPrice > 0 ? minPrice : 0, MAX: maxPrice > 0 ? maxPrice : 1000 };
  }, [allAds]);

  const [minVal, setMinVal] = useState(MIN);
  const [maxVal, setMaxVal] = useState(MAX);
  const range = useRef<HTMLDivElement>(null);

  // Convert to percentage for styling
  const getPercent = useCallback((value: number) => Math.round(((value - MIN) / (MAX - MIN)) * 100), [MIN, MAX]);

  // Set the width of the range to decrease from the left side
  useEffect(() => {
    if (range.current) {
      const minPercent = getPercent(minVal);
      const maxPercent = getPercent(maxVal);
      range.current.style.left = `${minPercent}%`;
      range.current.style.width = `${maxPercent - minPercent}%`;
    }
  }, [minVal, maxVal, getPercent]);
  
  // Debounce price changes
  useEffect(() => {
    const handler = setTimeout(() => {
      if (minVal !== MIN || maxVal !== MAX) {
        onPriceChange(minVal, maxVal);
      } else {
        onPriceChange(0, 0); // Clear signal
      }
    }, 500);
    return () => clearTimeout(handler);
  }, [minVal, maxVal, MIN, MAX, onPriceChange]);

  // Sync inputs with MIN/MAX changes from props
  useEffect(() => {
    setMinVal(MIN);
    setMaxVal(MAX);
  }, [MIN, MAX]);

  const handleInputChange = (type: 'min' | 'max', value: string) => {
    const sanitizedValue = value.replace(',', '.').replace(/[^0-9.]/g, '');
    let numValue = Math.round(parseFloat(sanitizedValue));
    
    if (isNaN(numValue)) numValue = type === 'min' ? minVal : maxVal;
    
    numValue = Math.max(MIN, Math.min(MAX, numValue)); // Clamp to MIN/MAX
    
    if (type === 'min') {
        const newMin = Math.min(numValue, maxVal); // Ensure min doesn't cross max
        setMinVal(newMin);
    } else {
        const newMax = Math.max(numValue, minVal); // Ensure max doesn't cross min
        setMaxVal(newMax);
    }
  };
  
  const handleReset = () => {
    setMinVal(MIN);
    setMaxVal(MAX);
    onPriceChange(0, 0);
  };

  return (
    <div className='py-4 px-2'>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold">Price Range</h3>
          <button onClick={handleReset} className="text-sm text-blue-600 hover:underline">Reset</button>
        </div>

        {/* Custom Slider */}
        <div className="relative h-10 flex items-center">
            <input
                type="range"
                min={MIN}
                max={MAX}
                value={minVal}
                onChange={(event) => {
                    const value = Math.min(Number(event.target.value), maxVal);
                    setMinVal(value);
                }}
                className="thumb thumb--left"
            />
            <input
                type="range"
                min={MIN}
                max={MAX}
                value={maxVal}
                onChange={(event) => {
                    const value = Math.max(Number(event.target.value), minVal);
                    setMaxVal(value);
                }}
                className="thumb thumb--right"
            />
            <div className="relative w-full">
                <div className="absolute h-1.5 bg-gray-200 rounded w-full z-10"></div>
                <div ref={range} className="absolute h-1.5 bg-blue-500 rounded z-20"></div>
            </div>
        </div>

        {/* Input Fields */}
        <div className="flex items-center justify-between mt-2 space-x-4">
            <div className="relative w-full">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">€</span>
                <input type="text" value={minVal} onChange={(e) => handleInputChange('min', e.target.value)} className="w-full pl-7 pr-2 py-2 border border-gray-300 rounded-md shadow-sm" />
            </div>
            <span className="text-gray-500">-</span>
            <div className="relative w-full">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">€</span>
                <input type="text" value={maxVal} onChange={(e) => handleInputChange('max', e.target.value)} className="w-full pl-7 pr-2 py-2 border border-gray-300 rounded-md shadow-sm" />
            </div>
        </div>
    </div>
  );
};

export default CustomPriceSlider;