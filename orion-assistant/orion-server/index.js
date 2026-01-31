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

  const systemPrompt = `
You are Orion, a desktop AI assistant.

Your job is to convert user speech into ONE valid JSON command.

Allowed intents:
- open_app
- play_playlist
- set_alarm
- set_timer
- get_weather
- get_time
- chat

Rules:
- ALWAYS return JSON
- No markdown
- No explanations
- If unsure, use intent "chat"

JSON format:
{
  "intent": "...",
  "args": {},
  "reply": "what Orion should say"
}
`;

  try {
    const response = await fetch(CLAUDE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-3-5-sonnet-20240620",
        max_tokens: 500,
        system: systemPrompt,
        messages: [
          { role: "user", content: text }
        ]
      })
    });

    const data = await response.json();
    const raw = data.content[0].text;

    res.json({ result: raw });
  } catch (err) {
    res.status(500).json({
      result: JSON.stringify({
        intent: "chat",
        args: {},
        reply: "I'm having trouble connecting to my intelligence core."
      })
    });
  }
});

app.listen(3000, () => {
  console.log("🟣 Orion server (Claude) running on port 3000");
});
