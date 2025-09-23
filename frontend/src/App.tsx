// src/App.tsx

import React, { useEffect, useState } from 'react';
import AdCard from './components/AdCard';
import FilterModal from './components/FilterModal';
import { getAds, getFilterOptions } from './services/api';
import { Ad, FilterOptions } from './types';

type ActiveModal = 'brand' | 'length' | 'volume' | null;

const App: React.FC = () => {
  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ brands: [], lengths: [], volumes: [] });
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedLengths, setSelectedLengths] = useState<string[]>([]);
  const [selectedVolumes, setSelectedVolumes] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<string>('date_desc');
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);

  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalAds, setTotalAds] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);

  useEffect(() => {
    const fetchFilters = async () => {
      try {
        const options = await getFilterOptions();
        setFilterOptions(options);
      } catch (error) {
        console.error("Failed to fetch filter options:", error);
      }
    };
    fetchFilters();
  }, []);

  useEffect(() => {
    const fetchAds = async () => {
      setLoading(true);
      
      const filters = {
        brand: selectedBrands.join(','),
        liters: selectedVolumes.join(','), // Pass selected volumes to the backend
        sort_by: sortBy,
      };

      try {
        const data = await getAds(currentPage, filters);
        
        // Frontend filtering for length remains necessary
        let filteredAds = data.items;
        if (selectedLengths.length > 0) {
          filteredAds = data.items.filter(ad => {
            const lengthStr = `${ad.length_ft}'${ad.length_in || 0}"`;
            return selectedLengths.includes(lengthStr);
          });
        }
        
        setAds(filteredAds);
        setTotalAds(data.total_items);
        setTotalPages(Math.ceil(data.total_items / data.page_size));
      } catch (error) {
        console.error("Failed to fetch ads:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchAds();
  }, [selectedBrands, selectedLengths, selectedVolumes, sortBy, currentPage]);

  const handleFilterChange = (setter: React.Dispatch<React.SetStateAction<string[]>>) => (option: string) => {
    setter(prev =>
      prev.includes(option) ? prev.filter(item => item !== option) : [...prev, option]
    );
  };

  const handleReset = (setter: React.Dispatch<React.SetStateAction<string[]>>) => () => {
    setter([]);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage > 0 && newPage <= totalPages) {
      setCurrentPage(newPage);
      window.scrollTo(0, 0);
    }
  };

  const renderModal = () => {
    if (!activeModal) return null;
    
    const modalProps = {
        onClose: () => setActiveModal(null),
    };

    switch (activeModal) {
      case 'brand':
        return <FilterModal 
                  {...modalProps}
                  title="Brand" 
                  options={filterOptions.brands} 
                  selectedOptions={selectedBrands} 
                  onOptionChange={handleFilterChange(setSelectedBrands)} 
                  onReset={handleReset(setSelectedBrands)} 
               />;
      case 'length':
        return <FilterModal 
                  {...modalProps}
                  title="Length" 
                  options={filterOptions.lengths} 
                  selectedOptions={selectedLengths} 
                  onOptionChange={handleFilterChange(setSelectedLengths)} 
                  onReset={handleReset(setSelectedLengths)}
               />;
      case 'volume':
        return <FilterModal
                  {...modalProps}
                  title="Volume (Liters)"
                  // Use options from state, add "L" for display
                  options={filterOptions.volumes.map(v => ({...v, name: `${v.name}L`}))}
                  // Selected options are stored without "L"
                  selectedOptions={selectedVolumes.map(v => `${v}L`)}
                  // Strip "L" before updating state
                  onOptionChange={(optionNameWithL) => {
                      const optionName = optionNameWithL.replace('L', '');
                      handleFilterChange(setSelectedVolumes)(optionName);
                  }}
                  onReset={handleReset(setSelectedVolumes)}
               />;
      default:
        return null;
    }
  };

  return (
    <div className="bg-gray-100 min-h-screen">
      {renderModal()}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-3xl font-extrabold text-gray-800 tracking-tight">Surfboard Marketplace</h1>
          <p className="text-gray-500">Find your next secondhand surfboard</p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="bg-white p-4 rounded-lg shadow mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center space-x-2 overflow-x-auto pb-2 sm:pb-0">
              <span className="font-semibold text-gray-700">Filter:</span>
              <button onClick={() => setActiveModal('brand')} className="filter-button">Brand {selectedBrands.length > 0 && `(${selectedBrands.length})`}</button>
              <button onClick={() => setActiveModal('length')} className="filter-button">Size {selectedLengths.length > 0 && `(${selectedLengths.length})`}</button>
              <button onClick={() => setActiveModal('volume')} className="filter-button">Volume {selectedVolumes.length > 0 && `(${selectedVolumes.length})`}</button>
            </div>
            <div className="flex items-center space-x-4 mt-4 sm:mt-0">
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="border-gray-300 rounded-md shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
                >
                    <option value="date_desc">Date: new to old</option>
                    <option value="date_asc">Date: old to new</option>
                </select>
                <span className="font-semibold text-gray-800">{totalAds} products</span>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-10">
            <p className="text-lg font-semibold">Loading boards...</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {ads.map(ad => (
                <AdCard key={ad.id} ad={ad} />
              ))}
            </div>
            <div className="flex justify-center items-center mt-8 space-x-2">
              <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1} className="pagination-button">
                &larr; Previous
              </button>
              <span className="px-4 py-2 text-gray-700">
                Page {currentPage} of {totalPages}
              </span>
              <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages} className="pagination-button">
                Next &rarr;
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
};

export default App;