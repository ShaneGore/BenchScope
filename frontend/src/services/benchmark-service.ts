import type {
  AppMode,
  BenchmarkRun,
  ImportResult,
  ModelProfile,
  Paginated,
  RunFilters,
} from '@/types';
import { getStore } from '@/mock/store';
import {
  ApiBenchmarkService,
} from './api-benchmark-service';
import { DemoBenchmarkService } from './demo-benchmark-service';

export interface BenchmarkService {
  listProfiles(): Promise<ModelProfile[]>;
  getProfile(id: string): Promise<ModelProfile>;
  createProfile(
    input: Omit<ModelProfile, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
  ): Promise<ModelProfile>;
  updateProfile(id: string, patch: Partial<ModelProfile>): Promise<ModelProfile>;
  deleteProfile(id: string): Promise<void>;
  importRun(payload: unknown): Promise<ImportResult>;
  listRuns(filters?: RunFilters): Promise<Paginated<BenchmarkRun>>;
  getRun(id: string): Promise<BenchmarkRun>;
  deleteRun(id: string): Promise<void>;
  compareRuns(ids: string[]): Promise<BenchmarkRun[]>;
}

export function createBenchmarkService(
  mode: AppMode,
  apiUrl: string | undefined,
  fetcher?: typeof fetch
): BenchmarkService {
  if (mode === 'local') return new ApiBenchmarkService(apiUrl ?? '', fetcher ?? fetch);
  if (mode === 'demo') return new DemoBenchmarkService(apiUrl ?? '', fetcher);
  if (mode === 'hosted') return new ApiBenchmarkService(apiUrl ?? '', fetcher ?? fetch, true);
  return getStore(mode);
}

let localService: BenchmarkService | null = null;
let hostedService: BenchmarkService | null = null;
let demoService: BenchmarkService | null = null;

export function getBenchmarkService(mode: AppMode): BenchmarkService {
  if (mode === 'local') {
    if (!localService) {
      localService = createBenchmarkService(mode, import.meta.env.VITE_API_URL);
    }
    return localService;
  }
  if (mode === 'demo') {
    if (!demoService) {
      demoService = createBenchmarkService(mode, import.meta.env.VITE_API_URL);
    }
    return demoService;
  }
  if (!hostedService) {
    hostedService = createBenchmarkService(mode, import.meta.env.VITE_API_URL);
  }
  return hostedService;
}
