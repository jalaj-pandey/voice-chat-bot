import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import VoiceChat from "./VoiceChat";
import "./styles/ChatBot.css";

const ChatBot = () => {
  const [hotels, setHotels] = useState([]);
  const [selectedHotel, setSelectedHotel] = useState(null);
  const [messages, setMessages] = useState([]);
  const [userMsg, setUserMsg] = useState("");
  const [showVoiceChat, setShowVoiceChat] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const voiceRef = useRef(null)

  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/hotels")
      .then((res) => setHotels(res.data))
      .catch((err) => console.error("Error fetching hotels:", err));
  }, []);

  const sendMessage = async () => {
    if (!userMsg.trim()) return;

    const newMessages = [...messages, { sender: "You", text: userMsg }];
    setMessages(newMessages);

    try {
      const res = await axios.post("http://127.0.0.1:8000/chat", {
        hotel_name: selectedHotel.hotel_name,
        message: userMsg,
      });

      setMessages([
        ...newMessages,
        { sender: "Receptionist", text: res.data.response },
      ]);
      setUserMsg("");
    } catch (err) {
      console.error(err);
      setMessages([
        ...newMessages,
        { sender: "Receptionist", text: "Oops! Something went wrong." },
      ]);
    }
  };

  if (!selectedHotel) {
    return (
      <div className="container">
        <h2 className="title">Select a Hotel to Start Chatting</h2>
        <div className="grid">
          {hotels.map((hotel, index) => (
            <div key={index} className="card">
              <h3>{hotel.hotel_name}</h3>
              <p>
                <strong>Location:</strong> {hotel.location}
              </p>
              <p>
                <strong>Type:</strong> {hotel.type}
              </p>
              <p>
                <strong>Offer:</strong> {hotel.offers}
              </p>
              <button
                className="chat-btn"
                onClick={() => setSelectedHotel(hotel)}
              >
                Chat with Receptionist
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const handleVoiceMessage = (transcript, botResponse) => {
    const newMessages = [
      ...messages,
      { sender: "You", text: transcript },
      { sender: "Receptionist", text: botResponse },
    ];
    setMessages(newMessages);
  };

  const toggleRecording = () => {
    if (voiceRef.current) {
      voiceRef.current.toggleRecording();
      setIsRecording((prev) => !prev);
    }
  };

  return (
    <div className="chat-wrapper">
      <div className="chat-container">
        <div className="header">
          Chatting with: <strong>{selectedHotel.hotel_name}</strong>
        </div>
        <div className="messages">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`message ${msg.sender === "You" ? "user" : "bot"}`}
            >
              <strong>{msg.sender}:</strong> {msg.text}
            </div>
          ))}

          {showVoiceChat && (
            <VoiceChat
              selectedHotel={selectedHotel.hotel_name}
              onVoiceMessage={handleVoiceMessage}
            />
          )}
          
        </div>
        <div className="input-area">
          <input
            className="input"
            value={userMsg}
            onChange={(e) => setUserMsg(e.target.value)}
            placeholder="Type your message..."
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          />
          <button onClick={sendMessage} className="send-btn">
            Send
          </button>
          <button onClick={toggleRecording} className="voice-btn">
            {isRecording ? "🛑 Stop Recording" : "🎙️ Voice"}
          </button>
        </div>
      </div>

       <VoiceChat
        ref={voiceRef}
        selectedHotel={selectedHotel.hotel_name}
        onVoiceMessage={handleVoiceMessage}
        className="hidden"
      />
    </div>
  );
};

export default ChatBot;
