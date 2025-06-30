import base64
import os
import tempfile
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from data.prompt_details import get_prompt
from data.hotel_data import hotels_list, available_rooms
import whisper


load_dotenv()

gemini_api_key = os.getenv("GOOGLE_API_KEY")
# print("API Key Loaded:", gemini_api_key)
genai.configure(api_key=gemini_api_key)
whisper_model = whisper.load_model("base")
# result = whisper_model.transcribe("audio.mp3", fp16=False)
# print(result["text"])


# model = genai.GenerativeModel("gemma-3-1b-it")
model = genai.GenerativeModel("gemini-1.5-flash")

class UserQuery(BaseModel):
    hotel_name: str
    message: str

app = FastAPI()
chat_history = []
# booking_state = {
#     "check_in_date": None,
#     "check_out_date": None,
#     "guests": None,
#     "room_type": None,
#     "contact_name": None,
#     "contact_phone": None
# }
booking_state = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/hotels")
async def get_hotels():
    return JSONResponse(content=hotels_list, status_code=200)

@app.post("/chat")
async def chat_with_customer(user_query: UserQuery):
    if not user_query.hotel_name or not user_query.message:
        return JSONResponse(
            content={"error": "Missing hotel_name or message in request."},
            status_code=400
        )

    hotel = next(
        (h for h in hotels_list if h["hotel_name"].lower() == user_query.hotel_name.lower()), None
    )
    if not hotel:
        return JSONResponse(
            content={"error": f"Hotel '{user_query.hotel_name}' not found."},
            status_code=404
        )

    room_types = available_rooms.get(hotel["id"], [])
    available_rooms_str = ", ".join(room_types)

    chat_history.append({"user": user_query.message, "bot": ""})

    date_matches = re.findall(
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+(\d{4}))?',
        user_query.message,
        flags=re.IGNORECASE
    )

    valid_dates = []
    for day_str, month_str, year_str in date_matches:
        try:
            day = int(day_str)
            month = datetime.strptime(month_str, "%B").month
            year = int(year_str) if year_str else datetime.now().year

            date_obj = datetime(year, month, day)
            if date_obj.date() <= datetime.now().date():
                date_obj = datetime(year + 1, month, day)

            valid_dates.append(date_obj.strftime("%d %B %Y") if year_str else date_obj.strftime("%d %B"))
        except ValueError:
            continue

    if len(valid_dates) >= 2:
        booking_state["check_in_date"] = valid_dates[0]
        booking_state["check_out_date"] = valid_dates[1]
    elif len(valid_dates) == 1:
        check_in = datetime.strptime(valid_dates[0], "%d %B")
        check_out = check_in + timedelta(days=2)
        booking_state["check_in_date"] = valid_dates[0]
        booking_state["check_out_date"] = check_out.strftime("%d %B")

    msg_lower = user_query.message.lower()
    if "2 persons" in msg_lower or "2 guests" in msg_lower:
        booking_state["guests"] = "2"
    if "cottage" in msg_lower:
        booking_state["room_type"] = "Standard Cottage"
    if "valley" in msg_lower:
        booking_state["room_type"] = "Valley View Room"

    full_prompt = get_prompt(
        hotel,
        user_query,
        available_rooms_str,
        chat_history=chat_history,
        booking_state=booking_state
    )

    try:
        response = await get_completion(full_prompt)

        cleaned_response = re.sub(r'^["“”\']?Receptionist:\s*', '', response.strip(), flags=re.IGNORECASE)

        chat_history[-1]["bot"] = cleaned_response
        return JSONResponse(content={"response": cleaned_response}, status_code=200)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def get_completion(prompt: str):
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=200,
                temperature=0.4  
            )
        )

        if hasattr(response, "text"):
            print("LLM Response Text:", response.text)
            return response.text.strip()
        else:
            print("Unexpected LLM response format:", response)
            return "Sorry, I couldn't generate a response at the moment."

    except Exception as e:
        print("Error during completion:", str(e))
        return "An error occurred while generating a response. Please try again."
    

class VoiceRequest(BaseModel):
    audio: str
    hotel_name: str

@app.post("/voice")
async def voice_chat(req: VoiceRequest):
    try:
        audio_data = base64.b64decode(req.audio)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        result = whisper_model.transcribe(tmp_path)
        message = result["text"]

        user_query = UserQuery(hotel_name=req.hotel_name, message=message)
        # return await chat_with_customer(user_query)
        response = await chat_with_customer(user_query)
        bot_reply_json = response.body.decode("utf-8")
        bot_reply = json.loads(bot_reply_json)["response"]

        return JSONResponse(content={
            "response": bot_reply,
            "transcript": message
        })

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             data = await websocket.receive_text()
#             user_query = UserQuery(hotel_name="Default Hotel", message=data) 
#             response = await chat_with_customer(user_query)
#             await websocket.send_text(response.body.decode())
#     except WebSocketDisconnect:
#         print("Client disconnected")
