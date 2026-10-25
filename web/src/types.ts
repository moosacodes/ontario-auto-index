export type Vehicle = {
  id: string;
  source_dealer_id: string;
  dealer_name: string;
  listing_url: string;
  observed_at: string;
  last_verified_at: string;
  original: Record<string, string | null>;
  year: number | null;
  make: string | null;
  model: string | null;
  trim: string | null;
  mileage_km: number | null;
  price_cad: string | null;
  price_conditions: { text: string | null };
  validation_status: "valid" | "invalid" | "needs_review";
};

export type Manifest = {
  schema_version: number;
  generated_at: string;
  partitions: Array<{ file: string; compressed_file?: string; dealer_id: string; vehicle_count: number }>;
};
