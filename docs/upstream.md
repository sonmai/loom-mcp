# Upstream research and draft design

Read-only source inspection; upstream was neither installed nor executed.

Pinned commit: `9d5f0ce5bfad960541ae11a3e525640d5acc8081`.

[Source client](https://github.com/karbassi/mcp-loom/blob/9d5f0ce5bfad960541ae11a3e525640d5acc8081/src/loom_mcp/client.py)
and [MIT license](https://github.com/karbassi/mcp-loom/blob/9d5f0ce5bfad960541ae11a3e525640d5acc8081/LICENSE).

## Endpoint and headers

Upstream POSTs JSON containing `operationName`, `query`, and `variables` to
`https://www.loom.com/graphql`. Its explicit headers are:

```text
content-type: application/json
apollographql-client-name: web
x-loom-request-source: loom_web
cookie: <cookie string supplied to its client>
```

HTTPX adds ordinary transport headers. Our implementation constructs the cookie
header solely as `connect.sid=<Keychain value>`. Upstream supports cookie strings
or a browser-state file; only the cookie mechanism is adapted. No API key,
OAuth, or browser automation is required by these source paths.

## Exact relevant upstream methods and queries

```python
async def get_video(self, video_id: str) -> dict:
        data = await self.graphql(
            "fetchVideoData",
            """query fetchVideoData($id: ID!, $password: String) {
              video: getVideo(id: $id, password: $password) {
                ... on RegularUserVideo {
                  id name createdAt playable_duration
                  tags complete comments_enabled
                  owner { id display_name avatars { thumb } }
                  views { total distinct }
                  totalComments totalReactions
                  video_properties { width height screen_type }
                  organization { id name }
                  calendarMeetingGuid storage
                }
                ... on VideoPasswordMissingOrIncorrect { id message }
                ... on PrivateVideo { id message }
              }
            }""",
            {"id": video_id, "password": None},
        )
        return data["video"]
```

```python
async def get_description(self, video_id: str) -> str | None:
        data = await self.graphql(
            "GetVideoDescription",
            """query GetVideoDescription($videoId: ID!) {
              getVideo(id: $videoId) {
                ... on RegularUserVideo { id description }
              }
            }""",
            {"videoId": video_id},
        )
        return (data.get("getVideo") or {}).get("description")
```

```python
async def get_transcript_details(self, video_id: str) -> dict | None:
        data = await self.graphql(
            "fetchVideoTranscript",
            """query fetchVideoTranscript($videoId: ID!) {
              fetchVideoTranscript(videoId: $videoId) {
                ... on VideoTranscriptDetails {
                  idv2 video_id version
                  transcript_url captions_url source_url captions_source_url
                  transcription_status processing_service language
                }
              }
            }""",
            {"videoId": video_id},
        )
        return data.get("fetchVideoTranscript")
```

```python
async def get_download_url(self, video_id: str) -> str | None:
        data = await self.graphql(
            "GetVideoTranscodedUrl",
            """query GetVideoTranscodedUrl($videoId: ID!, $forceOriginal: Boolean) {
              getVideoTranscodedUrl(videoId: $videoId, forceOriginal: $forceOriginal) {
                ... on VideoSource { url }
              }
            }""",
            {"videoId": video_id, "forceOriginal": False},
        )
        return (data.get("getVideoTranscodedUrl") or {}).get("url")
```

## Transcript and media retrieval

Upstream GETs `fetchVideoTranscript.source_url` with its HTTP client, without the
GraphQL cookie headers. JSON `phrases` become `ts` (seconds), `speakerName`
(optional), and `value` (text).

`get_download_url` returns `getVideoTranscodedUrl.url`, with
`forceOriginal: false`. Our implementation streams that URL to a temporary local
file, checks for an MP4 file-type header, and atomically replaces the MP4 cache.

The alternative upstream `download_media` calls `get_cdn_url(video_id, "DASH")`.
That query reads `getVideo(id: $id, password: $password)` and
`nullableRawCdnUrl(acceptableMimes: [DASH], password: $password) { url }`.
Its media helper downloads selected DASH tracks/segments and uses ffmpeg to
assemble them. We choose the smaller MP4-export route permitted by the brief.
We do not adapt its separate `regenerate_mp4` mutation.

## Adaptations

- Combine the existing metadata selection and the read-only description
  selection into one `fetchVideoData` query.
- Trim unrelated fields and add `__typename` to detect non-success union results.
- Keep the transcript and MP4 operation names and variables.
- Do not return upstream error messages or bodies, which might contain secrets.
  Errors use controlled messages instead. Network errors, subprocess output,
  and unexpected exceptions never escape into SDK tracebacks.
- Use the official SDK `MCPServer` API, pinned to `mcp==2.3.0`, checked using
  Context7 against [v2.3.0 docs](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0/docs).
- Separate HTTP clients for GraphQL and asset requests; the cookie is never
  configured on a download client.
- Exactly three tools. Authentication is lazy so discovery works before Keychain
  setup; tools read Keychain at runtime.
- Cache MP4s across calls and processes. A file lock protects download/extraction,
  and temporary files prevent partially written media from becoming final files.
- Preserve the source's MIT notice in `THIRD_PARTY_NOTICES.md`.

## File layout

```text
pyproject.toml
README.md
THIRD_PARTY_NOTICES.md
.gitignore
src/loom_mcp/
  __init__.py
  queries.py       fixed read-only GraphQL documents
  client.py        Keychain and Loom HTTP reads
  parsing.py       video references and timestamp bounds
  frames.py        shared MP4 cache and ffmpeg extraction
  server.py        exactly three SDK tools and console entry point
tests/
  test_parsing.py  URL/ID and frame-input contracts
docs/
  upstream.md     source evidence and design
  review.md       full draft code for approval
```

A single-file server would be shorter to navigate initially but mixes secrets,
transport, and filesystem behavior. A DASH implementation would cover more videos
but needs manifest/segment handling. This draft uses focused modules and MP4
exports to stay within the requested small scope.

## Approval and verification state

The initial code draft was approved for installation. See
[verification status](verification.md) for checks actually performed and pending work.
The selected clients are Claude Code (user scope) and Codex CLI. Installation into
those clients follows successful live verification in Inspector. No push is authorized.
