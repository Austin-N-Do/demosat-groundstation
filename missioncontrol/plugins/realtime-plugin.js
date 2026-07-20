/*
 * Realtime telemetry provider — one shared WebSocket to /ws/realtime,
 * routes incoming datums to whichever OpenMCT views subscribed to that
 * parameter key. Only implements supportsSubscribe/subscribe, so the
 * framework never asks it for historical data (that's historical-plugin.js).
 */

export default function RealtimePlugin() {
  return function install(openmct) {
    const callbacksByKey = new Map();   // parameter key -> Set<callback>
    let socket = null;
    let reconnectTimer = null;

    function send(msg) {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(msg));
      }
    }

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${proto}//${location.host}/ws/realtime`);

      socket.onopen = () => {
        for (const key of callbacksByKey.keys()) {
          send({ type: 'subscribe', key });
        }
      };

      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type !== 'telemetry') return;
        const callbacks = callbacksByKey.get(msg.key);
        if (!callbacks) return;
        const datum = { timestamp: msg.timestamp, value: msg.value, alarm: msg.alarm };
        for (const cb of callbacks) cb(datum);
      };

      socket.onclose = () => {
        reconnectTimer = setTimeout(connect, 2000);
      };
    }

    connect();

    openmct.telemetry.addProvider({
      supportsSubscribe(domainObject) {
        return domainObject.identifier.namespace === 'sat';
      },
      subscribe(domainObject, callback) {
        const key = domainObject.identifier.key;
        if (!callbacksByKey.has(key)) {
          callbacksByKey.set(key, new Set());
          send({ type: 'subscribe', key });
        }
        callbacksByKey.get(key).add(callback);

        return function unsubscribe() {
          const callbacks = callbacksByKey.get(key);
          if (!callbacks) return;
          callbacks.delete(callback);
          if (callbacks.size === 0) {
            callbacksByKey.delete(key);
            send({ type: 'unsubscribe', key });
          }
        };
      }
    });

    openmct.on('destroy', () => {
      clearTimeout(reconnectTimer);
      if (socket) socket.close();
    });
  };
}
