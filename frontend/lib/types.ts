export interface TopRegion {
  nuts_id: string;
  nuts_name: string;
  total_lending_eur: number;
}

export interface SectorTotal {
  sector: string;
  total_eur: number;
}

export interface YearTotal {
  year: number;
  total_eur: number;
  climate_eur: number;
}

export interface Summary {
  mode: "sample" | "real";
  generated_at: string;
  total_lending_eur: number;
  total_projects: number;
  climate_relevant_projects: number;
  countries_covered: number;
  year_range: [number, number];
  top_regions: TopRegion[];
  sector_breakdown: SectorTotal[];
  lending_over_time: YearTotal[];
  limitations: string[];
}

export interface RegionProperties {
  NUTS_ID: string;
  NUTS_NAME: string;
  CNTR_CODE: string;
  total_lending_eur: number;
  project_count: number;
  avg_lending_eur: number | null;
  climate_share: number | null;
  top_sectors: SectorTotal[];
}
