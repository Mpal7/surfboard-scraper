// src/App.tsx

import React, { useEffect, useState } from 'react';
import AdCard from './components/AdCard';
import Sidebar from './components/Sidebar';
import { getAds, getFilterOptions } from './services/api';
import { Ad, FilterOptions, PaginatedAds } from './types';

const App: React.FC = () => {
  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ brands: [], lengths: [] });
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedLengths, setSelectedLengths] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);


  useEffect(() => {
    const fetchFilters = async () => {
      const options = await getFilterOptions();
      setFilterOptions(options);
    };
    fetchFilters();
  }, []);

  useEffect(() => {
    const fetchAds = async () => {
      setLoading(true);
      const filters = {
        brand: selectedBrands.join(','),
        // The length filter will require backend changes to support multiple values.
        // For now, we will filter on the frontend for demonstration.
      };
      const data: PaginatedAds = await getAds(currentPage, filters);
      
      let filteredAds = data.items;
      if (selectedLengths.length > 0) {
        filteredAds = data.items.filter(ad => {
          const lengthStr = `${ad.length_ft}'${ad.length_in || 0}"`;
          return selectedLengths.includes(lengthStr);
        });
      }
      
      setAds(filteredAds);
      setTotalPages(Math.ceil(data.total_items / data.page_size));
      setLoading(false);
    };
    fetchAds();
  }, [selectedBrands, selectedLengths, currentPage]);

  const handleBrandChange = (brand: string) => {
    setSelectedBrands(prev =>
      prev.includes(brand) ? prev.filter(b => b !== brand) : [...prev, brand]
    );
  };

  const handleLengthChange = (length: string) => {
    setSelectedLengths(prev =>
      prev.includes(length) ? prev.filter(l => l !== length) : [...prev, length]
    );
  };
  
  const handlePageChange = (newPage: number) => {
    if (newPage > 0 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };


  return (
    <div className="bg-gray-50 min-h-screen">
      <header className="bg-white shadow-md">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-800">Surfboard Marketplace</h1>
          <p className="text-gray-600">Find your next secondhand surfboard</p>
        </div>
      </header>
      <main className="container mx-auto px-4 py-8 flex">
        <Sidebar
          filters={filterOptions}
          selectedBrands={selectedBrands}
          selectedLengths={selectedLengths}
          onBrandChange={handleBrandChange}
          onLengthChange={handleLengthChange}
        />
        <div className="w-3/4 pl-8">
          {loading ? (
            <p>Loading...</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {ads.map(ad => (
                  <AdCard key={ad.id} ad={ad} />
                ))}
              </div>
              <div className="flex justify-center mt-8">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="px-4 py-2 mx-1 bg-white border rounded disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="px-4 py-2 mx-1">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="px-4 py-2 mx-1 bg-white border rounded disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
};

export default App;