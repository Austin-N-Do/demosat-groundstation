/*
 * Limits provider — yellow/red alarm styling and plot limit bands.
 *
 * Two halves:
 *   evaluate()  colors an individual sample. It trusts the `alarm` field the
 *               ingest service already computed against the same telemetry
 *               dictionary, so the ground system has ONE limit-checking
 *               implementation rather than a second one drifting in the UI.
 *               The threshold values are consulted only to decide whether the
 *               breach was upper or lower, which OpenMCT styles differently.
 *   getLimits() returns the static bands so plots can draw limit lines.
 *
 * Limits ride on the domain object as `telemetry.limits`, embedded by
 * dictionary-plugin.js — no second fetch of the dictionary.
 */

const COLOR_BY_ALARM = { YELLOW: 'yellow', RED: 'red' };

function limitsFor(domainObject) {
  return (domainObject.telemetry && domainObject.telemetry.limits) || null;
}

export default function LimitsPlugin() {
  return function install(openmct) {
    openmct.telemetry.addProvider({
      supportsLimits(domainObject) {
        return domainObject.identifier.namespace === 'sat' && limitsFor(domainObject) !== null;
      },

      getLimitEvaluator(domainObject) {
        const limits = limitsFor(domainObject);

        return {
          evaluate(datum) {
            const color = COLOR_BY_ALARM[datum && datum.alarm];
            if (!color) {
              return undefined;   // NOMINAL — no styling
            }

            // Upper vs lower breach, for the correct arrow/label styling.
            const value = datum.value;
            const high = datum.alarm === 'RED' ? limits.red_high : limits.yellow_high;
            const isUpper = high !== undefined && high !== null && value >= high;

            return {
              cssClass: `is-limit--${color} is-limit--${isUpper ? 'upr' : 'lwr'}`,
              name: datum.alarm
            };
          }
        };
      },

      getLimits(domainObject) {
        const limits = limitsFor(domainObject);

        // Only emit a band for thresholds this parameter actually defines —
        // several are one-sided (e.g. wheel speed has highs but no lows).
        const bands = {};
        const add = (level, color, low, high) => {
          const band = {};
          if (low !== undefined && low !== null) {
            band.low = { color, value: low };
          }
          if (high !== undefined && high !== null) {
            band.high = { color, value: high };
          }
          if (band.low || band.high) {
            bands[level] = band;
          }
        };

        if (limits) {
          add('YELLOW', 'yellow', limits.yellow_low, limits.yellow_high);
          add('RED', 'red', limits.red_low, limits.red_high);
        }

        return { limits: () => Promise.resolve(bands) };
      }
    });
  };
}
