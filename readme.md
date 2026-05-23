# Azure VideoRAG Pipeline

Azure-based automated Video Understanding and Retrieval-Augmented
Generation (RAG) pipeline using:

- Azure Blob Storage
- Azure Queue Storage
- Azure Functions
- Azure Video Indexer
- Azure AI Foundry / Azure OpenAI
- GPT-5.5 Vision

The system converts uploaded videos into structured multimodal
RAG-ready JSON suitable for semantic search, knowledge retrieval,
agentic workflows, and downstream AI applications.

Status: Completed Reference Implementation

This repository is archived and released as a successful project
reference. No active maintenance is planned.

# Supported Video Formats

Azure Video Indexer does not reliably support all legacy video formats.

During testing, MPEG Program Stream files (`.m2p`) were not accepted
by Video Indexer.

Convert `.m2p` files to `.mp4` before upload.

Windows PowerShell:

```powershell
Get-ChildItem *.m2p | ForEach-Object {
    ffmpeg -i $_.FullName -c:v copy -c:a aac -b:a 224k "$($_.BaseName).mp4"
}

### Recommended Upload Format

* **Video:** H.264 MP4
* **Audio:** AAC audio


---

# Processing Performance

# Benchmark

Example production run:

Video:

- Size: 186.2 MiB
- Duration: 16.53 minutes

Timeline:

| Stage | Timestamp |
|---------|---------|
| Upload | 13:31:02 |
| Manifest Created | 13:31:02 |
| Video Indexer Processing Complete | 13:38:02 |
| Insights Downloaded | 13:38:02 |
| Frame Extraction Complete | 13:41:07 |
| Segment Analysis Complete | 14:14:06 |
| Final RAG JSON Generated | 14:14:59 |

Total End-to-End Time:

Approximately 44 minutes

Azure Services Used:

- Azure Video Indexer
- Azure Functions
- Azure Queue Storage
- Azure Blob Storage
- Azure OpenAI GPT-5.5 Vision

# Azure Resources

The reference deployment used:

## Storage Account

Purpose:

- input videos
- extracted frames
- checkpoints
- manifests
- final RAG outputs
- queues

Services:

- Blob Storage
- Queue Storage

---

## Azure Function App (Linux)

Triggers:

- Blob Trigger
- Queue Trigger
- HTTP Trigger

Functions:

- trigger_vi
- video_indexer_callback
- process_vi_output_worker
- frame_extraction_worker
- segment_analysis_worker
- aggregation_worker
- health

---

## Azure Video Indexer

Used for:

- transcript extraction
- speech timestamps
- metadata generation

---

## Azure AI Foundry / Azure OpenAI

Model:

GPT-5.5

Used for:

- multimodal frame understanding
- transcript-grounded visual analysis
- structured JSON generation

---

## Application Insights

Used for:

- diagnostics
- exception tracking
- timeout analysis

```mermaid
graph TD
    A[input-videos/] --> B(trigger_vi)
    B --> C(Azure Video Indexer)
    C --> D(video_indexer_callback)
    D --> E(process_vi_output_worker)
    E --> F[video-indexer-outputs/]
    F --> G(frame_extraction_worker)
    G --> H[extracted-frames/]
    H --> I(segment_analysis_worker)
    I --> J[processing-checkpoints/]
    J --> K(aggregation_worker)
    K --> L[rag-database-json/]
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style F fill:#f9f,stroke:#333,stroke-width:2px
    style H fill:#f9f,stroke:#333,stroke-width:2px
    style J fill:#f9f,stroke:#333,stroke-width:2px
    style L fill:#f9f,stroke:#333,stroke-width:2px

    # Storage Containers

## input-videos

Uploaded source videos.

---

## video-indexer-outputs

Video Indexer insights JSON.

---

## extracted-frames

Extracted JPG frames.

Frame manifest stored here.

---

## processing-manifests

Pipeline status manifests.

Tracks:

- callback status
- frame counts
- processing progress
- completion state

---

## processing-checkpoints

Frame-level checkpoints.

Allows:

- timeout recovery
- resume processing
- aggregation rebuild

---

## rag-database-json

Final multimodal RAG JSON outputs.

