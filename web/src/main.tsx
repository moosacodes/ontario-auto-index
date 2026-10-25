import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { getSaved, toggleSaved } from "./storage";
import type { Manifest, Vehicle } from "./types";
import "./styles.css";

const PAGE_SIZE = 50;

async function loadVehicles(): Promise<Vehicle[]> {
  const response = await fetch("/data/manifest.json", { cache: "force-cache" });
  if (!response.ok) throw new Error("The inventory manifest is unavailable.");
  const manifest = (await response.json()) as Manifest;
  const parts = await Promise.all(
    manifest.partitions.map(async (partition) => {
      const result = await fetch(`/data/${partition.file}`, { cache: "force-cache" });
      if (!result.ok) throw new Error(`Inventory partition failed: ${partition.file}`);
      return (await result.json()) as Vehicle[];
    }),
  );
  return parts.flat().filter((vehicle) => vehicle.validation_status === "valid");
}

function App() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string>();

  useEffect(() => {
    Promise.all([loadVehicles(), getSaved()])
      .then(([loaded, stored]) => {
        setVehicles(loaded);
        setSaved(stored);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Load failed."));
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return vehicles;
    return vehicles.filter((vehicle) =>
      [vehicle.make, vehicle.model, vehicle.trim, vehicle.dealer_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [query, vehicles]);
  const visible = filtered.slice(0, page * PAGE_SIZE);

  async function save(vehicle: Vehicle) {
    const next = !saved.has(vehicle.id);
    await toggleSaved(vehicle.id, next);
    setSaved((current) => {
      const updated = new Set(current);
      if (next) updated.add(vehicle.id);
      else updated.delete(vehicle.id);
      return updated;
    });
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Ontario Auto Index</p>
        <h1>Evidence-backed dealership inventory</h1>
        <p className="lede">Search published listings without downloading the whole province at startup.</p>
        <input
          aria-label="Search inventory"
          value={query}
          onChange={(event) => { setQuery(event.target.value); setPage(1); }}
          placeholder="Search make, model, trim or dealer"
        />
      </header>
      {error ? <section className="notice">{error} No inventory is shown until a valid snapshot is published.</section> : null}
      <section className="summary">{filtered.length} verified listing{filtered.length === 1 ? "" : "s"}</section>
      <section className="grid" aria-live="polite">
        {visible.map((vehicle) => (
          <article className="card" key={vehicle.id}>
            <div className="card-top"><span>{vehicle.year ?? "Year unavailable"} {vehicle.make ?? ""}</span>
              <button onClick={() => void save(vehicle)} aria-label={`${saved.has(vehicle.id) ? "Remove" : "Save"} ${vehicle.model ?? "vehicle"}`}>
                {saved.has(vehicle.id) ? "Saved" : "Save"}
              </button>
            </div>
            <h2>{vehicle.model ?? "Model unavailable"}{vehicle.trim ? ` ${vehicle.trim}` : ""}</h2>
            <p>{vehicle.mileage_km?.toLocaleString() ?? "Mileage unavailable"} km · {vehicle.price_cad ? `$${vehicle.price_cad}` : "Price unavailable"}</p>
            <p className="dealer">{vehicle.dealer_name}</p>
            <a href={vehicle.listing_url} target="_blank" rel="noreferrer">View original listing</a>
          </article>
        ))}
      </section>
      {visible.length < filtered.length ? <button className="load" onClick={() => setPage((current) => current + 1)}>Load more</button> : null}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
