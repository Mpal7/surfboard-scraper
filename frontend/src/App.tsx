import React, { useCallback, useEffect, useState, useMemo } from 'react';
import AdCard from './components/AdCard';
import FilterModal from './components/FilterModal';
import MeasurementFilterModal from './components/MeasurementFilterModal';
import CustomPriceSlider from './components/CustomPriceSlider';
import Login from './components/Login';
import { AUTH_LOGOUT_EVENT, getAllAds, getCurrentAdmin, getJob, hasAuthToken, logout, triggerRefresh } from './services/api';
import { Ad, FilterOptions, MeasurementFilters, MeasurementKey, NumericRange } from './types';

type ActiveModal = 'boardType' | 'equipmentType' | 'brand' | 'length' | 'volume' | 'measurements' | 'price' | 'location' | null;

const EMPTY_MEASUREMENT_FILTERS: MeasurementFilters = {
  foil_area_cm2: {},
  mast_length_cm: {},
  foil_wingspan_cm: {},
  wing_area_m2: {},
  board_length_cm: {},
  board_width_cm: {},
};

const matchesRange = (value: number | null, range: NumericRange): boolean => {
  if (range.min === undefined && range.max === undefined) return true;
  if (value === null) return false;
  if (range.min !== undefined && value < range.min) return false;
  if (range.max !== undefined && value > range.max) return false;
  return true;
};

const matchesMeasurementFilters = (ad: Ad, filters: MeasurementFilters): boolean => (
  (Object.keys(filters) as MeasurementKey[]).every(key => matchesRange(ad[key], filters[key]))
);

const hasMeasurementFilters = (filters: MeasurementFilters): boolean => (
  Object.values(filters).some(range => range.min !== undefined || range.max !== undefined)
);

const parseLengthToInches = (lengthStr: string): number => {
    try {
        const parts = lengthStr.replace('"', '').split("'");
        const feet = parseInt(parts[0], 10) || 0;
        const inches = parseInt(parts[1], 10) || 0;
        return (feet * 12) + inches;
    } catch {
        return 0;
    }
};

const App: React.FC = () => {
  const [authState, setAuthState] = useState<'checking' | 'authenticated' | 'unauthenticated'>(
    hasAuthToken() ? 'checking' : 'unauthenticated'
  );
  const [adminUsername, setAdminUsername] = useState('');
  const [loading, setLoading] = useState<boolean>(true);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  const [allAds, setAllAds] = useState<Ad[]>([]); 
  
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedBoardTypes, setSelectedBoardTypes] = useState<string[]>([]);
  const [selectedEquipmentTypes, setSelectedEquipmentTypes] = useState<string[]>([]);
  const [selectedLengths, setSelectedLengths] = useState<string[]>([]);
  const [selectedVolumes, setSelectedVolumes] = useState<string[]>([]);
  const [measurementFilters, setMeasurementFilters] = useState<MeasurementFilters>(EMPTY_MEASUREMENT_FILTERS);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState<{min?: number, max?: number}>({});
  const [sortBy, setSortBy] = useState<string>('date_desc');
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  
  const [currentPage, setCurrentPage] = useState<number>(1);
  const ADS_PER_PAGE = 20;

  useEffect(() => {
    const handleLogout = () => {
      setAdminUsername('');
      setAuthState('unauthenticated');
    };
    window.addEventListener(AUTH_LOGOUT_EVENT, handleLogout);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, handleLogout);
  }, []);

  useEffect(() => {
    if (!hasAuthToken()) return;

    getCurrentAdmin()
      .then((admin) => {
        setAdminUsername(admin.username);
        setAuthState('authenticated');
      })
      .catch(() => {
        logout();
        setAuthState('unauthenticated');
      });
  }, []);

  const fetchAllAds = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAllAds();
      setAllAds(data.items || []);
    } catch (error) {
      console.error("Failed to fetch ads:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authState !== 'authenticated') return;
    fetchAllAds();
  }, [authState, fetchAllAds]);

  const filteredAds = useMemo(() => {
    let ads = [...allAds];
    if (selectedBoardTypes.length > 0) ads = ads.filter(ad => ad.board_type && selectedBoardTypes.includes(ad.board_type));
    if (selectedEquipmentTypes.length > 0) ads = ads.filter(ad => ad.equipment_type && selectedEquipmentTypes.includes(ad.equipment_type));
    if (selectedBrands.length > 0) ads = ads.filter(ad => ad.brand && selectedBrands.includes(ad.brand));
    if (selectedLengths.length > 0) ads = ads.filter(ad => selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`));
    if (selectedVolumes.length > 0) ads = ads.filter(ad => ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))));
    ads = ads.filter(ad => matchesMeasurementFilters(ad, measurementFilters));
    if (selectedLocations.length > 0) ads = ads.filter(ad => ad.location && selectedLocations.includes(ad.location));
    if (priceRange.min) ads = ads.filter(ad => ad.price && ad.price >= priceRange.min!);
    if (priceRange.max) ads = ads.filter(ad => ad.price && ad.price <= priceRange.max!);
    
    ads.sort((a, b) => {
        if (sortBy === 'date_asc') {
          return new Date(a.scraped_at!).getTime() - new Date(b.scraped_at!).getTime();}
        else if (sortBy === 'date_desc'){
          return new Date(b.scraped_at!).getTime()- new Date(a.scraped_at!).getTime();}
        else if (sortBy === 'price_asc'){
          return (a.price || 0) - (b.price || 0);}
        else if (sortBy === 'price_desc'){
          return (b.price || 0) - (a.price || 0);
        }
        return 0;
    });

    return ads;
  }, [allAds, selectedBoardTypes, selectedEquipmentTypes, selectedBrands, selectedLengths, selectedVolumes, measurementFilters, selectedLocations, priceRange, sortBy]);

  const dynamicFilterOptions = useMemo(() => {
    const options: FilterOptions = { brands: [], boardTypes: [], equipmentTypes: [], lengths: [], volumes: [], locations: [] };
    const getCounts = (ads: Ad[]) => {
      const brandCounts: { [key: string]: number } = {};
      const boardTypeCounts: { [key: string]: number } = {};
      const equipmentTypeCounts: { [key: string]: number } = {};
      const lengthCounts: { [key: string]: number } = {};
      const volumeCounts: { [key: string]: number } = {};
      const locationCounts: { [key: string]: number } = {};
      ads.forEach(ad => {
          if (ad.brand) brandCounts[ad.brand] = (brandCounts[ad.brand] || 0) + 1;
          if (ad.board_type) boardTypeCounts[ad.board_type] = (boardTypeCounts[ad.board_type] || 0) + 1;
          if (ad.equipment_type) equipmentTypeCounts[ad.equipment_type] = (equipmentTypeCounts[ad.equipment_type] || 0) + 1;
          lengthCounts[`${ad.length_ft}'${ad.length_in || 0}"`] = (lengthCounts[`${ad.length_ft}'${ad.length_in || 0}"`] || 0) + 1;
          if (ad.liters) volumeCounts[String(Math.round(ad.liters))] = (volumeCounts[String(Math.round(ad.liters))] || 0) + 1;
          if (ad.location) locationCounts[ad.location] = (locationCounts[ad.location] || 0) + 1;
      });
      return { brandCounts, boardTypeCounts, equipmentTypeCounts, lengthCounts, volumeCounts, locationCounts };
    };
    options.boardTypes = Object.entries(getCounts(allAds.filter(ad => (selectedEquipmentTypes.length === 0 || (ad.equipment_type && selectedEquipmentTypes.includes(ad.equipment_type))) && (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))) && (selectedLocations.length === 0 || (ad.location && selectedLocations.includes(ad.location))))).boardTypeCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));
    options.equipmentTypes = Object.entries(getCounts(allAds.filter(ad => (selectedBoardTypes.length === 0 || (ad.board_type && selectedBoardTypes.includes(ad.board_type))) && (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))) && (selectedLocations.length === 0 || (ad.location && selectedLocations.includes(ad.location))))).equipmentTypeCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));
    options.brands = Object.entries(getCounts(allAds.filter(ad => (selectedBoardTypes.length === 0 || (ad.board_type && selectedBoardTypes.includes(ad.board_type))) && (selectedEquipmentTypes.length === 0 || (ad.equipment_type && selectedEquipmentTypes.includes(ad.equipment_type))) && (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))) && (selectedLocations.length === 0 || (ad.location && selectedLocations.includes(ad.location))))).brandCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));
    
    options.lengths = Object.entries(getCounts(allAds.filter(ad => (selectedBoardTypes.length === 0 || (ad.board_type && selectedBoardTypes.includes(ad.board_type))) && (selectedEquipmentTypes.length === 0 || (ad.equipment_type && selectedEquipmentTypes.includes(ad.equipment_type))) && (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))) && (selectedLocations.length === 0 || (ad.location && selectedLocations.includes(ad.location))))).lengthCounts)
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => parseLengthToInches(a.name) - parseLengthToInches(b.name));

    options.volumes = Object.entries(getCounts(allAds.filter(ad => (selectedBoardTypes.length === 0 || (ad.board_type && selectedBoardTypes.includes(ad.board_type))) && (selectedEquipmentTypes.length === 0 || (ad.equipment_type && selectedEquipmentTypes.includes(ad.equipment_type))) && (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) && (selectedLocations.length === 0 || (ad.location && selectedLocations.includes(ad.location))))).volumeCounts).map(([name, count]) => ({ name, count })).sort((a, b) => Number(a.name) - Number(b.name));
    
    options.locations = Object.entries(getCounts(allAds.filter(ad => (selectedBoardTypes.length === 0 || (ad.board_type && selectedBoardTypes.includes(ad.board_type))) && (selectedEquipmentTypes.length === 0 || (ad.equipment_type && selectedEquipmentTypes.includes(ad.equipment_type))) && (selectedBrands.length === 0 || (ad.brand && selectedBrands.includes(ad.brand))) && (selectedLengths.length === 0 || selectedLengths.includes(`${ad.length_ft}'${ad.length_in || 0}"`)) && (selectedVolumes.length === 0 || (ad.liters && selectedVolumes.includes(String(Math.round(ad.liters))))))).locationCounts).map(([name, count]) => ({ name, count })).sort((a,b) => a.name.localeCompare(b.name));
    
    return options;
  }, [allAds, selectedBoardTypes, selectedEquipmentTypes, selectedBrands, selectedLengths, selectedVolumes, selectedLocations]);

  const totalPages = Math.ceil(filteredAds.length / ADS_PER_PAGE);
  const paginatedAds = filteredAds.slice((currentPage - 1) * ADS_PER_PAGE, currentPage * ADS_PER_PAGE);

  useEffect(() => { setCurrentPage(1); }, [selectedBoardTypes, selectedEquipmentTypes, selectedBrands, selectedLengths, selectedVolumes, measurementFilters, selectedLocations, priceRange]);

  const handleFilterChange = (setter: React.Dispatch<React.SetStateAction<string[]>>) => (option: string) => setter(prev => prev.includes(option) ? prev.filter(item => item !== option) : [...prev, option]);
  const handleReset = (setter: React.Dispatch<React.SetStateAction<string[]>>) => () => setter([]);
  const handlePageChange = (newPage: number) => { if (newPage > 0 && newPage <= totalPages) { setCurrentPage(newPage); window.scrollTo(0, 0); } };
  const handlePriceChange = (min: number, max: number) => { if (min === 0 && max === 0) { setPriceRange({}); } else { setPriceRange({ min, max }); } };
  const handleMeasurementChange = (key: MeasurementKey, bound: 'min' | 'max', value: string) => {
    setMeasurementFilters(previous => ({
      ...previous,
      [key]: {
        ...previous[key],
        [bound]: value === '' ? undefined : Number(value),
      },
    }));
  };
  
  const handleGlobalReset = () => {
    setSelectedBoardTypes([]);
    setSelectedEquipmentTypes([]);
    setSelectedBrands([]);
    setSelectedLengths([]);
    setSelectedVolumes([]);
    setMeasurementFilters(EMPTY_MEASUREMENT_FILTERS);
    setSelectedLocations([]);
    setPriceRange({});
  };
  
  const isAnyFilterActive = selectedBoardTypes.length > 0 || selectedEquipmentTypes.length > 0 || selectedBrands.length > 0 || selectedLengths.length > 0 || selectedVolumes.length > 0 || hasMeasurementFilters(measurementFilters) || selectedLocations.length > 0 || Object.keys(priceRange).length > 0;

  const REFRESH_POLL_INTERVAL_MS = 2000;

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMessage('Starting refresh…');
    try {
      const started = await triggerRefresh();
      let job = await getJob(started.job_id);
      while (job.status === 'queued' || job.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, REFRESH_POLL_INTERVAL_MS));
        job = await getJob(started.job_id);
      }
      if (job.status === 'completed') {
        const added = job.result?.new_ads_added ?? 0;
        setRefreshMessage(`Refresh complete — ${added} new ${added === 1 ? 'ad' : 'ads'}.`);
        await fetchAllAds();
      } else {
        setRefreshMessage(`Refresh failed${job.error_message ? `: ${job.error_message}` : '.'}`);
      }
    } catch (error) {
      setRefreshMessage(error instanceof Error ? error.message : 'Refresh failed.');
    } finally {
      setRefreshing(false);
    }
  };

  const renderModal = () => {
    if (!activeModal) return null;
    const modalProps = { onClose: () => setActiveModal(null) };
    switch (activeModal) {
      case 'boardType': return <FilterModal {...modalProps} title="Type" options={dynamicFilterOptions.boardTypes} selectedOptions={selectedBoardTypes} onOptionChange={handleFilterChange(setSelectedBoardTypes)} onReset={handleReset(setSelectedBoardTypes)} />;
      case 'equipmentType': return <FilterModal {...modalProps} title="Component" options={dynamicFilterOptions.equipmentTypes} selectedOptions={selectedEquipmentTypes} onOptionChange={handleFilterChange(setSelectedEquipmentTypes)} onReset={handleReset(setSelectedEquipmentTypes)} />;
      case 'brand': return <FilterModal {...modalProps} title="Brand" options={dynamicFilterOptions.brands} selectedOptions={selectedBrands} onOptionChange={handleFilterChange(setSelectedBrands)} onReset={handleReset(setSelectedBrands)} />;
      case 'length': return <FilterModal {...modalProps} title="Length" options={dynamicFilterOptions.lengths} selectedOptions={selectedLengths} onOptionChange={handleFilterChange(setSelectedLengths)} onReset={handleReset(setSelectedLengths)} />;
      case 'volume': return <FilterModal {...modalProps} title="Volume (Liters)" options={dynamicFilterOptions.volumes.map(v => ({...v, name: `${v.name}L`}))} selectedOptions={selectedVolumes.map(v => `${v}L`)} onOptionChange={(optionWithL) => handleFilterChange(setSelectedVolumes)(optionWithL.replace('L', ''))} onReset={handleReset(setSelectedVolumes)} />;
      case 'measurements': return <MeasurementFilterModal values={measurementFilters} boardTypes={selectedBoardTypes} onChange={handleMeasurementChange} onReset={() => setMeasurementFilters(EMPTY_MEASUREMENT_FILTERS)} {...modalProps} />;
      case 'location': return <FilterModal {...modalProps} title="Location" options={dynamicFilterOptions.locations} selectedOptions={selectedLocations} onOptionChange={handleFilterChange(setSelectedLocations)} onReset={handleReset(setSelectedLocations)} />;
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

  if (authState === 'checking') {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm text-slate-300">Checking session...</div>;
  }

  if (authState === 'unauthenticated') {
    return <Login onAuthenticated={(username) => { setAdminUsername(username); setAuthState('authenticated'); }} />;
  }

  return (
    <div className="bg-gray-100 min-h-screen">
      {renderModal()}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="container mx-auto flex items-center justify-between gap-4 px-4 py-4">
          <div><h1 className="text-3xl font-extrabold text-gray-800 tracking-tight">Surfboard Marketplace</h1><p className="text-gray-500">Find your next secondhand surfboard</p></div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
            <button onClick={() => { logout(); setAdminUsername(''); setAuthState('unauthenticated'); }} className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-600 transition hover:border-gray-400 hover:text-gray-900">Sign out{adminUsername && ` (${adminUsername})`}</button>
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        {refreshMessage && (
          <div className="mb-4 rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-800">{refreshMessage}</div>
        )}
        <div className="bg-white p-4 rounded-lg shadow mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center space-x-6">
              <span className="font-semibold text-gray-500">Filter:</span>
              <button onClick={() => setActiveModal('boardType')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Type {selectedBoardTypes.length > 0 && `(${selectedBoardTypes.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
               <button onClick={() => setActiveModal('equipmentType')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Component {selectedEquipmentTypes.length > 0 && `(${selectedEquipmentTypes.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
               <button onClick={() => setActiveModal('brand')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Brand {selectedBrands.length > 0 && `(${selectedBrands.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
               <button onClick={() => setActiveModal('length')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Size {selectedLengths.length > 0 && `(${selectedLengths.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
               <button onClick={() => setActiveModal('volume')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Volume {selectedVolumes.length > 0 && `(${selectedVolumes.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
               <button onClick={() => setActiveModal('measurements')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Measurements {hasMeasurementFilters(measurementFilters) && '(active)'}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l7 7-7-7" /></svg></button>
              <button onClick={() => setActiveModal('location')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Location {selectedLocations.length > 0 && `(${selectedLocations.length})`}</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
              <button onClick={() => setActiveModal('price')} className="flex items-center space-x-1.5 text-base font-medium text-gray-700 hover:text-blue-600 group"><span className="group-hover:underline">Price</span><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
              
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
                <span className="font-semibold text-gray-500">Sort by:</span>
                <select value={sortBy}
                 onChange={(e) => setSortBy(e.target.value)} 
                 className="border-gray-300 rounded-md shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
                 >
                  <option value="date_desc">Date: new to old</option>
                  <option value="date_asc">Date: old to new</option>
                  <option value="price_asc">Price: low to high</option>
                  <option value="price_desc">Price: high to low</option>
                  </select>
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
