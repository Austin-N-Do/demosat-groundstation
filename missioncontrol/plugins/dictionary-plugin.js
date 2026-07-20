/*
 * Builds the DemoSat-1 object tree (spacecraft -> subsystem folders ->
 * parameter leaves) from GET /api/dictionary. Composition and telemetry
 * metadata ride the framework's own defaults: any object with a
 * `composition` array is handled by OpenMCT's DefaultCompositionProvider,
 * and any object with a `telemetry.values` property is handled by its
 * DefaultMetadataProvider — so this plugin only needs one ObjectProvider,
 * no separate composition/metadata providers.
 */

const NAMESPACE = 'sat';
const ROOT_KEY = 'spacecraft';

function keyString(identifier) {
  return `${identifier.namespace}:${identifier.key}`;
}

function valueMetadataFor(param) {
  if (param.enum) {
    return {
      key: 'value',
      name: param.name,
      format: 'enum',
      enumerations: Object.entries(param.enum).map(([value, string]) => ({
        value: Number(value),
        string
      })),
      hints: { range: 1 }
    };
  }
  return {
    key: 'value',
    name: param.name,
    unit: param.units || undefined,
    format: 'number',
    hints: { range: 1 }
  };
}

function buildObjectMap(dictionary) {
  const objects = new Map();
  const rootId = { namespace: NAMESPACE, key: ROOT_KEY };

  objects.set(keyString(rootId), {
    identifier: rootId,
    name: dictionary.spacecraft_name,
    type: 'folder',
    location: 'ROOT',
    composition: dictionary.packets.map((p) => ({ namespace: NAMESPACE, key: p.name }))
  });

  for (const packet of dictionary.packets) {
    const folderId = { namespace: NAMESPACE, key: packet.name };
    objects.set(keyString(folderId), {
      identifier: folderId,
      name: packet.name.toUpperCase(),
      type: 'folder',
      location: keyString(rootId),
      composition: packet.parameters.map((param) => ({ namespace: NAMESPACE, key: param.key }))
    });

    for (const param of packet.parameters) {
      const paramId = { namespace: NAMESPACE, key: param.key };
      objects.set(keyString(paramId), {
        identifier: paramId,
        name: param.name,
        type: 'sat.parameter',
        location: keyString(folderId),
        telemetry: {
          values: [
            { key: 'utc', source: 'timestamp', name: 'Timestamp', format: 'utc', hints: { domain: 1 } },
            valueMetadataFor(param)
          ],
          // Not part of the OpenMCT contract — read by our own limits-plugin.js
          // so it doesn't need a second fetch of the dictionary.
          limits: param.limits || null
        }
      });
    }
  }

  return objects;
}

export default function DictionaryPlugin() {
  return function install(openmct) {
    const rootIdentifier = { namespace: NAMESPACE, key: ROOT_KEY };
    const objectsReady = fetch('/api/dictionary')
      .then((res) => res.json())
      .then(buildObjectMap);

    openmct.objects.addRoot(rootIdentifier, openmct.priority.HIGH);

    openmct.types.addType('sat.parameter', {
      name: 'Telemetry Parameter',
      description: 'A single DemoSat-1 telemetry parameter',
      cssClass: 'icon-telemetry'
    });

    openmct.objects.addProvider(NAMESPACE, {
      get(identifier) {
        return objectsReady.then((objects) => objects.get(keyString(identifier)));
      }
    });
  };
}
