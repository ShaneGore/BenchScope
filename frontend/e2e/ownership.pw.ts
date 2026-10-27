import { expect, test } from '@playwright/test';
import { apiRequest, installLocalAuth, runPayload, setLocalSubject } from './support';

interface CreatedProfile {
  id: string;
  owner_id: string;
}

interface ImportedRun {
  ok: boolean;
  run: { id: string; owner_id: string };
}

test('verified subjects isolate records despite forged fields and identifiers', async ({
  page,
}) => {
  await installLocalAuth(page);
  await page.goto('/');

  const aliceProfile = await apiRequest<CreatedProfile>(page, '/profiles', {
    method: 'POST',
    body: { name: 'Owner A profile', model_name: 'synthetic/owner-a' },
  });
  expect(aliceProfile.status).toBe(201);
  expect(aliceProfile.body.owner_id).toBe('e2e-owner-a');

  const forgedProfile = await apiRequest(page, '/profiles', {
    method: 'POST',
    body: {
      name: 'Forged owner profile',
      model_name: 'synthetic/forged',
      owner_id: 'e2e-owner-b',
    },
  });
  expect(forgedProfile.status).toBe(422);

  const aliceImport = await apiRequest<ImportedRun>(page, '/runs/import', {
    method: 'POST',
    body: runPayload(`ownership-${Date.now()}-alice`, new Date().toISOString()),
  });
  expect(aliceImport.status).toBe(201);
  expect(aliceImport.body.run.owner_id).toBe('e2e-owner-a');

  await setLocalSubject(page, 'e2e-owner-b');
  const bobImport = await apiRequest<ImportedRun>(page, '/runs/import', {
    method: 'POST',
    body: runPayload(`ownership-${Date.now()}-bob`, new Date().toISOString()),
  });
  expect(bobImport.status).toBe(201);
  expect(bobImport.body.run.owner_id).toBe('e2e-owner-b');

  const bobForgedImport = await apiRequest(page, '/runs/import', {
    method: 'POST',
    body: {
      ...runPayload(`ownership-${Date.now()}-forged`, new Date().toISOString()),
      owner_id: 'e2e-owner-a',
    },
  });
  expect(bobForgedImport.status).toBe(422);

  const bobRuns = await apiRequest<{
    items: { id: string; owner_id: string }[];
  }>(page, '/runs?owner_id=e2e-owner-a');
  expect(bobRuns.status).toBe(200);
  expect(bobRuns.body.items.map((run) => run.owner_id)).toEqual(['e2e-owner-b']);

  for (const [path, method] of [
    [`/runs/${aliceImport.body.run.id}`, 'GET'],
    [`/runs/${aliceImport.body.run.id}`, 'DELETE'],
    [`/runs/compare?ids=${bobImport.body.run.id},${aliceImport.body.run.id}`, 'GET'],
    [`/profiles/${aliceProfile.body.id}`, 'GET'],
    [`/profiles/${aliceProfile.body.id}`, 'PATCH'],
    [`/profiles/${aliceProfile.body.id}`, 'DELETE'],
  ] as const) {
    const response = await apiRequest(page, path, {
      method,
      ...(method === 'PATCH' ? { body: { name: 'Stolen profile' } } : {}),
    });
    expect(response.status).toBe(404);
    expect(JSON.stringify(response.body)).not.toContain('Owner A');
  }

  await setLocalSubject(page, 'e2e-owner-a');
  expect(
    (await apiRequest(page, `/runs/${aliceImport.body.run.id}`)).status
  ).toBe(200);
  expect(
    (await apiRequest(page, `/profiles/${aliceProfile.body.id}`)).status
  ).toBe(200);
});
