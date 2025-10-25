from locust import HttpUser, task, between
import random
from pathlib import Path


class AIPipelineUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        self.token = "token_abc123"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.audio_files = list(Path("/test-data/audio").glob("*.wav"))
        self.pdf_files = list(Path("/test-data/documents").glob("*.pdf"))

    @task(30)
    def asr_only(self):
        audio_file = random.choice(self.audio_files)

        with open(audio_file, "rb") as f:
            files = {"file": (audio_file.name, f, "audio/wav")}
            data = {
                "language": "pt",
                "model": "large-v3-turbo",
                "enable_diarization": False,
            }

            with self.client.post(
                "/api/v1/asr",
                files=files,
                data=data,
                headers=self.headers,
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    result = response.json()
                    if result.get("processing_time_ms", 9999) > 2000:
                        response.failure(f"ASR too slow: {result['processing_time_ms']}ms")
                    else:
                        response.success()

    @task(15)
    def asr_with_diarization(self):
        audio_file = random.choice(self.audio_files)

        with open(audio_file, "rb") as f:
            files = {"file": (audio_file.name, f, "audio/wav")}
            data = {
                "language": "pt",
                "model": "large-v3",
                "enable_diarization": True,
                "enable_alignment": True,
            }

            with self.client.post(
                "/api/v1/asr",
                files=files,
                data=data,
                headers=self.headers,
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    result = response.json()
                    segments = result.get("segments", [])
                    if not segments or not segments[0].get("speaker"):
                        response.failure("Missing diarization data")
                    else:
                        response.success()

    @task(20)
    def ocr_document(self):
        pdf_file = random.choice(self.pdf_files)

        with open(pdf_file, "rb") as f:
            files = {"file": (pdf_file.name, f, "application/pdf")}
            data = {
                "languages": ["pt", "en"],
                "output_format": "json",
                "use_gpu": True,
            }

            with self.client.post(
                "/api/v1/ocr",
                files=files,
                data=data,
                headers=self.headers,
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    result = response.json()
                    pages = result.get("pages", [])
                    if not pages:
                        response.failure("No OCR pages returned")
                    else:
                        total_time = sum(
                            p["metadata"].get("processing_time_ms", 0) for p in pages
                        )
                        if pages and total_time / len(pages) > 1000:
                            response.failure(f"OCR too slow: {total_time}ms")
                        else:
                            response.success()

    @task(25)
    def llm_chat(self):
        prompts = [
            "Resuma este texto em 3 parágrafos",
            "Analise o sentimento desta conversa",
            "Liste os principais tópicos discutidos",
        ]

        payload = {
            "model": random.choice([
                "qwen2.5-14b-instruct",
                "qwen2.5-14b-instruct-awq",
            ]),
            "messages": [
                {"role": "system", "content": "Você é um assistente útil."},
                {"role": "user", "content": random.choice(prompts)},
            ],
            "max_tokens": 300,
            "temperature": 0.7,
        }

        with self.client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if result.get("usage", {}).get("completion_tokens", 0) < 50:
                    response.failure("Response too short")
                else:
                    response.success()
