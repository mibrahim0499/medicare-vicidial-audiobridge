# Audio Streaming Bridge - Overview & Technology Stack

## What is This Application?

The **Audio Streaming Bridge** is a real-time audio streaming system that connects VICIdial (a call center platform) with an AI backend. It captures live call audio from active phone calls, streams it securely to a FastAPI backend, and logs all call data for processing and analysis.

### Core Purpose

This application serves as the **foundational infrastructure** (Phase 1) for an AI-powered voice bot system. It enables:

- **Real-time audio capture** from active phone calls
- **Secure streaming** of audio data to AI processing systems
- **Comprehensive logging** of call metadata and audio streams
- **Monitoring and validation** of audio data flow

Think of it as a "bridge" that allows AI systems to "listen" to phone calls in real-time, which is essential for building AI voice bots that can have natural conversations with customers.

---

## What is Asterisk?

**Asterisk** is an open-source telephony engine and toolkit that powers phone systems. It's the underlying technology that handles:

- **Call routing** - Directing calls to the right destination
- **SIP (Session Initiation Protocol)** - The protocol used for VoIP (Voice over IP) calls
- **Call management** - Managing call states, channels, and connections
- **Media handling** - Processing audio streams

### Asterisk REST Interface (ARI)

**ARI (Asterisk REST Interface)** is a powerful API that allows external applications to:

- **Monitor calls** in real-time
- **Control call behavior** programmatically
- **Access call audio** streams
- **Receive events** when calls start, end, or change state

In our application, we use ARI to:
- Detect when calls are active
- Capture audio from those calls
- Stream the audio to our FastAPI backend
- Monitor call lifecycle events

### Why We Need Asterisk

Asterisk is the **telephony engine** that VICIdial uses. Without Asterisk, there would be no way to:
- Make or receive phone calls
- Process audio streams
- Monitor call events
- Access call data programmatically

ARI gives us the "hooks" we need to tap into the phone system and extract audio data in real-time.

---

## What is VICIdial?

**VICIdial** is an open-source call center software built on top of Asterisk. It provides:

- **Campaign management** - Organize and manage outbound calling campaigns
- **Agent interface** - Web-based interface for call center agents
- **Call distribution** - Automatically route calls to available agents
- **Reporting and analytics** - Track call performance, agent productivity, etc.
- **List management** - Manage contact lists for outbound campaigns

### VICIdial Architecture

```
┌─────────────────┐
│   VICIdial Web  │  ← Admin panel, agent interface
│     Interface   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Asterisk     │  ← Telephony engine (handles calls)
│   (with ARI)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Phone Lines   │  ← Actual phone calls
│   (SIP Trunks)  │
└─────────────────┘
```

### Why We Need VICIdial

VICIdial provides the **call center infrastructure** we need:

1. **Call Management** - It handles all the complex logic of managing campaigns, agents, and call routing
2. **Existing Infrastructure** - Your organization already has VICIdial set up and running
3. **Integration Point** - It's built on Asterisk, which gives us access to ARI for audio streaming
4. **Production Ready** - It's a mature, stable platform used by many call centers

We're not replacing VICIdial - we're **enhancing it** by adding AI capabilities on top of it.

---

## Why Do We Need This Bridge?

### The Problem

To build AI voice bots that can have conversations with customers, we need:

1. **Real-time audio access** - The AI needs to "hear" what the customer is saying
2. **Low latency** - Responses must be fast (under 3 seconds) for natural conversation
3. **Scalability** - Handle 1,000-2,000 concurrent calls simultaneously
4. **Reliability** - System must work consistently without disrupting existing operations

### The Solution: Audio Streaming Bridge

This application solves these challenges by:

#### 1. Real-Time Audio Capture
- Uses Asterisk ARI to monitor active calls
- Captures audio streams as they happen
- No need to wait for call recordings

#### 2. Secure Streaming
- WebSocket-based streaming for low latency
- Secure connection between VICIdial server and AI backend
- Handles multiple concurrent streams efficiently

#### 3. Data Logging
- Logs all call metadata (caller, callee, duration, etc.)
- Stores audio stream references
- Enables analysis and debugging

#### 4. Monitoring Dashboard
- Real-time visualization of active calls
- Stream health monitoring
- Call history and metrics

### How It Fits in the Bigger Picture

```
┌─────────────────────────────────────────────────────────┐
│                    Phase 1 (Current)                    │
│              Audio Streaming Bridge                     │
│  ┌──────────────┐         ┌──────────────┐            │
│  │   VICIdial   │────────▶│  FastAPI     │            │
│  │  (Asterisk)  │  Audio  │  Backend     │            │
│  └──────────────┘  Stream └──────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Phase 2 (Future)                     │
│              AI Processing Layer                         │
│  ┌──────────────┐         ┌──────────────┐            │
│  │  Audio       │────────▶│  AI Engine   │            │
│  │  Stream      │         │  (GPT-4,     │            │
│  │              │         │   Whisper)   │            │
│  └──────────────┘         └──────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Phase 3 (Future)                     │
│         Conversational AI Voice Bots                     │
│  ┌──────────────┐         ┌──────────────┐            │
│  │  Customer   │◀────────▶│  AI Bot     │            │
│  │             │  Voice  │  (ElevenLabs)│            │
│  └──────────────┘         └──────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Application Scope

### Phase 1: Audio Streaming Bridge (Current)

**What it does:**
- Connects VICIdial/Asterisk to FastAPI backend
- Captures live call audio in real-time
- Streams audio via WebSocket
- Logs call metadata and audio references
- Provides monitoring dashboard

**What it does NOT do:**
- ❌ AI processing or transcription
- ❌ Voice bot responses
- ❌ Intent detection
- ❌ Call automation

**Deliverables:**
- ✅ Working audio streaming bridge
- ✅ Real-time call monitoring
- ✅ Data logging system
- ✅ Monitoring dashboard
- ✅ End-to-end data flow validation

### Future Phases

**Phase 2: AI Processing Layer**
- Real-time transcription (Whisper)
- Intent detection
- Session analytics

**Phase 3: Conversational Automation**
- Two-way AI voice bot
- Natural conversation flow
- Human agent transfer
- Performance optimization

---

## Technical Architecture

### Components

1. **VICIdial Server** (`autodialer1.worldatlantus.com`)
   - Runs Asterisk telephony engine
   - Handles actual phone calls
   - Provides ARI interface

2. **FastAPI Backend** (This application)
   - Receives audio streams via WebSocket
   - Processes and validates audio
   - Logs call data to database
   - Serves monitoring dashboard

3. **Database** (SQLite/PostgreSQL)
   - Stores call metadata
   - Tracks audio streams
   - Maintains call history

4. **Monitoring Dashboard** (Web interface)
   - Visualizes active calls
   - Shows stream health
   - Displays metrics and statistics

### Data Flow

```
Phone Call → Asterisk → ARI → FastAPI → WebSocket → Dashboard
                │                        │
                │                        ▼
                │                    Database
                │                        │
                └────────────────────────┘
                    (Logging & Storage)
```

---

## Key Technologies

- **FastAPI** - Modern Python web framework for the backend
- **WebSocket** - Real-time bidirectional communication
- **Asterisk ARI** - REST interface for telephony control
- **SQLAlchemy** - Database ORM for data persistence
- **aiohttp** - Async HTTP client for ARI communication
- **SQLite/PostgreSQL** - Database for call logging

---

## Use Cases

### Current (Phase 1)
- **Call Monitoring** - Real-time visibility into active calls
- **Audio Validation** - Verify audio streams are working correctly
- **Data Collection** - Gather call metadata for analysis
- **System Testing** - Validate infrastructure before adding AI

### Future (Phase 2 & 3)
- **AI Voice Bots** - Automated customer service agents
- **Call Transcription** - Real-time speech-to-text
- **Sentiment Analysis** - Detect customer emotions
- **Intent Detection** - Understand what customers want
- **Automated Routing** - Route calls based on AI analysis

---

## Why This Approach?

### Benefits

1. **Non-Disruptive** - Doesn't interfere with existing VICIdial operations
2. **Scalable** - Can handle thousands of concurrent calls
3. **Modular** - Each phase builds on the previous one
4. **Flexible** - Can add new features without breaking existing ones
5. **Production-Ready** - Uses proven technologies and patterns

### Challenges Solved

- ✅ Real-time audio access without disrupting calls
- ✅ Low-latency streaming for AI processing
- ✅ Handling high call volumes (1,000-2,000 concurrent)
- ✅ Secure data transmission
- ✅ Reliable logging and monitoring

---

## Summary

This application is the **foundation** for building AI-powered voice bots. It solves the critical problem of accessing real-time call audio from VICIdial, which is essential for:

- Building conversational AI agents
- Real-time call analysis
- Automated customer service
- Advanced call center features

By completing Phase 1, you'll have a working bridge that can stream audio from VICIdial calls to your AI backend, enabling all future AI capabilities.

