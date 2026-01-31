import express from "express";
import fetch from "node-fetch";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const CLAUDE_URL = "https://api.anthropic.com/v1/messages";

app.post("/interpret", async (req, res) => {
  const { text, memory } = req.body;

  if (!text) {
    return res.status(400).json({
      result: {
        intent: "unknown",
        args: {},
        reply: "No text provided."
      }
    });
  }

  const systemPrompt = `
You are Orion, a desktop AI assistant.
Your job is to convert user speech into ONE valid JSON command.

Current datetime: ${new Date().toISOString().slice(0, 19).replace('T', ' ')}

Allowed intents:
- add_note, list_notes
- add_task, list_tasks, complete_task
- add_reminder, list_reminders
- get_weather, get_time
- set_alarm, open_app, close_app
- send_email, call_number, set_volume
- find_file, summarize_file
- music_play, music_pause, music_next, music_previous
- set_preference, get_preference
- chat (for general conversation)

Rules:
- ALWAYS return ONLY valid JSON, nothing else
- No markdown code blocks
- No explanations before or after
- If unsure, use intent "chat"

JSON format:
{
  "intent": "...",
  "args": {},
  "reply": "what Orion should say"
}

Examples:
User: "remind me to call mom at 5pm"
{
  "intent": "add_reminder",
  "args": {
    "text": "call mom",
    "time": "2025-02-01 17:00"
  },
  "reply": "I'll remind you at 5pm to call mom."
}

User: "what's the weather?"
{
  "intent": "get_weather",
  "args": {
    "location": null
  },
  "reply": "Let me check the weather for you."
}

User: "hey how are you?"
{
  "intent": "chat",
  "args": {},
  "reply": "I'm operating at full capacity, ma'am. How may I assist you?"
}
`;

  try {
    console.log(`[Orion] Interpreting: "${text}"`);

    const response = await fetch(CLAUDE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 500,
        system: systemPrompt,
        messages: [
          { role: "user", content: text }
        ]
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[Orion] Claude API error (${response.status}):`, errorText);
      throw new Error(`Claude API returned ${response.status}`);
    }

    const data = await response.json();
    let raw = data.content[0].text.trim();

    console.log(`[Orion] Claude response: ${raw.substring(0, 200)}...`);

    // Clean up response - remove markdown code blocks if present
    if (raw.startsWith("```json")) {
      raw = raw.slice(7);
    }
    if (raw.startsWith("```")) {
      raw = raw.slice(3);
    }
    if (raw.endsWith("```")) {
      raw = raw.slice(0, -3);
    }
    raw = raw.trim();

    // Try to parse as JSON
    let result;
    try {
      result = JSON.parse(raw);
      
      // Validate structure
      if (!result.intent) result.intent = "unknown";
      if (!result.args) result.args = {};
      if (!result.reply) result.reply = "Done.";

      console.log(`[Orion] Parsed intent: ${result.intent}`);
      
    } catch (parseError) {
      console.error(`[Orion] JSON parse error:`, parseError);
      console.error(`[Orion] Raw response was:`, raw);
      
      // Fallback to chat intent with the raw response
      result = {
        intent: "chat",
        args: {},
        reply: raw || "I understood you, but I'm not sure how to respond."
      };
    }

    res.json({ result });

  } catch (err) {
    console.error("[Orion] Server error:", err);
    res.status(500).json({
      result: {
        intent: "chat",
        args: {},
        reply: "I'm having trouble connecting to my intelligence core right now."
      }
    });
  }
});

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({ 
    status: "ok",
    service: "Orion Claude Server",
    timestamp: new Date().toISOString()
  });
});

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    service: "Orion Claude API Server",
    version: "1.0.0",
    endpoints: {
      interpret: "POST /interpret",
      health: "GET /health"
    }
  });
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`🟣 Orion server (Claude) running on port ${PORT}`);
  console.log(`🔗 Health check: http://localhost:${PORT}/health`);
  console.log(`🧠 Using Claude model: claude-sonnet-4-20250514`);
});