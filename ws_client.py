import asyncio
import json
from pydub import AudioSegment
import os
from dotenv import load_dotenv
import websockets

load_dotenv()

WS_URL = "ws://localhost:8000/ws/stream/ws"
BEARER_TOKEN= os.getenv("BIRDNET_API_KEY", "")
lat = 60.44324706064409
lon = 22.2632729407483
if not BEARER_TOKEN:
    raise RuntimeError("Environment variable BIRDNET_API_KEY is not set")

AUDIO_FILE = "example.wav"

async def realtime_client():
    uri = f"{WS_URL}?token={BEARER_TOKEN}"
    async with websockets.connect(uri) as ws:
        init_payload = {
            "lat": lat,
            "lon": lon,
            "min_conf": 0.8,
            "timeout": 30.0,
        }
        await ws.send(json.dumps(init_payload))
        print("Sent init:", init_payload)

        audio = AudioSegment.from_file(AUDIO_FILE) \
                            .set_frame_rate(48000) \
                            .set_channels(1) \
                            .set_sample_width(2)  # 2 bytes = 16-bit

        pcm_bytes = audio.raw_data
        total_len = len(pcm_bytes)
        print(f"Loaded audio: {total_len} bytes of PCM")

        # Stream in real-time chunks (e.g. 0.5 s at a time):
        #    0.5 s of 48 kHz × 2 bytes × 1 channel = 48000 bytes
        chunk_size = int(48000 * 2 * 1 * 0.5)  # = 48000
        idx = 0

        while idx < total_len:
            chunk = pcm_bytes[idx : idx + chunk_size]
            await ws.send(chunk)
            idx += len(chunk)
            await asyncio.sleep(0.5)

            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=0.1)
                print("Received:", resp)
                return
            except asyncio.TimeoutError:
                pass

        print("Finished streaming entire file; waiting for server to timeout…")
        try:
            resp = await ws.recv()
            print("Received at end:", resp)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(realtime_client())
