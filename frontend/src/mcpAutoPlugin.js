import { randomUUID } from 'node:crypto';

export function createMcpState(now = Date.now) {
  let state = { seq: '', heading: 270, altitude: 3000, client: '', ackAt: 0 };
  return {
    get: () => ({ ...state, ready: !!state.ackAt && now() - state.ackAt < 1200 }),
    set(data) {
      if (!Number.isInteger(data.heading) || data.heading < 0 || data.heading > 359 ||
          !Number.isInteger(data.altitude) || data.altitude < 0 || data.altitude > 99900 ||
          !/^[a-zA-Z0-9_-]{1,64}$/.test(data.client || '')) throw Error('Invalid values or display ID');
      state = { seq: randomUUID(), heading: data.heading, altitude: data.altitude, client: data.client, ackAt: 0 };
      return this.get();
    },
    ack(data) {
      if (!state.seq || data.seq !== state.seq || data.client !== state.client ||
          data.heading !== state.heading || data.altitude !== state.altitude) throw Error('Stale or wrong display ACK');
      state.ackAt = now();
      return this.get();
    },
  };
}
export function mcpAutoPlugin() {
  const state = createMcpState();
  return { name: 'radar-mcp-auto-local', configureServer(server) {
    server.middlewares.use('/api/mcp-auto', async (req, res, next) => {
      const path = (req.url || '').split('?')[0];
      if (!['/state', '/set', '/ack'].includes(path)) return next();
      res.setHeader('Content-Type', 'application/json'); res.setHeader('Cache-Control', 'no-store');
      try {
        let result;
        if (req.method === 'GET' && path === '/state') result = state.get();
        else if (req.method === 'POST' && ['/set', '/ack'].includes(path)) {
          let raw = ''; for await (const chunk of req) { raw += chunk; if (raw.length > 2048) throw Error('Request too large'); }
          result = state[path === '/set' ? 'set' : 'ack'](JSON.parse(raw));
        } else { res.statusCode = 405; return res.end('{}'); }
        res.end(JSON.stringify(result));
      } catch (error) { res.statusCode = 400; res.end(JSON.stringify({ error: String(error) })); }
    });
  } };
}
