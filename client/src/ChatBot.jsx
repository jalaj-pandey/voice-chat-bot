import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import VoiceChat from "./VoiceChat";
import "./styles/ChatBot.css";

const ChatBot = () => {
  const [hotels, setHotels] = useState([]);
  const [selectedHotel, setSelectedHotel] = useState(null);
  const [messages, setMessages] = useState([]);
  const [userMsg, setUserMsg] = useState("");
  const [isRecording, setIsRecording] = useState(false);

  const voiceRef = useRef(null);

  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/hotels")
      .then((res) => setHotels(res.data))
      .catch((err) => console.error("Error fetching hotels:", err));
  }, []);

  const sendMessage = async () => {
    if (!userMsg.trim()) return;

    const messageToSend = userMsg;
    setUserMsg("");

    setMessages((prev) => [...prev, { sender: "You", text: messageToSend }]);
    setMessages((prev) => [...prev, { sender: "bot", text: "Receptionist is typing...", typing: true }]);

    try {
      const res = await axios.post("http://127.0.0.1:8000/chat", {
        hotel_name: selectedHotel.hotel_name,
        message: messageToSend,
      });

      const botReply = res.data.response;

      setMessages((prev) => [
        ...prev.filter((msg) => !msg.typing),
        { sender: "Receptionist", text: botReply },
      ]);
      speak(botReply);

    } catch (err) {
      const errorReply = "Oops! Something went wrong.";
      setMessages((prev) => [
        ...prev.filter((msg) => !msg.typing),
        { sender: "Receptionist", text: errorReply },
      ]);
      speak(errorReply);
    }
  };

  const speak = (text) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
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

 const handleVoiceMessage = (userText, botTextOrTyping) => {
  if (userText) {
    setMessages(prev => [
      ...prev,
      { sender: "You", text: userText },
      { sender: "Receptionist", text: "Receptionist is typing...", typing: true }
    ]);
    return;
  }
  if (botTextOrTyping && botTextOrTyping !== "__typing__") {
    setMessages(prev => [
      ...prev.filter(m => !m.typing),
      { sender: "Receptionist", text: botTextOrTyping }
    ]);
  }
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
              <strong>{msg.sender}:</strong>{" "}
              {msg.typing ? <i className="typing-dots">...</i> : msg.text}
            </div>
          ))}
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