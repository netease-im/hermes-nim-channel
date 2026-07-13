## Context

The reference OpenClaw channel maps private deployment fields from its advanced config into the NIM Bot SDK constructor. NOS-related fields are passed under `privateConf`; LBS and link fields must also be passed through `V2NIMLoginServiceConfig` so login routing uses the configured private endpoints.

## Goals / Non-Goals

**Goals:**
- Add endpoint configuration compatible with the reference implementation
- Preserve existing public-cloud behavior when no private endpoints are configured
- Keep SDK-specific option shaping in the Node bridge

**Non-Goals:**
- Reconnect strategy changes
- Runtime endpoint reload without reconnect
- Multi-instance config redesign

## Decisions

### 1. Keep Python config as a flat plugin surface

Decision: expose endpoint fields as `private_*` / existing SDK names in `PlatformConfig.extra` and `NIM_*` env vars, then normalize them into an `advanced` bridge payload.

Rationale:
- The current Hermes plugin config is flat, not OpenClaw's nested `advanced` object.
- The bridge can still receive a reference-compatible `advanced` object.
- Operators get explicit env var names without needing nested config support.

### 2. Build SDK options in the bridge

Decision: construct `privateConf` and `V2NIMLoginServiceConfig` in Node.

Rationale:
- The bridge owns the SDK constructor call.
- The SDK option shape is JavaScript-specific.
- Tests can validate option generation without starting the real SDK.

## Risks / Trade-offs

- Invalid endpoint values still come from operator configuration -> bridge passes them through and SDK reports connection failure
- LBS/link values are duplicated into both `privateConf` and login service config -> this matches reference behavior and SDK expectations

## Migration Plan

1. Add OpenSpec delta for private deployment endpoint support.
2. Extend Python config parsing and bridge payload generation.
3. Add bridge helper to build SDK private deployment options.
4. Apply helper output in `new NIM(...)`.
5. Add Python and Node tests, then validate.
