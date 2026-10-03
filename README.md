# ReelForge • AI Text-to-Video Studio

A clean, modern, minimalist AI text-to-video generation system. 
Enter any topic, idea, or lesson prompt and watch the entire video automatically generated with:
- **Google Gemini API**: High-accuracy, topic-matched scene-by-scene scriptwriting (`gemini-2.0-flash` / `gemini-1.5-flash`).
- **Pixabay API**: Safe, royalty-free stock video clips & photography (`safesearch=true` strictly enforced, no harmful or negative content).
- **Microsoft Edge Neural TTS**: Crystal-clear voiceovers with realistic voices (Christopher, Guy, Jenny, Aria, Ryan, Sonia, Madhur, Swara, etc.).
- **Synchronized Subtitles**: Clean, modern captions burned onto the video with optional WebVTT/SRT export.
- **Ultra-Clean Minimalist UI**: Neutral matte charcoal/slate palette, no neon, mobile-responsive layout.
- **100% Client-Side BYOK Security**: Users enter their free API keys directly in the website interface. Keys are saved strictly in the user's browser `localStorage` and sent per-request. **No `.env` or secret keys exist in the repository or on server disk**, preventing any key leakage when pushed to GitHub or deployed publicly!

---

## 🚀 Quick Start (Local)

### 1. Launch the Server
Double-click `run.bat` or run in terminal:
```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🔑 Environment Variables & Optional User Keys

### Option A: Server-Side Keys (Recommended for Render)
As the site owner, you can add your API keys directly into Render's secure **Environment Variables** dashboard:
- `GEMINI_API_KEY`: Get a free key at [Google AI Studio](https://aistudio.google.com/apikey).
- `PIXABAY_API_KEY`: Get a free key at [Pixabay Docs](https://pixabay.com/api/docs/).

👉 **When configured in Render, visitors can use your website immediately with 0 keys required!**

### Option B: Optional User Custom Keys
Visitors also have the option to click the **API Keys (Optional)** button in the header if they want to use their own personal quota. Any keys entered in the browser:
- Remain strictly in the visitor's local browser (`localStorage`).
- Override the server keys for that visitor's session.
- Never write to disk or `.env`.

---

## ☁️ Deploying Live on Render (Zero-Leak Guarantee)

### Step 1: Push Code to GitHub
1. In your local project directory:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: ReelForge AI Text-to-Video"
   ```
2. Create a new repository on [GitHub](https://github.com/new).
3. Push your code:
   ```bash
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```
   *(Notice: `.gitignore` and `.dockerignore` ensure `.env` and all temporary files are completely excluded.)*

### Step 2: Deploy on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Environment**: `Docker` *(The included `Dockerfile` installs FFmpeg and fonts automatically)*.
   - **Instance Type**: `Free`.
4. In the **Environment** section (or Environment Variables):
   - Add `GEMINI_API_KEY` = your Gemini API key
   - Add `PIXABAY_API_KEY` = your Pixabay API key
5. Click **Create Web Service**.
6. Once deployed, Render will give you a live HTTPS link (e.g. `https://reelforge.onrender.com`). Anyone visiting the link can create videos immediately without entering any keys!

---

## 📱 Features & Highlights

- **Pure Minimalist Design**: Deep matte slate palette, crisp Inter typography, Apple/Linear aesthetic.
- **100% Mobile Responsive**: Fluid single-column layout with sticky mobile action buttons and touch-friendly controls.
- **Aspect Ratio Selection**: 
  - `16:9 Landscape` (YouTube, Desktop)
  - `9:16 Portrait` (Instagram Reels, YouTube Shorts, TikTok)
- **Live Generation Stepper**: Real-time progress bar powered by Server-Sent Events (SSE).
- **In-Browser Video Player**: Full playback controls, download MP4 button, and scene-by-scene script breakdown.
