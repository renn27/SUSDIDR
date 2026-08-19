# ==============================================================================
# Entry Point untuk Hugging Face Spaces (Gradio SDK - 100% GRATIS)
# ==============================================================================
import gradio as gr
from api.main import app

# Buat antarmuka visual sederhana di Gradio untuk halaman depan Space
with gr.Blocks(title="USD/IDR Real-Time Scraper & API") as demo:
    gr.Markdown("# 🚀 USD/IDR Real-Time Scraper & WebSocket API")
    gr.Markdown("Server FastAPI & Scraper Google Finance sedang aktif berjalan di background.")
    gr.Markdown("### 📡 Endpoint Aktif:")
    gr.Markdown("- **REST API PantauTreasury**: `/api/pantau-treasury`")
    gr.Markdown("- **REST API Latest**: `/latest`")
    gr.Markdown("- **REST API History**: `/history`")
    gr.Markdown("- **WebSocket Stream**: `/ws`")
    gr.Markdown("- **Swagger Documentation**: `/docs`")

# Mount Gradio ke FastAPI app (sehingga semua endpoint REST & WebSocket /ws tetap bekerja 100%)
app = gr.mount_gradio_app(app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
