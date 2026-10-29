# Queries adapted from karbassi/mcp-loom@9d5f0ce5bfad960541ae11a3e525640d5acc8081 (MIT)

VIDEO = """query fetchVideoData($id: ID!, $password: String) {
  video: getVideo(id: $id, password: $password) {
    __typename
    ... on RegularUserVideo {
      id name createdAt playable_duration description
      owner { id display_name }
    }
  }
}"""

TRANSCRIPT = """query fetchVideoTranscript($videoId: ID!) {
  fetchVideoTranscript(videoId: $videoId) {
    __typename
    ... on VideoTranscriptDetails {
      source_url transcription_status
    }
  }
}"""

DOWNLOAD = """query GetVideoTranscodedUrl($videoId: ID!, $forceOriginal: Boolean) {
  getVideoTranscodedUrl(videoId: $videoId, forceOriginal: $forceOriginal) {
    __typename
    ... on VideoSource { url }
  }
}"""
