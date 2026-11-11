export function mcpAutoPlugin() {
  let state = { seq: 0, heading: 270, altitude: 3000, ack: 0 };
  const respond = (res, code, value) => {
    res.statusCode = code;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.end(JSON.stringify(value));
  };
  const readJson = async req => {
    let raw = '';
    for await (const chunk of req) {
      raw += chunk;
      if (raw.length > 2048) throw new Error('Request too large');
    }
    return JSON.parse(raw);
  };
  return {
    name: 'radar-mcp-auto-local',
    configureServer(server) {
      server.middlewares.use('/api/mcp-auto', async (req, res, next) => {
        const path = (req.url || '').split('?')[0];
        if (req.method === 'GET' && path === '/state') return respond(res, 200, state);
        if (req.method === 'POST' && path === '/set') {
          try {
            const data = await readJson(req);
            const h = data.heading, a = data.altitude;
            if (!Number.isInteger(h) || h < 0 || h > 359 || !Number.isInteger(a) || a < 0 || a > 99900)
              return respond(res, 400, { error: 'Invalid heading/altitude' });
            state = { ...state, seq: state.seq + 1, heading: h, altitude: a };
            return respond(res, 200, state);
          } catch (error) { return respond(res, 400, { error: String(error) }); }
        }
        if (req.method === 'POST' && path === '/ack') {
          try {
            const data = await readJson(req);
            if (data.seq === state.seq) state.ack = data.seq;
            return respond(res, 200, state);
          } catch (error) { return respond(res, 400, { error: String(error) }); }
        }
        next();
      });
    },
  };
}
