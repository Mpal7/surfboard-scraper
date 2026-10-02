import { getJob, triggerRefresh } from './api';

describe('refresh jobs api', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    sessionStorage.clear();
  });

  it('triggers a refresh and returns job metadata', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({
        message: 'Refresh scheduled.',
        job_id: 'job-1',
        status: 'queued',
        worker: 'thread',
        task_id: null,
        status_url: '/jobs/job-1',
      }),
    } as unknown as Response);

    const result = await triggerRefresh();

    expect(result.job_id).toBe('job-1');
    expect(result.status_url).toBe('/jobs/job-1');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/refresh'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('surfaces the cooldown error detail', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Refresh allowed only every 1 minutes.' }),
    } as unknown as Response);

    await expect(triggerRefresh()).rejects.toThrow('Refresh allowed only every 1 minutes.');
  });

  it('fetches a job by id', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 'job-1', status: 'completed', result: { new_ads_added: 2 } }),
    } as unknown as Response);

    const job = await getJob('job-1');

    expect(job.status).toBe('completed');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/job-1'),
      expect.anything()
    );
  });
});
