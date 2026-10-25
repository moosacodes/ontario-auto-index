import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { getSaved, toggleSaved } from "./storage";
import type { Manifest, Vehicle } from "./types";
import "./styles.css";

const PAGE_SIZE = 24;
const money = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat("en-CA");
type Sort = "recommended" | "price-asc" | "price-desc" | "mileage" | "newest";
const dataUrl = (path: string) => new URL(`data/${path}`, document.baseURI).toString();

async function loadVehicles(): Promise<{ vehicles: Vehicle[]; generatedAt: string }> {
  const response = await fetch(dataUrl("manifest.json"), { cache: "no-cache" });
  if (!response.ok) throw new Error("The latest inventory could not be loaded.");
  const manifest = (await response.json()) as Manifest;
  const partitions = await Promise.all(manifest.partitions.map(async ({ file }) => {
    const result = await fetch(dataUrl(`partitions/${file}`), { cache: "force-cache" });
    if (!result.ok) throw new Error(`An inventory source is unavailable (${file}).`);
    return (await result.json()) as Vehicle[];
  }));
  return { vehicles: partitions.flat().filter((item) => item.validation_status === "valid"), generatedAt: manifest.generated_at };
}

const title = (vehicle: Vehicle) => [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ") || "Vehicle listing";
const optionValues = (vehicles: Vehicle[], field: keyof Vehicle) => [...new Set(vehicles.map((vehicle) => vehicle[field]).filter((value): value is string => typeof value === "string" && !!value))].sort((a, b) => a.localeCompare(b));

function VehicleImage({ vehicle }: { vehicle: Vehicle }) {
  const [failed, setFailed] = useState(false);
  const source = vehicle.image_urls?.[0];
  if (!source || failed) return <div className="image-placeholder" aria-label="Photo not supplied by dealer"><span>OA</span><small>Photo unavailable</small></div>;
  return <img className="vehicle-image" src={source} alt={title(vehicle)} loading="lazy" onError={() => setFailed(true)} />;
}

function App() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [make, setMake] = useState("");
  const [dealer, setDealer] = useState("");
  const [municipality, setMunicipality] = useState("");
  const [body, setBody] = useState("");
  const [transmission, setTransmission] = useState("");
  const [drivetrain, setDrivetrain] = useState("");
  const [fuelType, setFuelType] = useState("");
  const [exteriorColour, setExteriorColour] = useState("");
  const [minYear, setMinYear] = useState("");
  const [maxYear, setMaxYear] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [maxMileage, setMaxMileage] = useState("");
  const [photosOnly, setPhotosOnly] = useState(false);
  const [savedOnly, setSavedOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("recommended");
  const [page, setPage] = useState(1);
  const [generatedAt, setGeneratedAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  useEffect(() => {
    Promise.all([loadVehicles(), getSaved()])
      .then(([inventory, stored]) => { setVehicles(inventory.vehicles); setGeneratedAt(inventory.generatedAt); setSaved(stored); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Inventory load failed."))
      .finally(() => setLoading(false));
  }, []);

  const makes = useMemo(() => optionValues(vehicles, "make"), [vehicles]);
  const dealers = useMemo(() => optionValues(vehicles, "dealer_name"), [vehicles]);
  const municipalities = useMemo(() => optionValues(vehicles, "municipality"), [vehicles]);
  const bodies = useMemo(() => optionValues(vehicles, "body_style"), [vehicles]);
  const transmissions = useMemo(() => optionValues(vehicles, "transmission"), [vehicles]);
  const drivetrains = useMemo(() => optionValues(vehicles, "drivetrain"), [vehicles]);
  const fuelTypes = useMemo(() => optionValues(vehicles, "fuel_type"), [vehicles]);
  const exteriorColours = useMemo(() => optionValues(vehicles, "exterior_colour"), [vehicles]);
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = vehicles.filter((vehicle) => {
      const searchable = [vehicle.year, vehicle.make, vehicle.model, vehicle.trim, vehicle.dealer_name, vehicle.municipality, vehicle.body_style, vehicle.exterior_colour, vehicle.transmission, vehicle.drivetrain, vehicle.fuel_type].filter(Boolean).join(" ").toLowerCase();
      return (!needle || searchable.includes(needle)) && (!make || vehicle.make === make) && (!dealer || vehicle.dealer_name === dealer) && (!municipality || vehicle.municipality === municipality) && (!body || vehicle.body_style === body) && (!transmission || vehicle.transmission === transmission) && (!drivetrain || vehicle.drivetrain === drivetrain) && (!fuelType || vehicle.fuel_type === fuelType) && (!exteriorColour || vehicle.exterior_colour === exteriorColour) && (!minYear || (vehicle.year ?? 0) >= Number(minYear)) && (!maxYear || (vehicle.year ?? Infinity) <= Number(maxYear)) && (!minPrice || Number(vehicle.price_cad ?? 0) >= Number(minPrice)) && (!maxPrice || Number(vehicle.price_cad ?? Infinity) <= Number(maxPrice)) && (!maxMileage || (vehicle.mileage_km ?? Infinity) <= Number(maxMileage)) && (!photosOnly || Boolean(vehicle.image_urls?.length)) && (!savedOnly || saved.has(vehicle.id));
    });
    return filtered.sort((a, b) => {
      if (sort === "price-asc") return Number(a.price_cad ?? Infinity) - Number(b.price_cad ?? Infinity);
      if (sort === "price-desc") return Number(b.price_cad ?? -1) - Number(a.price_cad ?? -1);
      if (sort === "mileage") return (a.mileage_km ?? Infinity) - (b.mileage_km ?? Infinity);
      if (sort === "newest") return (b.year ?? 0) - (a.year ?? 0);
      return Number(Boolean(b.image_urls?.length)) - Number(Boolean(a.image_urls?.length));
    });
  }, [vehicles, query, make, dealer, municipality, body, transmission, drivetrain, fuelType, exteriorColour, minYear, maxYear, minPrice, maxPrice, maxMileage, photosOnly, savedOnly, saved, sort]);

  const activeFilters = [make, dealer, municipality, body, transmission, drivetrain, fuelType, exteriorColour, minYear, maxYear, minPrice, maxPrice, maxMileage, photosOnly ? "photos" : "", savedOnly ? "saved" : ""].filter(Boolean).length;
  const resetFilters = () => { setQuery(""); setMake(""); setDealer(""); setMunicipality(""); setBody(""); setTransmission(""); setDrivetrain(""); setFuelType(""); setExteriorColour(""); setMinYear(""); setMaxYear(""); setMinPrice(""); setMaxPrice(""); setMaxMileage(""); setPhotosOnly(false); setSavedOnly(false); setPage(1); };
  const update = (setter: (value: string) => void) => (event: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => { setter(event.target.value); setPage(1); };
  async function save(vehicle: Vehicle) {
    const next = !saved.has(vehicle.id);
    await toggleSaved(vehicle.id, next);
    setSaved((current) => { const updated = new Set(current); next ? updated.add(vehicle.id) : updated.delete(vehicle.id); return updated; });
  }

  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="./" aria-label="Ontario Auto Index home"><span className="brand-mark">OA</span><span>Ontario Auto Index<small>Verified dealer inventory</small></span></a><button className={`saved-nav ${savedOnly ? "active" : ""}`} onClick={() => { setSavedOnly((value) => !value); setPage(1); }} aria-pressed={savedOnly}>♡ <span>Saved</span><b>{saved.size}</b></button></header>
    <section className="hero"><div><p className="eyebrow">Shop local. Compare clearly.</p><h1>Find your next car<br /><em>across Ontario.</em></h1><p className="hero-copy">One clean search across independent dealership inventory, with every result linked directly to its source.</p></div><div className="search-panel"><label className="search-box"><span>⌕</span><input aria-label="Search inventory" value={query} onChange={update(setQuery)} placeholder="Search make, model, trim or dealer" /></label><div className="quick-filters"><label><span>Make</span><select value={make} onChange={update(setMake)}><option value="">All makes</option>{makes.map((value) => <option key={value}>{value}</option>)}</select></label><label><span>Maximum price</span><select value={maxPrice} onChange={update(setMaxPrice)}><option value="">Any price</option><option value="10000">Under $10,000</option><option value="15000">Under $15,000</option><option value="20000">Under $20,000</option><option value="30000">Under $30,000</option><option value="50000">Under $50,000</option></select></label></div></div></section>
    <main className="marketplace"><aside className="filters"><div className="filter-heading"><h2>Filters</h2>{activeFilters > 0 && <button onClick={resetFilters}>Clear all</button>}</div><label>City or region<select value={municipality} onChange={update(setMunicipality)}><option value="">All Ontario</option>{municipalities.map((value) => <option key={value}>{value}</option>)}</select></label><label>Dealership<select value={dealer} onChange={update(setDealer)}><option value="">All dealerships</option>{dealers.map((value) => <option key={value}>{value}</option>)}</select></label>{bodies.length > 0 && <label>Body style<select value={body} onChange={update(setBody)}><option value="">All body styles</option>{bodies.map((value) => <option key={value}>{value}</option>)}</select></label>}{transmissions.length > 0 && <label>Transmission<select value={transmission} onChange={update(setTransmission)}><option value="">Any transmission</option>{transmissions.map((value) => <option key={value}>{value}</option>)}</select></label>}{drivetrains.length > 0 && <label>Drivetrain<select value={drivetrain} onChange={update(setDrivetrain)}><option value="">Any drivetrain</option>{drivetrains.map((value) => <option key={value}>{value}</option>)}</select></label>}{fuelTypes.length > 0 && <label>Fuel type<select value={fuelType} onChange={update(setFuelType)}><option value="">Any fuel type</option>{fuelTypes.map((value) => <option key={value}>{value}</option>)}</select></label>}{exteriorColours.length > 0 && <label>Exterior colour<select value={exteriorColour} onChange={update(setExteriorColour)}><option value="">Any colour</option>{exteriorColours.map((value) => <option key={value}>{value}</option>)}</select></label>}<label>Minimum year<select value={minYear} onChange={update(setMinYear)}><option value="">Any year</option>{[2026, 2025, 2023, 2020, 2018, 2015, 2010].map((year) => <option key={year}>{year}</option>)}</select></label><label>Maximum year<select value={maxYear} onChange={update(setMaxYear)}><option value="">Any year</option>{[2026, 2025, 2023, 2020, 2018, 2015, 2010].map((year) => <option key={year}>{year}</option>)}</select></label><label>Minimum price<select value={minPrice} onChange={update(setMinPrice)}><option value="">Any price</option><option value="10000">$10,000+</option><option value="20000">$20,000+</option><option value="30000">$30,000+</option><option value="50000">$50,000+</option></select></label><label>Maximum mileage<select value={maxMileage} onChange={update(setMaxMileage)}><option value="">Any mileage</option><option value="50000">50,000 km</option><option value="100000">100,000 km</option><option value="150000">150,000 km</option><option value="200000">200,000 km</option></select></label><label className="check"><input type="checkbox" checked={photosOnly} onChange={(event) => { setPhotosOnly(event.target.checked); setPage(1); }} /> Photos available</label><label className="check"><input type="checkbox" checked={savedOnly} onChange={(event) => { setSavedOnly(event.target.checked); setPage(1); }} /> Saved vehicles only</label><div className="source-note"><span>✓</span><p><strong>Source verified</strong>Listings come from dealership-published inventory. Details may change—confirm on the original listing.</p></div></aside>
      <section className="results"><div className="results-bar"><div><p className="eyebrow">Ontario inventory</p><h2>{loading ? "Loading vehicles…" : `${integer.format(results.length)} vehicle${results.length === 1 ? "" : "s"}`}</h2>{generatedAt && <small>Inventory updated {new Date(generatedAt).toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" })}</small>}</div><label className="sort">Sort by <select value={sort} onChange={(event) => { setSort(event.target.value as Sort); setPage(1); }}><option value="recommended">Recommended</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="mileage">Lowest mileage</option><option value="newest">Newest year</option></select></label></div>
        {error && <div className="notice" role="alert"><strong>Inventory unavailable</strong><p>{error} Please try again later.</p></div>}{!loading && !error && results.length === 0 && <div className="empty"><span>⌕</span><h3>No vehicles match those filters</h3><p>Try widening your price, mileage, or year range.</p><button onClick={resetFilters}>Reset filters</button></div>}
        <div className="vehicle-grid" aria-live="polite">{results.slice(0, page * PAGE_SIZE).map((vehicle) => <article className="vehicle-card" key={vehicle.id}><div className="media"><VehicleImage vehicle={vehicle} /><button className={`heart ${saved.has(vehicle.id) ? "saved" : ""}`} onClick={() => void save(vehicle)} aria-label={`${saved.has(vehicle.id) ? "Remove" : "Save"} ${title(vehicle)}`}>{saved.has(vehicle.id) ? "♥" : "♡"}</button>{vehicle.body_style && <span className="body-tag">{vehicle.body_style}</span>}</div><div className="card-content"><p className="vehicle-year">{vehicle.year ?? "Year unavailable"}</p><h3>{[vehicle.make, vehicle.model].filter(Boolean).join(" ") || "Model unavailable"}</h3>{vehicle.trim && <p className="trim">{vehicle.trim}</p>}<p className="price">{vehicle.price_cad ? money.format(Number(vehicle.price_cad)) : "Contact for price"}</p><div className="specs"><span><b>↗</b>{vehicle.mileage_km != null ? `${integer.format(vehicle.mileage_km)} km` : "Mileage n/a"}</span>{vehicle.drivetrain && <span><b>⚙</b>{vehicle.drivetrain}</span>}{vehicle.transmission && <span><b>◇</b>{vehicle.transmission}</span>}</div><div className="dealer"><div><strong>{vehicle.dealer_name}</strong><span>{vehicle.municipality || "Ontario"}</span></div><span className="verified" title="Dealer-published source">✓</span></div><a className="listing-link" href={vehicle.listing_url} target="_blank" rel="noopener noreferrer">View original listing <span>↗</span></a></div></article>)}</div>{page * PAGE_SIZE < results.length && <button className="load-more" onClick={() => setPage((value) => value + 1)}>Show more vehicles</button>}</section>
    </main><footer><div className="brand"><span className="brand-mark">OA</span><span>Ontario Auto Index</span></div><p>Independent vehicle search built from public dealership inventory.</p><p>Prices and availability are subject to change. Always confirm details with the dealer.</p></footer>
  </div>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
