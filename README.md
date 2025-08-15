# 🎥 AI Text-to-Video Web App (Vadoo API)

This is a minimal AI-integrated web application that takes a user prompt, generates a short AI-created video using the **Vadoo AI API**, and displays the result in the browser.  
Built with **FastAPI** for the backend and vanilla **HTML/CSS/JS** for the frontend. Deployed publicly on **Render**.

---

## 🚀 Features

- **Prompt to Video** – Enter text and get a generated short video (5–10 seconds+ depending on API).
- **Vadoo API Integration** – Uses the [`generate_video`](https://viralapi.vadoo.tv/docs) endpoint.
- **Webhook Support** – Receives video completion callbacks from Vadoo.
- **Polling Fallback** – UI polls backend `/job-status` for updates.
- **Bonus Features**:
  - Loading spinner while video is generating
  - Prompt template enhancement (`cinematic, high quality` appended automatically)
  - Video history so users can rewatch
  - Caching to avoid API rate-limit hits (optional)

---

## 📂 Folder Structure

```
.
├── backend/
│   ├── main.py           # FastAPI backend
│   ├── requirements.txt  # Backend dependencies
│   └── .env              # Environment variables (NOT committed to GitHub)
│
├── frontend/
│   ├── index.html        # Main UI
│   ├── style.css         # Basic styles
│   └── script.js         # API calls, UI updates
│
├── README.md
└── LICENSE
```

---

## 🔑 Environment Variables

Create a `.env` file in `backend/` with:

```env
VADOO_API_KEY=your_vadoo_api_key_here
BACKEND_BASE_URL=https://<your-render-service>.onrender.com
```

**Important:**  
- Do **not** commit `.env` to GitHub.  
- On Render, set these in **Environment → Environment Variables**.

---

## 🛠️ Installation & Local Development

1. **Clone the repo**
   ```bash
   git clone https://github.com/adityawalture/Text-to-Video-webapp.git
   cd ai-video-webapp
   ```

2. **Install backend dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Run FastAPI server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Open frontend locally**
   - Open `frontend/index.html` in your browser.
   - Make sure `BACKEND_URL` in `script.js` points to `http://localhost:8000`.

---

## 🌐 Deployment (Render)

1. Push code to GitHub.
2. Create a **Web Service** in Render:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port 10000`
3. Set `VADOO_API_KEY` and `BACKEND_BASE_URL` in Render Environment.
4. Deploy.
5. Set **Webhook URL** in Vadoo dashboard:
   ```
   https://<your-render-service>.onrender.com/webhook/vadoo
   ```
6. App url: https://adityawalture.github.io/Text-to-Video-webapp/frontend/

---

## 🔄 How It Works

1. **User Prompt**
   - Enter text in UI → POST to `/generate-video`.

2. **Video Generation**
   - Backend sends request to Vadoo API with API key.
   - Returns `job_id` to frontend.

3. **Webhook Update**
   - Vadoo calls `/webhook/vadoo` when video is ready.
   - Backend stores `video_url` in memory/cache.

4. **Frontend Polling**
   - UI calls `/job-status?job_id=...` until status is `"complete"`.
   - Displays video player with generated video.

---

## 🧪 Testing Without API Credits

You can simulate a completed job:

```bash
curl -X POST https://<your-render-service>.onrender.com/webhook/vadoo   -H "Content-Type: application/json"   -d '{"vid":"test-123","status":"complete","url":"https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4"}'
```

Then:
```bash
curl "https://<your-render-service>.onrender.com/job-status?job_id=test-123"
```

---

## ⚠️ Notes & Limitations

- Vadoo free tier has limited generations — you may hit `"Generation limits over"` errors.
- The mock video fallback allows UI testing without consuming credits.
- No API keys are stored in the frontend — all calls go through the backend.

---