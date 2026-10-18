# Schemaflow

**A VS Code extension that generates TypeScript interfaces from JSON Schema files on save, with live preview.**

You know the drill: the API team ships a new `schema.json`, and now you're hand-editing
`types.ts` to match — renaming a field here, widening a union there, praying you caught
every nested object. Every schema change becomes a small, error-prone transcription job,
and the drift between the two files is only discovered when something breaks in
production. Schemaflow turns that manual sync into a one-save action: the interfaces are
generated from the schema, so they can't drift.

## Example

<!-- A real command and its REAL pasted output. Run it first. -->

## Install

```bash
pip install -e ".[dev]"
```

## Usage

<!-- The 2-4 commands people actually need, one line each. -->

## How it works

<!-- 3-6 bullets: what it checks, computes or produces. -->

## Limitations

- **No `$ref` resolution.** Schemas that reference other definitions (local or remote) are not followed; a `$ref` is emitted as `unknown`.
- **Advanced keywords are ignored.** `additionalProperties`, `patternProperties`, `unevaluatedProperties`, and conditional subschemas (`if`/`then`/`else`) are not mapped to TypeScript types.
- **No `allOf`/`anyOf`/`oneOf` composition.** Composed schemas are not inlined or intersected; only the `type` keyword is honored.
- **No `enum` or `const` support.** These are not converted to literal union types.
- **No `format` handling.** `format` annotations (e.g. `date-time`, `email`) are not mapped to branded or library types.
- **No validation.** Schemaflow generates types; it does not validate data against the schema.
- **Single-file input.** The CLI takes one schema file at a time; there is no project-wide or directory-based generation.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

## License

MIT -- see [LICENSE](LICENSE).
