/*
 * Historical telemetry provider — backs OpenMCT's time-conductor playback by
 * querying the TimescaleDB archive through GET /api/history/{key}.
 *
 * Without this, OpenMCT logs "Missing request provider" and a plot can only
 * show points that arrived live since it was opened; with it, scrubbing to any
 * past window replays the recorded mission.
 */

export default function HistoricalPlugin() {
  return function install(openmct) {
    openmct.telemetry.addProvider({
      supportsRequest(domainObject) {
        return domainObject.identifier.namespace === 'sat';
      },

      async request(domainObject, options = {}) {
        // The conductor hands us ms-epoch bounds, which is exactly what the
        // API expects — the whole pipeline is ms-epoch end to end.
        const start = Math.round(options.start);
        const end = Math.round(options.end);
        const key = encodeURIComponent(domainObject.identifier.key);
        const url = `/api/history/${key}?start=${start}&end=${end}`;

        const response = await fetch(url, { signal: options.signal });
        if (!response.ok) {
          throw new Error(`history request failed: ${response.status}`);
        }
        return response.json();
      }
    });
  };
}
