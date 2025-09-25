// src/App.tsx

import React, { useEffect, useState, useMemo } from 'react';
import AdCard from './components/AdCard';
import FilterModal from './components/FilterModal';
import CustomPriceSlider from './components/CustomPriceSlider';
import { Ad, FilterOptions } from './types';

type ActiveModal = 'brand' | 'length' | 'volume' | 'price' | null;

// --- NEW: Helper function to sort surfboard sizes correctly ---
const parseLengthToInches = (lengthStr: string): number => {
    try {
        const parts = lengthStr.replace('"', '').split("'");
        const feet = parseInt(parts[0], 10) || 0;
        const inches = parseInt(parts[1], 10) || 0;
        return (feet * 12) + inches;
    } catch {
        return 0; // Fallback for any unexpected format
    }
};

const App: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  const [allAds, setAllAds] = useState<Ad[]>([]); 
  
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedLengths, setSelectedLengths] = useState<string[]>([]);
  const [selectedVolumes, setSelectedVolumes] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState<{min?: number, max?: number}>({});
  const [sortBy, setSortBy] = useState<string>('date_desc');
  
  const [currentPage, setCurrentPage] = useState<number>(1);
  const ADS_PER_PAGE = 20;

  useEffect(() => {
    const fetchAllData = async () => {
      setLoading(true);
      try {
        const response = await fetch('http://localhost:8000/ads?page_size=10000');
        const data = await response.json();
        setAllAds(data.items || []);
      } catch (error) {
        console.error("Failed to fetch ads:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchAllData();
  }, []);

  const filteredAds = useMemo(() => {
    let ads = [...allAds];
    if (selectedBrands.length > 0) ads = ads.filter(ad => ad.brand && selectedBrands.includes(ad.brand));
    if (selectedLengths.length > 0) ads = ads.filter(ad => selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`));
    if (selectedVolumes.length > 0) ads = ads.filter(ad => ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))));
    if (priceRange.min) ads = ads.filter(ad => ad.price && ad.price >= priceRange.min!);
    if (priceRange.max) ads = ads.filter(ad => ad.price && ad.price <= priceRange.max!);
    
    ads.sort((a, b) => {
        if (sortBy === 'date_asc') return new Date(a.scraped_at!).getTime() - new Date(b.scraped_at!).getTime();
        return new Date(b.scraped_at!).getTime() - new Date(a.scraped_at!).getTime();
    });
    return ads;
  }, [allAds, selectedBrands, selectedLengths, selectedVolumes, priceRange, sortBy]);

  const dynamicFilterOptions = useMemo(() => {
    const options: FilterOptions = { brands: [], lengths: [], volumes: [] };
    const getCounts = (ads: Ad[]) => {
      const brandCounts: { [key: string]: number } = {};
      const lengthCounts: { [key: string]: number } = {};
      const volumeCounts: { [key: string]: number } = {};
      ads.forEach(ad => {
          if (ad.brand) brandCounts[ad.brand] = (brandCounts[ad.brand] || 0) + 1;
          lengthCounts[`${ad.length_ft}'${ad.length_in || 0}"`] = (lengthCounts[`${ad.length_ft}'${ad.length_in || 0}"`] || 0) + 1;
          if (ad.liters) volumeCounts[String(Math.round(ad.liters))] = (volumeCounts[String(Math.round(ad.liters))] || 0) + 1;
      });
      return { brandCounts, lengthCounts, volumeCounts };
    };
    options.brands = Object.entries(getCounts(allAds.filter(ad => (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))))).brandCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));
    
    // --- FIXED: Use the custom sort function for lengths ---
    options.lengths = Object.entries(getCounts(allAds.filter(ad => (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))))).lengthCounts)
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => parseLengthToInches(a.name) - parseLengthToInches(b.name));

    options.volumes = Object.entries(getCounts(allAds.filter(ad => (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)))).volumeCounts).map(([name, count]) => ({ name, count })).sort((a, b) => Number(a.name) - Number(b.name));
    return options;
  }, [allAds, selectedBrands, selectedLengths, selectedVolumes]);

  const totalPages = Math.ceil(filteredAds.length / ADS_PER_PAGE);
  const paginatedAds = filteredAds.slice((currentPage - 1) * ADS_PER_PAGE, currentPage * ADS_PER_PAGE);

  useEffect(() => { setCurrentPage(1); }, [selectedBrands, selectedLengths, selectedVolumes, priceRange]);

  const handleFilterChange = (setter: React.Dispatch<React.SetStateAction<string[]>>) => (option: string) => setter(prev => prev.includes(option) ? prev.filter(item => item !== option) : [...prev, option]);
  const handleReset = (setter: React.Dispatch<React.SetStateAction<string[]>>) => () => setter([]);
  const handlePageChange = (newPage: number) => { if (newPage > 0 && newPage <= totalPages) { setCurrentPage(newPage); window.scrollTo(0, 0); } };
  const handlePriceChange = (min: number, max: number) => { if (min === 0 && max === 0) { setPriceRange({}); } else { setPriceRange({ min, max }); } };
  
  // --- NEW: Global reset function ---
  const handleGlobalReset = () => {
    setSelectedBrands([]);
    setSelectedLengths([]);
    setSelectedVolumes([]);
    setPriceRange({});
  };
  
  // --- NEW: Check if any filter is active to show the reset button ---
  const isAnyFilterActive = selectedBrands.length > 0 || selectedLengths.length > 0 || selectedVolumes.length > 0 || Object.keys(priceRange).length > 0;

  const renderModal = () => {
    if (!activeModal) return null;
    const modalProps = { onClose: () => setActiveModal(null) };
    switch (activeModal) {
      case 'brand': return <FilterModal {...modalProps} title="Brand" options={dynamicFilterOptions.brands} selectedOptions={selectedBrands} onOptionChange={handleFilterChange(setSelectedBrands)} onReset={handleReset(setSelectedBrands)} />;
      case 'length': return <FilterModal {...modalProps} title="Length" options={dynamicFilterOptions.lengths} selectedOptions={selectedLengths} onOptionChange={handleFilterChange(setSelectedLengths)} onReset={handleReset(setSelectedLengths)} />;
      case 'volume': return <FilterModal {...modalProps} title="Volume (Liters)" options={dynamicFilterOptions.volumes.map(v => ({...v, name: `${v.name}L`}))} selectedOptions={selectedVolumes.map(v => `${v}L`)} onOptionChange={(optionWithL) => handleFilterChange(setSelectedVolumes)(optionWithL.replace('L', ''))} onReset={handleReset(setSelectedVolumes)} />;
      case 'price': return (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-40 flex justify-center items-center" onClick={modalProps.onClose}>
            <div className="bg-white rounded-lg shadow-xl w-full max-w-sm m-4" onClick={(e) => e.stopPropagation()}>
                <CustomPriceSlider allAds={allAds} onPriceChange={handlePriceChange} />
            </div>
        </div>
      );
      default: return null;
    }
  };

  return (
    <div className="bg-gray-100 min-h-screen">
      {renderModal()}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4"><h1 className="text-3xl font-extrabold text-gray-800 tracking-tight">Surfboard Marketplace</h1><p className="text-gray-500">Find your next secondhand surfboard</p></div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <div className="bg-white p-4 rounded-lg shadow mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center space-x-6">
              <span className="font-semibold text-gray-500">Filter:</span>
              <button onClick={() => setActiveModal('brand')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Brand {selectedBrands.length > 0 && `(${selectedBrands.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
              <button onClick={() => setActiveModal('length')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Size {selectedLengths.length > 0 && `(${selectedLengths.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
              <button onClick={() => setActiveModal('volume')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Volume {selectedVolumes.length > 0 && `(${selectedVolumes.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
              <button onClick={() => setActiveModal('price')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Price</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
              
              {/* --- NEW: Conditionally rendered Reset button --- */}
              {isAnyFilterActive && (
                  <button 
                      onClick={handleGlobalReset}
                      className="text-sm text-blue-600 hover:underline"
                  >
                      Reset All
                  </button>
              )}
            </div>
            
            <div className="flex items-center space-x-4 mt-4 sm:mt-0">
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="border-gray-300 rounded-md shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"><option value="date_desc">Date: new to old</option><option value="date_asc">Date: old to new</option></select>
                <span className="font-semibold text-gray-800">{filteredAds.length} products</span>
            </div>
          </div>
        </div>
        {loading ? (<div className="text-center py-10"><p className="text-lg font-semibold">Loading boards...</p></div>) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{paginatedAds.map(ad => (<AdCard key={ad.id} ad={ad} />))}</div>
            <div className="flex justify-center items-center mt-8 space-x-2"><button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1} className="pagination-button">&larr; Previous</button><span className="px-4 py-2 text-gray-700">Page {currentPage} of {totalPages}</span><button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages} className="pagination-button">Next &rarr;</button></div>
          </>
        )}
      </main>
    </div>
  );
};

export default App;