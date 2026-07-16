## 1. Stateful Streaming

- [x] 1.1 Add bridge-owned stream session keys, base-message reuse, completion cleanup, timeout cleanup, and fallback metadata
- [x] 1.2 Extend Python bridge and registered adapter stream metadata with stable stream IDs and Topic-aware parameters
- [x] 1.3 Add multi-chunk, reply-stream, completion, fallback, and cleanup tests

## 2. QChat Parity

- [x] 2.1 Split QChat passive listener registration from authenticated activation
- [x] 2.2 Add bounded QChat raw-message caching and native reply/fallback sending
- [x] 2.3 Inject channel context into inbound Hermes text and add QChat media-link fallback
- [x] 2.4 Add QChat startup, invite/subscription, native reply, context, and media tests

## 3. Topic Isolation and Routing

- [x] 3.1 Add Topic-aware target parsing, chat IDs, titles, and batch keys in bridge and both Python adapters
- [x] 3.2 Add bounded Topic context registry with reply aliases, Topic lookup, TTL, and disconnect cleanup
- [x] 3.3 Route text, media, stream, and delayed Topic sends through the registry with ordinary fallback on misses
- [x] 3.4 Add same-user multi-Topic isolation, delayed routing, cache expiry, and fallback tests

## 4. Plugin Integration and Validation

- [x] 4.1 Add coverage for the root `HermesNimAdapter` registration path or extract shared routing helpers used by both adapters
- [x] 4.2 Update README and Hermes integration guidance for stream IDs, QChat behavior, and Topic chat IDs
- [x] 4.3 Run Python tests, Node tests, and `./scripts/sdd validate complete-nim-stream-qchat-topic-parity`
- [x] 4.4 Add a user-only local relay and registered standalone sender for `hermes send` without duplicate NIM login
- [x] 4.5 Validate standalone relay lifecycle, successful delivery, unavailable-gateway behavior, and live gateway health after a send
