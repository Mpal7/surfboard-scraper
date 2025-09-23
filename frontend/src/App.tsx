import React, { useEffect, useState, useMemo } from 'react';
import AdCard from './components/AdCard';
import FilterModal from './components/FilterModal';
import { getFilterOptions } from './services/api'; // We only need getFilterOptions now
import { Ad, FilterOptions } from './types';

type ActiveModal = 'brand' | 'length' | 'volume' | null;

const App: React.FC = () => {
  // --- STATE ---
  const [loading, setLoading] = useState<boolean>(true);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  
  // Master list of all ads, fetched only once
  const [allAds, setAllAds] = useState<Ad[]>([]); 
  
  // Selected filter values
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedLengths, setSelectedLengths] = useState<string[]>([]);
  const [selectedVolumes, setSelectedVolumes] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<string>('date_desc');
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const ADS_PER_PAGE = 20;

  // --- DATA FETCHING ---
  // This effect runs only once to fetch all ads and populate our filter options
  useEffect(() => {
    const fetchAllData = async () => {
      setLoading(true);
      try {
        // We can get all ads by using the getFilterOptions endpoint which fetches a large number
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

  // --- DYNAMIC FILTERING & COUNTING (The Magic Happens Here) ---
  // useMemo will re-calculate only when its dependencies change
  const filteredAds = useMemo(() => {
    let ads = [...allAds];

    if (selectedBrands.length > 0) {
      ads = ads.filter(ad => ad.brand && selectedBrands.includes(ad.brand));
    }
    if (selectedLengths.length > 0) {
      ads = ads.filter(ad => {
        const lengthStr = `${ad.length_ft}'${ad.length_in || 0}"`;
        return selectedLengths.includes(lengthStr);
      });
    }
    if (selectedVolumes.length > 0) {
      ads = ads.filter(ad => {
        if (!ad.liters) return false;
        const roundedLiters = String(Math.round(ad.liters));
        return selectedVolumes.includes(roundedLiters);
      });
    }
    
    // Sorting
    ads.sort((a, b) => {
        if (sortBy === 'date_asc') {
            return new Date(a.scraped_at!).getTime() - new Date(b.scraped_at!).getTime();
        }
        // Default to date_desc
        return new Date(b.scraped_at!).getTime() - new Date(a.scraped_at!).getTime();
    });

    return ads;
  }, [allAds, selectedBrands, selectedLengths, selectedVolumes, sortBy]);

  // --- DYNAMIC FILTER OPTIONS CALCULATION ---
  const dynamicFilterOptions = useMemo(() => {
    const options: FilterOptions = { brands: [], lengths: [], volumes: [] };
    
    // Helper to count options from a filtered list of ads
    const getCounts = (ads: Ad[], currentFilters: {brands?: string[], lengths?: string[], volumes?: string[]}) => {
      const brandCounts: { [key: string]: number } = {};
      const lengthCounts: { [key: string]: number } = {};
      const volumeCounts: { [key: string]: number } = {};

      ads.forEach(ad => {
          // Brand Count
          if (ad.brand) {
              brandCounts[ad.brand] = (brandCounts[ad.brand] || 0) + 1;
          }
          // Length Count
          const lengthStr = `${ad.length_ft}'${ad.length_in || 0}"`;
          lengthCounts[lengthStr] = (lengthCounts[lengthStr] || 0) + 1;
          // Volume Count
          if (ad.liters) {
              const roundedLiters = String(Math.round(ad.liters));
              volumeCounts[roundedLiters] = (volumeCounts[roundedLiters] || 0) + 1;
          }
      });
      return { brandCounts, lengthCounts, volumeCounts };
    };
    
    // For Brand options, filter by everything EXCEPT brand
    const brandFilteredAds = allAds.filter(ad => 
        (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) &&
        (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters)))))
    );
    options.brands = Object.entries(getCounts(brandFilteredAds, {}).brandCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));

    // For Length options, filter by everything EXCEPT length
    const lengthFilteredAds = allAds.filter(ad => 
        (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) &&
        (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters)))))
    );
    options.lengths = Object.entries(getCounts(lengthFilteredAds, {}).lengthCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));

    // For Volume options, filter by everything EXCEPT volume
    const volumeFilteredAds = allAds.filter(ad => 
        (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) &&
        (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`))
    );
    options.volumes = Object.entries(getCounts(volumeFilteredAds, {}).volumeCounts).map(([name, count]) => ({ name, count })).sort((a, b) => Number(a.name) - Number(b.name));


    return options;

  }, [allAds, selectedBrands, selectedLengths, selectedVolumes]);

  // --- PAGINATION LOGIC ---
  const totalPages = Math.ceil(filteredAds.length / ADS_PER_PAGE);
  const paginatedAds = filteredAds.slice((currentPage - 1) * ADS_PER_PAGE, currentPage * ADS_PER_PAGE);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedBrands, selectedLengths, selectedVolumes]);

  // --- HANDLER FUNCTIONS ---
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
  
  // --- RENDER LOGIC ---
  const renderModal = () => {
    if (!activeModal) return null;
    
    const modalProps = { onClose: () => setActiveModal(null) };

    switch (activeModal) {
      case 'brand':
        return <FilterModal {...modalProps} title="Brand" options={dynamicFilterOptions.brands} selectedOptions={selectedBrands} onOptionChange={handleFilterChange(setSelectedBrands)} onReset={handleReset(setSelectedBrands)} />;
      case 'length':
        return <FilterModal {...modalProps} title="Length" options={dynamicFilterOptions.lengths} selectedOptions={selectedLengths} onOptionChange={handleFilterChange(setSelectedLengths)} onReset={handleReset(setSelectedLengths)} />;
      case 'volume':
        return <FilterModal {...modalProps} title="Volume (Liters)" options={dynamicFilterOptions.volumes.map(v => ({...v, name: `${v.name}L`}))} selectedOptions={selectedVolumes.map(v => `${v}L`)} onOptionChange={(optionWithL) => handleFilterChange(setSelectedVolumes)(optionWithL.replace('L', ''))} onReset={handleReset(setSelectedVolumes)} />;
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
        {/* --- NEW & IMPROVED FILTER AND SORT BAR --- */}
        <div className="bg-white p-4 rounded-lg shadow mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
            {/* Filter Buttons Section */}
            <div className="flex items-center space-x-6"> {/* Increased spacing */}
              <span className="font-semibold text-gray-500">Filter:</span>
              
              {/* Brand Filter Button */}
              <button 
                onClick={() => setActiveModal('brand')} 
                className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"
              >
                <span className="group-hover:underline">Brand {selectedBrands.length > 0 && `(${selectedBrands.length})`}</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              
              {/* Size Filter Button */}
              <button 
                onClick={() => setActiveModal('length')} 
                className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"
              >
                <span className="group-hover:underline">Size {selectedLengths.length > 0 && `(${selectedLengths.length})`}</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Volume Filter Button */}
              <button 
                onClick={() => setActiveModal('volume')} 
                className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"
              >
                <span className="group-hover:underline">Volume {selectedVolumes.length > 0 && `(${selectedVolumes.length})`}</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            
            {/* Sorting Section */}
            <div className="flex items-center space-x-4 mt-4 sm:mt-0">
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="border-gray-300 rounded-md shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <option value="date_desc">Date: new to old</option>
                    <option value="date_asc">Date: old to new</option>
                </select>
                <span className="font-semibold text-gray-800">{filteredAds.length} products</span>
            </div>
          </div>
        </div>

        {/* --- ADS GRID (No Changes Below) --- */}
        {loading ? (
          <div className="text-center py-10"><p className="text-lg font-semibold">Loading boards...</p></div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {paginatedAds.map(ad => (
                <AdCard key={ad.id} ad={ad} />
              ))}
            </div>
            <div className="flex justify-center items-center mt-8 space-x-2">
              <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1} className="pagination-button">&larr; Previous</button>
              <span className="px-4 py-2 text-gray-700">Page {currentPage} of {totalPages}</span>
              <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages} className="pagination-button">Next &rarr;</button>
            </div>
          </>
        )}
      </main>
    </div>
  );
};

export default App;