# AI-Based Food Waste Prediction and Reduction System

A local EVS mini-project for tracking canteen food preparation, consumption and leftovers. The dashboard turns SQLite records into waste trends, meal comparisons, recommendations and a simple, explainable demand estimate.

## Public demo

GitHub Pages runs the React frontend as a static site. In that mode, the app includes the same 120-record demonstration data and keeps each visitor's added or edited records in that visitor's browser storage. It does not connect to a publicly hosted Flask service. The local setup below uses Flask and SQLite instead.

After the first GitHub Actions deployment, the project page is available at `https://abhignya-c12.github.io/food-waste-project/`.

## What it does

- Overview dashboard with date ranges, summary metrics, charts and recent records.
- Food record create, edit, delete, search and meal filtering. Leftover is calculated as prepared minus consumed.
- Backend prediction using the selected meal's average historical consumption per person (when at least three records exist), with a clearly labelled fallback estimate.
- Dynamic practical recommendations based on total and meal-specific waste.
- 120 clearly labelled demonstration records are seeded on first database creation.
- Flask + SQLite backend and React + Vite frontend. It runs locally and uses no external data service.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer and npm

## Run on Windows / VS Code

Open this folder in VS Code. Use two integrated terminals.

### 1. Backend

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The API starts at `http://127.0.0.1:5000`. The SQLite database (`backend/food_waste.db`) is created and seeded automatically on first run.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, usually `http://localhost:5173`.

## Prediction method

For a meal with at least three database records, the backend averages `consumed kg / expected people` for that meal, then multiplies by forecast attendance. The suggested preparation amount adds a 3% buffer to expected consumption. Estimated leftover and waste percentage are calculated from the preparation quantity supplied in the form, or from the recommendation when it is blank. With fewer than three records, the entered prepared-per-person average is used when supplied; otherwise a simple breakfast/dinner-sized fallback is used and explained in the result.

Waste status: Low below 5%, Moderate from 5% through 10%, High above 10%.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Local API status |
| GET | `/api/records` | List/filter records (`search`, `meal`, `start`, `end`) |
| POST | `/api/records` | Add a record |
| PUT | `/api/records/<id>` | Edit a record |
| DELETE | `/api/records/<id>` | Delete a record |
| GET | `/api/dashboard` | Summary, daily chart, meal chart and recent records |
| POST | `/api/predict` | Generate backend prediction |
| GET | `/api/recommendations` | Generate data-based recommendations |

## Limitations

The predictor is a small historical average, not a trained machine-learning model. It cannot account for a changed menu, weather, special events, attendance uncertainty or food safety practices. Results are estimates for planning, and donation/storage decisions must follow local food safety rules.

## Reset demo data

Stop the backend, delete `backend/food_waste.db`, then restart `python app.py`. The initial sample set will be created again.
