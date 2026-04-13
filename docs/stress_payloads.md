# Stress Payloads

Stress endpoints use a compact `stress` block. The API converts this block into a `StressRequest` and injects the generated scenarios into the request QML under `shiftScenariosWithMultAdd`.

Endpoints:

```text
POST /stress/full-qml
POST /stress/ot
```

## Payload Shape

```json
{
  "dir": "working_dir",
  "ps_request": {},
  "stress": {
    "stress_name": "stress_berm_mult_add",
    "deformations": {
      "rates": {
        "name": "RateLevel",
        "mult": {
          "type": "iter",
          "start": -5,
          "delta": 0.1,
          "nbr_points": 101
        },
        "add": {
          "type": "scalar",
          "value": 0
        }
      },
      "vol": {
        "name": "SigmaShock",
        "mult": {
          "type": "vector",
          "values": [-10, 0, 10]
        },
        "add": {
          "type": "scalar",
          "value": 0
        }
      }
    }
  }
}
```

`stress_name` becomes the XML `<refKey>` value for every generated scenario.

Each item under `deformations` is one affine deformation. The object key, such as `rates` or `vol`, is only a payload label. The real QML deformation name is `name`, for example `RateLevel` or `SigmaShock`.

## Factor Types

Each deformation has two factors:

```json
{
  "mult": {},
  "add": {}
}
```

Both `mult` and `add` support the same three value modes.

### scalar

Use `scalar` for one fixed value.

```json
{
  "type": "scalar",
  "value": 0
}
```

Generated values:

```text
[0]
```

Typical usage:

```json
"add": {
  "type": "scalar",
  "value": 0
}
```

### vector

Use `vector` for an explicit list of values.

```json
{
  "type": "vector",
  "values": [-10, 0, 10]
}
```

Generated values:

```text
[-10, 0, 10]
```

Typical usage:

```json
"mult": {
  "type": "vector",
  "values": [-10, 0, 10]
}
```

### iter

Use `iter` for regularly spaced values.

```json
{
  "type": "iter",
  "start": -5,
  "delta": 0.1,
  "nbr_points": 101
}
```

Generated values:

```text
[-5.0, -4.9, -4.8, ..., 4.9, 5.0]
```

Formula:

```text
value_i = start + i * delta
```

for:

```text
i = 0 ... nbr_points - 1
```

## Scenario Count

The API generates the cartesian product of all deformation factor values.

Example:

```text
RateLevel mult: 101 values
RateLevel add: 1 value
SigmaShock mult: 3 values
SigmaShock add: 1 value
```

Total scenarios:

```text
101 * 1 * 3 * 1 = 303
```

The generated request QML contains:

```xml
<shiftScenariosWithMultAdd>
  <count>303</count>
  ...
</shiftScenariosWithMultAdd>
```

## Generated XML Item

Each generated scenario becomes one XML item:

```xml
<item version="1">
  <refKey>stress_berm_mult_add</refKey>
  <affineDeformations>
    <count>2</count>
    <item>
      <key>RateLevel</key>
      <val>
        <add>0.0</add>
        <mult>-5.0</mult>
      </val>
    </item>
    <item>
      <key>SigmaShock</key>
      <val>
        <add>0.0</add>
        <mult>-10.0</mult>
      </val>
    </item>
  </affineDeformations>
</item>
```

## Notes

Use `scalar` when a factor should remain fixed.

Use `vector` when values are explicitly selected.

Use `iter` when values are evenly spaced.

Keep scenario grids reasonable. Large cartesian products create large request XML and can produce heavy pricing jobs.
