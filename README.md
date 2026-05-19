# PlantPal v3.0 — AI Plant Health Assistant

A production-ready, AI-powered plant health assistant with:
- **GPT-powered chatbot** with conversational memory and multi-modal reasoning
- **Computer vision leaf scanner** using MobileNetV2 (TensorFlow)
- **Live weather integration** with risk assessment and vitality scoring
- **SQLite database** for chat history, scan logs, and plant tracking
- **Responsive modern frontend** (vanilla HTML/CSS/JS, no framework required)

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> **Minimum Python version:** 3.10

> If you don't want TensorFlow (large download), remove the `tensorflow` line from `requirements.txt`.
> The scanner will run in simulation mode and still show results.

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your **OpenAI API key** — the chatbot will use GPT.
Without a key it falls back to the built-in rule engine (still useful but less powerful).

### 3. Run the app

```bash
python backend/app.py
```

Then open: **http://localhost:5000**

---

## Project Structure

```
plantpal/
├── backend/
│   ├── app.py              ← Flask entry point
│   ├── config.py           ← Configuration + env vars
│   ├── routes/
│   │   ├── chat.py         ← POST /api/chat (AI chatbot)
│   │   ├── scan.py         ← POST /api/scan (leaf analysis)
│   │   ├── weather.py      ← GET  /api/weather
│   │   ├── plants.py       ← GET  /api/plants
│   │   └── train.py        ← POST /api/train (retrain model)
│   ├── services/
│   │   ├── ai_service.py   ← GPT + rule-engine chatbot logic
│   │   ├── plant_service.py ← Plant knowledge base (10 species)
│   │   ├── weather_service.py ← Weather fetch + caching
│   │   └── scan_service.py ← TensorFlow prediction + simulation
│   ├── models/
│   │   └── ml_model.py     ← Model training (MobileNetV2)
│   ├── database/
│   │   └── db.py           ← SQLite init + CRUD
│   └── utils/
│       └── helpers.py      ← Validation + utilities
│
├── frontend/
│   ├── index.html          ← Home (chatbot + weather dashboard)
│   ├── scanner.html        ← Leaf scanner page
│   ├── about.html
│   ├── contact.html
│   ├── css/
│   │   ├── main.css        ← All page styles (responsive)
│   │   └── chatbot.css     ← Chatbot-specific styles
│   └── js/
│       ├── chatbot.js      ← Chatbot UI (API calls only)
│       ├── scanner.js      ← Scanner UI + API calls
│       └── weather.js      ← Weather dashboard
│
├── model/                  ← Place plant_model.h5 + labels.json here
├── training_data/
│   ├── Healthy/            ← Add training images here
│   ├── Fungal/
│   ├── Scorch/
│   └── Wilting/
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Reference

### POST /api/chat
AI chatbot endpoint.

**Request body:**
```json
{
  "message": "Why are my monstera leaves yellowing?",
  "session_id": "optional-uuid",
  "plant_name": "monstera",
  "conversation_history": [{"role": "user", "content": "..."}],
  "weather": {"temp": 32, "humidity": 85, "uvIndex": 7, "city": "London"},
  "scan_result": {"label": "Fungal", "confidence": 0.82}
}
```

**Response:**
```json
{
  "response": "Based on the 85% humidity and the fungal scan...",
  "confidence": 0.92,
  "intent": "disease",
  "suggestions": ["How do I treat root rot?", "..."],
  "severity": "high",
  "source": "openai"
}
```

---

### POST /api/scan
Leaf health prediction.

**Request (multipart form):**
- `image` — image file (JPG/PNG/WebP)
- `session_id` — optional string
- `weather` — optional JSON string

**Request (JSON):**
```json
{"image_base64": "base64string...", "session_id": "...", "weather": {...}}
```

**Response:**
```json
{
  "label": "Fungal",
  "confidence": 0.87,
  "all_scores": {"Healthy": 0.05, "Fungal": 0.87, "Wilting": 0.05, "Scorch": 0.03},
  "diagnosis": "Fungal infection detected...",
  "multi_modal": "HIGH CONFIDENCE: Fungal + 85% humidity...",
  "weather_risks": [{"level": "high", "message": "..."}],
  "simulated": false
}
```

---

### GET /api/weather?lat=51.5&lon=-0.12
Returns weather data for given coordinates.

---

### POST /api/train
Trigger model retraining.

```json
{"epochs": 10, "batch_size": 16}
```

### GET /api/train/status
Returns training progress.

---

## Training Your Own Model

1. Add leaf images to `training_data/`:
   - `training_data/Healthy/` — healthy leaf photos
   - `training_data/Fungal/` — fungal infection photos
   - `training_data/Scorch/` — sun scorch photos
   - `training_data/Wilting/` — wilting photos

2. Make sure TensorFlow is installed and call the train endpoint:
   ```bash
   curl -X POST http://localhost:5000/api/train -H "Content-Type: application/json" -d '{"epochs":15}'
   ```

3. Check progress:
   ```bash
   curl http://localhost:5000/api/train/status
   ```

The trained model is saved to `model/plant_model.h5` and used automatically on next scan.

---

## Chatbot Capabilities

The chatbot understands 14+ intents including:
`watering` · `sunlight` · `humidity` · `temperature` · `fertiliser` · `disease`
`pest` · `travel` · `emergency` · `recovery` · `greeting` · `gratitude` · `diagnosis` · `propagation`

It has detailed knowledge profiles for 9 species:
Monstera · Snake Plant · Pothos · Aloe Vera · Peace Lily · ZZ Plant · Fiddle Leaf Fig · Spider Plant · Succulent

### Multi-modal reasoning examples

| Scan result | Weather | AI conclusion |
|-------------|---------|---------------|
| Fungal (87%) | Humidity 85% | High-confidence fungal — act immediately |
| Wilting (79%) | Temp 38°C | Heat stress — shade and water now |
| Scorch (81%) | UV index 9 | Sun damage confirmed — relocate plant |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required for GPT) | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use |
| `OPENWEATHER_API_KEY` | included | OpenWeatherMap key |
| `SECRET_KEY` | `plantpal-dev-secret-2024` | Flask session secret |
| `DEBUG` | `true` | Flask debug mode |
| `PORT` | `5000` | Server port |
| `DATABASE_PATH` | `database/plantpal.db` | SQLite path |
| `WEATHER_CACHE_TTL` | `600` | Weather cache seconds |

---

## Troubleshooting

**Chatbot returns generic responses** → Add `OPENAI_API_KEY` to `.env`. Without it, the rule engine is used.

**Weather not showing** → Allow location access in the browser prompt.

**Scan fails** → Ensure `tensorflow` and `Pillow` are installed. Without a trained model, simulation mode is used automatically.

**Port in use** → Change `PORT=5001` in `.env`.
