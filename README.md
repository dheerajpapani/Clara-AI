# 🚀 **Clara AI Automation Pipeline**

An end-to-end **automation pipeline** specifically engineered to process unstructured client conversations (such as demo calls and follow-up onboarding chats) into highly structured, deployment-ready AI voice agent configurations.

It supports dynamic semantic extraction, intelligent regex fallback execution, strict dataset tracking, and clean JSON generation using Llama 3.1 8B.

---

## 📘 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Architecture Diagrams](#-architecture-diagrams)
- [Developer Setup Guide](#-developer-setup-guide)
- [Execution Commands](#-execution-commands)
- [Optional Features](#-optional-features)
- [Contributor](#-contributor)

---

## 🌐 Overview

The **Clara AI Automation Pipeline** executes extractions across distinct phases:

- **Pipeline A (Demo Phase):** Parses raw demo call transcripts to build a foundational **Version 1** account and agent specification.
- **Pipeline B (Onboarding Phase):** Integrates separate text chat updates dynamically upon the V1 baseline, establishing a newly tuned **Version 2** specification.
- **Master Orchestrator:** Ties everything into a seamless, autonomous end-to-end execution.

The engine functions perfectly with AI (via Groq API) or entirely offline using a highly-tuned Python Regex fallback system.

---

## ✨ Key Features

### 🔧 Intelligent Extraction Engine

- Highly structured Pydantic schemas enforce robust JSON generation.
- Zero-Hallucination rules: If data is missing from text, it is set to "Unknown".
- Verified Contact Injection via Regex mapping to guarantee clean phone numbers and emails.

### 🧰 Rule-Based Fallback System

- Automatically handles data extraction via tight Regex sequences if an API key is missing.
- Accurately identifies 15+ complex trade services, phrase-based routing networks, and isolated CRMs locally and entirely offline.

### ⏸ Modularity & Traceability

- Pipeline components can be run explicitly by target `account_id` or auto-incremented dynamically.
- `DeepDiff` engine generates robust precise changelogs highlighting specifically what the AI logic loop updated.

---

## 🧱 Architecture

The project has been uniquely organized for maximum cleanliness. Unused caches, IDE configs, virtual environments, and structural artifacts are intentionally ignored or hidden.

```text
Clara-AI/
│
├── data/                                 # Raw input data for the pipeline
│   ├── Clara-demo-for-Bens-electrical-solutions-team-mp4-86f5e3d8-a55c.json
│   ├── Copy of audio1975518882.m4a
│   └── Copy of chat.txt
│
├── outputs/                              # Auto-generated processing artifacts
│   └── accounts/
│       ├── account-[ID]/                 # Configs isolated by target ID
│       │   ├── v1/
│       │   │   ├── account_memo.json
│       │   │   └── agent_spec.json
│       │   └── v2/
│       │       ├── account_memo.json
│       │       ├── agent_spec.json
│       │       └── changelog.json
│
├── scripts/                              # Core Python execution logic
│   ├── pipeline_a_demo.py                # Demo extraction (Phase A)
│   ├── pipeline_b_onboarding.py          # Onboarding modification (Phase B)
│   ├── pipeline_master.py                # Autonomous Master Orchestrator
│   ├── pipeline_utils.py                 # Core Schema & Extraction logic
│   └── transcribe_audio.py               # Optional offline Whisper script
│
├── requirements.txt                      # Project dependency locking
├── .env                                  # (Optional) Environment keys
└── video_presentation_script.md          # Director's pipeline walk-through
```

---

## 🧩 Architecture Diagrams

### **High-Level System Diagram**

```mermaid
flowchart TD
    Data[Raw Audio / Chat]

    %% Main pipeline
    Data --> PA[Pipeline A]
    PA --> V1[(V1 Config)]
    V1 --> PB[Pipeline B]

    %% Orchestrator path
    Data --> Master[Master Pipeline]
    Master --> V3[(V1 Config - By Master)]

    %% Final merge
    PB --> V2[(V2 Config & Changelog)]
    V3 --> V2
    Master -.-> V2
```

---

### **Extraction Logic Flow**

```mermaid
flowchart TD

    %% Ingestion
    Start["Ingest Text"] --> PreExtract["Regex Pre-Extract Contacts"]

    %% Decision
    PreExtract --> CheckKey{"API Key Present?"}

    %% Extraction
    CheckKey -->|Yes| LLM["LLM Extraction - Llama 3.1"]
    CheckKey -->|No| Regex["Offline Regex Fallback Engine"]

    %% Validation
    LLM --> SchemaCheck["Pydantic Schema Validation"]
    Regex --> SchemaCheck

    %% Output
    SchemaCheck --> EndSuccess["Valid JSON Output"]
```

---

## 🧑‍💻 Developer Setup Guide

### 1️⃣ Clone repo

```bash
git clone https://github.com/dheerajpapani/Clara-AI.git
cd Clara-AI
```

### 2️⃣ Backend setup

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3️⃣ Optional API setup

If you heavily require true AI generation (free setup):
Create a `.env` file in the root directory and add your Groq Key:

```text
GROQ_API_KEY=your_key_here
```

---

## 📡 Execution Commands

### ▶ Master Orchestrator (End-to-End)

The master pipeline autonomously runs Phase A and Phase B concurrently across unified data sources.

**Without Explicit ID (Auto-Increments to `account-1`, `account-2`...):**

```powershell
python scripts/pipeline_master.py --demo_json "data/Clara-demo-for-Bens-electrical-solutions-team-mp4-86f5e3d8-a55c.json" --onboarding_text "data/Copy of chat.txt"
```

### ▶ Pipeline A (Demo Extraction Phase)

**With Explicit ID:**

```powershell
python scripts/pipeline_a_demo.py --input "data/Clara-demo-for-Bens-electrical-solutions-team-mp4-86f5e3d8-a55c.json" --account_id "bens_electrical"
```

**Without Explicit ID:**

```powershell
python scripts/pipeline_a_demo.py --input "data/Clara-demo-for-Bens-electrical-solutions-team-mp4-86f5e3d8-a55c.json"
```

### ▶ Pipeline B (Onboarding Modification Phase)

**With Explicit ID:**

```powershell
python scripts/pipeline_b_onboarding.py --input "data/Copy of chat.txt" --account_id "bens_electrical"
```

**Without Explicit ID:**
_(Automatically connects backwards to modify the most recently generated account folder directly)_

```powershell
python scripts/pipeline_b_onboarding.py --input "data/Copy of chat.txt"
```

---

## 🎤 Optional Features

### ▶ Offline Audio Transcription

This repository comes packed with an optional lightweight, offline `Whisper-v3` transcriber to turn raw media files sequentially into clean texts:

```powershell
python scripts/transcribe_audio.py --audio "data/Copy of audio1975518882.m4a" --output "data/onboarding_transcript.txt"
```

---

## 👤 Contributor

**Dheeraj Papani**
AI Engineer | Backend & Systems Development

[![LinkedIn](https://img.shields.io/badge/LinkedIn-blue?logo=linkedin)](https://www.linkedin.com/in/dheeraj-papani-507693274/)
[![GitHub](https://img.shields.io/badge/GitHub-black?logo=github)](https://github.com/dheerajpapani)
[![Gmail](https://img.shields.io/badge/Email-red?logo=gmail)](https://mail.google.com/mail/?view=cm&fs=1&to=dheerajpapani@gmail.com)

---
