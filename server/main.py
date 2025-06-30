import base64
import os
import tempfile
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
from fastapi import FastAPI
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
BOOKING_STATE_FILE = "booking_state.json"

def load_booking_state():
    if os.path.exists(BOOKING_STATE_FILE):
        with open(BOOKING_STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_booking_state(state):
    with open(BOOKING_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

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

    booking_state = load_booking_state()
    msg_lower = user_query.message.lower()
    hotel = next(
        (h for h in hotels_list if h["hotel_name"].lower() == user_query.hotel_name.lower()), None
    )
    if not hotel:
        return JSONResponse(
            content={"error": f"Hotel '{user_query.hotel_name}' not found."},
            status_code=404
        )

    booking_state["hotel_name"] = hotel["hotel_name"]
    room_types = available_rooms.get(hotel["id"], [])
    available_rooms_str = ", ".join(room_types)

    chat_history.append({"user": user_query.message, "bot": ""})

    extract_name_and_phone(user_query.message, booking_state)
    extract_guest_info(msg_lower, booking_state)
    extract_room_type(msg_lower, room_types, booking_state)
    extract_dates(user_query.message, booking_state)

    save_booking_state(booking_state)

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

def extract_dates(message: str, booking_state: dict):
    now = datetime.now()
    range_match = re.search(
        r'(\d{1,2})(?:st|nd|rd|th)?\s*(?:to|-)\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?',
        message,
        flags=re.IGNORECASE
    )
    if range_match:
        day1, day2, month_str, year_str = range_match.groups()
        year = int(year_str) if year_str else now.year
        try:
            check_in = datetime(year, datetime.strptime(month_str, "%B").month, int(day1))
            check_out = datetime(year, datetime.strptime(month_str, "%B").month, int(day2))
            if check_out <= check_in:
                check_out += timedelta(days=2)
            booking_state["check_in_date"] = check_in.strftime("%d %B")
            booking_state["check_out_date"] = check_out.strftime("%d %B")
        except Exception:
            return
    else:
        matches = re.findall(
            r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?',
            message,
            flags=re.IGNORECASE
        )
        valid_dates = []
        for day_str, month_str, year_str in matches:
            try:
                day = int(day_str)
                month = datetime.strptime(month_str, "%B").month
                year = int(year_str) if year_str else now.year
                date_obj = datetime(year, month, day)
                if date_obj.date() <= now.date():
                    date_obj = datetime(year + 1, month, day)
                valid_dates.append(date_obj)
            except ValueError:
                continue

        if len(valid_dates) >= 2:
            booking_state["check_in_date"] = valid_dates[0].strftime("%d %B")
            booking_state["check_out_date"] = valid_dates[1].strftime("%d %B")
        elif len(valid_dates) == 1:
            check_in = valid_dates[0]
            booking_state["check_in_date"] = check_in.strftime("%d %B")
            booking_state["check_out_date"] = (check_in + timedelta(days=2)).strftime("%d %B")

def extract_guest_info(msg: str, booking_state: dict):
    adults = re.search(r'(\d+)\s*adults?', msg)
    children = re.search(r'(\d+)\s*(?:children|child)', msg)
    guests = []

    if adults:
        guests.append(f"{adults.group(1)} adults")
    if children:
        guests.append(f"{children.group(1)} children")
    if guests:
        booking_state["guests"] = " and ".join(guests)
        return

    guests_generic = re.search(r'(\d+)\s*(guests|persons|people)', msg)
    if guests_generic:
        booking_state["guests"] = guests_generic.group(1)
    elif "2 persons" in msg or "2 guests" in msg:
        booking_state["guests"] = "2"

def extract_room_type(msg: str, room_types: list, booking_state: dict):
    for rt in room_types:
        if rt.lower() in msg:
            booking_state["room_type"] = rt
            return
    keyword_to_room = {
        "balcony": "Balcony Suite",
        "deluxe": "Deluxe Twin Room",
        "cottage": "Standard Cottage",
        "valley": "Valley View Room"
    }
    for keyword, rt in keyword_to_room.items():
        if keyword in msg:
            booking_state["room_type"] = rt
            return

def extract_name_and_phone(message: str, booking_state: dict):
    name_match = re.search(r"(?:my name is|i am|this is)\s+([A-Za-z ]+)", message, re.IGNORECASE)
    if name_match:
        booking_state["name"] = name_match.group(1).strip()
    else:
        alt_name_match = re.match(r"^([A-Za-z ]+)[, ]+\+?\d{10,13}", message.strip())
        if alt_name_match:
            booking_state["name"] = alt_name_match.group(1).strip()

    phone_match = re.search(r"(\+?\d{10,13})", message)
    if phone_match:
        booking_state["contact_no"] = phone_match.group(1).strip()



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